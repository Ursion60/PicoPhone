/*
 * gfx : mini moteur 2D sur framebuffer RGB565 (240x320 = 150 Ko en SRAM).
 * Aucune dépendance matérielle : compile aussi sur PC (voir host/preview.c).
 * Chaque primitive agrandit automatiquement la "zone sale" ; le pilote LCD
 * n'envoie ensuite que cette zone au lieu de tout l'écran.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "font.h"

#define SCREEN_W 240
#define SCREEN_H 320

#define RGB565(r, g, b) ((uint16_t)((((r) & 0xF8) << 8) | (((g) & 0xFC) << 3) | (((b) & 0xF8) >> 3)))

typedef struct { int x0, y0, x1, y1; } GfxRect;   /* bornes incluses */

/* Icône bitmap RGB565 + alpha 8 bits (générée par tools/gen_icons.py). */
typedef struct { uint8_t w, h; const uint16_t *px; const uint8_t *alpha; } Icon;

void      gfx_init(void);
uint16_t *gfx_framebuffer(void);
bool      gfx_take_dirty(GfxRect *out);   /* récupère + réinitialise la zone sale */

void gfx_clear(uint16_t c);
void gfx_fill_rect(int x, int y, int w, int h, uint16_t c);
void gfx_rect(int x, int y, int w, int h, uint16_t c);          /* contour 1 px */
void gfx_hline(int x0, int x1, int y, uint16_t c);
void gfx_fill_circle(int cx, int cy, int r, uint16_t c);
void gfx_fill_round_rect(int x, int y, int w, int h, int r, uint16_t c);
void gfx_fill_round_rect_alpha(int x, int y, int w, int h, int r, uint16_t c, uint8_t alpha); /* alpha 0-255 */
void gfx_blit(const Icon *icon, int x, int y);            /* compose l'icône sur le fond (coins transparents) */
void gfx_fill_triangle_up(int x, int y, int w, int h, uint16_t c);

int  gfx_text_width(const Font *f, const char *utf8);
void gfx_text(const Font *f, const char *utf8, int x, int y, uint16_t c);            /* (x,y) = coin haut-gauche de la boîte de ligne */

/* Alignement vertical "optique" : c'est la hauteur des capitales/chiffres qui est
 * centrée sur cy (et non la boîte de ligne, qui inclut la place des jambages g, p, y...
 * et fait paraître le texte trop haut). */
void gfx_text_at_cy(const Font *f, const char *utf8, int x, int cy, uint16_t c);     /* x = bord gauche      */
void gfx_text_centered(const Font *f, const char *utf8, int cx, int cy, uint16_t c); /* centré sur (cx, cy)  */
