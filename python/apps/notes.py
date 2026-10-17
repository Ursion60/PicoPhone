"""
Notes : deux onglets - Tâches (à cocher) et Notes (titre + description) - avec ajout, édition,
suppression et consultation au clavier tactile. Sauvegardé sur la carte (notes_data.json) : les
tâches et notes survivent à un redémarrage.
"""
import json
import os
import phone
import appkit
import i18n
from appkit import W, H, BG, WHITE, BLACK, GREY, GREEN, RED, LIGHT, ACCENT, HEADER_H

DATA_FILE = "notes_data.json"

TAB_H = 30                    # barre d'onglets (ou barre "< Liste" en consultation), sous l'en-tête
LIST_TOP = HEADER_H + TAB_H + 6
ROW = 34
ADD_H = 40                    # bouton du bas : "+ ..." (liste) ou "Modifier" (consultation)
CHK_W = 26                    # largeur de la case à cocher (onglet Tâches)
DEL_W = 34                    # largeur du bouton de suppression, à droite de chaque ligne
ARROW_W = 34                  # boutons de défilement (liste plus longue que l'écran), à droite du bouton "+"
VISIBLE = (appkit.H - ADD_H - LIST_TOP) // ROW      # lignes visibles à la fois
STEP = max(1, VISIBLE // 2)                          # une flèche fait défiler d'une demi-page

TAB_TASKS = "tasks"
TAB_NOTES = "notes"


def _fit(text, maxw, font):
    """Tronque `text` (avec "..") pour qu'il tienne dans `maxw` pixels : jamais de débordement sur le
    bouton de suppression, quelle que soit la largeur des lettres (W, caractères CJK...)."""
    if phone.text_w(text, font) <= maxw:
        return text
    while text and phone.text_w(text + "..", font) > maxw:
        text = text[:-1]
    return text + ".."


def _wrap_px(text, maxw, font):
    """Retour à la ligne en pixels, aux espaces ; un mot plus large que `maxw` est coupé."""
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
    return lines


def _default_data():
    return {
        "tasks": [
            {"text": i18n.t("notes_demo_1"), "done": True},
            {"text": i18n.t("notes_demo_2"), "done": True},
            {"text": i18n.t("notes_demo_3"), "done": False},
        ],
        "notes": [],
    }


def _clean(data):
    """Valide la structure lue (fichier abîmé ou d'un ancien format) : jamais d'exception plus tard."""
    if not isinstance(data, dict):
        raise ValueError("structure inattendue")
    tasks, notes = [], []
    raw = data.get("tasks")
    for t in (raw if isinstance(raw, list) else []):
        if isinstance(t, dict):
            tasks.append({"text": str(t.get("text", "")), "done": bool(t.get("done"))})
    raw = data.get("notes")
    for n in (raw if isinstance(raw, list) else []):
        if isinstance(n, dict):                      # migration : anciennes notes {"text": ...}
            title = n["title"] if "title" in n else n.get("text", "")
            notes.append({"title": str(title), "body": str(n.get("body", ""))})
    return {"tasks": tasks, "notes": notes}


def _load():
    for name in (DATA_FILE, DATA_FILE + ".tmp"):     # le .tmp : reste d'une coupure pendant la sauvegarde
        try:
            with open(name) as f:
                return _clean(json.load(f))
        except (OSError, ValueError):
            pass
    return _default_data()


def _save(data):
    """Écrit dans un fichier temporaire puis le renomme : une coupure de courant en pleine écriture ne
    détruit plus toutes les notes."""
    tmp = DATA_FILE + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(data, f)
        try:
            os.rename(tmp, DATA_FILE)
        except OSError:
            os.remove(DATA_FILE)
            os.rename(tmp, DATA_FILE)
    except OSError:
        pass                                       # pas grave : les changements resteront pour cette session


class App(appkit.App):
    title_key = "app_notes"

    def __init__(self):
        self.data = _load()
        self.tab = TAB_TASKS
        self.confirm_idx = None                     # index en attente de confirmation de suppression
        self.viewing = None                          # index de la note consultée (onglet Notes), ou None
        self.scroll = 0                              # index de la 1re ligne affichée

    def items(self):
        return self.data[self.tab]

    def save(self):
        _save(self.data)

    def max_scroll(self):
        return max(0, len(self.items()) - VISIBLE)

    def overflow(self):
        return len(self.items()) > VISIBLE

    def clamp_scroll(self):
        self.scroll = min(max(self.scroll, 0), self.max_scroll())

    def scroll_by(self, direction):
        old = self.scroll
        self.scroll += direction * STEP
        self.clamp_scroll()
        if self.scroll != old:
            self.confirm_idx = None
            self.draw_list()
            self.draw_add_button()

    # ---------- Dessin : liste ----------

    def draw(self):
        appkit.clear()
        if self.tab == TAB_NOTES and self.viewing is not None:
            self.draw_view()
        else:
            self.clamp_scroll()
            self.draw_tabs()
            self.draw_list()
            self.draw_add_button()

    def draw_tabs(self):
        half = W // 2
        for i, (tab, key) in enumerate(((TAB_TASKS, "tab_tasks"), (TAB_NOTES, "tab_notes"))):
            active = tab == self.tab
            x = i * half
            phone.fill_rect(x, HEADER_H, half, TAB_H, ACCENT if active else LIGHT)
            phone.text_c(i18n.t(key), x + half // 2, HEADER_H + TAB_H // 2,
                        WHITE if active else BLACK, phone.SMALL)

    def draw_list(self):
        top, bottom = LIST_TOP, H - ADD_H
        phone.fill_rect(0, top, W, bottom - top, BG)
        for i in range(self.scroll, min(len(self.items()), self.scroll + VISIBLE)):
            self.draw_row(i)

    def draw_row(self, i):
        items = self.items()
        r = i - self.scroll
        if i >= len(items) or r < 0 or r >= VISIBLE:
            return                                  # ligne hors de la fenêtre affichée
        y = LIST_TOP + r * ROW
        it = items[i]
        cy = y + ROW // 2
        phone.fill_rect(0, y, W, ROW, BG)

        x = 8
        if self.tab == TAB_TASKS:
            phone.rect(x, cy - 9, 18, 18, BLACK)
            if it["done"]:
                phone.fill_rect(x + 4, cy - 5, 10, 10, GREEN)
            x += CHK_W

        label = it["title"] if self.tab == TAB_NOTES else it["text"]
        color = GREY if (self.tab == TAB_TASKS and it["done"]) else BLACK
        text = _fit(label, (W - DEL_W - 4) - x, phone.SMALL)     # jamais sous le bouton de suppression
        phone.text_l(text, x, cy, color, phone.SMALL)
        if self.tab == TAB_TASKS and it["done"]:
            phone.hline(x, x + phone.text_w(text, phone.SMALL), cy, GREY)

        confirming = self.confirm_idx == i
        dx = W - DEL_W
        phone.fill_rect(dx, y + 3, DEL_W - 6, ROW - 6, RED if confirming else LIGHT)
        phone.text_c("!" if confirming else "\u00d7", dx + (DEL_W - 6) // 2, cy,
                    WHITE if confirming else BLACK, phone.BOLD)

    def _arrow_x(self):
        """Abscisses des flèches haut / bas (à droite du bouton \"+\")."""
        down_x = W - 14 - ARROW_W
        return down_x - ARROW_W - 4, down_x

    def draw_add_button(self):
        y = H - ADD_H
        phone.fill_rect(0, y, W, ADD_H, BG)
        key = "notes_new_task_btn" if self.tab == TAB_TASKS else "notes_new_note_btn"
        width = W - 28
        if self.overflow():
            width -= 2 * ARROW_W + 8
            up_x, down_x = self._arrow_x()
            self.draw_arrow(up_x, y + 4, True, self.scroll > 0)
            self.draw_arrow(down_x, y + 4, False, self.scroll < self.max_scroll())
        appkit.button(14, y + 4, width, ADD_H - 10, i18n.t(key), ACCENT)

    def draw_arrow(self, x, y, up, enabled):
        h = ADD_H - 10
        phone.round_rect(x, y, ARROW_W, h, 8, ACCENT if enabled else LIGHT)
        cx, cy = x + ARROW_W // 2, y + h // 2
        for k in range(7):                           # petit triangle
            yy = cy - 3 + k if up else cy + 3 - k
            phone.hline(cx - k, cx + k, yy, WHITE if enabled else GREY)

    # ---------- Dessin : consultation d'une note ----------

    def draw_view(self):
        phone.fill_rect(0, HEADER_H, W, TAB_H, ACCENT)
        phone.text_l(i18n.t("notes_back_to_list"), 8, HEADER_H + TAB_H // 2, WHITE, phone.SMALL)

        note = self.data["notes"][self.viewing]
        y = LIST_TOP
        phone.text_l(_fit(note["title"], W - 24, phone.BOLD), 12, y, BLACK, phone.BOLD)
        y += 28
        phone.hline(12, W - 13, y, LIGHT)
        y += 12
        lines = _wrap_px(note.get("body", ""), W - 24, phone.SMALL)
        room = (H - ADD_H - 16 - y) // 18 + 1
        if len(lines) > room:                        # description trop longue : on le signale par "..."
            lines = lines[:room]
            lines[-1] = _fit(lines[-1] + "...", W - 24, phone.SMALL)
        for line in lines:
            phone.text_l(line, 12, y, BLACK, phone.SMALL)
            y += 18

        appkit.button(14, H - ADD_H, W - 28, ADD_H - 10, i18n.t("notes_edit_title"), ACCENT)

    # ---------- Interaction ----------

    def on_tap(self, x, y):
        if self.tab == TAB_NOTES and self.viewing is not None:
            self.on_tap_view(x, y)
            return

        if HEADER_H <= y < HEADER_H + TAB_H:
            new_tab = TAB_TASKS if x < W // 2 else TAB_NOTES
            if new_tab != self.tab:
                self.tab = new_tab
                self.scroll = 0
                self.confirm_idx = None
                self.draw()
            return

        if y >= H - ADD_H:
            if self.overflow():
                up_x, down_x = self._arrow_x()
                if x >= up_x:
                    self.scroll_by(-1 if x < down_x else 1)
                    return
            self.add_item()
            return

        items = self.items()
        row = (y - LIST_TOP) // ROW
        i = self.scroll + row
        if y < LIST_TOP or not (0 <= row < VISIBLE) or i >= len(items):
            return

        if x >= W - DEL_W:                          # bouton de suppression : 1er tap = confirmation
            if self.confirm_idx == i:
                del items[i]
                self.save()
                self.confirm_idx = None
                self.clamp_scroll()
                self.draw_list()
                self.draw_add_button()              # les flèches apparaissent/disparaissent selon la longueur
            else:
                old = self.confirm_idx
                self.confirm_idx = i
                if old is not None:
                    self.draw_row(old)
                self.draw_row(i)
            return

        if self.confirm_idx is not None:             # un tap ailleurs annule une suppression en attente
            old = self.confirm_idx
            self.confirm_idx = None
            self.draw_row(old)

        if self.tab == TAB_TASKS:
            if x < 8 + CHK_W:
                items[i]["done"] = not items[i]["done"]
                self.save()
                self.draw_row(i)
            else:
                self.edit_item(i)                    # tâches : tap sur le texte -> édition directe
        else:
            self.viewing = i                          # notes : tap -> consultation (voir), pas édition directe
            self.draw()

    def on_tap_view(self, x, y):
        if HEADER_H <= y < HEADER_H + TAB_H and x < W // 2:
            self.viewing = None
            self.draw()
            return
        if y >= H - ADD_H:
            self.edit_item(self.viewing)

    def add_item(self):
        self.confirm_idx = None
        if self.tab == TAB_TASKS:
            text = appkit.prompt_text(i18n.t("notes_new_task_title"))
            if text:
                self.items().append({"text": text, "done": False})
                self.save()
        else:
            title = appkit.prompt_text(i18n.t("notes_title_prompt"))
            if title:
                body = appkit.prompt_text(i18n.t("notes_body_prompt"))
                if body is not None:
                    self.items().append({"title": title, "body": body})
                    self.save()
        self.scroll = self.max_scroll()               # montre le nouvel élément (le dernier)
        appkit.header(self.display_title())            # le clavier avait pris tout l'écran
        self.draw()

    def edit_item(self, i):
        if not (0 <= i < len(self.items())):
            return
        it = self.items()[i]
        if self.tab == TAB_TASKS:
            text = appkit.prompt_text(i18n.t("notes_edit_title"), it["text"])
            if text:
                it["text"] = text
                self.save()
        else:
            title = appkit.prompt_text(i18n.t("notes_title_prompt"), it["title"])
            if title:
                body = appkit.prompt_text(i18n.t("notes_body_prompt"), it["body"])
                if body is not None:
                    it["title"], it["body"] = title, body
                    self.save()
        appkit.header(self.display_title())
        self.draw()                                   # le clavier avait pris tout l'écran : on redessine
