"""Paramètres : luminosité de l'écran, langue de l'interface, infos système."""
import gc
import sys
import phone
import appkit
import i18n
from appkit import W, BLACK, GREY, LIGHT, ACCENT, WHITE

STEP = 10      # pas de réglage de luminosité, en %
MINIMUM = 10   # jamais 0 % : on ne veut pas se retrouver avec un écran noir

BRIGHT_Y = 44                 # zone luminosité
LANG_Y = 156                  # zone langue (grille 3x2)
LANG_COLS = 3
LANG_CELL_W = (W - 16 - 2 * 6) // LANG_COLS   # 3 colonnes, marges 8px, espaces 6px
LANG_CELL_H = 30
LANG_GAP = 6
SYS_Y = 260                   # zone infos système


class App(appkit.App):
    title_key = "app_parametres"

    def __init__(self):
        self.level = 100

    # ---------- Luminosité ----------

    def draw_brightness(self):
        phone.text_l(i18n.t("settings_brightness"), 16, BRIGHT_Y, BLACK, phone.BOLD)

        phone.round_rect(16, BRIGHT_Y + 20, 208, 16, 8, LIGHT)
        fill = 208 * self.level // 100
        if fill >= 16:
            phone.round_rect(16, BRIGHT_Y + 20, fill, 16, 8, ACCENT)
        phone.fill_rect(16, BRIGHT_Y + 44, 208, 18, appkit.BG)
        phone.text_c("%d %%" % self.level, W // 2, BRIGHT_Y + 53, BLACK, phone.SMALL)

        appkit.button(16, BRIGHT_Y + 64, 96, 34, "-")
        appkit.button(128, BRIGHT_Y + 64, 96, 34, "+")

    # ---------- Langue ----------

    def lang_cell(self, i):
        col, row = i % LANG_COLS, i // LANG_COLS
        x = 8 + col * (LANG_CELL_W + LANG_GAP)
        y = LANG_Y + 20 + row * (LANG_CELL_H + LANG_GAP)
        return x, y, LANG_CELL_W, LANG_CELL_H

    def draw_lang(self):
        phone.text_l(i18n.t("settings_language"), 16, LANG_Y, BLACK, phone.BOLD)
        current = i18n.get_lang()
        for i, code in enumerate(i18n.LANGS):
            x, y, w, h = self.lang_cell(i)
            selected = code == current
            phone.round_rect(x, y, w, h, 6, ACCENT if selected else LIGHT)
            phone.text_c(i18n.LANG_NAMES[code], x + w // 2, y + h // 2,
                        WHITE if selected else BLACK, phone.TINY)

    # ---------- Système ----------

    def draw_system(self):
        phone.fill_rect(0, SYS_Y - 10, W, appkit.H - (SYS_Y - 10), appkit.BG)
        phone.hline(16, W - 17, SYS_Y - 10, GREY)
        phone.text_l("%s : %s" % (i18n.t("settings_system"), sys.platform), 16, SYS_Y + 8, BLACK, phone.SMALL)
        v = sys.implementation.version
        phone.text_l("MicroPython %d.%d.%d" % (v[0], v[1], v[2]), 16, SYS_Y + 26, BLACK, phone.SMALL)
        if hasattr(gc, "mem_free"):
            phone.text_l("%s : %d Ko" % (i18n.t("settings_ram_free"), gc.mem_free() // 1024),
                        16, SYS_Y + 44, BLACK, phone.SMALL)

    # ---------- appkit.App ----------

    def draw(self):
        appkit.clear()
        self.draw_brightness()
        self.draw_lang()
        self.draw_system()

    def on_tap(self, x, y):
        if BRIGHT_Y + 64 <= y < BRIGHT_Y + 98:
            if x < 120:
                self.level = max(MINIMUM, self.level - STEP)
            else:
                self.level = min(100, self.level + STEP)
            phone.backlight(self.level * 255 // 100)
            self.draw_brightness()
            return

        for i, code in enumerate(i18n.LANGS):
            cx, cy, cw, ch = self.lang_cell(i)
            if appkit.inside(x, y, (cx, cy, cw, ch)) and code != i18n.get_lang():
                i18n.set_lang(code)                  # persiste + retraduit l'accueil (C)
                appkit.header(self.display_title())   # notre propre titre change aussi de langue
                self.draw()
                return
