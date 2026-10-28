/*
 * hal : tout ce qui touche au matériel (ou à la fenêtre du simulateur).
 * Deux implémentations, choisies par le build :
 *   hal_rp2.c : Waveshare Core2350B -> écran ILI9341 (SPI+DMA) + tactile FT6336U (I2C)
 *   hal_sdl.c : PC (MicroPython "unix") -> fenêtre SDL2, souris = doigt
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>

/* Placement du framebuffer de gfx.c (150 Ko). Par défaut en SRAM. Avec -DPHONE_FB_IN_PSRAM (firmware
 * uniquement, voir micropython.cmake et tools/build_firmware.sh) il va en PSRAM : 150 Ko de SRAM de plus
 * pour le tas MicroPython. Expérimental : non testé sur la carte. */
#ifdef PHONE_FB_IN_PSRAM
#include "pico.h"
#define HAL_FB_ATTR __uninitialized_psram("phone_fb")
#else
#define HAL_FB_ATTR
#endif

void hal_init(void);
bool hal_fb_ready(void);                                            /* false : PSRAM demandée mais absente */
void hal_backlight(uint8_t level);                                  /* 0-255                        */
void hal_flush(const uint16_t *fb, int x0, int y0, int x1, int y1); /* zone [x0..x1]x[y0..y1] incluse */
bool hal_touch(int *x, int *y);                                     /* true = doigt posé            */

#ifdef PHONE_SIM   /* uniquement dans le simulateur PC : tests automatisés et captures d'écran */
void hal_sim_touch(int x, int y, bool down);
bool hal_sim_screenshot(const char *path, const uint16_t *fb);
#endif
