#include "ui.h"
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include "gfx.h"
#include "icons.h"

#define MAX_APPS 8
#define FLASH_MS 160          /* ancien : 10 images à ~60 Hz */
#define STATUS_H      17      /* barre de statut : 1 px de bordure + 15 px intérieurs...   */
#define STATUS_CY      8      /* ...donc une ligne centrale exacte (n°8) pour tout aligner  */
#define STATUS_MARGIN  6      /* marge gauche = marge droite, depuis le bord de l'écran    */
#define TITLE_H       22

/* ---------- Couleurs ---------- */
typedef struct { uint8_t r, g, b; } Color;
#define C565(c) RGB565((c).r, (c).g, (c).b)

static const Color COL_BG       = {236, 236, 236};
static const Color COL_WHITE    = {255, 255, 255};
static const Color COL_BLACK    = {20, 20, 20};
static const Color COL_TITLEBAR = {90, 70, 200};
static const Color COL_BORDER   = {60, 60, 60};

static const Color COL_EDT    = {0, 140, 130};
static const Color COL_NOTES  = {245, 205, 60};
static const Color COL_NFC    = {40, 140, 235};
static const Color COL_SHOP   = {245, 150, 20};
static const Color COL_SYNC   = {90, 90, 220};
static const Color COL_PARAMS = {150, 150, 150};
static const Color COL_MUSIC  = {150, 40, 220};
static const Color COL_PDF    = {225, 40, 40};

/* ---------- Données ---------- */
typedef struct { int x, y, w, h; } Rect;

typedef struct {
    char        name[24];     /* libellé affiché (traduit -> voir ui_set_app_label) */
    const char *id;           /* identifiant de l'appli (apps/<id>.py)         */
    Color       color;        /* couleur de repli si icon == NULL              */
    const Icon *icon;
    Rect        cell;         /* zone tactile (icône + libellé)                    */
    Rect        box;          /* carré coloré                                      */
    Rect        slot;         /* zone effacée/redessinée (déborde pour les libellés larges) */
    uint32_t    flash_until;  /* 0 = pas de flash, sinon échéance en ms            */
} AppIcon;

static AppIcon apps[MAX_APPS];
static int appCount = 0;

static Rect optionsBtn, allAppsBtn;
static const char *pending_event = NULL;
static uint32_t optionsFlash = 0, allAppsFlash = 0;

/* Libellés traduisibles (voir python/i18n.py) ; tailles généreuses par rapport à la plus longue
 * chaîne observée dans STRINGS (toutes langues confondues, CJK compris). */
static char home_title_buf[24]    = "Accueil";
static char options_label_buf[24] = "Options";
static char allapps_label_buf[32] = "Toutes les apps";

static void set_label(char *dst, size_t cap, const char *utf8) {
    size_t n = strlen(utf8);
    if (n > cap - 1) n = cap - 1;
    memcpy(dst, utf8, n);
    dst[n] = 0;
}

static inline bool expired(uint32_t deadline, uint32_t now) {
    return deadline != 0 && (int32_t)(now - deadline) >= 0;
}

static inline bool point_in(int px, int py, const Rect *r) {
    return px >= r->x && px < r->x + r->w && py >= r->y && py < r->y + r->h;
}

/* ---------- Construction ---------- */

/* Zones tactiles = zones redessinées = libellé mesuré (jamais rogné, quelle que soit la langue). */
static void layout_options(void) {
    int w = 16 + gfx_text_width(&font_small10, options_label_buf);
    optionsBtn = (Rect){ 4, SCREEN_H - 20, w, 16 };
}

static void layout_allapps(void) {
    int w = 12 + gfx_text_width(&font_small10, allapps_label_buf);   /* 12 px = triangle + espace */
    allAppsBtn = (Rect){ SCREEN_W - 8 - w, SCREEN_H - 20, w + 8, 16 };
}

static void addApp(const char *name, const char *id, Color color, const Icon *icon, int col, int row, int colsInRow) {
    const int iconSize = 44;
    const int rowY[3] = { 46, 128, 210 };
    int cellW = SCREEN_W / colsInRow;
    int cellX = cellW * col + cellW / 2;

    AppIcon *a = &apps[appCount++];
    set_label(a->name, sizeof a->name, name);
    a->id    = id;
    a->color = color;
    a->icon  = icon;
    a->box   = (Rect){ cellX - iconSize / 2, rowY[row], iconSize, iconSize };
    a->cell  = (Rect){ a->box.x - 6, a->box.y - 4, iconSize + 12, iconSize + 24 };
    a->slot  = (Rect){ cellW * col, a->cell.y, cellW, a->cell.h };
    a->flash_until = 0;
}

void ui_init(void) {
    appCount = 0;
    addApp("EDT",         "edt",         COL_EDT,    &icon_edt,    0, 0, 3);
    addApp("Notes",       "notes",       COL_NOTES,  &icon_notes,  1, 0, 3);
    addApp("NFC",         "nfc",         COL_NFC,    &icon_nfc,    2, 0, 3);
    addApp("Shop",        "shop",        COL_SHOP,   &icon_shop,   0, 1, 3);
    addApp("Synchro",     "synchro",     COL_SYNC,   &icon_synchro,   1, 1, 3);
    addApp("Paramètres",  "parametres",  COL_PARAMS, &icon_parametres, 2, 1, 3);
    addApp("Musique",     "musique",     COL_MUSIC,  &icon_musique,  0, 2, 2);
    addApp("Lecteur PDF", "lecteur_pdf", COL_PDF,    &icon_lecteur_pdf,    1, 2, 2);
    layout_options();
    layout_allapps();
    optionsFlash = allAppsFlash = 0;
    pending_event = NULL;
}

/* ---------- Widgets (chacun se redessine seul sur son fond) ---------- */

static void draw_statusbar(void) {
    const uint16_t black = C565(COL_BLACK);
    const Font *f = &font_small10;

    gfx_fill_rect(0, 0, SCREEN_W, STATUS_H, C565(COL_WHITE));

    /* Batterie 12x9 + plot 2x5 : tout est de hauteur impaire, donc centré pile sur STATUS_CY */
    const int bw = 12, bh = 9, nubW = 2, nubH = 5;
    int bx = SCREEN_W - STATUS_MARGIN - nubW - bw;
    gfx_rect(bx, STATUS_CY - bh / 2, bw, bh, black);
    gfx_fill_rect(bx + bw, STATUS_CY - nubH / 2, nubW, nubH, black);

    /* Pourcentage collé à la batterie (largeur mesurée : jamais de chevauchement) */
    int pctX = bx - 4 - gfx_text_width(f, "75%");
    gfx_text_at_cy(f, "75%", pctX, STATUS_CY, black);

    /* Indicateur rond 7x7 (l'ancien disque r=3 sortait en croix), même axe */
    gfx_fill_round_rect(pctX - 5 - 7, STATUS_CY - 3, 7, 7, 3, black);

    /* Heure : le bord gauche de l'ENCRE est à STATUS_MARGIN, comme la batterie à droite */
    gfx_text_at_cy(f, "12:30", STATUS_MARGIN - font_glyph(f, '1')->xo, STATUS_CY, black);

    gfx_rect(0, 0, SCREEN_W, STATUS_H, C565(COL_BORDER));
}

static void draw_titlebar(void) {
    gfx_fill_rect(0, STATUS_H, SCREEN_W, TITLE_H, C565(COL_TITLEBAR));
    gfx_text_centered(&font_bold13, home_title_buf, SCREEN_W / 2, STATUS_H + TITLE_H / 2, C565(COL_WHITE));
}

static void draw_icon(int i) {
    AppIcon *a = &apps[i];
    gfx_fill_rect(a->slot.x, a->slot.y, a->slot.w, a->slot.h, C565(COL_BG));
    if (a->icon) {
        gfx_blit(a->icon, a->box.x, a->box.y);
        if (a->flash_until)                             /* éclaircit : voile blanc à 45 % */
            gfx_fill_round_rect_alpha(a->box.x, a->box.y, a->box.w, a->box.h, 10, C565(COL_WHITE), 115);
    } else {
        Color box = a->color;
        if (a->flash_until) {                           /* pas d'icône : repli carré coloré, éclairci de 50 % */
            box.r = 255 - (255 - box.r) / 2;
            box.g = 255 - (255 - box.g) / 2;
            box.b = 255 - (255 - box.b) / 2;
        }
        gfx_fill_round_rect(a->box.x, a->box.y, a->box.w, a->box.h, 10, C565(box));
    }
    gfx_text_centered(&font_tiny9, a->name, a->box.x + a->box.w / 2,
                      a->box.y + a->box.h + 12, C565(COL_BLACK));
}

static void draw_options(void) {
    Color bg = optionsFlash ? (Color){210, 210, 210} : COL_BG;
    gfx_fill_rect(optionsBtn.x, optionsBtn.y, optionsBtn.w, optionsBtn.h, C565(bg));
    gfx_rect(optionsBtn.x, optionsBtn.y, optionsBtn.w, optionsBtn.h, C565(COL_BLACK));
    gfx_text_centered(&font_small10, options_label_buf, optionsBtn.x + optionsBtn.w / 2,
                      optionsBtn.y + optionsBtn.h / 2, C565(COL_BLACK));
}

static void draw_allapps(void) {
    Color fg = allAppsFlash ? (Color){120, 120, 120} : COL_BLACK;
    const Font *f = &font_small10;
    int x  = allAppsBtn.x + 4;
    int cy = allAppsBtn.y + allAppsBtn.h / 2;
    gfx_fill_rect(allAppsBtn.x, allAppsBtn.y, allAppsBtn.w, allAppsBtn.h, C565(COL_BG));
    gfx_fill_triangle_up(x, cy - 3, 7, 7, C565(fg));          /* 7 lignes = hauteur des capitales */
    gfx_text_at_cy(f, allapps_label_buf, x + 12, cy, C565(fg));
}

/* ---------- API ---------- */

void ui_draw_all(void) {
    for (int i = 0; i < appCount; i++) apps[i].flash_until = 0;   /* repart d'un état propre (retour d'appli) */
    optionsFlash = allAppsFlash = 0;
    gfx_clear(C565(COL_BG));
    draw_statusbar();
    draw_titlebar();
    for (int i = 0; i < appCount; i++) draw_icon(i);
    gfx_hline(4, SCREEN_W - 5, SCREEN_H - 26, C565(COL_BORDER));
    draw_options();
    draw_allapps();
}

void ui_draw_loading(const char *label, int step, int total) {
    const Font *f = &font_small10;
    gfx_clear(C565(COL_BG));
    gfx_text_centered(f, "Chargement...", SCREEN_W / 2, SCREEN_H / 2 - 20, C565(COL_BLACK));
    gfx_text_centered(f, label, SCREEN_W / 2, SCREEN_H / 2, C565(COL_BLACK));

    int barW = SCREEN_W - 60, barH = 8, barX = 30, barY = SCREEN_H / 2 + 20;
    gfx_rect(barX, barY, barW, barH, C565(COL_BLACK));
    int fillW = total > 0 ? (barW - 2) * step / total : 0;
    if (fillW > 0) gfx_fill_rect(barX + 1, barY + 1, fillW, barH - 2, C565(COL_TITLEBAR));
}

void ui_touch_down(int x, int y, uint32_t now_ms) {
    uint32_t until = now_ms + FLASH_MS;
    if (until == 0) until = 1;

    for (int i = 0; i < appCount; i++) {
        if (point_in(x, y, &apps[i].cell)) {
            apps[i].flash_until = until;
            draw_icon(i);
            pending_event = apps[i].id;
            return;
        }
    }
    if (point_in(x, y, &optionsBtn)) {
        optionsFlash = until;
        draw_options();
        pending_event = "options";
        return;
    }
    if (point_in(x, y, &allAppsBtn)) {
        allAppsFlash = until;
        draw_allapps();
        pending_event = "all_apps";
    }
}

void ui_tick(uint32_t now_ms) {
    for (int i = 0; i < appCount; i++)
        if (expired(apps[i].flash_until, now_ms)) { apps[i].flash_until = 0; draw_icon(i); }
    if (expired(optionsFlash, now_ms))  { optionsFlash = 0;  draw_options(); }
    if (expired(allAppsFlash, now_ms))  { allAppsFlash = 0;  draw_allapps(); }
}

const char *ui_take_event(void) {
    const char *e = pending_event;
    pending_event = NULL;
    return e;
}

/* ---------- Traduction (voir python/i18n.py) ---------- */

void ui_set_home_title(const char *utf8) { set_label(home_title_buf, sizeof home_title_buf, utf8); }

void ui_set_options_label(const char *utf8) {
    set_label(options_label_buf, sizeof options_label_buf, utf8);
    layout_options();
}

void ui_set_allapps_label(const char *utf8) {
    set_label(allapps_label_buf, sizeof allapps_label_buf, utf8);
    layout_allapps();
}

void ui_set_app_label(const char *app_id, const char *utf8) {
    for (int i = 0; i < appCount; i++)
        if (strcmp(apps[i].id, app_id) == 0) { set_label(apps[i].name, sizeof apps[i].name, utf8); return; }
}
