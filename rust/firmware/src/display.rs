//! Écran ILI9341 240x320 en SPI + DMA (port de phone/hal_rp2.c).
//!
//! Le SPI d'embassy-rp travaille en trames de 8 bits : chaque ligne de la zone sale est convertie en
//! octets (poids fort d'abord, ordre attendu par l'ILI9341) avant d'être envoyée en DMA.

use embassy_rp::gpio::Output;
use embassy_rp::peripherals::SPI0;
use embassy_rp::spi::{Async, Spi};
use embassy_time::Timer;
use picophone_gfx::{FB_LEN, Rect, SCREEN_W};

/// Orientation portrait (MX | BGR), comme LCD_MADCTL dans phone/config.h.
const MADCTL: u8 = 0x48;
/// Mettre à `true` si les couleurs sont inversées (LCD_INVERT).
const INVERT: bool = false;

pub struct Ili9341<'d> {
    spi: Spi<'d, SPI0, Async>,
    cs: Output<'d>,
    dc: Output<'d>,
    rst: Output<'d>,
    line: [u8; SCREEN_W as usize * 2],
}

impl<'d> Ili9341<'d> {
    pub fn new(spi: Spi<'d, SPI0, Async>, cs: Output<'d>, dc: Output<'d>, rst: Output<'d>) -> Self {
        Ili9341 {
            spi,
            cs,
            dc,
            rst,
            line: [0; SCREEN_W as usize * 2],
        }
    }

    async fn command(&mut self, cmd: u8, data: &[u8]) {
        self.dc.set_low();
        self.cs.set_low();
        let _ = self.spi.write(&[cmd]).await;
        self.cs.set_high();
        if !data.is_empty() {
            self.dc.set_high();
            self.cs.set_low();
            let _ = self.spi.write(data).await;
            self.cs.set_high();
        }
    }

    /// Réinitialisation matérielle puis séquence d'initialisation ILI9341 standard (identique au C).
    pub async fn init(&mut self) {
        self.cs.set_high();
        self.rst.set_high();
        Timer::after_millis(10).await;
        self.rst.set_low();
        Timer::after_millis(20).await;
        self.rst.set_high();
        Timer::after_millis(120).await;

        self.command(0xEF, &[0x03, 0x80, 0x02]).await;
        self.command(0xCF, &[0x00, 0xC1, 0x30]).await;
        self.command(0xED, &[0x64, 0x03, 0x12, 0x81]).await;
        self.command(0xE8, &[0x85, 0x00, 0x78]).await;
        self.command(0xCB, &[0x39, 0x2C, 0x00, 0x34, 0x02]).await;
        self.command(0xF7, &[0x20]).await;
        self.command(0xEA, &[0x00, 0x00]).await;
        self.command(0xC0, &[0x23]).await; // alimentation
        self.command(0xC1, &[0x10]).await;
        self.command(0xC5, &[0x3E, 0x28]).await; // VCOM
        self.command(0xC7, &[0x86]).await;
        self.command(0x36, &[MADCTL]).await;
        self.command(0x3A, &[0x55]).await; // 16 bits/pixel (RGB565)
        self.command(0xB1, &[0x00, 0x18]).await;
        self.command(0xB6, &[0x08, 0x82, 0x27]).await;
        self.command(0xF2, &[0x00]).await;
        self.command(0x26, &[0x01]).await;
        self.command(
            0xE0,
            &[
                0x0F, 0x31, 0x2B, 0x0C, 0x0E, 0x08, 0x4E, 0xF1, 0x37, 0x07, 0x10, 0x03, 0x0E, 0x09,
                0x00,
            ],
        )
        .await;
        self.command(
            0xE1,
            &[
                0x00, 0x0E, 0x14, 0x03, 0x11, 0x07, 0x31, 0xC1, 0x48, 0x08, 0x0F, 0x0C, 0x31, 0x36,
                0x0F,
            ],
        )
        .await;
        if INVERT {
            self.command(0x21, &[]).await;
        }
        self.command(0x11, &[]).await; // sortie de veille
        Timer::after_millis(120).await;
        self.command(0x29, &[]).await; // affichage ON
        Timer::after_millis(20).await;
    }

    /// Envoie la zone `r` (bornes incluses) du framebuffer.
    pub async fn flush(&mut self, fb: &[u16; FB_LEN], r: Rect) {
        let (x0, y0, x1, y1) = (r.x0 as u16, r.y0 as u16, r.x1 as u16, r.y1 as u16);
        self.command(
            0x2A,
            &[(x0 >> 8) as u8, x0 as u8, (x1 >> 8) as u8, x1 as u8],
        )
        .await;
        self.command(
            0x2B,
            &[(y0 >> 8) as u8, y0 as u8, (y1 >> 8) as u8, y1 as u8],
        )
        .await;
        self.command(0x2C, &[]).await; // RAMWR : les pixels suivent
        let w = (r.x1 - r.x0 + 1) as usize;
        self.dc.set_high();
        self.cs.set_low();
        for y in r.y0..=r.y1 {
            let start = (y * SCREEN_W + r.x0) as usize;
            for (i, px) in fb[start..start + w].iter().enumerate() {
                self.line[2 * i] = (px >> 8) as u8;
                self.line[2 * i + 1] = *px as u8;
            }
            let _ = self.spi.write(&self.line[..2 * w]).await;
        }
        self.cs.set_high();
    }
}
