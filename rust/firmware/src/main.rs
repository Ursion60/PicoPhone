//! PicoPhone (Rust) pour la Waveshare Core2350B (RP2350B) : écran ILI9341 (SPI0 + DMA), tactile
//! FT6336U (I2C0), écran d'accueil. Les applis seront portées une à une ; en attendant, toucher une
//! icône ouvre un écran provisoire avec « Retour ».
//! Broches : celles de phone/config.h (à adapter à votre câblage).
#![no_std]
#![no_main]

mod display;
mod touch;

use display::Ili9341;
use embassy_executor::Spawner;
use embassy_rp::gpio::{Input, Level, Output, Pull};
use embassy_rp::peripherals::DMA_CH0;
use embassy_rp::pwm::{self, Pwm};
use embassy_rp::{bind_interrupts, i2c, spi};
use embassy_time::{Instant, Timer};
use panic_halt as _;
use picophone_gfx::{FB_LEN, Gfx};
use picophone_ui::{HomeEvent, draw_loading, draw_not_ported, in_back_zone};
use static_cell::ConstStaticCell;
use touch::Ft6336;

bind_interrupts!(struct Irqs {
    DMA_IRQ_0 => embassy_rp::dma::InterruptHandler<DMA_CH0>;
});

#[unsafe(link_section = ".bi_entries")]
#[used]
pub static PICOTOOL_ENTRIES: [embassy_rp::binary_info::EntryAddr; 4] = [
    embassy_rp::binary_info::rp_program_name!(c"PicoPhone"),
    embassy_rp::binary_info::rp_program_description!(c"PicoPhone (Rust) pour Waveshare Core2350B"),
    embassy_rp::binary_info::rp_cargo_version!(),
    embassy_rp::binary_info::rp_program_build_attribute!(),
];

/// Framebuffer de 150 Ko en mémoire statique (jamais copié sur la pile).
static FB: ConstStaticCell<[u16; FB_LEN]> = ConstStaticCell::new([0; FB_LEN]);

const LCD_SPI_HZ: u32 = 40_000_000; // baissez à 20 MHz si fils longs / artefacts
const TOUCH_I2C_HZ: u32 = 400_000;

fn now_ms() -> u32 {
    Instant::now().as_millis() as u32
}

async fn flush(gfx: &mut Gfx<'_>, lcd: &mut Ili9341<'_>) {
    if let Some(r) = gfx.take_dirty() {
        lcd.flush(gfx.framebuffer(), r).await;
    }
}

#[embassy_executor::main]
async fn main(_spawner: Spawner) {
    let p = embassy_rp::init(Default::default());

    // Rétroéclairage (PWM, éteint pendant l'initialisation)
    let mut bl_cfg = pwm::Config::default();
    bl_cfg.top = 255;
    bl_cfg.compare_a = 0;
    let mut backlight = Pwm::new_output_a(p.PWM_SLICE3, p.PIN_22, bl_cfg.clone());

    // Écran
    let mut spi_cfg = spi::Config::default();
    spi_cfg.frequency = LCD_SPI_HZ;
    let spi = spi::Spi::new_txonly(p.SPI0, p.PIN_18, p.PIN_19, p.DMA_CH0, Irqs, spi_cfg);
    let mut lcd = Ili9341::new(
        spi,
        Output::new(p.PIN_17, Level::High),
        Output::new(p.PIN_20, Level::Low),
        Output::new(p.PIN_21, Level::High),
    );
    lcd.init().await;

    // Tactile : réinitialisation puis I2C
    let _touch_int = Input::new(p.PIN_7, Pull::Up); // lu en entrée ; inutilisé en mode polling
    let mut touch_rst = Output::new(p.PIN_6, Level::High);
    Timer::after_millis(5).await;
    touch_rst.set_low();
    Timer::after_millis(10).await;
    touch_rst.set_high();
    Timer::after_millis(60).await;
    let mut i2c_cfg = i2c::Config::default();
    i2c_cfg.frequency = TOUCH_I2C_HZ;
    let mut touch = Ft6336::new(i2c::I2c::new_blocking(p.I2C0, p.PIN_5, p.PIN_4, i2c_cfg));

    let mut gfx = Gfx::new(FB.take());
    draw_loading(&mut gfx, "Démarrage", 1, 2);
    flush(&mut gfx, &mut lcd).await;
    bl_cfg.compare_a = 255;
    backlight.set_config(&bl_cfg);
    Timer::after_millis(150).await;

    let mut home = picophone_ui::Home::new();
    home.draw_all(&mut gfx);
    let mut open: Option<HomeEvent> = None; // appli « ouverte » (écran provisoire)
    let mut was_down = false;

    loop {
        let pos = touch.read();
        let tap = if was_down { None } else { pos }; // seulement au moment où le doigt se pose
        was_down = pos.is_some();
        let now = now_ms();

        match open {
            None => {
                if let Some((x, y)) = tap {
                    home.touch_down(&mut gfx, x, y, now);
                }
                home.tick(&mut gfx, now);
                if let Some(ev) = home.take_event() {
                    flush(&mut gfx, &mut lcd).await;
                    Timer::after_millis(120).await; // laisse voir l'icône s'allumer
                    draw_not_ported(
                        &mut gfx,
                        "« Retour",
                        home.label(ev),
                        "Pas encore portée en Rust",
                        ev.as_str(),
                    );
                    open = Some(ev);
                }
            }
            Some(_) => {
                if let Some((x, y)) = tap
                    && in_back_zone(x, y)
                {
                    home.draw_all(&mut gfx);
                    open = None;
                }
            }
        }
        flush(&mut gfx, &mut lcd).await;
        Timer::after_millis(10).await;
    }
}
