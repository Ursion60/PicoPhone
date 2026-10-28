/*
 * Module MicroPython `phone` : expose à Python le moteur 2D (gfx), l'écran d'accueil (ui)
 * et le matériel (hal). Les applis, écrites en MicroPython, n'ont qu'à faire `import phone`.
 *
 *   phone.init()                      initialise écran + tactile
 *   phone.home() / phone.home_poll()  écran d'accueil ; home_poll() renvoie l'id de l'appli touchée
 *   phone.clear/fill_rect/rect/round_rect/circle/hline/text/text_c/text_l/text_w
 *   phone.tap() / phone.touch()       tactile : front montant / état
 *   phone.flush()                     envoie à l'écran la zone modifiée
 */
#include <string.h>
#include "py/runtime.h"
#include "py/mphal.h"
#include "gfx.h"
#include "ui.h"
#include "hal.h"

static bool s_ready = false;
static bool s_was_down = false;

static void ensure_ready(void) {
    if (!s_ready) mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("phone.init() not called"));
}

static void present(void) {                    /* envoie la zone sale, s'il y en a une */
    GfxRect r;
    if (gfx_take_dirty(&r)) hal_flush(gfx_framebuffer(), r.x0, r.y0, r.x1, r.y1);
}

/* Lit le tactile ; met à jour l'état "doigt posé" partagé entre l'accueil et les applis
 * (ainsi un appui qui lance une appli ne compte pas comme un 2e appui dans l'appli). */
static bool poll_touch(int *x, int *y, bool *edge) {
    bool down = hal_touch(x, y);
    *edge = down && !s_was_down;
    s_was_down = down;
    return down;
}

static uint16_t color_arg(mp_obj_t o) { return (uint16_t)mp_obj_get_int(o); }

static const Font *font_arg(size_t n_args, const mp_obj_t *args, size_t idx) {
    int f = n_args > idx ? mp_obj_get_int(args[idx]) : 1;
    switch (f) {
        case 0:  return &font_bold13;
        case 2:  return &font_tiny9;
        default: return &font_small10;
    }
}

/* ---------- Cycle de vie ---------- */

static mp_obj_t phone_init(void) {
    if (!s_ready) {
        if (!hal_fb_ready()) mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("PSRAM not available"));
        gfx_init();
        ui_init();
        hal_init();
        s_ready = true;
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(phone_init_obj, phone_init);

static mp_obj_t phone_backlight(mp_obj_t level) {
    ensure_ready();
    int l = mp_obj_get_int(level);
    hal_backlight((uint8_t)(l < 0 ? 0 : (l > 255 ? 255 : l)));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(phone_backlight_obj, phone_backlight);

static mp_obj_t phone_flush(void) {
    ensure_ready();
    present();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(phone_flush_obj, phone_flush);

/* ---------- Écran d'accueil ---------- */

static mp_obj_t phone_loading(mp_obj_t label, mp_obj_t step, mp_obj_t total) {
    ensure_ready();
    ui_draw_loading(mp_obj_str_get_str(label), mp_obj_get_int(step), mp_obj_get_int(total));
    present();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_3(phone_loading_obj, phone_loading);

static mp_obj_t phone_home(void) {
    ensure_ready();
    ui_draw_all();
    present();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(phone_home_obj, phone_home);

/* À appeler en boucle : gère le tactile, les animations, l'envoi écran.
 * Renvoie l'identifiant ("notes", "parametres", "options"...) quand on touche un élément. */
static mp_obj_t phone_home_poll(void) {
    ensure_ready();
    int x, y;
    bool edge;
    uint32_t now = mp_hal_ticks_ms();
    if (poll_touch(&x, &y, &edge) && edge) ui_touch_down(x, y, now);
    ui_tick(now);
    present();
    const char *ev = ui_take_event();
    return ev ? mp_obj_new_str(ev, strlen(ev)) : mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(phone_home_poll_obj, phone_home_poll);

/* ---------- Tactile ---------- */

static mp_obj_t xy_tuple(int x, int y) {
    mp_obj_t t[2] = { MP_OBJ_NEW_SMALL_INT(x), MP_OBJ_NEW_SMALL_INT(y) };
    return mp_obj_new_tuple(2, t);
}

/* (x, y) uniquement au moment où le doigt se pose, sinon None */
static mp_obj_t phone_tap(void) {
    ensure_ready();
    int x, y;
    bool edge;
    poll_touch(&x, &y, &edge);
    return edge ? xy_tuple(x, y) : mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(phone_tap_obj, phone_tap);

/* (x, y) tant que le doigt est posé (glisser), sinon None */
static mp_obj_t phone_touch(void) {
    ensure_ready();
    int x, y;
    bool edge;
    return poll_touch(&x, &y, &edge) ? xy_tuple(x, y) : mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(phone_touch_obj, phone_touch);

/* ---------- Dessin (couleurs = entiers RGB565, voir phone.rgb) ---------- */

static mp_obj_t phone_rgb(mp_obj_t r, mp_obj_t g, mp_obj_t b) {
    return MP_OBJ_NEW_SMALL_INT(RGB565(mp_obj_get_int(r), mp_obj_get_int(g), mp_obj_get_int(b)));
}
static MP_DEFINE_CONST_FUN_OBJ_3(phone_rgb_obj, phone_rgb);

static mp_obj_t phone_clear(mp_obj_t c) {
    ensure_ready();
    gfx_clear(color_arg(c));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(phone_clear_obj, phone_clear);

static mp_obj_t phone_fill_rect(size_t n, const mp_obj_t *a) {
    (void)n; ensure_ready();
    gfx_fill_rect(mp_obj_get_int(a[0]), mp_obj_get_int(a[1]), mp_obj_get_int(a[2]), mp_obj_get_int(a[3]), color_arg(a[4]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(phone_fill_rect_obj, 5, 5, phone_fill_rect);

static mp_obj_t phone_rect(size_t n, const mp_obj_t *a) {
    (void)n; ensure_ready();
    gfx_rect(mp_obj_get_int(a[0]), mp_obj_get_int(a[1]), mp_obj_get_int(a[2]), mp_obj_get_int(a[3]), color_arg(a[4]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(phone_rect_obj, 5, 5, phone_rect);

static mp_obj_t phone_round_rect(size_t n, const mp_obj_t *a) {
    (void)n; ensure_ready();
    gfx_fill_round_rect(mp_obj_get_int(a[0]), mp_obj_get_int(a[1]), mp_obj_get_int(a[2]), mp_obj_get_int(a[3]),
                        mp_obj_get_int(a[4]), color_arg(a[5]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(phone_round_rect_obj, 6, 6, phone_round_rect);

static mp_obj_t phone_circle(size_t n, const mp_obj_t *a) {
    (void)n; ensure_ready();
    gfx_fill_circle(mp_obj_get_int(a[0]), mp_obj_get_int(a[1]), mp_obj_get_int(a[2]), color_arg(a[3]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(phone_circle_obj, 4, 4, phone_circle);

static mp_obj_t phone_hline(size_t n, const mp_obj_t *a) {
    (void)n; ensure_ready();
    gfx_hline(mp_obj_get_int(a[0]), mp_obj_get_int(a[1]), mp_obj_get_int(a[2]), color_arg(a[3]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(phone_hline_obj, 4, 4, phone_hline);

/* text(s, x, y, color [, font])     (x,y) = coin haut-gauche de la ligne */
static mp_obj_t phone_text(size_t n, const mp_obj_t *a) {
    ensure_ready();
    gfx_text(font_arg(n, a, 4), mp_obj_str_get_str(a[0]), mp_obj_get_int(a[1]), mp_obj_get_int(a[2]), color_arg(a[3]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(phone_text_obj, 4, 5, phone_text);

/* text_c(s, cx, cy, color [, font]) centré horizontalement sur cx, verticalement sur cy */
static mp_obj_t phone_text_c(size_t n, const mp_obj_t *a) {
    ensure_ready();
    gfx_text_centered(font_arg(n, a, 4), mp_obj_str_get_str(a[0]), mp_obj_get_int(a[1]), mp_obj_get_int(a[2]), color_arg(a[3]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(phone_text_c_obj, 4, 5, phone_text_c);

/* text_l(s, x, cy, color [, font])  aligné à gauche en x, centré verticalement sur cy */
static mp_obj_t phone_text_l(size_t n, const mp_obj_t *a) {
    ensure_ready();
    gfx_text_at_cy(font_arg(n, a, 4), mp_obj_str_get_str(a[0]), mp_obj_get_int(a[1]), mp_obj_get_int(a[2]), color_arg(a[3]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(phone_text_l_obj, 4, 5, phone_text_l);

static mp_obj_t phone_text_w(size_t n, const mp_obj_t *a) {
    return MP_OBJ_NEW_SMALL_INT(gfx_text_width(font_arg(n, a, 1), mp_obj_str_get_str(a[0])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(phone_text_w_obj, 1, 2, phone_text_w);

/* ---------- Traduction (voir python/i18n.py) ---------- */

static mp_obj_t phone_set_home_title(mp_obj_t s) {
    ui_set_home_title(mp_obj_str_get_str(s));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(phone_set_home_title_obj, phone_set_home_title);

static mp_obj_t phone_set_options_label(mp_obj_t s) {
    ui_set_options_label(mp_obj_str_get_str(s));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(phone_set_options_label_obj, phone_set_options_label);

static mp_obj_t phone_set_allapps_label(mp_obj_t s) {
    ui_set_allapps_label(mp_obj_str_get_str(s));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(phone_set_allapps_label_obj, phone_set_allapps_label);

static mp_obj_t phone_set_app_label(mp_obj_t app_id, mp_obj_t s) {
    ui_set_app_label(mp_obj_str_get_str(app_id), mp_obj_str_get_str(s));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(phone_set_app_label_obj, phone_set_app_label);

/* ---------- Simulateur PC uniquement ---------- */
#ifdef PHONE_SIM
static mp_obj_t phone_sim_touch(size_t n, const mp_obj_t *a) {
    if (n == 2) hal_sim_touch(mp_obj_get_int(a[0]), mp_obj_get_int(a[1]), true);
    else        hal_sim_touch(0, 0, false);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(phone_sim_touch_obj, 0, 2, phone_sim_touch);

static mp_obj_t phone_sim_screenshot(mp_obj_t path) {
    return mp_obj_new_bool(hal_sim_screenshot(mp_obj_str_get_str(path), gfx_framebuffer()));
}
static MP_DEFINE_CONST_FUN_OBJ_1(phone_sim_screenshot_obj, phone_sim_screenshot);
#endif

/* ---------- Table du module ---------- */

static const mp_rom_map_elem_t phone_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__),   MP_ROM_QSTR(MP_QSTR_phone) },
    { MP_ROM_QSTR(MP_QSTR_WIDTH),      MP_ROM_INT(SCREEN_W) },
    { MP_ROM_QSTR(MP_QSTR_HEIGHT),     MP_ROM_INT(SCREEN_H) },
    { MP_ROM_QSTR(MP_QSTR_BOLD),       MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_SMALL),      MP_ROM_INT(1) },
    { MP_ROM_QSTR(MP_QSTR_TINY),       MP_ROM_INT(2) },

    { MP_ROM_QSTR(MP_QSTR_init),       MP_ROM_PTR(&phone_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_backlight),  MP_ROM_PTR(&phone_backlight_obj) },
    { MP_ROM_QSTR(MP_QSTR_flush),      MP_ROM_PTR(&phone_flush_obj) },
    { MP_ROM_QSTR(MP_QSTR_loading),    MP_ROM_PTR(&phone_loading_obj) },
    { MP_ROM_QSTR(MP_QSTR_home),       MP_ROM_PTR(&phone_home_obj) },
    { MP_ROM_QSTR(MP_QSTR_home_poll),  MP_ROM_PTR(&phone_home_poll_obj) },
    { MP_ROM_QSTR(MP_QSTR_tap),        MP_ROM_PTR(&phone_tap_obj) },
    { MP_ROM_QSTR(MP_QSTR_touch),      MP_ROM_PTR(&phone_touch_obj) },

    { MP_ROM_QSTR(MP_QSTR_rgb),        MP_ROM_PTR(&phone_rgb_obj) },
    { MP_ROM_QSTR(MP_QSTR_clear),      MP_ROM_PTR(&phone_clear_obj) },
    { MP_ROM_QSTR(MP_QSTR_fill_rect),  MP_ROM_PTR(&phone_fill_rect_obj) },
    { MP_ROM_QSTR(MP_QSTR_rect),       MP_ROM_PTR(&phone_rect_obj) },
    { MP_ROM_QSTR(MP_QSTR_round_rect), MP_ROM_PTR(&phone_round_rect_obj) },
    { MP_ROM_QSTR(MP_QSTR_circle),     MP_ROM_PTR(&phone_circle_obj) },
    { MP_ROM_QSTR(MP_QSTR_hline),      MP_ROM_PTR(&phone_hline_obj) },
    { MP_ROM_QSTR(MP_QSTR_text),       MP_ROM_PTR(&phone_text_obj) },
    { MP_ROM_QSTR(MP_QSTR_text_c),     MP_ROM_PTR(&phone_text_c_obj) },
    { MP_ROM_QSTR(MP_QSTR_text_l),     MP_ROM_PTR(&phone_text_l_obj) },
    { MP_ROM_QSTR(MP_QSTR_text_w),     MP_ROM_PTR(&phone_text_w_obj) },

    { MP_ROM_QSTR(MP_QSTR_set_home_title),    MP_ROM_PTR(&phone_set_home_title_obj) },
    { MP_ROM_QSTR(MP_QSTR_set_options_label), MP_ROM_PTR(&phone_set_options_label_obj) },
    { MP_ROM_QSTR(MP_QSTR_set_allapps_label), MP_ROM_PTR(&phone_set_allapps_label_obj) },
    { MP_ROM_QSTR(MP_QSTR_set_app_label),     MP_ROM_PTR(&phone_set_app_label_obj) },
#ifdef PHONE_SIM
    { MP_ROM_QSTR(MP_QSTR_sim_touch),      MP_ROM_PTR(&phone_sim_touch_obj) },
    { MP_ROM_QSTR(MP_QSTR_sim_screenshot), MP_ROM_PTR(&phone_sim_screenshot_obj) },
#endif
};
static MP_DEFINE_CONST_DICT(phone_module_globals, phone_module_globals_table);

const mp_obj_module_t phone_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&phone_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_phone, phone_user_cmodule);
