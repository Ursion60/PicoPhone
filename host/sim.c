/*
 * Simulateur de l'ÉCRAN D'ACCUEIL seul (sans MicroPython, compile en une seconde) :
 * même code d'interface que sur la carte (gfx.c + ui.c), dans une fenêtre SDL2.
 * Souris = doigt. Pour tester aussi les applis Python, utilisez le build MicroPython
 * "unix" décrit dans le README.
 *
 *   gcc -O2 -Wall -Iphone host/sim.c phone/gfx.c phone/ui.c phone/font.c phone/font_data.c \
 *       -o sim $(pkg-config --cflags --libs sdl2)
 *   ./sim          (Échap pour quitter)
 */
#include <SDL2/SDL.h>
#include <stdio.h>
#include "gfx.h"
#include "ui.h"

#define SCALE 2   /* fenêtre 480x640 pour y voir quelque chose sur un écran de PC */

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;
    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        fprintf(stderr, "Erreur SDL_Init : %s\n", SDL_GetError());
        return 1;
    }
    SDL_Window *win = SDL_CreateWindow("phone_ui - simulateur Pico 2",
        SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
        SCREEN_W * SCALE, SCREEN_H * SCALE, SDL_WINDOW_SHOWN);
    if (!win) { fprintf(stderr, "Erreur fenêtre : %s\n", SDL_GetError()); return 1; }

    /* Rendu logiciel par défaut : un écran 240x320 en 2D n'a besoin d'aucune accélération
     * matérielle, et l'accéléré peut planter DANS certains pilotes GPU proprio (vu avec NVIDIA
     * en conteneur toolbox/Wayland - la création réussit mais le pilote crashe plus tard, dans
     * SDL_RenderPresent, donc un simple test de retour NULL ne l'aurait pas détecté). */
    SDL_Renderer *ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_SOFTWARE);
    if (!ren) ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_ACCELERATED);
    SDL_Texture *tex = SDL_CreateTexture(ren, SDL_PIXELFORMAT_RGB565,
        SDL_TEXTUREACCESS_STREAMING, SCREEN_W, SCREEN_H);   /* même format que le framebuffer */

    gfx_init();
    ui_init();
    ui_draw_all();

    bool running = true;
    while (running) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_QUIT) running = false;
            else if (e.type == SDL_KEYDOWN && e.key.keysym.sym == SDLK_ESCAPE) running = false;
            else if (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT) {
                /* Coordonnées de la souris (espace "fenêtre") -> écran 240x320.
                 * On divise par la taille réelle de la fenêtre au lieu de supposer
                 * SCALE : ça reste juste avec la mise à l'échelle Wayland/HiDPI. */
                int ww, wh;
                SDL_GetWindowSize(win, &ww, &wh);
                int x = e.button.x * SCREEN_W / ww;
                int y = e.button.y * SCREEN_H / wh;
                printf("Appui en (%d, %d)\n", x, y);
                ui_touch_down(x, y, SDL_GetTicks());
            }
        }
        ui_tick(SDL_GetTicks());
        const char *ev = ui_take_event();
        if (ev) printf("Événement : %s\n", ev);

        GfxRect r;
        if (gfx_take_dirty(&r))   /* comme lcd_flush() : on ne renvoie que la zone modifiée */
            SDL_UpdateTexture(tex, NULL, gfx_framebuffer(), SCREEN_W * 2);
        SDL_RenderClear(ren);
        SDL_RenderCopy(ren, tex, NULL, NULL);
        SDL_RenderPresent(ren);
        SDL_Delay(10);
    }

    SDL_DestroyTexture(tex);
    SDL_DestroyRenderer(ren);
    SDL_DestroyWindow(win);
    SDL_Quit();
    return 0;
}
