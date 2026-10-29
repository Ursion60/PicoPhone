"""
EDT : emploi du temps, un jour à la fois (◀ ▶ pour changer de jour, ▲ ▼ si la journée est longue).

Les données sont envoyées par la synchro (tools/sync_pronote.py, sur le PC) dans le dossier edt/ :
    edt/meta.json         {"v": 1, "synced": "2026-10-28T08:12", "source": "pronote",
                           "days": ["2026-10-26", "2026-10-27", ...]}      jours qui ont des cours
    edt/AAAA-MM-JJ.json   {"lessons": [{"start": "08:00", "end": "08:55", "subject": "Mathématiques",
                           "room": "B12", "teacher": "M. Dupont", "cancelled": false, "note": ""}]}

Un seul jour est chargé en RAM à la fois. Tout fichier absent, abîmé ou d'un autre format est ignoré
ou signalé à l'écran, jamais une exception.

La carte n'a pas d'horloge fiable : l'appli utilise la date du système si elle est plausible (réglée
par la synchro), sinon la date de la dernière synchro, et l'indique en bas de l'écran.
"""
import json
import time
import phone
import appkit
import i18n
from appkit import W, H, BG, WHITE, BLACK, GREY, RED, LIGHT, ACCENT, HEADER_H

DATA_DIR = "edt"
META_FILE = DATA_DIR + "/meta.json"

NAV_H = 34                    # barre ◀ date ▶, sous l'en-tête
BTN_W = 44
ROW = 36
FOOT_H = 30                   # pied : date de synchro (+ flèches de défilement)
LIST_TOP = HEADER_H + NAV_H + 4
VISIBLE = (H - FOOT_H - LIST_TOP) // ROW
STEP = max(1, VISIBLE // 2)
TIME_W = 46                   # colonne des heures ; la barre de couleur est juste après
ARROW_W = 34

MAX_DAYS = 120                # bornes : un fichier abîmé ou énorme ne doit pas saturer la RAM
MAX_LESSONS = 16
MIN_YEAR = 2024               # en dessous, l'horloge de la carte n'a pas été réglée


def _fit(text, maxw, font):
    """Tronque `text` (avec "..") pour qu'il tienne dans `maxw` pixels, quelle que soit la largeur des lettres."""
    if phone.text_w(text, font) <= maxw:
        return text
    while text and phone.text_w(text + "..", font) > maxw:
        text = text[:-1]
    return text + ".."


# ---------------------------------------------------------------------------
# Dates et heures
# ---------------------------------------------------------------------------
def _days_in_month(y, m):
    if m == 2:
        return 29 if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0 else 28
    return 30 if m in (4, 6, 9, 11) else 31


def _parse_date(s):
    """"AAAA-MM-JJ" -> (a, m, j), ou None si ce n'est pas une date valide."""
    if not isinstance(s, str) or len(s) != 10 or s[4] != "-" or s[7] != "-":
        return None
    try:
        y, m, d = int(s[:4]), int(s[5:7]), int(s[8:])
    except ValueError:
        return None
    if 2000 <= y <= 2099 and 1 <= m <= 12 and 1 <= d <= _days_in_month(y, m):
        return y, m, d
    return None


def _weekday(y, m, d):
    """Jour de la semaine, 0 = lundi (algorithme de Sakamoto)."""
    if m < 3:
        y -= 1
    t = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    return (y + y // 4 - y // 100 + y // 400 + t[m - 1] + d + 6) % 7


def _valid_time(s):
    """"HH:MM" -> True si valide (les comparaisons de chaînes suffisent ensuite pour trier)."""
    if not isinstance(s, str) or len(s) != 5 or s[2] != ":":
        return False
    try:
        h, mi = int(s[:2]), int(s[3:])
    except ValueError:
        return False
    return 0 <= h < 24 and 0 <= mi < 60


def _today():
    """Date du jour "AAAA-MM-JJ", ou None si l'horloge de la carte n'a pas été réglée."""
    t = time.localtime()
    if t[0] < MIN_YEAR:
        return None
    return "%04d-%02d-%02d" % (t[0], t[1], t[2])


def _date_label(iso):
    y, m, d = _parse_date(iso)
    weekdays = i18n.t("edt_weekdays").split(" ")
    months = i18n.t("edt_months").split(" ")
    return i18n.t("edt_date_fmt").format(wd=weekdays[_weekday(y, m, d)], d=d, m=months[m - 1])


# ---------------------------------------------------------------------------
# Lecture des données (validation : un fichier abîmé ne doit jamais faire planter l'appli)
# ---------------------------------------------------------------------------
def _text(v, n):
    return v[:n] if isinstance(v, str) else ""


def _load_meta():
    """Renvoie {"days": [...], "synced": "..."} ou None s'il n'y a pas (encore) de données valides."""
    try:
        with open(META_FILE) as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get("days"), list):
        return None
    days = sorted(set(d for d in raw["days"][:MAX_DAYS] if _parse_date(d)))
    if not days:
        return None
    return {"days": days, "synced": _text(raw.get("synced"), 16)}


def _load_day(iso):
    """Cours du jour `iso` (liste triée, éventuellement vide), ou None si le fichier est absent/illisible."""
    try:
        with open("%s/%s.json" % (DATA_DIR, iso)) as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get("lessons"), list):
        return None
    lessons = []
    for it in raw["lessons"][:MAX_LESSONS]:
        if not isinstance(it, dict) or not _valid_time(it.get("start")) or not _valid_time(it.get("end")):
            continue
        lessons.append({
            "start": it["start"], "end": it["end"],
            "subject": _text(it.get("subject"), 40) or "?",
            "room": _text(it.get("room"), 12),
            "teacher": _text(it.get("teacher"), 32),
            "note": _text(it.get("note"), 40),
            "cancelled": bool(it.get("cancelled")),
        })
    lessons.sort(key=lambda x: (x["start"], x["end"]))
    return lessons


def _start_index(days, ref):
    """Indice du premier jour >= ref (sinon le dernier) : le jour affiché à l'ouverture."""
    for i, d in enumerate(days):
        if d >= ref:
            return i
    return len(days) - 1


class App(appkit.App):
    title_key = "app_edt"

    def __init__(self):
        self.meta = _load_meta()
        self.today = _today()
        self.idx = 0
        self.lessons = []
        self.scroll = 0
        if self.meta:
            days = self.meta["days"]
            ref = self.today or (self.meta["synced"][:10] if _parse_date(self.meta["synced"][:10]) else days[0])
            self.idx = _start_index(days, ref)
            self.lessons = _load_day(days[self.idx])

    def date(self):
        return self.meta["days"][self.idx]

    def max_scroll(self):
        return max(0, len(self.lessons or ()) - VISIBLE)

    def overflow(self):
        return len(self.lessons or ()) > VISIBLE

    # ---------- Dessin ----------

    def draw(self):
        appkit.clear()
        if not self.meta:
            self.draw_empty(i18n.t("edt_none"), i18n.t("edt_hint"), "tools/sync_pronote.py")
            return
        self.scroll = min(max(self.scroll, 0), self.max_scroll())
        self.draw_nav()
        self.draw_list()
        self.draw_footer()

    def draw_empty(self, l1, l2=None, l3=None):
        phone.text_c(_fit(l1, W - 24, phone.BOLD), W // 2, 130, BLACK, phone.BOLD)
        if l2:
            phone.text_c(_fit(l2, W - 24, phone.SMALL), W // 2, 166, GREY, phone.SMALL)
        if l3:
            phone.text_c(l3, W // 2, 186, BLACK, phone.BOLD)

    def draw_nav(self):
        y = HEADER_H + 2
        last = len(self.meta["days"]) - 1
        self.draw_nav_button(6, y, "<", self.idx > 0)
        self.draw_nav_button(W - 6 - BTN_W, y, ">", self.idx < last)
        iso = self.date()
        phone.fill_rect(6 + BTN_W + 2, y, W - 2 * (6 + BTN_W + 2), NAV_H - 4, BG)
        phone.text_c(_fit(_date_label(iso), W - 2 * (BTN_W + 10), phone.BOLD), W // 2, y + (NAV_H - 4) // 2,
                     ACCENT if iso == self.today else BLACK, phone.BOLD)

    def draw_nav_button(self, x, y, label, enabled):
        phone.round_rect(x, y, BTN_W, NAV_H - 4, 8, ACCENT if enabled else LIGHT)
        phone.text_c(label, x + BTN_W // 2, y + (NAV_H - 4) // 2, WHITE if enabled else GREY, phone.BOLD)

    def draw_list(self):
        phone.fill_rect(0, LIST_TOP, W, VISIBLE * ROW, BG)
        if self.lessons is None:
            self.draw_empty(i18n.t("edt_bad_day"))
        elif not self.lessons:
            self.draw_empty(i18n.t("edt_empty"))
        else:
            for i in range(self.scroll, min(len(self.lessons), self.scroll + VISIBLE)):
                self.draw_row(i)

    def draw_row(self, i):
        y = LIST_TOP + (i - self.scroll) * ROW
        it = self.lessons[i]
        cancelled = it["cancelled"]
        phone.fill_rect(TIME_W + 2, y + 3, 3, ROW - 7, RED if cancelled else ACCENT)
        phone.text_l(it["start"], 6, y + 11, GREY if cancelled else BLACK, phone.SMALL)
        phone.text_l(it["end"], 6, y + 25, GREY, phone.TINY)
        x = TIME_W + 10
        maxw = W - x - 6
        phone.text_l(_fit(it["subject"], maxw, phone.BOLD), x, y + 11, GREY if cancelled else BLACK, phone.BOLD)
        if cancelled:
            detail, color = i18n.t("edt_cancelled"), RED
        else:
            detail, color = " - ".join([s for s in (it["room"], it["teacher"]) if s]), GREY
            if it["note"]:
                detail = it["note"] if not detail else detail + " - " + it["note"]
        phone.text_l(_fit(detail, maxw, phone.SMALL), x, y + 26, color, phone.SMALL)
        phone.hline(6, W - 7, y + ROW - 1, LIGHT)

    def draw_footer(self):
        y = H - FOOT_H
        phone.fill_rect(0, y, W, FOOT_H, BG)
        if self.meta["synced"]:
            phone.text_l(_fit(i18n.t("edt_synced") % self.meta["synced"].replace("T", " "), 150, phone.TINY),
                         8, y + 9, GREY, phone.TINY)
        if self.today is None:
            phone.text_l(_fit(i18n.t("edt_date_unset"), 150, phone.TINY), 8, y + 21, RED, phone.TINY)
        if self.overflow():
            up_x, down_x = self._arrow_x()
            self.draw_arrow(up_x, y + 3, True, self.scroll > 0)
            self.draw_arrow(down_x, y + 3, False, self.scroll < self.max_scroll())

    def _arrow_x(self):
        down_x = W - 8 - ARROW_W
        return down_x - ARROW_W - 4, down_x

    def draw_arrow(self, x, y, up, enabled):
        h = FOOT_H - 8
        phone.round_rect(x, y, ARROW_W, h, 8, ACCENT if enabled else LIGHT)
        cx, cy = x + ARROW_W // 2, y + h // 2
        for k in range(6):
            yy = cy - 3 + k if up else cy + 3 - k
            phone.hline(cx - k, cx + k, yy, WHITE if enabled else GREY)

    # ---------- Interaction ----------

    def go(self, idx):
        idx = min(max(idx, 0), len(self.meta["days"]) - 1)
        if idx == self.idx:
            return
        self.idx = idx
        self.lessons = _load_day(self.date())
        self.scroll = 0
        self.draw()

    def go_today(self):
        if self.today:
            idx = _start_index(self.meta["days"], self.today)
            if idx != self.idx:
                self.go(idx)

    def scroll_by(self, direction):
        old = self.scroll
        self.scroll = min(max(self.scroll + direction * STEP, 0), self.max_scroll())
        if self.scroll != old:
            self.draw_list()
            self.draw_footer()

    def on_tap(self, x, y):
        if not self.meta:
            return
        if HEADER_H <= y < HEADER_H + NAV_H:
            if x < BTN_W + 10:
                self.go(self.idx - 1)
            elif x >= W - BTN_W - 10:
                self.go(self.idx + 1)
            else:
                self.go_today()
        elif y >= H - FOOT_H and self.overflow():
            up_x, down_x = self._arrow_x()
            if x >= up_x:
                self.scroll_by(-1 if x < down_x else 1)
