/*
 * Aperçu sur PC de l'interface, sans carte ni SDL : exécute exactement le
 * même code (gfx.c + ui.c) et écrit le framebuffer en fichiers .ppm.
 *
 *   gcc -O2 -Wall -Iphone host/preview.c phone/gfx.c phone/ui.c phone/font.c phone/font_data.c -o preview
 *   ./preview            -> preview_*.ppm  (ouvrable avec GIMP, feh, ImageMagick...)
 */
#include <stdio.h>
#include "gfx.h"
#include "ui.h"

static void dump(const char *path) {
    FILE *f = fopen(path, "wb");
    if (!f) return;
    fprintf(f, "P6\n%d %d\n255\n", SCREEN_W, SCREEN_H);
    const uint16_t *fb = gfx_framebuffer();
    for (int i = 0; i < SCREEN_W * SCREEN_H; i++) {
        uint16_t p = fb[i];
        uint8_t rgb[3] = { (uint8_t)((p >> 11) << 3), (uint8_t)(((p >> 5) & 0x3F) << 2), (uint8_t)((p & 0x1F) << 3) };
        fwrite(rgb, 1, 3, f);
    }
    fclose(f);
}

static void report(const char *what) {
    GfxRect r;
    if (gfx_take_dirty(&r)) {
        int px = (r.x1 - r.x0 + 1) * (r.y1 - r.y0 + 1);
        printf("%-22s zone sale %3dx%-3d = %6d px (%2d %% de l'écran)\n", what,
               r.x1 - r.x0 + 1, r.y1 - r.y0 + 1, px, px * 100 / (SCREEN_W * SCREEN_H));
    } else printf("%-22s rien à envoyer\n", what);
}

int main(void) {
    gfx_init();
    ui_init();

    ui_draw_loading("Prêt", 2, 3);
    dump("preview_loading.ppm");
    report("écran de chargement");

    ui_draw_all();
    dump("preview_home.ppm");
    report("premier affichage");

    ui_touch_down(120, 70, 1000);           /* tap sur "Notes" */
    dump("preview_tap_notes.ppm");
    report("tap sur Notes");

    ui_tick(1100);  report("tick à +100 ms");
    ui_tick(1200);  report("tick à +200 ms (fin)");

    ui_touch_down(170, 300, 2000);          /* tap sur "Toutes les apps" */
    report("tap Toutes les apps");
    ui_touch_down(30, 308, 3000);           /* tap sur "Options" */
    report("tap Options");
    ui_touch_down(230, 30, 4000);           /* tap dans le vide */
    report("tap dans le vide");
    return 0;
}
