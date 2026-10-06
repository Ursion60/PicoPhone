/*
 * ui : écran d'accueil 240x320 (port de l'ancien main.c SDL2).
 * Indépendant du matériel : ne dépend que de gfx.h. Le temps est fourni
 * par l'appelant en millisecondes (remplace flashFrames + SDL_Delay(16)).
 */
#pragma once
#include <stdint.h>

void ui_init(void);                                          /* construit la grille d'icônes    */
void ui_draw_loading(const char *label, int step, int total);
void ui_draw_all(void);                                      /* affichage complet de l'accueil  */
void ui_touch_down(int x, int y, uint32_t now_ms);           /* = SDL_MOUSEBUTTONDOWN gauche    */
void ui_tick(uint32_t now_ms);                               /* fin des flashs, redessine le delta */

/* Identifiant de l'élément touché depuis le dernier appel, ou NULL :
 * "edt", "notes", "nfc", "shop", "synchro", "parametres", "musique",
 * "lecteur_pdf", "options", "all_apps". L'événement est consommé à la lecture. */
const char *ui_take_event(void);

/* Traduction (voir python/i18n.py) : change les libellés affichés, pris en compte au prochain
 * ui_draw_all(). Chaîne copiée (tronquée si trop longue) ; UTF-8 accepté (CJK compris). */
void ui_set_home_title(const char *utf8);
void ui_set_options_label(const char *utf8);
void ui_set_allapps_label(const char *utf8);
void ui_set_app_label(const char *app_id, const char *utf8);   /* app_id = "edt", "notes"... */
