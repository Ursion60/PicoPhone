"""
appkit : petite boîte à outils pour écrire une appli (MicroPython).

Une appli = un fichier apps/<id>.py qui définit une classe App :

    import phone, appkit
    from appkit import BLACK

    class App(appkit.App):
        title = "Ma super appli"

        def draw(self):                      # dessine le contenu (sous la barre de titre)
            appkit.clear()
            phone.text_c("Bonjour !", 120, 160, BLACK, phone.BOLD)

        def on_tap(self, x, y):              # le doigt vient de se poser en (x, y)
            pass

        def on_tick(self, ms):               # ~60 fois par seconde (facultatif)
            pass

Le bouton « Retour » de la barre de titre est géré par appkit.
"""
import gc
import os
import sys
import time
import phone
import i18n

W = phone.WIDTH
H = phone.HEIGHT
rgb = phone.rgb

# Palette (mêmes couleurs que l'écran d'accueil)
BG = rgb(236, 236, 236)
WHITE = rgb(255, 255, 255)
BLACK = rgb(20, 20, 20)
ACCENT = rgb(90, 70, 200)
GREY = rgb(150, 150, 150)
LIGHT = rgb(210, 210, 210)
GREEN = rgb(0, 140, 130)
RED = rgb(225, 40, 40)
KEY_BG = rgb(255, 255, 255)
KEY_SHADOW = rgb(190, 190, 190)

HEADER_H = 30
BACK_ZONE = (0, 0, 84, HEADER_H)      # zone tactile du bouton Retour


def inside(x, y, zone):
    """True si (x, y) est dans zone = (x0, y0, largeur, hauteur)."""
    return zone[0] <= x < zone[0] + zone[2] and zone[1] <= y < zone[1] + zone[3]


def header(title):
    phone.fill_rect(0, 0, W, HEADER_H, ACCENT)
    phone.text_l(i18n.t("back"), 8, HEADER_H // 2, WHITE, phone.SMALL)
    phone.text_c(title, W // 2 + 22, HEADER_H // 2, WHITE, phone.BOLD)


def clear():
    """Efface la zone de contenu (tout sauf la barre de titre)."""
    phone.fill_rect(0, HEADER_H, W, H - HEADER_H, BG)


def button(x, y, w, h, label, color=ACCENT, fg=WHITE):
    phone.round_rect(x, y, w, h, 8, color)
    phone.text_c(label, x + w // 2, y + h // 2, fg, phone.BOLD)


class App:
    title = "Application"     # libellé brut (repli si title_key n'est pas défini)
    title_key = None          # clé i18n (voir python/i18n.py) ; prioritaire sur `title`

    def display_title(self):
        return i18n.t(self.title_key) if self.title_key else self.title

    def draw(self):
        clear()

    def on_tap(self, x, y):
        pass

    def on_tick(self, ms):
        pass


class MissingApp(App):
    """Affichée quand apps/<id>.py n'existe pas encore."""

    def __init__(self, app_id):
        self.title = app_id

    def draw(self):
        clear()
        phone.text_c("Pas encore disponible", W // 2, 120, BLACK, phone.BOLD)
        phone.text_c("Pour créer cette appli, écrivez", W // 2, 160, GREY, phone.SMALL)
        phone.text_c("le fichier :", W // 2, 176, GREY, phone.SMALL)
        phone.text_c("apps/%s.py" % self.title, W // 2, 200, BLACK, phone.BOLD)


def _wrap(text, width):
    """Retour à la ligne aux espaces (les mots plus longs que width sont laissés tels quels)."""
    lines, cur = [], ""
    for word in text.split(" "):
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = cur + " " + word if cur else word
    if cur:
        lines.append(cur)
    return lines


class ErrorApp(App):
    """Affichée quand une appli plante : le lanceur reste en vie."""
    title = "Erreur"

    def __init__(self, exc):
        self.msg = "%s: %s" % (type(exc).__name__, exc)

    def draw(self):
        clear()
        phone.text_c("Cette appli a planté", W // 2, 70, RED, phone.BOLD)
        y = 110
        for line in _wrap(self.msg, 32):
            if y > 300:
                break
            phone.text_l(line[:36], 12, y, BLACK, phone.SMALL)
            y += 16


def run(app):
    """Boucle d'une appli : dessine, puis distribue les appuis jusqu'à « Retour »."""
    header(app.display_title())
    app.draw()
    phone.flush()
    while True:
        t = phone.tap()
        if t:
            if inside(t[0], t[1], BACK_ZONE):
                return
            app.on_tap(t[0], t[1])
        app.on_tick(time.ticks_ms())
        phone.flush()
        time.sleep_ms(15)


def _exists(app_id):
    for ext in (".py", ".mpy"):
        try:
            os.stat("apps/" + app_id + ext)
            return True
        except OSError:
            pass
    return False


def launch(app_id):
    """Lance l'appli apps/<app_id>.py ; ne lève jamais d'exception d'appli."""
    modname = "apps." + app_id
    if not _exists(app_id):
        app = MissingApp(app_id)
    else:
        try:
            __import__(modname)
            app = sys.modules[modname].App()
        except Exception as e:                      # erreur à l'import ou dans __init__
            sys.print_exception(e)
            app = ErrorApp(e)
    try:
        run(app)
    except Exception as e:                          # erreur pendant l'exécution
        sys.print_exception(e)
        run(ErrorApp(e))
    sys.modules.pop(modname, None)                  # libère la RAM de l'appli...
    for m in [k for k in sys.modules if k.startswith("apps.")]:
        sys.modules.pop(m, None)                    # ...et de ses modules d'aide (ex. apps.pdftext)
    gc.collect()


# ---------------------------------------------------------------------------
# Clavier tactile AZERTY, pour écrire du texte (utilisé par ex. dans Notes).
# ---------------------------------------------------------------------------

_ROW1 = "azertyuiop"
_ROW2 = "qsdfghjklm"
_ROW3 = "wxcvbn"
_DIG1 = "1234567890"
_DIG2 = "-/:;()€&@\""
_DIG3 = ".,?!'"
_ACC1 = "éèêëàâ"
_ACC2 = "äùûüïî"
_ACC3 = "ôöçñ"

KEY_H = 34
FIELD_Y = HEADER_H + 8            # champ de texte, juste sous la barre de titre
KB_TOP = FIELD_Y + 34 + 10 + 30 + 14   # ...+ son espace, + les boutons Annuler/OK, + une marge


def _row_rects(letters, y, extra=()):
    """Répartit `letters` + les touches spéciales `extra` (id, largeur_en_unités, libellé)
    sur toute la largeur, unité = largeur d'une touche lettre."""
    units = len(letters) + sum(u for _, u, _ in extra)
    unit_w = W // units
    x = (W - unit_w * units) // 2
    keys = []
    for ch in letters:
        keys.append((x, unit_w, ch, ch))
        x += unit_w
    for kid, u, label in extra:
        keys.append((x, unit_w * u, kid, label))
        x += unit_w * u
    return keys, y


class Keyboard:
    """Clavier AZERTY : minuscule/majuscule, page chiffres/symboles, et page accents (touche
    dédiée « é ») pour taper é/è/ê/à/ç/ñ/ö... quelle que soit la langue de l'interface.

    k = Keyboard("texte initial")
    k.draw()                      # à appeler après avoir dessiné le champ de texte
    consumed = k.on_tap(x, y)     # True si le point touché faisait partie du clavier
    k.text                        # le texte courant
    k.done                        # "ok" / "cancel" une fois validé, sinon None
    """

    LETTERS, DIGITS, ACCENTS = "letters", "digits", "accents"

    def __init__(self, initial=""):
        self.text = initial
        self.shift = False
        self.page = self.LETTERS
        self.done = None

    def _rows(self):
        rows = []
        if self.page == self.DIGITS:
            rows.append(_row_rects(_DIG1, KB_TOP))
            rows.append(_row_rects(_DIG2, KB_TOP + KEY_H))
            rows.append(_row_rects(_DIG3, KB_TOP + 2 * KEY_H,
                                    extra=[("to_letters", 2, "ABC"), ("back", 2, "<-")]))
            rows.append(([
                (4, 64, "to_accents", "é"),
                (4 + 64 + 4, W - 8 - 64 - 4, "space", i18n.t("space_key")),
            ], KB_TOP + 3 * KEY_H))
        elif self.page == self.ACCENTS:
            rows.append(_row_rects(_ACC1, KB_TOP))
            rows.append(_row_rects(_ACC2, KB_TOP + KEY_H))
            rows.append(_row_rects(_ACC3, KB_TOP + 2 * KEY_H,
                                    extra=[("to_letters", 2, "ABC"), ("back", 2, "<-")]))
            rows.append(([
                (4, 64, "to_digits", "123"),
                (4 + 64 + 4, W - 8 - 64 - 4, "space", i18n.t("space_key")),
            ], KB_TOP + 3 * KEY_H))
        else:
            r1 = _ROW1.upper() if self.shift else _ROW1
            r2 = _ROW2.upper() if self.shift else _ROW2
            r3 = _ROW3.upper() if self.shift else _ROW3
            rows.append(_row_rects(r1, KB_TOP))
            rows.append(_row_rects(r2, KB_TOP + KEY_H))
            rows.append(_row_rects(r3, KB_TOP + 2 * KEY_H,
                                    extra=[("shift", 2, "^"), ("to_accents", 2, "é"), ("back", 2, "<-")]))
            rows.append(([
                (4, 64, "to_digits", "123"),
                (4 + 64 + 4, W - 8 - 64 - 4, "space", i18n.t("space_key")),
            ], KB_TOP + 3 * KEY_H))
        return rows

    def draw(self):
        """Dessin complet (clavier + boutons) : à appeler une fois à l'ouverture, et à chaque
        changement de page/majuscule (les libellés des touches changent). Pour une frappe
        normale, seul le champ de texte doit être redessiné -> voir draw_field()."""
        clear()
        self.draw_field()

        button(10, FIELD_Y + 42, 100, 30, i18n.t("cancel"), GREY)
        button(W - 110, FIELD_Y + 42, 100, 30, i18n.t("ok"), GREEN)

        for keys, y in self._rows():
            for x, w, kid, label in keys:
                phone.round_rect(x + 2, y + 2, w - 4, KEY_H - 4, 6, KEY_BG)
                phone.text_c(label, x + w // 2, y + KEY_H // 2, BLACK, phone.SMALL)

    def draw_field(self):
        """Redessine seulement le champ de texte (appelé à chaque frappe : rapide)."""
        field_y = FIELD_Y
        phone.round_rect(10, field_y, W - 20, 34, 6, KEY_SHADOW)
        phone.fill_rect(12, field_y + 2, W - 24, 30, WHITE)
        shown = self.text[-22:] if len(self.text) > 22 else self.text
        phone.text_l(shown + "|", 18, field_y + 17, BLACK, phone.SMALL)

    def on_tap(self, x, y):
        field_y = FIELD_Y
        if inside(x, y, (10, field_y + 42, 100, 30)):
            self.done = "cancel"
            return True
        if inside(x, y, (W - 110, field_y + 42, 100, 30)):
            self.done = "ok"
            return True

        if y < KB_TOP - 6:
            return False
        for keys, ry in self._rows():
            if not (ry <= y < ry + KEY_H):
                continue
            for kx, kw, kid, _label in keys:
                if kx <= x < kx + kw:
                    self._key(kid)
                    if kid in ("shift", "to_digits", "to_letters", "to_accents"):
                        self.draw()          # les libellés des touches changent -> tout redessiner
                    else:
                        self.draw_field()    # frappe normale : juste le champ, pas les touches
                    return True
        return True   # dans la zone du clavier mais entre deux touches : on absorbe quand même

    def _key(self, kid):
        if kid == "shift":
            self.shift = not self.shift
        elif kid == "to_digits":
            self.page, self.shift = self.DIGITS, False
        elif kid == "to_letters":
            self.page, self.shift = self.LETTERS, False
        elif kid == "to_accents":
            self.page, self.shift = self.ACCENTS, False
        elif kid == "back":
            self.text = self.text[:-1]
        elif kid == "space":
            self.text += " "
        else:
            self.text += kid
            if self.shift:
                self.shift = False


def prompt_text(title=None, initial=""):
    """Ouvre le clavier en plein écran ; renvoie le texte saisi, ou None si Annuler.
    Bloquant : gère sa propre boucle tactile (comme appkit.run)."""
    header(title if title is not None else i18n.t("text_default"))
    kb = Keyboard(initial)
    kb.draw()
    phone.flush()
    while kb.done is None:
        t = phone.tap()
        if t:
            kb.on_tap(t[0], t[1])
        phone.flush()
        time.sleep_ms(15)
    return kb.text if kb.done == "ok" else None
