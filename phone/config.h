/*
 * Câblage et réglages matériels (firmware Pico 2 uniquement) - à adapter à VOTRE montage.
 *
 * Carte : Waveshare Core2350B = carte MicroPython WAVESHARE_RP2350B_CORE (RP2350B, 48 GPIO,
 * PSRAM sur GPIO 47, LED sur GPIO 39). Les broches ci-dessous sont des propositions libres
 * (SPI0 / I2C0 par défaut de la carte) : changez-les selon votre câblage.
 * Évitez : GPIO 47 (PSRAM), 39 (LED), 0/1 (UART0).
 */
#pragma once
#include "hardware/i2c.h"
#include "hardware/spi.h"

/* ---------- Écran (hypothèse : ILI9341, SPI, 240x320) ---------- */
#define LCD_SPI        spi0
#define LCD_SPI_HZ     (40 * 1000 * 1000)   /* baissez à 20 MHz si fils longs / artefacts */
#define LCD_PIN_SCK    18
#define LCD_PIN_MOSI   19
#define LCD_PIN_CS     17
#define LCD_PIN_DC     20
#define LCD_PIN_RST    21
#define LCD_PIN_BL     22                   /* rétroéclairage, piloté en PWM              */
#define LCD_MADCTL     0x48                 /* orientation portrait (MX | BGR)            */
#define LCD_INVERT     0                    /* mettre 1 si les couleurs sont inversées    */

/* ---------- Tactile capacitif (hypothèse : FT6336U, I2C 0x38) ---------- */
#define TOUCH_I2C      i2c0
#define TOUCH_I2C_HZ   (400 * 1000)
#define TOUCH_PIN_SDA  4
#define TOUCH_PIN_SCL  5
#define TOUCH_PIN_RST  6
#define TOUCH_PIN_INT  7                    /* lu en entrée ; inutilisé en mode polling   */
#define TOUCH_ADDR     0x38
#define TOUCH_SWAP_XY  0                    /* ajustez si le doigt et l'affichage ne      */
#define TOUCH_FLIP_X   0                    /* coïncident pas (essayez un réglage à la    */
#define TOUCH_FLIP_Y   0                    /* fois)                                      */

/* ---------- Réservé pour la suite ---------- */
#define SD_PIN_CS      13                   /* Micro SD : même bus SPI0, CS séparé        */
