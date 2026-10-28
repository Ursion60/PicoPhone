/*
 * HAL simulateur PC : fenêtre SDL2 (240x320, agrandie x2), souris = doigt.
 * Utilisée par le build MicroPython "unix" : les applis Python tournent sur le PC
 * avec exactement le même module `phone` que sur la carte.
 *
 * Volontairement SANS SDL_Renderer/SDL_Texture : sur certains systèmes (observé avec le pilote
 * NVIDIA propriétaire, en conteneur toolbox, une fois SDL2 lié dans un gros binaire comme
 * MicroPython), l'API de rendu de sdl2-compat (la couche de compatibilité SDL2-sur-SDL3 utilisée
 * par ex. sur Fedora) retombe sur OpenGL même quand un rendu logiciel est explicitement demandé
 * (drapeau ET variable d'environnement), et le pilote GPU plante en interne à la présentation.
 * On utilise donc l'API de surface de fenêtre, plus ancienne et plus simple, qui n'a jamais
 * besoin d'un contexte GL/EGL pour un simple blit de pixels.
 */
#include <SDL2/SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include "hal.h"
#include "gfx.h"

#define SCALE 2

static SDL_Window *win;
static bool sim_active;
static int  sim_x, sim_y;

static void die(const char *what) {
    fprintf(stderr, "phone: %s a échoué : %s\n", what, SDL_GetError());
    exit(1);
}

void hal_init(void) {
    if (win) return;
    /* Sous Wayland, quand le compositeur ne gère pas nativement les bordures, SDL dessine la
     * barre de titre via libdecor - qui utilise elle-même OpenGL/EGL en interne. C'est cette
     * étape, indépendante de tout rendu applicatif, qui plante dans certains pilotes GPU
     * propriétaires (NVIDIA, observé en conteneur toolbox). On désactive donc libdecor : les
     * compositeurs qui savent gérer eux-mêmes la décoration (KDE Plasma, GNOME...) le feront
     * côté serveur sans que SDL n'ait besoin d'EGL pour ça ; sinon la fenêtre sera juste sans
     * bordure (pas de plantage, cosmétique seulement).
     */
    SDL_SetHint("SDL_VIDEO_WAYLAND_ALLOW_LIBDECOR", "0");
    if (SDL_Init(SDL_INIT_VIDEO) != 0) die("SDL_Init");

    win = SDL_CreateWindow("phone - simulateur Pico 2", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                           SCREEN_W * SCALE, SCREEN_H * SCALE, SDL_WINDOW_SHOWN);
    if (!win) die("SDL_CreateWindow");

    if (!SDL_GetWindowSurface(win)) die("SDL_GetWindowSurface");
}

void hal_backlight(uint8_t level) { (void)level; }
bool hal_fb_ready(void) { return true; }

void hal_flush(const uint16_t *fb, int x0, int y0, int x1, int y1) {
    SDL_Surface *surf = SDL_GetWindowSurface(win);
    if (!surf) return;                          /* fenêtre fermée/minimisée : rien à faire */

    if (SDL_MUSTLOCK(surf)) SDL_LockSurface(surf);
    int bpp = surf->format->BytesPerPixel;
    for (int y = y0; y <= y1; y++) {
        const uint16_t *src = fb + y * SCREEN_W + x0;
        for (int x = x0; x <= x1; x++) {
            uint16_t p = src[x - x0];
            uint8_t r = (uint8_t)((p >> 11) << 3), g = (uint8_t)(((p >> 5) & 0x3F) << 2), b = (uint8_t)((p & 0x1F) << 3);
            uint32_t mapped = SDL_MapRGB(surf->format, r, g, b);
            for (int dy = 0; dy < SCALE; dy++) {
                uint8_t *row = (uint8_t *)surf->pixels + (y * SCALE + dy) * surf->pitch + (x * SCALE) * bpp;
                for (int dx = 0; dx < SCALE; dx++, row += bpp) {
                    if (bpp == 4) *(uint32_t *)row = mapped;
                    else if (bpp == 2) *(uint16_t *)row = (uint16_t)mapped;
                    else if (bpp == 3) { row[0] = (uint8_t)mapped; row[1] = (uint8_t)(mapped >> 8); row[2] = (uint8_t)(mapped >> 16); }
                }
            }
        }
    }
    if (SDL_MUSTLOCK(surf)) SDL_UnlockSurface(surf);

    SDL_Rect r = { x0 * SCALE, y0 * SCALE, (x1 - x0 + 1) * SCALE, (y1 - y0 + 1) * SCALE };
    SDL_UpdateWindowSurfaceRects(win, &r, 1);
}

bool hal_touch(int *x, int *y) {
    SDL_Event e;
    while (SDL_PollEvent(&e)) {
        if (e.type == SDL_QUIT || (e.type == SDL_KEYDOWN && e.key.keysym.sym == SDLK_ESCAPE)) exit(0);
        if (e.type == SDL_WINDOWEVENT && e.window.event == SDL_WINDOWEVENT_EXPOSED)
            SDL_UpdateWindowSurface(win);
    }
    if (sim_active) { *x = sim_x; *y = sim_y; return true; }

    int mx, my, ww, wh;
    if (!(SDL_GetMouseState(&mx, &my) & SDL_BUTTON(SDL_BUTTON_LEFT))) return false;
    SDL_GetWindowSize(win, &ww, &wh);            /* robuste à la mise à l'échelle Wayland/HiDPI */
    int px = mx * SCREEN_W / ww, py = my * SCREEN_H / wh;
    *x = px < 0 ? 0 : (px >= SCREEN_W ? SCREEN_W - 1 : px);
    *y = py < 0 ? 0 : (py >= SCREEN_H ? SCREEN_H - 1 : py);
    return true;
}

#ifdef PHONE_SIM
void hal_sim_touch(int x, int y, bool down) { sim_active = down; sim_x = x; sim_y = y; }

bool hal_sim_screenshot(const char *path, const uint16_t *fb) {
    FILE *f = fopen(path, "wb");
    if (!f) return false;
    fprintf(f, "P6\n%d %d\n255\n", SCREEN_W, SCREEN_H);
    for (int i = 0; i < SCREEN_W * SCREEN_H; i++) {
        uint16_t p = fb[i];
        uint8_t rgb[3] = { (uint8_t)((p >> 11) << 3), (uint8_t)(((p >> 5) & 0x3F) << 2), (uint8_t)((p & 0x1F) << 3) };
        fwrite(rgb, 1, 3, f);
    }
    fclose(f);
    return true;
}
#endif
