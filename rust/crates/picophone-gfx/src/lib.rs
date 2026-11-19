//! Moteur 2D sur framebuffer RGB565 240x320 (port de phone/gfx.c), sans `std` ni allocation.
//!
//! Chaque primitive agrandit la « zone sale » ; le pilote d'écran n'envoie ensuite que cette zone.
//! Le framebuffer est fourni par l'appelant (`&mut [u16; FB_LEN]`) : SRAM ou PSRAM sur la carte,
//! tableau ordinaire dans le simulateur. Le comportement (pixels et zone sale) est celui de gfx.c,
//! vérifié pixel pour pixel par le crate picophone-parity.
#![no_std]

pub mod font;
#[rustfmt::skip]
mod fonts_data;
#[rustfmt::skip]
mod icons_data;

pub use font::{Font, Glyph, WideGlyph};

/// Polices générées par tools/gen_font.py.
pub mod fonts {
    pub use crate::fonts_data::{FONT_BOLD13, FONT_SMALL10, FONT_TINY9};
}

/// Icônes 44x44 générées par tools/gen_icons.py.
pub mod icons {
    pub use crate::icons_data::{
        ICON_EDT, ICON_LECTEUR_PDF, ICON_MUSIQUE, ICON_NFC, ICON_NOTES, ICON_PARAMETRES, ICON_SHOP,
        ICON_SYNCHRO,
    };
}

pub const SCREEN_W: i32 = 240;
pub const SCREEN_H: i32 = 320;
pub const FB_LEN: usize = (SCREEN_W * SCREEN_H) as usize;

/// Couleur RGB565 (comme la macro RGB565 de gfx.h).
pub const fn rgb565(r: u8, g: u8, b: u8) -> u16 {
    (((r as u16) & 0xF8) << 8) | (((g as u16) & 0xFC) << 3) | (((b as u16) & 0xF8) >> 3)
}

/// Rectangle à bornes incluses.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Rect {
    pub x0: i32,
    pub y0: i32,
    pub x1: i32,
    pub y1: i32,
}

/// Icône RGB565 + alpha 8 bits.
pub struct Icon {
    pub w: u8,
    pub h: u8,
    pub px: &'static [u16],
    pub alpha: &'static [u8],
}

/// Mélange alpha RGB565 (alpha 0..32), sans division, sur 32 bits (identique à gfx_blend565).
pub fn blend565(fg: u16, bg: u16, alpha: u32) -> u16 {
    let f = (fg as u32 | ((fg as u32) << 16)) & 0x07E0_F81F;
    let b = (bg as u32 | ((bg as u32) << 16)) & 0x07E0_F81F;
    let r = ((f.wrapping_sub(b).wrapping_mul(alpha) >> 5).wrapping_add(b)) & 0x07E0_F81F;
    (r | (r >> 16)) as u16
}

fn isqrt(n: i32) -> i32 {
    let mut r = 0;
    while (r + 1) * (r + 1) <= n {
        r += 1;
    }
    r
}

/// Retrait horizontal de la ligne `row` d'un rectangle arrondi (une ligne = un segment).
fn round_inset(row: i32, h: i32, r: i32) -> i32 {
    let k = if row < r {
        row
    } else if row >= h - r {
        h - 1 - row
    } else {
        r
    };
    if k < r {
        let dy2 = 2 * (r - k) - 1; // distance au centre, en demi-pixels
        let dx2 = isqrt(4 * r * r - dy2 * dy2);
        (2 * r - dx2) / 2
    } else {
        0
    }
}

pub struct Gfx<'a> {
    fb: &'a mut [u16; FB_LEN],
    dirty: Rect,
}

const CLEAN: Rect = Rect {
    x0: SCREEN_W,
    y0: SCREEN_H,
    x1: -1,
    y1: -1,
};

impl<'a> Gfx<'a> {
    /// Le contenu du framebuffer est conservé ; la zone sale part vide.
    pub fn new(fb: &'a mut [u16; FB_LEN]) -> Self {
        Gfx { fb, dirty: CLEAN }
    }

    pub fn framebuffer(&self) -> &[u16; FB_LEN] {
        self.fb
    }

    /// Récupère puis réinitialise la zone sale (`None` si rien n'a changé).
    pub fn take_dirty(&mut self) -> Option<Rect> {
        let d = self.dirty;
        if d.x1 < d.x0 || d.y1 < d.y0 {
            return None;
        }
        self.dirty = CLEAN;
        Some(d)
    }

    fn mark(&mut self, x0: i32, y0: i32, x1: i32, y1: i32) {
        let d = &mut self.dirty;
        d.x0 = d.x0.min(x0);
        d.y0 = d.y0.min(y0);
        d.x1 = d.x1.max(x1);
        d.y1 = d.y1.max(y1);
    }

    #[inline]
    fn px(&mut self, x: i32, y: i32) -> &mut u16 {
        &mut self.fb[(y * SCREEN_W + x) as usize]
    }

    // ---------- Rectangles / lignes ----------

    pub fn fill_rect(&mut self, x: i32, y: i32, w: i32, h: i32, c: u16) {
        let (x0, y0) = (x.max(0), y.max(0));
        let x1 = (x + w - 1).min(SCREEN_W - 1);
        let y1 = (y + h - 1).min(SCREEN_H - 1);
        if x0 > x1 || y0 > y1 {
            return;
        }
        for yy in y0..=y1 {
            let row = (yy * SCREEN_W) as usize;
            self.fb[row + x0 as usize..=row + x1 as usize].fill(c);
        }
        self.mark(x0, y0, x1, y1);
    }

    pub fn clear(&mut self, c: u16) {
        self.fill_rect(0, 0, SCREEN_W, SCREEN_H, c);
    }

    pub fn hline(&mut self, x0: i32, x1: i32, y: i32, c: u16) {
        self.fill_rect(x0, y, x1 - x0 + 1, 1, c);
    }

    /// Contour de 1 px.
    pub fn rect(&mut self, x: i32, y: i32, w: i32, h: i32, c: u16) {
        if w <= 0 || h <= 0 {
            return;
        }
        self.fill_rect(x, y, w, 1, c);
        self.fill_rect(x, y + h - 1, w, 1, c);
        self.fill_rect(x, y, 1, h, c);
        self.fill_rect(x + w - 1, y, 1, h, c);
    }

    // ---------- Formes (entiers uniquement) ----------

    pub fn fill_circle(&mut self, cx: i32, cy: i32, r: i32, c: u16) {
        for dy in -r..=r {
            let dx = isqrt(r * r - dy * dy);
            self.fill_rect(cx - dx, cy + dy, 2 * dx + 1, 1, c);
        }
    }

    pub fn fill_round_rect(&mut self, x: i32, y: i32, w: i32, h: i32, mut r: i32, c: u16) {
        if r * 2 > w {
            r = w / 2;
        }
        if r * 2 > h {
            r = h / 2;
        }
        for row in 0..h {
            let inset = round_inset(row, h, r);
            self.fill_rect(x + inset, y + row, w - 2 * inset, 1, c);
        }
    }

    /// Rectangle arrondi semi-transparent (`alpha8` 0-255), p. ex. le voile du « flash » d'une icône.
    #[allow(clippy::too_many_arguments)]
    pub fn fill_round_rect_alpha(
        &mut self,
        x: i32,
        y: i32,
        w: i32,
        h: i32,
        mut r: i32,
        c: u16,
        alpha8: u8,
    ) {
        if alpha8 == 0 {
            return;
        }
        if alpha8 == 255 {
            self.fill_round_rect(x, y, w, h, r, c);
            return;
        }
        if r * 2 > w {
            r = w / 2;
        }
        if r * 2 > h {
            r = h / 2;
        }
        let a = (alpha8 as u32 + 4) >> 3; // 0..255 -> 0..32
        let (x0, y0) = (x.max(0), y.max(0));
        let x1 = (x + w - 1).min(SCREEN_W - 1);
        let y1 = (y + h - 1).min(SCREEN_H - 1);
        if x0 > x1 || y0 > y1 {
            return;
        }
        for row in 0..h {
            let py = y + row;
            if !(0..SCREEN_H).contains(&py) {
                continue;
            }
            let inset = round_inset(row, h, r);
            let sx0 = (x + inset).max(0);
            let sx1 = (x + w - 1 - inset).min(SCREEN_W - 1);
            for px in sx0..=sx1 {
                let p = self.px(px, py);
                *p = blend565(c, *p, a);
            }
        }
        self.mark(x0, y0, x1, y1);
    }

    /// Compose une icône RGB565+alpha sur le fond actuel (coins transparents -> fond visible).
    pub fn blit(&mut self, icon: &Icon, x: i32, y: i32) {
        let (w, h) = (icon.w as i32, icon.h as i32);
        for row in 0..h {
            let py = y + row;
            if !(0..SCREEN_H).contains(&py) {
                continue;
            }
            for col in 0..w {
                let pxx = x + col;
                let i = (row * w + col) as usize;
                let al = icon.alpha[i];
                if !(0..SCREEN_W).contains(&pxx) || al == 0 {
                    continue;
                }
                let src = icon.px[i];
                let p = self.px(pxx, py);
                *p = if al > 250 {
                    src
                } else {
                    blend565(src, *p, (al as u32 + 4) >> 3)
                };
            }
        }
        // Comme gfx_blit : bornes ramenées dans l'écran sans vérifier que l'icône y est.
        let x0 = x.max(0);
        let y0 = y.max(0);
        let x1 = (x + w - 1).min(SCREEN_W - 1);
        let y1 = (y + h - 1).min(SCREEN_H - 1);
        self.mark(x0, y0, x1, y1);
    }

    /// Petit triangle plein pointe en haut (remplace le glyphe U+25B2, absent de Latin-1).
    pub fn fill_triangle_up(&mut self, x: i32, y: i32, w: i32, h: i32, c: u16) {
        for row in 0..h {
            let span = ((w * (row + 1)) / h).max(1);
            self.fill_rect(x + (w - span) / 2, y + row, span, 1, c);
        }
    }

    // ---------- Texte ----------

    /// (x, y) = coin haut-gauche de la boîte de ligne.
    pub fn text(&mut self, f: &Font, s: &str, x: i32, y: i32, c: u16) {
        let mut pen = x;
        let base = y + f.ascent as i32;
        for ch in s.chars() {
            let g = *f.glyph(ch as u32);
            let bmp = f.bitmap_of(&g);
            let (gw, gh) = (g.w as i32, g.h as i32);
            let gx = pen + g.xo as i32;
            let gy = base + g.yo as i32;
            for j in 0..gh {
                let py = gy + j;
                if !(0..SCREEN_H).contains(&py) {
                    continue;
                }
                for i in 0..gw {
                    let px = gx + i;
                    let a = bmp[(j * gw + i) as usize];
                    if a != 0 && (0..SCREEN_W).contains(&px) {
                        let p = self.px(px, py);
                        *p = if a > 250 {
                            c
                        } else {
                            blend565(c, *p, (a as u32 + 4) >> 3)
                        };
                    }
                }
            }
            if gw != 0 {
                self.mark(
                    gx.max(0),
                    gy.max(0),
                    (gx + gw - 1).min(SCREEN_W - 1),
                    (gy + gh - 1).min(SCREEN_H - 1),
                );
            }
            pen += g.adv as i32;
        }
    }

    /// Alignement vertical « optique » : la hauteur des capitales est centrée sur `cy`.
    pub fn text_at_cy(&mut self, f: &Font, s: &str, x: i32, cy: i32, c: u16) {
        let cap = f.glyph('H' as u32).h as i32;
        let baseline = cy - cap / 2 + cap;
        self.text(f, s, x, baseline - f.ascent as i32, c);
    }

    /// Centré sur (cx, cy).
    pub fn text_centered(&mut self, f: &Font, s: &str, cx: i32, cy: i32, c: u16) {
        self.text_at_cy(f, s, cx - f.text_width(s) / 2, cy, c);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rgb565_matches_c_macro() {
        assert_eq!(rgb565(255, 255, 255), 0xFFFF);
        assert_eq!(
            rgb565(90, 70, 200),
            ((90 & 0xF8) << 8) | ((70 & 0xFC) << 3) | ((200 & 0xF8) >> 3)
        );
    }

    #[test]
    fn dirty_rect_accumulates_and_resets() {
        let mut fb = [0u16; FB_LEN];
        let mut g = Gfx::new(&mut fb);
        assert_eq!(g.take_dirty(), None);
        g.fill_rect(10, 20, 5, 5, 1);
        g.fill_rect(-10, 300, 30, 100, 1);
        assert_eq!(
            g.take_dirty(),
            Some(Rect {
                x0: 0,
                y0: 20,
                x1: 19,
                y1: 319
            })
        );
        assert_eq!(g.take_dirty(), None);
        g.fill_rect(500, 500, 10, 10, 1); // entièrement hors écran : rien
        assert_eq!(g.take_dirty(), None);
    }

    #[test]
    fn unknown_char_uses_question_mark() {
        let f = &fonts::FONT_SMALL10;
        assert_eq!(f.glyph(0x1F600), f.glyph('?' as u32));
        assert_eq!(f.glyph(0x4E00 + 7), f.glyph('?' as u32)); // CJK absent du vocabulaire
        assert_ne!(f.glyph('A' as u32), f.glyph('?' as u32));
    }
}
