//! picophone-sim [DOSSIER] : rend les écrans de base et écrit des captures PPM dans DOSSIER
//! (défaut : dossier courant). Le simulateur avec fenêtre viendra à l'étape suivante.

use std::path::PathBuf;

use picophone_gfx::{FB_LEN, Gfx};
use picophone_sim::to_ppm;
use picophone_ui::{AppId, Home, draw_loading, draw_not_ported};

fn save(gfx: &Gfx, dir: &std::path::Path, name: &str) -> std::io::Result<()> {
    let path = dir.join(format!("{name}.ppm"));
    std::fs::write(&path, to_ppm(gfx.framebuffer()))?;
    println!("{}", path.display());
    Ok(())
}

fn main() -> std::io::Result<()> {
    let dir = PathBuf::from(std::env::args().nth(1).unwrap_or_else(|| ".".into()));
    std::fs::create_dir_all(&dir)?;
    let mut fb = Box::new([0u16; FB_LEN]);
    let mut gfx = Gfx::new(&mut fb);

    draw_loading(&mut gfx, "Démarrage", 1, 2);
    save(&gfx, &dir, "rs_loading")?;

    let mut home = Home::new();
    home.draw_all(&mut gfx);
    save(&gfx, &dir, "rs_home_fr")?;

    home.touch_down(&mut gfx, 40, 60, 1000); // icône EDT : flash
    println!("événement : {:?}", home.take_event().map(|e| e.as_str()));
    save(&gfx, &dir, "rs_home_tap_edt")?;

    home.set_title("ホーム");
    home.set_options_label("オプション");
    home.set_allapps_label("すべてのアプリ");
    for (id, s) in AppId::ALL.iter().zip([
        "時間割",
        "メモ",
        "NFC",
        "ショップ",
        "同期",
        "設定",
        "音楽",
        "PDFリーダー",
    ]) {
        home.set_app_label(*id, s);
    }
    home.draw_all(&mut gfx);
    save(&gfx, &dir, "rs_home_jp")?;

    draw_not_ported(
        &mut gfx,
        "« Retour",
        "EDT",
        "Pas encore portée en Rust",
        "edt",
    );
    save(&gfx, &dir, "rs_not_ported")?;
    Ok(())
}
