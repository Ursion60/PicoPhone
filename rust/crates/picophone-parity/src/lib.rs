//! Interface vers le moteur C historique (phone/gfx.c, phone/ui.c), compilé par build.rs.
//! Utilisé uniquement par les tests de parité (tests/parity.rs).
#![allow(non_upper_case_globals)]

use std::ffi::{c_char, c_int};

#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct GfxRect {
    pub x0: c_int,
    pub y0: c_int,
    pub x1: c_int,
    pub y1: c_int,
}

/// Types opaques (on ne manipule que leur adresse).
#[repr(C)]
pub struct CFont {
    _private: [u8; 0],
}
#[repr(C)]
pub struct CIcon {
    _private: [u8; 0],
}

unsafe extern "C" {
    pub fn gfx_init();
    pub fn gfx_framebuffer() -> *mut u16;
    pub fn gfx_take_dirty(out: *mut GfxRect) -> bool;
    pub fn gfx_clear(c: u16);
    pub fn gfx_fill_rect(x: c_int, y: c_int, w: c_int, h: c_int, c: u16);
    pub fn gfx_rect(x: c_int, y: c_int, w: c_int, h: c_int, c: u16);
    pub fn gfx_hline(x0: c_int, x1: c_int, y: c_int, c: u16);
    pub fn gfx_fill_circle(cx: c_int, cy: c_int, r: c_int, c: u16);
    pub fn gfx_fill_round_rect(x: c_int, y: c_int, w: c_int, h: c_int, r: c_int, c: u16);
    pub fn gfx_fill_round_rect_alpha(
        x: c_int,
        y: c_int,
        w: c_int,
        h: c_int,
        r: c_int,
        c: u16,
        alpha: u8,
    );
    pub fn gfx_blit(icon: *const CIcon, x: c_int, y: c_int);
    pub fn gfx_fill_triangle_up(x: c_int, y: c_int, w: c_int, h: c_int, c: u16);
    pub fn gfx_text_width(f: *const CFont, s: *const c_char) -> c_int;
    pub fn gfx_text(f: *const CFont, s: *const c_char, x: c_int, y: c_int, c: u16);
    pub fn gfx_text_at_cy(f: *const CFont, s: *const c_char, x: c_int, cy: c_int, c: u16);
    pub fn gfx_text_centered(f: *const CFont, s: *const c_char, cx: c_int, cy: c_int, c: u16);

    pub static font_bold13: CFont;
    pub static font_small10: CFont;
    pub static font_tiny9: CFont;
    pub static icon_edt: CIcon;
    pub static icon_notes: CIcon;
    pub static icon_nfc: CIcon;
    pub static icon_shop: CIcon;
    pub static icon_synchro: CIcon;
    pub static icon_parametres: CIcon;
    pub static icon_musique: CIcon;
    pub static icon_lecteur_pdf: CIcon;

    pub fn ui_init();
    pub fn ui_draw_loading(label: *const c_char, step: c_int, total: c_int);
    pub fn ui_draw_all();
    pub fn ui_touch_down(x: c_int, y: c_int, now_ms: u32);
    pub fn ui_tick(now_ms: u32);
    pub fn ui_take_event() -> *const c_char;
    pub fn ui_set_home_title(s: *const c_char);
    pub fn ui_set_options_label(s: *const c_char);
    pub fn ui_set_allapps_label(s: *const c_char);
    pub fn ui_set_app_label(app_id: *const c_char, s: *const c_char);
}
