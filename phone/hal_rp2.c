/*
 * HAL Waveshare Core2350B : écran ILI9341 en SPI + DMA, tactile FT6336U en I2C.
 *
 * Astuce : le PL022 du RP2350 sait faire du 16 bits, MSB en premier. Un pixel
 * RGB565 stocké en uint16_t part donc dans le bon ordre (octet fort d'abord)
 * sans aucune conversion, et le DMA alimente le SPI sans occuper le CPU.
 *
 * Attention : ce module s'approprie spi0 et i2c0 (voir config.h). N'utilisez pas
 * machine.SPI(0) / machine.I2C(0) dans vos scripts, ou changez les broches/bus.
 */
#include "hal.h"
#include "config.h"
#include "gfx.h"
#include "hardware/dma.h"
#ifdef PHONE_FB_IN_PSRAM
#include "hardware/psram.h"
#endif
#include "hardware/gpio.h"
#include "hardware/pwm.h"
#include "pico/stdlib.h"

static int dma_ch;

static inline void cs_low(void)  { gpio_put(LCD_PIN_CS, 0); }
static inline void cs_high(void) { gpio_put(LCD_PIN_CS, 1); }

static inline void spi_wait_idle(void) {
    while (spi_get_hw(LCD_SPI)->sr & SPI_SSPSR_BSY_BITS) tight_loop_contents();
}

static void write_cmd(uint8_t cmd) {
    gpio_put(LCD_PIN_DC, 0);
    cs_low();
    spi_write_blocking(LCD_SPI, &cmd, 1);
    cs_high();
}

static void write_data(const uint8_t *d, size_t n) {
    gpio_put(LCD_PIN_DC, 1);
    cs_low();
    spi_write_blocking(LCD_SPI, d, n);
    cs_high();
}

static void cmd(uint8_t c, const uint8_t *d, size_t n) {
    write_cmd(c);
    if (n) write_data(d, n);
}

#define CMD(c, ...) do { const uint8_t d_[] = { __VA_ARGS__ }; cmd((c), d_, sizeof d_); } while (0)

void hal_backlight(uint8_t level) {
    pwm_set_gpio_level(LCD_PIN_BL, level);
}

static void lcd_init(void) {
    spi_init(LCD_SPI, LCD_SPI_HZ);
    spi_set_format(LCD_SPI, 8, SPI_CPOL_0, SPI_CPHA_0, SPI_MSB_FIRST);
    gpio_set_function(LCD_PIN_SCK,  GPIO_FUNC_SPI);
    gpio_set_function(LCD_PIN_MOSI, GPIO_FUNC_SPI);

    gpio_init(LCD_PIN_CS);  gpio_set_dir(LCD_PIN_CS,  GPIO_OUT); gpio_put(LCD_PIN_CS, 1);
    gpio_init(LCD_PIN_DC);  gpio_set_dir(LCD_PIN_DC,  GPIO_OUT);
    gpio_init(LCD_PIN_RST); gpio_set_dir(LCD_PIN_RST, GPIO_OUT);

    gpio_set_function(LCD_PIN_BL, GPIO_FUNC_PWM);
    uint slice = pwm_gpio_to_slice_num(LCD_PIN_BL);
    pwm_set_wrap(slice, 255);
    pwm_set_enabled(slice, true);
    hal_backlight(0);                       /* écran éteint pendant l'init */

    dma_ch = dma_claim_unused_channel(true);

    gpio_put(LCD_PIN_RST, 1); sleep_ms(10);
    gpio_put(LCD_PIN_RST, 0); sleep_ms(20);
    gpio_put(LCD_PIN_RST, 1); sleep_ms(120);

    /* Séquence d'initialisation ILI9341 standard */
    CMD(0xEF, 0x03, 0x80, 0x02);
    CMD(0xCF, 0x00, 0xC1, 0x30);
    CMD(0xED, 0x64, 0x03, 0x12, 0x81);
    CMD(0xE8, 0x85, 0x00, 0x78);
    CMD(0xCB, 0x39, 0x2C, 0x00, 0x34, 0x02);
    CMD(0xF7, 0x20);
    CMD(0xEA, 0x00, 0x00);
    CMD(0xC0, 0x23);                            /* alimentation */
    CMD(0xC1, 0x10);
    CMD(0xC5, 0x3E, 0x28);                      /* VCOM */
    CMD(0xC7, 0x86);
    CMD(0x36, LCD_MADCTL);
    CMD(0x3A, 0x55);                            /* 16 bits/pixel (RGB565) */
    CMD(0xB1, 0x00, 0x18);
    CMD(0xB6, 0x08, 0x82, 0x27);
    CMD(0xF2, 0x00);
    CMD(0x26, 0x01);
    CMD(0xE0, 0x0F, 0x31, 0x2B, 0x0C, 0x0E, 0x08, 0x4E, 0xF1, 0x37, 0x07, 0x10, 0x03, 0x0E, 0x09, 0x00);
    CMD(0xE1, 0x00, 0x0E, 0x14, 0x03, 0x11, 0x07, 0x31, 0xC1, 0x48, 0x08, 0x0F, 0x0C, 0x31, 0x36, 0x0F);
#if LCD_INVERT
    write_cmd(0x21);
#endif
    write_cmd(0x11); sleep_ms(120);             /* sortie de veille */
    write_cmd(0x29); sleep_ms(20);              /* affichage ON     */
}

static void set_window(int x0, int y0, int x1, int y1) {
    CMD(0x2A, x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF);
    CMD(0x2B, y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF);
    write_cmd(0x2C);                            /* RAMWR : les pixels suivent */
}

bool hal_fb_ready(void) {
#ifdef PHONE_FB_IN_PSRAM
    return psram_is_available();
#else
    return true;
#endif
}

static void dma_write16(const uint16_t *src, uint32_t count) {
    dma_channel_config c = dma_channel_get_default_config(dma_ch);
    channel_config_set_transfer_data_size(&c, DMA_SIZE_16);
    channel_config_set_dreq(&c, spi_get_dreq(LCD_SPI, true));
    channel_config_set_read_increment(&c, true);
    channel_config_set_write_increment(&c, false);
    dma_channel_configure(dma_ch, &c, &spi_get_hw(LCD_SPI)->dr, src, count, true);
    dma_channel_wait_for_finish_blocking(dma_ch);
    spi_wait_idle();
}

void hal_flush(const uint16_t *fb, int x0, int y0, int x1, int y1) {
    set_window(x0, y0, x1, y1);
    int w = x1 - x0 + 1;

    gpio_put(LCD_PIN_DC, 1);
    cs_low();
    spi_set_format(LCD_SPI, 16, SPI_CPOL_0, SPI_CPHA_0, SPI_MSB_FIRST);
    if (w == SCREEN_W) {
        /* Bande pleine largeur : mémoire contiguë -> UN seul transfert DMA */
        dma_write16(fb + y0 * SCREEN_W, (uint32_t)w * (y1 - y0 + 1));
    } else {
        for (int y = y0; y <= y1; y++) dma_write16(fb + y * SCREEN_W + x0, (uint32_t)w);
    }
    spi_set_format(LCD_SPI, 8, SPI_CPOL_0, SPI_CPHA_0, SPI_MSB_FIRST);
    cs_high();
}

/* ---------- Tactile FT6336U (I2C 0x38), lecture par polling ---------- */

static void touch_init(void) {
    i2c_init(TOUCH_I2C, TOUCH_I2C_HZ);
    gpio_set_function(TOUCH_PIN_SDA, GPIO_FUNC_I2C);
    gpio_set_function(TOUCH_PIN_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(TOUCH_PIN_SDA);
    gpio_pull_up(TOUCH_PIN_SCL);

    gpio_init(TOUCH_PIN_INT); gpio_set_dir(TOUCH_PIN_INT, GPIO_IN); gpio_pull_up(TOUCH_PIN_INT);

    gpio_init(TOUCH_PIN_RST); gpio_set_dir(TOUCH_PIN_RST, GPIO_OUT);
    gpio_put(TOUCH_PIN_RST, 1); sleep_ms(5);
    gpio_put(TOUCH_PIN_RST, 0); sleep_ms(10);
    gpio_put(TOUCH_PIN_RST, 1); sleep_ms(60);
}

bool hal_touch(int *x, int *y) {
    uint8_t reg = 0x02;                  /* TD_STATUS, puis P1_XH, P1_XL, P1_YH, P1_YL */
    uint8_t b[5];
    if (i2c_write_timeout_us(TOUCH_I2C, TOUCH_ADDR, &reg, 1, true, 2000) != 1) return false;
    if (i2c_read_timeout_us(TOUCH_I2C, TOUCH_ADDR, b, sizeof b, false, 2000) != (int)sizeof b) return false;
    if ((b[0] & 0x0F) == 0) return false;          /* aucun point de contact */

    int rx = ((b[1] & 0x0F) << 8) | b[2];
    int ry = ((b[3] & 0x0F) << 8) | b[4];
#if TOUCH_SWAP_XY
    { int t = rx; rx = ry; ry = t; }
#endif
#if TOUCH_FLIP_X
    rx = SCREEN_W - 1 - rx;
#endif
#if TOUCH_FLIP_Y
    ry = SCREEN_H - 1 - ry;
#endif
    if (rx < 0) rx = 0; else if (rx >= SCREEN_W) rx = SCREEN_W - 1;
    if (ry < 0) ry = 0; else if (ry >= SCREEN_H) ry = SCREEN_H - 1;
    *x = rx; *y = ry;
    return true;
}

void hal_init(void) {
    lcd_init();
    touch_init();
}
