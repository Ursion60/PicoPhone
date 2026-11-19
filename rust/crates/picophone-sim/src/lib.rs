//! Simulateur PC : un framebuffer en mémoire et l'export de captures PPM.

use picophone_gfx::{FB_LEN, SCREEN_H, SCREEN_W};

/// Capture PPM (P6) : même conversion RGB565 -> RGB888 que le simulateur C (phone/hal_sdl.c).
pub fn to_ppm(fb: &[u16; FB_LEN]) -> Vec<u8> {
    let mut out = format!("P6\n{SCREEN_W} {SCREEN_H}\n255\n").into_bytes();
    out.reserve(FB_LEN * 3);
    for &p in fb.iter() {
        out.extend_from_slice(&[
            ((p >> 11) << 3) as u8,
            (((p >> 5) & 0x3F) << 2) as u8,
            ((p & 0x1F) << 3) as u8,
        ]);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ppm_header_and_colors() {
        let mut fb = [0u16; FB_LEN];
        fb[0] = 0xFFFF;
        fb[1] = 0xF800;
        let ppm = to_ppm(&fb);
        let header = b"P6\n240 320\n255\n";
        assert_eq!(&ppm[..header.len()], header);
        assert_eq!(ppm.len(), header.len() + FB_LEN * 3);
        assert_eq!(
            &ppm[header.len()..header.len() + 6],
            &[248, 252, 248, 248, 0, 0]
        );
    }
}
