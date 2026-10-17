"""
Lecteur PDF : liste les .pdf du dossier pdfs/ de la carte, en affiche le texte page par page
(extraction par apps/pdftext.py : pas d'images ni de mise en page). Défilement dans la page
(▲▼), changement de page (◀ ▶), dernière page lue mémorisée par fichier (pdf_state.json).
"""
import gc
import json
import os
import phone
import appkit
import i18n
from appkit import W, H, BG, WHITE, BLACK, GREY, LIGHT, ACCENT, RED, HEADER_H
from apps import pdftext

PDF_DIR = "pdfs"
STATE_FILE = "pdf_state.json"
SAVE_DELAY_MS = 1500          # la position n'est écrite qu'une fois le lecteur au repos (usure de la flash)

BAR_H = 30                    # barre « < Liste   Page 3/12 »
NAV_H = 40                    # boutons du bas
LINE_H = 15
TOP = HEADER_H + BAR_H + 6
LINES = (H - NAV_H - TOP) // LINE_H          # lignes de texte visibles
STEP = max(1, LINES - 2)                     # une pression fait défiler d'un écran (2 lignes de recouvrement)

ROW = 34
LIST_TOP = HEADER_H + 6
LIST_ROWS = (H - NAV_H - LIST_TOP) // ROW
MAX_LINES = 3000                             # plafond de lignes par page (RAM)

# Caractères hors de la police de l'écran (ASCII + Latin-1) -> équivalent affichable
_MAP = {
    "\u2018": "'", "\u2019": "'", "\u201a": ",", "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2032": "'", "\u2033": '"', "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2010": "-", "\u2011": "-",
    "\u2026": "...", "\u2022": "*", "\u00b7": "\u00b7", "\u20ac": "EUR", "\u2122": "TM",
    "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl",
    "\u0152": "OE", "\u0153": "oe", "\u0160": "S", "\u0161": "s", "\u017d": "Z", "\u017e": "z",
    "\u0178": "Y", "\u0141": "L", "\u0142": "l", "\u0131": "i", "\u2039": "<", "\u203a": ">",
    "\u00a0": " ", "\u2002": " ", "\u2003": " ", "\u2009": " ", "\u202f": " ", "\u00ad": "",
    "\u200b": "", "\u2020": "+", "\u2021": "+", "\u2044": "/", "\u02c6": "^", "\u02dc": "~",
}


def _display(text):
    """Remplace ce que la police ne sait pas dessiner (guillemets typographiques, ligatures, €...)."""
    out = []
    for ch in text:
        r = _MAP.get(ch)
        if r is not None:
            out.append(r)
        elif ch < "\u0100":
            out.append(ch)
        else:
            out.append("?")
    return "".join(out)


def _fit(text, maxw, font):
    if phone.text_w(text, font) <= maxw:
        return text
    while text and phone.text_w(text + "..", font) > maxw:
        text = text[:-1]
    return text + ".."


def _wrap(text, maxw, font, limit=MAX_LINES):
    """Retour à la ligne en pixels, aux espaces ; un mot trop large est coupé. Garde les lignes vides."""
    lines = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            while len(word) > 1 and phone.text_w(word, font) > maxw:
                n = len(word)
                while n > 1 and phone.text_w(word[:n], font) > maxw:
                    n -= 1
                if cur:
                    lines.append(cur)
                    cur = ""
                lines.append(word[:n])
                word = word[n:]
            trial = cur + " " + word if cur else word
            if cur and phone.text_w(trial, font) > maxw:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        lines.append(cur)
        if len(lines) >= limit:
            break
    return lines


def _load_state():
    try:
        with open(STATE_FILE) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(d):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(d, f)
    except OSError:
        pass


def _list_pdfs():
    try:
        names = os.listdir(PDF_DIR)
    except OSError:
        return []
    out = []
    for n in names:
        if n.lower().endswith(".pdf"):
            try:
                size = os.stat(PDF_DIR + "/" + n)[6]
            except OSError:
                size = 0
            out.append((n, size))
    out.sort()
    return out


def _arrow(x, y, w, h, kind, enabled):
    """Bouton avec un triangle : kind = 'u', 'd', 'l' ou 'r'."""
    phone.round_rect(x, y, w, h, 8, ACCENT if enabled else LIGHT)
    col = WHITE if enabled else GREY
    cx, cy = x + w // 2, y + h // 2
    if kind == "u" or kind == "d":
        for k in range(7):
            phone.hline(cx - k, cx + k, cy - 3 + k if kind == "u" else cy + 3 - k, col)
    else:
        for dy in range(-6, 7):
            if kind == "l":
                phone.hline(cx - 4 + abs(dy), cx + 3, cy + dy, col)
            else:
                phone.hline(cx - 3, cx + 4 - abs(dy), cy + dy, col)


class App(appkit.App):
    title_key = "app_lecteur_pdf"

    def __init__(self):
        self.files = _list_pdfs()
        self.fscroll = 0
        self.state = _load_state()
        self.pdf = None
        self.name = None
        self.page = 0
        self.lines = []
        self.top = 0
        self.msg = None                 # (clé i18n, couleur) quand la page n'a pas de texte à afficher
        self.dirty = False
        self.changed_at = 0

    # ---------- Liste ----------

    def draw(self):
        appkit.clear()
        if self.pdf is None and self.name is None:
            self.draw_list()
        else:
            self.draw_reader()

    def draw_list(self):
        if not self.files:
            phone.text_c(i18n.t("pdf_none"), W // 2, 120, BLACK, phone.BOLD)
            phone.text_c(i18n.t("pdf_hint"), W // 2, 150, GREY, phone.SMALL)
            phone.text_c(PDF_DIR + "/", W // 2, 172, BLACK, phone.BOLD)
            return
        phone.fill_rect(0, LIST_TOP, W, LIST_ROWS * ROW, BG)
        for r in range(LIST_ROWS):
            i = self.fscroll + r
            if i >= len(self.files):
                break
            name, size = self.files[i]
            y = LIST_TOP + r * ROW
            cy = y + ROW // 2
            kb = "%d %s" % (max(1, size // 1024), i18n.t("pdf_unit_kb"))
            kw = phone.text_w(kb, phone.SMALL)
            phone.text_l(_fit(_display(name[:-4]), W - 28 - kw - 8, phone.SMALL), 12, cy, BLACK, phone.SMALL)
            phone.text_l(kb, W - 12 - kw, cy, GREY, phone.SMALL)
            phone.hline(8, W - 9, y + ROW - 1, LIGHT)
        if len(self.files) > LIST_ROWS:
            y = H - NAV_H + 3
            h = NAV_H - 8
            _arrow(W // 2 - 60, y, 56, h, "u", self.fscroll > 0)
            _arrow(W // 2 + 4, y, 56, h, "d", self.fscroll + LIST_ROWS < len(self.files))

    def tap_list(self, x, y):
        if y >= H - NAV_H and len(self.files) > LIST_ROWS:
            if W // 2 - 60 <= x < W // 2 - 4:
                self.fscroll = max(0, self.fscroll - LIST_ROWS)
            elif W // 2 + 4 <= x < W // 2 + 60:
                self.fscroll = min(len(self.files) - LIST_ROWS, self.fscroll + LIST_ROWS)
            else:
                return
            self.draw()
            return
        if y < LIST_TOP:
            return
        i = self.fscroll + (y - LIST_TOP) // ROW
        if 0 <= i < len(self.files) and (y - LIST_TOP) // ROW < LIST_ROWS:
            self.open_file(self.files[i][0])

    # ---------- Ouverture / pages ----------

    def open_file(self, name):
        self.name = name
        self.pdf = None
        self.lines = []
        self.msg = None
        self.page = 0
        self.top = 0
        self.show_status("pdf_loading")
        gc.collect()
        try:
            self.pdf = pdftext.PDF(PDF_DIR + "/" + name)
        except pdftext.PDFError as e:
            self.msg = ("pdf_encrypted" if str(e) == "chiffré" else "pdf_bad", RED)
        except (OSError, MemoryError, ValueError, KeyError, IndexError, TypeError):
            self.msg = ("pdf_bad", RED)
        if self.pdf is not None:
            p = self.state.get(name, 0)
            self.page = p if isinstance(p, int) and 0 <= p < self.pdf.n_pages else 0
            self.load_page(0)
        self.draw()

    def show_status(self, key):
        phone.fill_rect(0, TOP, W, H - TOP - NAV_H, BG)
        phone.text_c(i18n.t(key), W // 2, 150, GREY, phone.BOLD)
        phone.flush()

    def load_page(self, top):
        """Extrait + met en page self.page ; top = première ligne affichée (-1 : tout en bas)."""
        self.show_status("pdf_loading")
        self.msg = None
        self.lines = []
        gc.collect()
        try:
            text = self.pdf.page_text(self.page)
            if text:
                self.lines = _wrap(_display(text), W - 20, phone.SMALL)
                if self.pdf.truncated:
                    self.lines.append(i18n.t("pdf_truncated"))
            else:
                self.msg = ("pdf_garbled" if self.pdf.unreadable else "pdf_no_text", GREY)
        except pdftext.PDFError:
            self.msg = ("pdf_bad", RED)
        except MemoryError:
            self.lines = []
            gc.collect()
            self.msg = ("pdf_bad", RED)
        except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
            self.msg = ("pdf_bad", RED)
        last = max(0, len(self.lines) - LINES)
        self.top = last if top < 0 else min(top, last)
        self.mark_dirty()

    def mark_dirty(self):
        self.dirty = True
        self.changed_at = None

    # ---------- Lecteur ----------

    def draw_reader(self):
        phone.fill_rect(0, HEADER_H, W, BAR_H, ACCENT)
        phone.text_l(i18n.t("notes_back_to_list"), 8, HEADER_H + BAR_H // 2, WHITE, phone.SMALL)
        if self.pdf is not None:
            label = "%s %d/%d" % (i18n.t("pdf_page"), self.page + 1, self.pdf.n_pages)
            phone.text_l(label, W - 8 - phone.text_w(label, phone.SMALL), HEADER_H + BAR_H // 2, WHITE, phone.SMALL)
        else:
            phone.text_l(_fit(_display(self.name or ""), 120, phone.SMALL), W - 128, HEADER_H + BAR_H // 2,
                         WHITE, phone.SMALL)
        self.draw_text()
        self.draw_nav()

    def draw_text(self):
        phone.fill_rect(0, TOP - 4, W, LINES * LINE_H + 8, BG)
        if self.msg:
            key, col = self.msg
            y = 120
            for ln in _wrap(i18n.t(key), W - 30, phone.BOLD):
                phone.text_c(ln, W // 2, y, col, phone.BOLD)
                y += 20
            return
        for r in range(LINES):
            i = self.top + r
            if i >= len(self.lines):
                break
            phone.text_l(self.lines[i], 10, TOP + r * LINE_H + LINE_H // 2, BLACK, phone.SMALL)
        if len(self.lines) > LINES:                    # ascenseur
            area = LINES * LINE_H
            h = max(6, area * LINES // len(self.lines))
            y = TOP + (area - h) * self.top // max(1, len(self.lines) - LINES)
            phone.fill_rect(W - 4, y, 3, h, GREY)

    def draw_nav(self):
        y = H - NAV_H + 3
        h = NAV_H - 8
        n = self.pdf.n_pages if self.pdf is not None else 0
        can_down = self.top + LINES < len(self.lines) or self.page + 1 < n
        phone.fill_rect(0, H - NAV_H, W, NAV_H, BG)
        _arrow(4, y, 54, h, "l", self.page > 0)
        _arrow(62, y, 54, h, "u", self.top > 0 or self.page > 0)
        _arrow(124, y, 54, h, "d", can_down)
        _arrow(182, y, 54, h, "r", self.page + 1 < n)

    def goto_page(self, p, top):
        if self.pdf is None or not (0 <= p < self.pdf.n_pages):
            return
        self.page = p
        self.load_page(top)
        self.draw_reader()

    def tap_reader(self, x, y):
        if HEADER_H <= y < HEADER_H + BAR_H and x < 110:      # « < Liste »
            self.close_file()
            self.draw()
            return
        if y < H - NAV_H or self.pdf is None:
            return
        zone = x // 60
        if zone == 0:
            self.goto_page(self.page - 1, 0)
        elif zone == 3:
            self.goto_page(self.page + 1, 0)
        elif zone == 1:                                        # ▲
            if self.top > 0:
                self.top = max(0, self.top - STEP)
                self.draw_text()
                self.draw_nav()
            elif self.page > 0:
                self.goto_page(self.page - 1, -1)              # fin de la page précédente
        elif zone == 2:                                        # ▼
            if self.top + LINES < len(self.lines):
                self.top = min(self.top + STEP, len(self.lines) - LINES)
                self.draw_text()
                self.draw_nav()
            else:
                self.goto_page(self.page + 1, 0)

    def close_file(self):
        self.flush_state()
        if self.pdf is not None:
            self.pdf.close()
        self.pdf = None
        self.name = None
        self.lines = []
        self.msg = None
        gc.collect()

    # ---------- Position mémorisée ----------

    def flush_state(self):
        if self.dirty and self.pdf is not None and self.name:
            if len(self.state) > 20 and self.name not in self.state:
                del self.state[next(iter(self.state))]
            self.state[self.name] = self.page
            _save_state(self.state)
        self.dirty = False

    def on_tick(self, ms):
        if not self.dirty:
            return
        if self.changed_at is None:
            self.changed_at = ms
        elif ((ms - self.changed_at) & 0x3FFFFFFF) > SAVE_DELAY_MS:
            self.flush_state()

    # ---------- Interaction ----------

    def on_tap(self, x, y):
        if self.pdf is None and self.name is None:
            self.tap_list(x, y)
        else:
            self.tap_reader(x, y)
