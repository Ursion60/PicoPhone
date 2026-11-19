//! Parité pixel pour pixel entre le moteur C historique (phone/*.c) et le port Rust.
//! Après chaque opération : mêmes framebuffers et mêmes zones sales. Les scènes aléatoires utilisent
//! une graine fixe : un échec se reproduit à l'identique.

use std::ffi::{CStr, CString, c_char};
use std::sync::Mutex;

use picophone_gfx::{FB_LEN, Font, Gfx, Icon, Rect, SCREEN_W, fonts, icons};
use picophone_parity as c;
use picophone_ui::{AppId, Home, draw_loading};

/// Le moteur C a un état global (framebuffer, accueil) : un seul test à la fois.
static C_LOCK: Mutex<()> = Mutex::new(());

fn c_framebuffer() -> &'static [u16] {
    unsafe { std::slice::from_raw_parts(c::gfx_framebuffer(), FB_LEN) }
}

fn c_dirty() -> Option<Rect> {
    let mut r = c::GfxRect {
        x0: 0,
        y0: 0,
        x1: 0,
        y1: 0,
    };
    unsafe { c::gfx_take_dirty(&mut r) }.then_some(Rect {
        x0: r.x0,
        y0: r.y0,
        x1: r.x1,
        y1: r.y1,
    })
}

#[track_caller]
fn assert_same(rust: &Gfx, what: &str) {
    let (a, b) = (rust.framebuffer(), c_framebuffer());
    if a[..] != b[..] {
        let diffs = a.iter().zip(b).filter(|(x, y)| x != y).count();
        let first = a.iter().zip(b).position(|(x, y)| x != y).unwrap();
        panic!(
            "{what} : {diffs} pixel(s) différents, le 1er en ({}, {}) : rust={:#06x} c={:#06x}",
            first as i32 % SCREEN_W,
            first as i32 / SCREEN_W,
            a[first],
            b[first]
        );
    }
}

#[track_caller]
fn assert_same_dirty(rust: &mut Gfx, what: &str) {
    assert_eq!(
        rust.take_dirty(),
        c_dirty(),
        "zone sale différente après {what}"
    );
}

fn cstr(s: &str) -> CString {
    CString::new(s).unwrap()
}

/// Générateur pseudo-aléatoire minimal (xorshift32) : graine fixe, aucune dépendance.
struct Rng(u32);
impl Rng {
    fn next(&mut self) -> u32 {
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        self.0 = x;
        x
    }
    fn range(&mut self, lo: i32, hi: i32) -> i32 {
        lo + (self.next() % (hi - lo + 1) as u32) as i32
    }
    fn pick<'a, T>(&mut self, items: &'a [T]) -> &'a T {
        &items[self.next() as usize % items.len()]
    }
}

fn fonts_both() -> [(&'static Font, *const c::CFont); 3] {
    [
        (&fonts::FONT_BOLD13, &raw const c::font_bold13),
        (&fonts::FONT_SMALL10, &raw const c::font_small10),
        (&fonts::FONT_TINY9, &raw const c::font_tiny9),
    ]
}

fn icons_both() -> [(&'static Icon, *const c::CIcon); 8] {
    [
        (&icons::ICON_EDT, &raw const c::icon_edt),
        (&icons::ICON_NOTES, &raw const c::icon_notes),
        (&icons::ICON_NFC, &raw const c::icon_nfc),
        (&icons::ICON_SHOP, &raw const c::icon_shop),
        (&icons::ICON_SYNCHRO, &raw const c::icon_synchro),
        (&icons::ICON_PARAMETRES, &raw const c::icon_parametres),
        (&icons::ICON_MUSIQUE, &raw const c::icon_musique),
        (&icons::ICON_LECTEUR_PDF, &raw const c::icon_lecteur_pdf),
    ]
}

/// Textes : ASCII, accents Latin-1, CJK de l'interface, caractères absents de la police (-> « ? »).
const TEXTS: &[&str] = &[
    "Bonjour",
    "Paramètres Français ÉèêëàâçÇ ñ ü ß",
    "Wed Oct 28 - 08:00",
    "10月28日(水) 時間割 课程表 同步",
    "Ω ≠ → ☃ 한국",
    "",
    "W",
    "¡¿«»±×÷°",
];

#[test]
fn primitives_random_scene() {
    let _g = C_LOCK.lock().unwrap();
    let mut fb = Box::new([0u16; FB_LEN]);
    let mut r = Gfx::new(&mut fb);
    unsafe {
        c::gfx_init();
        c::gfx_clear(0);
    }
    r.clear(0);
    assert_same_dirty(&mut r, "clear");
    assert_same(&r, "clear");

    let fonts = fonts_both();
    let icons = icons_both();
    let mut rng = Rng(0x1234_5678);
    for step in 0..4000 {
        let x = rng.range(-300, 540);
        let y = rng.range(-300, 620);
        let w = rng.range(-20, 300);
        let h = rng.range(-20, 300);
        let col = rng.next() as u16;
        let op = rng.range(0, 11);
        let what = format!("étape {step}, op {op}, ({x},{y},{w},{h})");
        unsafe {
            match op {
                0 => {
                    r.fill_rect(x, y, w, h, col);
                    c::gfx_fill_rect(x, y, w, h, col);
                }
                1 => {
                    r.rect(x, y, w, h, col);
                    c::gfx_rect(x, y, w, h, col);
                }
                2 => {
                    r.hline(x, x + w, y, col);
                    c::gfx_hline(x, x + w, y, col);
                }
                3 => {
                    let rad = rng.range(-5, 90);
                    r.fill_circle(x, y, rad, col);
                    c::gfx_fill_circle(x, y, rad, col);
                }
                4 => {
                    let rad = rng.range(-5, 80);
                    r.fill_round_rect(x, y, w, h, rad, col);
                    c::gfx_fill_round_rect(x, y, w, h, rad, col);
                }
                5 => {
                    let rad = rng.range(-5, 80);
                    let a = *rng.pick(&[0u8, 1, 4, 115, 128, 200, 254, 255]);
                    r.fill_round_rect_alpha(x, y, w, h, rad, col, a);
                    c::gfx_fill_round_rect_alpha(x, y, w, h, rad, col, a);
                }
                6 => {
                    let (ri, ci) = *rng.pick(&icons);
                    let (ix, iy) = (rng.range(-60, 250), rng.range(-60, 330));
                    r.blit(ri, ix, iy);
                    c::gfx_blit(ci, ix, iy);
                }
                7 => {
                    let (tw, th) = (rng.range(0, 40), rng.range(1, 40));
                    r.fill_triangle_up(x, y, tw, th, col);
                    c::gfx_fill_triangle_up(x, y, tw, th, col);
                }
                8..=10 => {
                    let (rf, cf) = *rng.pick(&fonts);
                    let s = *rng.pick(TEXTS);
                    let cs = cstr(s);
                    let (tx, ty) = (rng.range(-80, 260), rng.range(-30, 340));
                    assert_eq!(
                        rf.text_width(s),
                        c::gfx_text_width(cf, cs.as_ptr()),
                        "largeur de {s:?}"
                    );
                    match op {
                        8 => {
                            r.text(rf, s, tx, ty, col);
                            c::gfx_text(cf, cs.as_ptr(), tx, ty, col);
                        }
                        9 => {
                            r.text_at_cy(rf, s, tx, ty, col);
                            c::gfx_text_at_cy(cf, cs.as_ptr(), tx, ty, col);
                        }
                        _ => {
                            r.text_centered(rf, s, tx, ty, col);
                            c::gfx_text_centered(cf, cs.as_ptr(), tx, ty, col);
                        }
                    }
                }
                _ => {
                    r.clear(col);
                    c::gfx_clear(col);
                }
            }
        }
        assert_same_dirty(&mut r, &what);
        assert_same(&r, &what);
    }
}

fn take_c_event() -> Option<String> {
    let p = unsafe { c::ui_take_event() };
    (!p.is_null()).then(|| {
        unsafe { CStr::from_ptr(p as *const c_char) }
            .to_str()
            .unwrap()
            .to_owned()
    })
}

struct Labels<'a> {
    title: &'a str,
    options: &'a str,
    allapps: &'a str,
    apps: [&'a str; 8],
}

const FR: Labels = Labels {
    title: "Accueil",
    options: "Options",
    allapps: "Toutes les apps",
    apps: [
        "EDT",
        "Notes",
        "NFC",
        "Shop",
        "Synchro",
        "Paramètres",
        "Musique",
        "Lecteur PDF",
    ],
};
const JP: Labels = Labels {
    title: "ホーム",
    options: "オプション",
    allapps: "すべてのアプリ",
    apps: [
        "時間割",
        "メモ",
        "NFC",
        "ショップ",
        "同期",
        "設定",
        "音楽",
        "PDFリーダー",
    ],
};
const CN: Labels = Labels {
    title: "主屏幕",
    options: "选项",
    allapps: "所有应用",
    apps: [
        "课程表",
        "笔记",
        "NFC",
        "商店",
        "同步",
        "设置",
        "音乐",
        "PDF阅读器",
    ],
};
const DE: Labels = Labels {
    title: "Start",
    options: "Optionen",
    allapps: "Alle Apps",
    apps: [
        "Stundenplan",
        "Notizen",
        "NFC",
        "Shop",
        "Synchro",
        "Einstellungen",
        "Musik",
        "PDF-Leser",
    ],
};

fn set_labels(home: &mut Home, l: &Labels) {
    home.set_title(l.title);
    home.set_options_label(l.options);
    home.set_allapps_label(l.allapps);
    for (id, s) in AppId::ALL.iter().zip(l.apps) {
        home.set_app_label(*id, s);
    }
    unsafe {
        c::ui_set_home_title(cstr(l.title).as_ptr());
        c::ui_set_options_label(cstr(l.options).as_ptr());
        c::ui_set_allapps_label(cstr(l.allapps).as_ptr());
        for (id, s) in AppId::ALL.iter().zip(l.apps) {
            c::ui_set_app_label(cstr(id.as_str()).as_ptr(), cstr(s).as_ptr());
        }
    }
}

#[test]
fn home_screen_all_languages_taps_and_flashes() {
    let _g = C_LOCK.lock().unwrap();
    let mut fb = Box::new([0u16; FB_LEN]);
    let mut r = Gfx::new(&mut fb);
    unsafe {
        c::gfx_init();
        c::gfx_clear(0);
        c::gfx_take_dirty(&mut c::GfxRect {
            x0: 0,
            y0: 0,
            x1: 0,
            y1: 0,
        });
    }
    r.clear(0);
    r.take_dirty();

    // Écran de chargement (étapes 0, 1, 2 sur 2, et total nul)
    for (label, step, total) in [
        ("Démarrage", 0, 2),
        ("Démarrage", 1, 2),
        ("Prêt", 2, 2),
        ("x", 1, 0),
    ] {
        draw_loading(&mut r, label, step, total);
        unsafe { c::ui_draw_loading(cstr(label).as_ptr(), step, total) };
        assert_same_dirty(&mut r, "chargement");
        assert_same(&r, &format!("chargement {label} {step}/{total}"));
    }

    for (lang, labels) in [("FR", &FR), ("JP", &JP), ("CN", &CN), ("AL", &DE)] {
        let mut home = Home::new();
        unsafe { c::ui_init() };
        set_labels(&mut home, labels);
        home.draw_all(&mut r);
        unsafe { c::ui_draw_all() };
        assert_same_dirty(&mut r, "accueil");
        assert_same(&r, &format!("accueil {lang}"));

        // Taps : chaque icône, Options, Toutes les apps, et des zones vides ; puis fin des flashs.
        let mut now = 1000u32;
        let mut points: Vec<(i32, i32)> =
            vec![(14, 302), (200, 302), (120, 10), (5, 100), (239, 319)];
        for row_y in [46, 128, 210] {
            for x in (0..SCREEN_W).step_by(8) {
                points.push((x, row_y + 10));
            }
        }
        for (x, y) in points {
            home.touch_down(&mut r, x, y, now);
            unsafe { c::ui_touch_down(x, y, now) };
            let ev = home.take_event().map(|e| e.as_str().to_owned());
            assert_eq!(ev, take_c_event(), "événement du tap ({x},{y}) {lang}");
            assert_same_dirty(&mut r, "tap");
            assert_same(&r, &format!("tap ({x},{y}) {lang}"));
            for t in [now + 159, now + 160, now + 500] {
                home.tick(&mut r, t);
                unsafe { c::ui_tick(t) };
                assert_same_dirty(&mut r, "tick");
                assert_same(&r, &format!("tick {t} après ({x},{y}) {lang}"));
            }
            now += 1000;
        }
        // Échéance qui passe par 0 (débordement de l'horloge 32 bits)
        let wrap = u32::MAX - 100;
        home.touch_down(&mut r, 30, 60, wrap);
        unsafe { c::ui_touch_down(30, 60, wrap) };
        assert_eq!(
            home.take_event().map(|e| e.as_str().to_owned()),
            take_c_event()
        );
        for t in [wrap.wrapping_add(59), wrap.wrapping_add(60), 200] {
            home.tick(&mut r, t);
            unsafe { c::ui_tick(t) };
            assert_same_dirty(&mut r, "tick (débordement)");
            assert_same(&r, &format!("tick {t} (débordement) {lang}"));
        }
    }
}
