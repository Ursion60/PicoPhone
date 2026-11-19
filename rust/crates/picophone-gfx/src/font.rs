//! Polices bitmap anti-aliasées (port de phone/font.h et phone/font.c).
//! Les données sont générées par tools/gen_font.py (fonts_data.rs + data/*.bin).

/// Glyphe : bitmap alpha 8 bits (`w * h` octets) dans `Font::bitmap`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Glyph {
    /// Offset dans `Font::bitmap`.
    pub off: u16,
    pub w: u8,
    pub h: u8,
    /// x = plume + `xo`.
    pub xo: i8,
    /// y (haut du bitmap) = ligne de base + `yo`.
    pub yo: i8,
    /// Avance horizontale.
    pub adv: u8,
}

/// Glyphe hors Latin-1 (CJK...), retrouvé par recherche dichotomique sur `cp`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct WideGlyph {
    pub cp: u16,
    pub g: Glyph,
}

pub struct Font {
    /// ASCII 0x20-0x7E puis Latin-1 0xA0-0xFF (191 entrées).
    pub glyphs: &'static [Glyph],
    pub bitmap: &'static [u8],
    pub line_h: u8,
    pub ascent: u8,
    /// Triés par codepoint croissant.
    pub wide: &'static [WideGlyph],
}

impl Font {
    /// Glyphe de `cp`, ou celui de « ? » s'il n'est pas dans la police.
    pub fn glyph(&self, cp: u32) -> &Glyph {
        match cp {
            0x20..=0x7E => &self.glyphs[(cp - 0x20) as usize],
            0xA0..=0xFF => &self.glyphs[(cp - 0xA0 + 95) as usize],
            _ => match u16::try_from(cp) {
                Ok(cp16) => match self.wide.binary_search_by_key(&cp16, |w| w.cp) {
                    Ok(i) => &self.wide[i].g,
                    Err(_) => self.question_mark(),
                },
                Err(_) => self.question_mark(),
            },
        }
    }

    fn question_mark(&self) -> &Glyph {
        &self.glyphs[(b'?' - 0x20) as usize]
    }

    /// Bitmap alpha du glyphe (`w * h` octets).
    pub fn bitmap_of(&self, g: &Glyph) -> &[u8] {
        let start = g.off as usize;
        &self.bitmap[start..start + g.w as usize * g.h as usize]
    }

    /// Largeur d'un texte en pixels (somme des avances).
    pub fn text_width(&self, s: &str) -> i32 {
        s.chars().map(|c| self.glyph(c as u32).adv as i32).sum()
    }
}
