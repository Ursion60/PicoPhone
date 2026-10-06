#include "gfx.h"
#include <string.h>

static uint16_t fb[SCREEN_W * SCREEN_H];   /* 153 600 octets */
static int dirty_x0, dirty_y0, dirty_x1, dirty_y1;

static void dirty_reset(void) {
    dirty_x0 = SCREEN_W; dirty_y0 = SCREEN_H; dirty_x1 = -1; dirty_y1 = -1;
}

static inline void mark(int x0, int y0, int x1, int y1) {
    if (x0 < dirty_x0) dirty_x0 = x0;
    if (y0 < dirty_y0) dirty_y0 = y0;
    if (x1 > dirty_x1) dirty_x1 = x1;
    if (y1 > dirty_y1) dirty_y1 = y1;
}

void gfx_init(void) { dirty_reset(); }

uint16_t *gfx_framebuffer(void) { return fb; }

bool gfx_take_dirty(GfxRect *out) {
    if (dirty_x1 < dirty_x0 || dirty_y1 < dirty_y0) return false;
    out->x0 = dirty_x0; out->y0 = dirty_y0; out->x1 = dirty_x1; out->y1 = dirty_y1;
    dirty_reset();
    return true;
}

/* ---------- Rectangles / lignes ---------- */

void gfx_fill_rect(int x, int y, int w, int h, uint16_t c) {
    int x1 = x + w - 1, y1 = y + h - 1;
    if (x < 0) x = 0;
    if (y < 0) y = 0;
    if (x1 >= SCREEN_W) x1 = SCREEN_W - 1;
    if (y1 >= SCREEN_H) y1 = SCREEN_H - 1;
    if (x > x1 || y > y1) return;
    for (int yy = y; yy <= y1; yy++) {
        uint16_t *p = &fb[yy * SCREEN_W + x];
        for (int xx = x; xx <= x1; xx++) *p++ = c;
    }
    mark(x, y, x1, y1);
}

void gfx_clear(uint16_t c) { gfx_fill_rect(0, 0, SCREEN_W, SCREEN_H, c); }

void gfx_hline(int x0, int x1, int y, uint16_t c) { gfx_fill_rect(x0, y, x1 - x0 + 1, 1, c); }

void gfx_rect(int x, int y, int w, int h, uint16_t c) {
    if (w <= 0 || h <= 0) return;
    gfx_fill_rect(x, y, w, 1, c);
    gfx_fill_rect(x, y + h - 1, w, 1, c);
    gfx_fill_rect(x, y, 1, h, c);
    gfx_fill_rect(x + w - 1, y, 1, h, c);
}

/* ---------- Formes : entiers uniquement (plus de double/sqrt) ---------- */

static int isqrt(int n) {
    int r = 0;
    while ((r + 1) * (r + 1) <= n) r++;
    return r;
}

void gfx_fill_circle(int cx, int cy, int r, uint16_t c) {
    for (int dy = -r; dy <= r; dy++) {
        int dx = isqrt(r * r - dy * dy);
        gfx_fill_rect(cx - dx, cy + dy, 2 * dx + 1, 1, c);
    }
}

/* Rectangle arrondi : UNE passe, une ligne = un span.
 * (l'original dessinait 3 rects + 4 disques complets, avec recouvrement) */
void gfx_fill_round_rect(int x, int y, int w, int h, int r, uint16_t c) {
    if (r * 2 > w) r = w / 2;
    if (r * 2 > h) r = h / 2;
    for (int row = 0; row < h; row++) {
        int inset = 0;
        int k = row < r ? row : (row >= h - r ? h - 1 - row : r);
        if (k < r) {
            int dy2 = 2 * (r - k) - 1;                       /* distance au centre, en demi-pixels */
            int dx2 = isqrt(4 * r * r - dy2 * dy2);
            inset = (2 * r - dx2) / 2;
        }
        gfx_fill_rect(x + inset, y + row, w - 2 * inset, 1, c);
    }
}

/* Mélange alpha RGB565 (alpha 0..32), sans division, sur 32 bits.
 * Déclarée ici (avant son 1er usage par gfx_fill_round_rect_alpha) ; le texte
 * plus bas en a sa propre copie locale historique -> on la fait pointer dessus. */
uint16_t gfx_blend565(uint16_t fg, uint16_t bg, uint32_t alpha) {
    uint32_t f = (fg | ((uint32_t)fg << 16)) & 0x07E0F81Fu;
    uint32_t b = (bg | ((uint32_t)bg << 16)) & 0x07E0F81Fu;
    uint32_t r = ((((f - b) * alpha) >> 5) + b) & 0x07E0F81Fu;
    return (uint16_t)(r | (r >> 16));
}

/* Rectangle arrondi semi-transparent (utilisé pour l'effet "flash" par-dessus une icône). */
void gfx_fill_round_rect_alpha(int x, int y, int w, int h, int r, uint16_t c, uint8_t alpha8) {
    if (alpha8 == 0) return;
    if (alpha8 >= 255) { gfx_fill_round_rect(x, y, w, h, r, c); return; }
    if (r * 2 > w) r = w / 2;
    if (r * 2 > h) r = h / 2;
    uint32_t a = (alpha8 + 4u) >> 3;                 /* 0..255 -> 0..32 */
    int x0 = x < 0 ? 0 : x, y0 = y < 0 ? 0 : y;
    int x1 = x + w - 1 >= SCREEN_W ? SCREEN_W - 1 : x + w - 1;
    int y1c = y + h - 1 >= SCREEN_H ? SCREEN_H - 1 : y + h - 1;
    if (x0 > x1 || y0 > y1c) return;
    for (int row = 0; row < h; row++) {
        int py = y + row;
        if (py < 0 || py >= SCREEN_H) continue;
        int inset = 0;
        int k = row < r ? row : (row >= h - r ? h - 1 - row : r);
        if (k < r) {
            int dy2 = 2 * (r - k) - 1;
            int dx2 = isqrt(4 * r * r - dy2 * dy2);
            inset = (2 * r - dx2) / 2;
        }
        int sx0 = x + inset, sx1 = x + w - 1 - inset;
        if (sx0 < 0) sx0 = 0;
        if (sx1 >= SCREEN_W) sx1 = SCREEN_W - 1;
        uint16_t *p = &fb[py * SCREEN_W + sx0];
        for (int px = sx0; px <= sx1; px++, p++) *p = gfx_blend565(c, *p, a);
    }
    mark(x0, y0, x1, y1c);
}

/* Compose une icône RGB565+alpha sur le fond actuel (coins transparents -> fond visible). */
void gfx_blit(const Icon *icon, int x, int y) {
    const uint16_t *px = icon->px;
    const uint8_t *al = icon->alpha;
    int x0 = x, y0 = y, x1 = x + icon->w - 1, y1 = y + icon->h - 1;
    for (int row = 0; row < icon->h; row++) {
        int py = y + row;
        if (py < 0 || py >= SCREEN_H) { px += icon->w; al += icon->w; continue; }
        for (int col = 0; col < icon->w; col++, px++, al++) {
            int pxx = x + col;
            if (pxx < 0 || pxx >= SCREEN_W || *al == 0) continue;
            uint16_t *dst = &fb[py * SCREEN_W + pxx];
            *dst = (*al > 250) ? *px : gfx_blend565(*px, *dst, (*al + 4u) >> 3);
        }
    }
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 >= SCREEN_W) x1 = SCREEN_W - 1;
    if (y1 >= SCREEN_H) y1 = SCREEN_H - 1;
    mark(x0, y0, x1, y1);
}

/* Petit triangle plein pointe en haut (remplace le glyphe U+25B2 absent de Latin-1) */
void gfx_fill_triangle_up(int x, int y, int w, int h, uint16_t c) {
    for (int row = 0; row < h; row++) {
        int span = (w * (row + 1)) / h;
        if (span < 1) span = 1;
        gfx_fill_rect(x + (w - span) / 2, y + row, span, 1, c);
    }
}

/* ---------- Texte ---------- */

static uint32_t utf8_next(const char **s) {
    const uint8_t *p = (const uint8_t *)*s;
    uint32_t cp;
    if (p[0] < 0x80) { cp = p[0]; *s += 1; }
    else if ((p[0] & 0xE0) == 0xC0 && (p[1] & 0xC0) == 0x80) {
        cp = ((p[0] & 0x1Fu) << 6) | (p[1] & 0x3Fu); *s += 2;
    } else if ((p[0] & 0xF0) == 0xE0 && (p[1] & 0xC0) == 0x80 && (p[2] & 0xC0) == 0x80) {
        cp = ((p[0] & 0x0Fu) << 12) | ((p[1] & 0x3Fu) << 6) | (p[2] & 0x3Fu); *s += 3;
    } else { cp = '?'; *s += 1; }
    return cp;
}

static inline uint16_t blend565(uint16_t fg, uint16_t bg, uint32_t alpha) {
    return gfx_blend565(fg, bg, alpha);
}

int gfx_text_width(const Font *f, const char *s) {
    int w = 0;
    while (*s) w += font_glyph(f, utf8_next(&s))->adv;
    return w;
}

void gfx_text(const Font *f, const char *s, int x, int y, uint16_t c) {
    int pen = x, base = y + f->ascent;
    while (*s) {
        const Glyph *g = font_glyph(f, utf8_next(&s));
        const uint8_t *bmp = f->bitmap + g->off;
        int gx = pen + g->xo, gy = base + g->yo;
        for (int j = 0; j < g->h; j++) {
            int py = gy + j;
            if (py < 0 || py >= SCREEN_H) { bmp += g->w; continue; }
            for (int i = 0; i < g->w; i++) {
                int px = gx + i;
                uint8_t a = bmp[i];
                if (a && px >= 0 && px < SCREEN_W) {
                    uint16_t *dst = &fb[py * SCREEN_W + px];
                    *dst = (a > 250) ? c : blend565(c, *dst, (a + 4u) >> 3);
                }
            }
            bmp += g->w;
        }
        if (g->w) mark(gx < 0 ? 0 : gx, gy < 0 ? 0 : gy,
                       gx + g->w - 1 >= SCREEN_W ? SCREEN_W - 1 : gx + g->w - 1,
                       gy + g->h - 1 >= SCREEN_H ? SCREEN_H - 1 : gy + g->h - 1);
        pen += g->adv;
    }
}

void gfx_text_at_cy(const Font *f, const char *s, int x, int cy, uint16_t c) {
    int cap = font_glyph(f, 'H')->h;                 /* hauteur des capitales */
    int baseline = cy - cap / 2 + cap;               /* capitales sur les lignes cy-cap/2 .. baseline-1 */
    gfx_text(f, s, x, baseline - f->ascent, c);
}

void gfx_text_centered(const Font *f, const char *s, int cx, int cy, uint16_t c) {
    gfx_text_at_cy(f, s, cx - gfx_text_width(f, s) / 2, cy, c);
}
