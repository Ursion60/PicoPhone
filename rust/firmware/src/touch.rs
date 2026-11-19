//! Tactile capacitif FT6336U en I2C (0x38), lecture par polling (port de phone/hal_rp2.c).

use embassy_rp::i2c::{Blocking, I2c};
use embassy_rp::peripherals::I2C0;
use picophone_gfx::{SCREEN_H, SCREEN_W};

const ADDR: u8 = 0x38;
// Ajustez si le doigt et l'affichage ne coïncident pas (TOUCH_SWAP_XY / FLIP_X / FLIP_Y de config.h).
const SWAP_XY: bool = false;
const FLIP_X: bool = false;
const FLIP_Y: bool = false;

pub struct Ft6336<'d> {
    i2c: I2c<'d, I2C0, Blocking>,
}

impl<'d> Ft6336<'d> {
    pub fn new(i2c: I2c<'d, I2C0, Blocking>) -> Self {
        Ft6336 { i2c }
    }

    /// Position du doigt, ou `None` s'il n'est pas posé (ou si le contrôleur ne répond pas).
    pub fn read(&mut self) -> Option<(i32, i32)> {
        let mut b = [0u8; 5]; // TD_STATUS, puis P1_XH, P1_XL, P1_YH, P1_YL
        self.i2c.blocking_write_read(ADDR, &[0x02], &mut b).ok()?;
        if b[0] & 0x0F == 0 {
            return None; // aucun point de contact
        }
        let mut x = (((b[1] & 0x0F) as i32) << 8) | b[2] as i32;
        let mut y = (((b[3] & 0x0F) as i32) << 8) | b[4] as i32;
        if SWAP_XY {
            core::mem::swap(&mut x, &mut y);
        }
        if FLIP_X {
            x = SCREEN_W - 1 - x;
        }
        if FLIP_Y {
            y = SCREEN_H - 1 - y;
        }
        Some((x.clamp(0, SCREEN_W - 1), y.clamp(0, SCREEN_H - 1)))
    }
}
