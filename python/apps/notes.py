"""
Notes : deux onglets - Tâches (à cocher) et Notes (titre + description) - avec ajout, édition,
suppression et consultation au clavier tactile. Sauvegardé sur la carte (notes_data.json) : les
tâches et notes survivent à un redémarrage.
"""
import json
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

TAB_TASKS = "tasks"
TAB_NOTES = "notes"


def _wrap(text, width):
    """Retour à la ligne aux espaces (les mots plus longs que `width` sont laissés tels quels)."""
    lines, cur = [], ""
    for word in text.split(" "):
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = cur + " " + word if cur else word
    if cur or not lines:
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


def _load():
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
        data.setdefault("tasks", [])
        data.setdefault("notes", [])
        for n in data["notes"]:                      # migration : anciennes notes {"text": ...}
            if "title" not in n:
                n["title"], n["body"] = n.pop("text", ""), n.get("body", "")
        return data
    except (OSError, ValueError):
        return _default_data()


def _save(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f)
    except OSError:
        pass                                       # pas grave : les changements resteront pour cette session


class App(appkit.App):
    title_key = "app_notes"

    def __init__(self):
        self.data = _load()
        self.tab = TAB_TASKS
        self.confirm_idx = None                     # index en attente de confirmation de suppression
        self.viewing = None                          # index de la note consultée (onglet Notes), ou None

    def items(self):
        return self.data[self.tab]

    def save(self):
        _save(self.data)

    # ---------- Dessin : liste ----------

    def draw(self):
        appkit.clear()
        if self.tab == TAB_NOTES and self.viewing is not None:
            self.draw_view()
        else:
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
        for i in range(len(self.items())):
            self.draw_row(i)

    def draw_row(self, i):
        items = self.items()
        if i >= len(items):
            return
        y = LIST_TOP + i * ROW
        if y + ROW > H - ADD_H:
            return                                  # liste trop longue pour l'écran (pas de défilement pour l'instant)
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
        text = label[:26]
        phone.text_l(text, x, cy, color, phone.SMALL)
        if self.tab == TAB_TASKS and it["done"]:
            phone.hline(x, x + phone.text_w(text, phone.SMALL), cy, GREY)

        confirming = self.confirm_idx == i
        dx = W - DEL_W
        phone.fill_rect(dx, y + 3, DEL_W - 6, ROW - 6, RED if confirming else LIGHT)
        phone.text_c("!" if confirming else "\u00d7", dx + (DEL_W - 6) // 2, cy,
                    WHITE if confirming else BLACK, phone.BOLD)

    def draw_add_button(self):
        y = H - ADD_H
        phone.fill_rect(0, y, W, ADD_H, BG)
        key = "notes_new_task_btn" if self.tab == TAB_TASKS else "notes_new_note_btn"
        appkit.button(14, y + 4, W - 28, ADD_H - 10, i18n.t(key), ACCENT)

    # ---------- Dessin : consultation d'une note ----------

    def draw_view(self):
        phone.fill_rect(0, HEADER_H, W, TAB_H, ACCENT)
        phone.text_l(i18n.t("notes_back_to_list"), 8, HEADER_H + TAB_H // 2, WHITE, phone.SMALL)

        note = self.data["notes"][self.viewing]
        y = LIST_TOP
        phone.text_l(note["title"][:26], 12, y, BLACK, phone.BOLD)
        y += 28
        phone.hline(12, W - 13, y, LIGHT)
        y += 12
        for line in _wrap(note.get("body", ""), 30):
            if y > H - ADD_H - 16:
                break
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
                self.confirm_idx = None
                self.draw()
            return

        if y >= H - ADD_H:
            self.add_item()
            return

        items = self.items()
        i = (y - LIST_TOP) // ROW
        if not (0 <= i < len(items)):
            return

        if x >= W - DEL_W:                          # bouton de suppression : 1er tap = confirmation
            if self.confirm_idx == i:
                del items[i]
                self.save()
                self.confirm_idx = None
                self.draw_list()
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
            self.draw()

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
        appkit.header(self.display_title())            # le clavier avait pris tout l'écran
        self.draw()

    def edit_item(self, i):
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
