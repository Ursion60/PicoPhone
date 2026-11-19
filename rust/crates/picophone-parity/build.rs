// Compile le moteur C historique (sans HAL ni MicroPython) pour le comparer au port Rust.
fn main() {
    let phone = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../phone");
    let files = ["gfx.c", "ui.c", "font.c", "font_data.c", "icons_data.c"];
    let mut b = cc::Build::new();
    b.include(&phone).warnings(false).opt_level(2);
    for f in files {
        let p = phone.join(f);
        println!("cargo:rerun-if-changed={}", p.display());
        b.file(p);
    }
    for h in ["gfx.h", "ui.h", "font.h", "icons.h", "hal.h"] {
        println!("cargo:rerun-if-changed={}", phone.join(h).display());
    }
    b.compile("phone_c");
}
