//! Écran d'accueil 240x320 et écran de chargement (port de phone/ui.c), sans `std` ni allocation.
//! Indépendant du matériel : ne dépend que de picophone-gfx. Le temps est fourni par l'appelant (ms).
#![no_std]

use heapless::String;
use picophone_gfx::{Font, Gfx, Icon, SCREEN_H, SCREEN_W, fonts, icons, rgb565};

const FLASH_MS: u32 = 160;
const STATUS_H: i32 = 17; // 1 px de bordure + 15 px intérieurs...
const STATUS_CY: i32 = 8; // ...donc une ligne centrale exacte pour tout aligner
const STATUS_MARGIN: i32 = 6;
const TITLE_H: i32 = 22;

#[derive(Clone, Copy)]
struct Color(u8, u8, u8);

impl Color {
    const fn c565(self) -> u16 {
        rgb565(self.0, self.1, self.2)
    }
}

const COL_BG: Color = Color(236, 236, 236);
const COL_WHITE: Color = Color(255, 255, 255);
const COL_BLACK: Color = Color(20, 20, 20);
const COL_TITLEBAR: Color = Color(90, 70, 200);
const COL_BORDER: Color = Color(60, 60, 60);

/// Applis de l'accueil (ordre de la grille).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum AppId {
    Edt,
    Notes,
    Nfc,
    Shop,
    Synchro,
    Parametres,
    Musique,
    LecteurPdf,
}

impl AppId {
    pub const ALL: [AppId; 8] = [
        AppId::Edt,
        AppId::Notes,
        AppId::Nfc,
        AppId::Shop,
        AppId::Synchro,
        AppId::Parametres,
        AppId::Musique,
        AppId::LecteurPdf,
    ];

    /// Identifiant historique (celui de ui.c et de python/apps/<id>.py).
    pub const fn as_str(self) -> &'static str {
        match self {
            AppId::Edt => "edt",
            AppId::Notes => "notes",
            AppId::Nfc => "nfc",
            AppId::Shop => "shop",
            AppId::Synchro => "synchro",
            AppId::Parametres => "parametres",
            AppId::Musique => "musique",
            AppId::LecteurPdf => "lecteur_pdf",
        }
    }
}

/// Élément touché sur l'accueil.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum HomeEvent {
    App(AppId),
    Options,
    AllApps,
}

impl HomeEvent {
    pub const fn as_str(self) -> &'static str {
        match self {
            HomeEvent::App(a) => a.as_str(),
            HomeEvent::Options => "options",
            HomeEvent::AllApps => "all_apps",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Area {
    x: i32,
    y: i32,
    w: i32,
    h: i32,
}

impl Area {
    fn contains(&self, px: i32, py: i32) -> bool {
        px >= self.x && px < self.x + self.w && py >= self.y && py < self.y + self.h
    }
}

struct AppIcon {
    id: AppId,
    name: String<24>,
    color: Color,
    icon: Option<&'static Icon>,
    cell: Area, // zone tactile (icône + libellé)
    box_: Area, // carré de l'icône
    slot: Area, // zone effacée/redessinée (déborde pour les libellés larges)
    flash_until: u32,
}

/// Copie `s` en la tronquant à la capacité, sur une frontière de caractère (ui.c coupe à l'octet,
/// ce qui pouvait couper un caractère UTF-8 en deux).
fn set_label<const N: usize>(dst: &mut String<N>, s: &str) {
    dst.clear();
    for ch in s.chars() {
        if dst.push(ch).is_err() {
            break;
        }
    }
}

fn label<const N: usize>(s: &str) -> String<N> {
    let mut l = String::new();
    set_label(&mut l, s);
    l
}

fn expired(deadline: u32, now: u32) -> bool {
    deadline != 0 && (now.wrapping_sub(deadline) as i32) >= 0
}

pub struct Home {
    apps: [AppIcon; 8],
    options_btn: Area,
    allapps_btn: Area,
    options_flash: u32,
    allapps_flash: u32,
    pending: Option<HomeEvent>,
    // Capacités = tailles des tampons de ui.c moins le zéro final.
    title: String<23>,
    options_label: String<23>,
    allapps_label: String<31>,
}

impl Default for Home {
    fn default() -> Self {
        Self::new()
    }
}

impl Home {
    pub fn new() -> Self {
        const ICON: i32 = 44;
        const ROW_Y: [i32; 3] = [46, 128, 210];
        let make = |id, name: &str, color, icon, col: i32, row: usize, cols: i32| {
            let cell_w = SCREEN_W / cols;
            let cell_x = cell_w * col + cell_w / 2;
            let box_ = Area {
                x: cell_x - ICON / 2,
                y: ROW_Y[row],
                w: ICON,
                h: ICON,
            };
            let cell = Area {
                x: box_.x - 6,
                y: box_.y - 4,
                w: ICON + 12,
                h: ICON + 24,
            };
            AppIcon {
                id,
                name: label(name),
                color,
                icon: Some(icon),
                cell,
                box_,
                slot: Area {
                    x: cell_w * col,
                    y: cell.y,
                    w: cell_w,
                    h: cell.h,
                },
                flash_until: 0,
            }
        };
        let mut h = Home {
            apps: [
                make(
                    AppId::Edt,
                    "EDT",
                    Color(0, 140, 130),
                    &icons::ICON_EDT,
                    0,
                    0,
                    3,
                ),
                make(
                    AppId::Notes,
                    "Notes",
                    Color(245, 205, 60),
                    &icons::ICON_NOTES,
                    1,
                    0,
                    3,
                ),
                make(
                    AppId::Nfc,
                    "NFC",
                    Color(40, 140, 235),
                    &icons::ICON_NFC,
                    2,
                    0,
                    3,
                ),
                make(
                    AppId::Shop,
                    "Shop",
                    Color(245, 150, 20),
                    &icons::ICON_SHOP,
                    0,
                    1,
                    3,
                ),
                make(
                    AppId::Synchro,
                    "Synchro",
                    Color(90, 90, 220),
                    &icons::ICON_SYNCHRO,
                    1,
                    1,
                    3,
                ),
                make(
                    AppId::Parametres,
                    "Paramètres",
                    Color(150, 150, 150),
                    &icons::ICON_PARAMETRES,
                    2,
                    1,
                    3,
                ),
                make(
                    AppId::Musique,
                    "Musique",
                    Color(150, 40, 220),
                    &icons::ICON_MUSIQUE,
                    0,
                    2,
                    2,
                ),
                make(
                    AppId::LecteurPdf,
                    "Lecteur PDF",
                    Color(225, 40, 40),
                    &icons::ICON_LECTEUR_PDF,
                    1,
                    2,
                    2,
                ),
            ],
            options_btn: Area {
                x: 0,
                y: 0,
                w: 0,
                h: 0,
            },
            allapps_btn: Area {
                x: 0,
                y: 0,
                w: 0,
                h: 0,
            },
            options_flash: 0,
            allapps_flash: 0,
            pending: None,
            title: label("Accueil"),
            options_label: label("Options"),
            allapps_label: label("Toutes les apps"),
        };
        h.layout_options();
        h.layout_allapps();
        h
    }

    // Zones tactiles = zones redessinées = libellé mesuré (jamais rogné, quelle que soit la langue).
    fn layout_options(&mut self) {
        let w = 16 + fonts::FONT_SMALL10.text_width(&self.options_label);
        self.options_btn = Area {
            x: 4,
            y: SCREEN_H - 20,
            w,
            h: 16,
        };
    }

    fn layout_allapps(&mut self) {
        let w = 12 + fonts::FONT_SMALL10.text_width(&self.allapps_label); // 12 px = triangle + espace
        self.allapps_btn = Area {
            x: SCREEN_W - 8 - w,
            y: SCREEN_H - 20,
            w: w + 8,
            h: 16,
        };
    }

    // ---------- Traduction ----------

    pub fn set_title(&mut self, s: &str) {
        set_label(&mut self.title, s);
    }

    pub fn set_options_label(&mut self, s: &str) {
        set_label(&mut self.options_label, s);
        self.layout_options();
    }

    pub fn set_allapps_label(&mut self, s: &str) {
        set_label(&mut self.allapps_label, s);
        self.layout_allapps();
    }

    pub fn set_app_label(&mut self, id: AppId, s: &str) {
        if let Some(a) = self.apps.iter_mut().find(|a| a.id == id) {
            set_label(&mut a.name, s);
        }
    }

    // ---------- Dessin ----------

    fn draw_statusbar(&self, g: &mut Gfx) {
        let black = COL_BLACK.c565();
        let f: &Font = &fonts::FONT_SMALL10;
        g.fill_rect(0, 0, SCREEN_W, STATUS_H, COL_WHITE.c565());

        // Batterie 12x9 + plot 2x5 : hauteurs impaires, centrées pile sur STATUS_CY
        let (bw, bh, nub_w, nub_h) = (12, 9, 2, 5);
        let bx = SCREEN_W - STATUS_MARGIN - nub_w - bw;
        g.rect(bx, STATUS_CY - bh / 2, bw, bh, black);
        g.fill_rect(bx + bw, STATUS_CY - nub_h / 2, nub_w, nub_h, black);

        let pct_x = bx - 4 - f.text_width("75%");
        g.text_at_cy(f, "75%", pct_x, STATUS_CY, black);
        g.fill_round_rect(pct_x - 5 - 7, STATUS_CY - 3, 7, 7, 3, black);

        // Le bord gauche de l'ENCRE de l'heure est à STATUS_MARGIN, comme la batterie à droite
        g.text_at_cy(
            f,
            "12:30",
            STATUS_MARGIN - f.glyph('1' as u32).xo as i32,
            STATUS_CY,
            black,
        );
        g.rect(0, 0, SCREEN_W, STATUS_H, COL_BORDER.c565());
    }

    fn draw_titlebar(&self, g: &mut Gfx) {
        g.fill_rect(0, STATUS_H, SCREEN_W, TITLE_H, COL_TITLEBAR.c565());
        g.text_centered(
            &fonts::FONT_BOLD13,
            &self.title,
            SCREEN_W / 2,
            STATUS_H + TITLE_H / 2,
            COL_WHITE.c565(),
        );
    }

    fn draw_icon(&self, g: &mut Gfx, i: usize) {
        let a = &self.apps[i];
        g.fill_rect(a.slot.x, a.slot.y, a.slot.w, a.slot.h, COL_BG.c565());
        let b = a.box_;
        match a.icon {
            Some(icon) => {
                g.blit(icon, b.x, b.y);
                if a.flash_until != 0 {
                    // éclaircit : voile blanc à 45 %
                    g.fill_round_rect_alpha(b.x, b.y, b.w, b.h, 10, COL_WHITE.c565(), 115);
                }
            }
            None => {
                let mut c = a.color;
                if a.flash_until != 0 {
                    c = Color(
                        255 - (255 - c.0) / 2,
                        255 - (255 - c.1) / 2,
                        255 - (255 - c.2) / 2,
                    );
                }
                g.fill_round_rect(b.x, b.y, b.w, b.h, 10, c.c565());
            }
        }
        g.text_centered(
            &fonts::FONT_TINY9,
            &a.name,
            b.x + b.w / 2,
            b.y + b.h + 12,
            COL_BLACK.c565(),
        );
    }

    fn draw_options(&self, g: &mut Gfx) {
        let o = self.options_btn;
        let bg = if self.options_flash != 0 {
            Color(210, 210, 210)
        } else {
            COL_BG
        };
        g.fill_rect(o.x, o.y, o.w, o.h, bg.c565());
        g.rect(o.x, o.y, o.w, o.h, COL_BLACK.c565());
        g.text_centered(
            &fonts::FONT_SMALL10,
            &self.options_label,
            o.x + o.w / 2,
            o.y + o.h / 2,
            COL_BLACK.c565(),
        );
    }

    fn draw_allapps(&self, g: &mut Gfx) {
        let a = self.allapps_btn;
        let fg = if self.allapps_flash != 0 {
            Color(120, 120, 120)
        } else {
            COL_BLACK
        };
        let (x, cy) = (a.x + 4, a.y + a.h / 2);
        g.fill_rect(a.x, a.y, a.w, a.h, COL_BG.c565());
        g.fill_triangle_up(x, cy - 3, 7, 7, fg.c565()); // 7 lignes = hauteur des capitales
        g.text_at_cy(
            &fonts::FONT_SMALL10,
            &self.allapps_label,
            x + 12,
            cy,
            fg.c565(),
        );
    }

    /// Affichage complet (repart d'un état propre, p. ex. au retour d'une appli).
    pub fn draw_all(&mut self, g: &mut Gfx) {
        for a in self.apps.iter_mut() {
            a.flash_until = 0;
        }
        self.options_flash = 0;
        self.allapps_flash = 0;
        g.clear(COL_BG.c565());
        self.draw_statusbar(g);
        self.draw_titlebar(g);
        for i in 0..self.apps.len() {
            self.draw_icon(g, i);
        }
        g.hline(4, SCREEN_W - 5, SCREEN_H - 26, COL_BORDER.c565());
        self.draw_options(g);
        self.draw_allapps(g);
    }

    /// Doigt posé en (x, y) à l'instant `now_ms`.
    pub fn touch_down(&mut self, g: &mut Gfx, x: i32, y: i32, now_ms: u32) {
        let mut until = now_ms.wrapping_add(FLASH_MS);
        if until == 0 {
            until = 1;
        }
        if let Some(i) = self.apps.iter().position(|a| a.cell.contains(x, y)) {
            self.apps[i].flash_until = until;
            self.draw_icon(g, i);
            self.pending = Some(HomeEvent::App(self.apps[i].id));
        } else if self.options_btn.contains(x, y) {
            self.options_flash = until;
            self.draw_options(g);
            self.pending = Some(HomeEvent::Options);
        } else if self.allapps_btn.contains(x, y) {
            self.allapps_flash = until;
            self.draw_allapps(g);
            self.pending = Some(HomeEvent::AllApps);
        }
    }

    /// Fin des flashs : redessine ce qui doit l'être.
    pub fn tick(&mut self, g: &mut Gfx, now_ms: u32) {
        for i in 0..self.apps.len() {
            if expired(self.apps[i].flash_until, now_ms) {
                self.apps[i].flash_until = 0;
                self.draw_icon(g, i);
            }
        }
        if expired(self.options_flash, now_ms) {
            self.options_flash = 0;
            self.draw_options(g);
        }
        if expired(self.allapps_flash, now_ms) {
            self.allapps_flash = 0;
            self.draw_allapps(g);
        }
    }

    /// Libellé affiché pour un élément de l'accueil (dans la langue courante).
    pub fn label(&self, ev: HomeEvent) -> &str {
        match ev {
            HomeEvent::App(id) => self
                .apps
                .iter()
                .find(|a| a.id == id)
                .map_or("", |a| a.name.as_str()),
            HomeEvent::Options => &self.options_label,
            HomeEvent::AllApps => &self.allapps_label,
        }
    }

    /// Élément touché depuis le dernier appel (consommé à la lecture).
    pub fn take_event(&mut self) -> Option<HomeEvent> {
        self.pending.take()
    }
}

/// Barre de titre des applis et zone tactile « Retour » (mêmes valeurs que python/appkit.py).
pub const HEADER_H: i32 = 30;
pub const BACK_ZONE: (i32, i32, i32, i32) = (0, 0, 84, HEADER_H);

/// Vrai si (x, y) est dans la zone « Retour » de la barre de titre.
pub fn in_back_zone(x: i32, y: i32) -> bool {
    let (bx, by, bw, bh) = BACK_ZONE;
    x >= bx && x < bx + bw && y >= by && y < by + bh
}

/// Écran provisoire d'une appli pas encore portée en Rust (barre de titre comme appkit.header()).
pub fn draw_not_ported(g: &mut Gfx, back: &str, title: &str, l1: &str, l2: &str) {
    let white = COL_WHITE.c565();
    g.clear(COL_BG.c565());
    g.fill_rect(0, 0, SCREEN_W, HEADER_H, COL_TITLEBAR.c565());
    g.text_at_cy(&fonts::FONT_SMALL10, back, 8, HEADER_H / 2, white);
    g.text_centered(
        &fonts::FONT_BOLD13,
        title,
        SCREEN_W / 2 + 22,
        HEADER_H / 2,
        white,
    );
    g.text_centered(&fonts::FONT_BOLD13, l1, SCREEN_W / 2, 140, COL_BLACK.c565());
    g.text_centered(
        &fonts::FONT_SMALL10,
        l2,
        SCREEN_W / 2,
        170,
        rgb565(150, 150, 150),
    );
}

/// Écran de chargement (`step` sur `total`).
pub fn draw_loading(g: &mut Gfx, label: &str, step: i32, total: i32) {
    let f = &fonts::FONT_SMALL10;
    g.clear(COL_BG.c565());
    g.text_centered(
        f,
        "Chargement...",
        SCREEN_W / 2,
        SCREEN_H / 2 - 20,
        COL_BLACK.c565(),
    );
    g.text_centered(f, label, SCREEN_W / 2, SCREEN_H / 2, COL_BLACK.c565());
    let (bar_w, bar_h, bar_x, bar_y) = (SCREEN_W - 60, 8, 30, SCREEN_H / 2 + 20);
    g.rect(bar_x, bar_y, bar_w, bar_h, COL_BLACK.c565());
    let fill_w = if total > 0 {
        (bar_w - 2) * step / total
    } else {
        0
    };
    if fill_w > 0 {
        g.fill_rect(bar_x + 1, bar_y + 1, fill_w, bar_h - 2, COL_TITLEBAR.c565());
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn labels_truncate_on_char_boundary() {
        let mut s: String<5> = String::new();
        set_label(&mut s, "ééé"); // 6 octets : le 3e « é » ne tient pas
        assert_eq!(s.as_str(), "éé");
    }

    #[test]
    fn labels_follow_translation() {
        let mut h = Home::new();
        assert_eq!(h.label(HomeEvent::App(AppId::Parametres)), "Paramètres");
        h.set_app_label(AppId::Parametres, "設定");
        h.set_options_label("オプション");
        assert_eq!(h.label(HomeEvent::App(AppId::Parametres)), "設定");
        assert_eq!(h.label(HomeEvent::Options), "オプション");
        assert_eq!(h.label(HomeEvent::AllApps), "Toutes les apps");
    }

    #[test]
    fn back_zone_bounds() {
        assert!(in_back_zone(0, 0) && in_back_zone(83, 29));
        assert!(!in_back_zone(84, 10) && !in_back_zone(10, 30) && !in_back_zone(-1, 5));
    }

    #[test]
    fn flash_deadline_wraps() {
        assert!(!expired(0, 123));
        assert!(expired(100, 100));
        assert!(!expired(100, 99));
        assert!(expired(5, 10) && !expired(u32::MAX - 5, 3u32.wrapping_sub(10)));
    }
}
