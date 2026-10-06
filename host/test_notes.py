"""
Test de l'appli Notes v3 : onglet Tâches inchangé ; onglet Notes avec titre+description,
ajout, consultation ("voir"), édition depuis la consultation, suppression, persistance.
Captures dans /tmp/notes_*.ppm.
"""
import os, sys, time
sys.path.append(".")
import phone, appkit, i18n

OUT = "/tmp/notes_"


def shot(n):
    assert phone.sim_screenshot(OUT + n + ".ppm")


def release():
    phone.sim_touch()
    phone.tap()


try:
    os.remove("notes_data.json")
except OSError:
    pass

phone.init()
import apps.notes as N

# ---------- Petit outil : scripte un prompt_text (une frappe touche par touche + OK) ----------
real_prompt_text = appkit.prompt_text


def make_scripted(words):
    """Renvoie un prompt_text qui tape successivement chaque mot de `words` (une pile), dans l'ordre
    des appels (utile car add/edit d'une note appelle prompt_text 2 fois : titre puis description)."""
    queue = list(words)

    def scripted(title=None, initial=""):
        word = queue.pop(0)
        appkit.header(title)
        kb = appkit.Keyboard(initial)
        kb.draw()
        phone.flush()
        for _ in range(len(initial)):                # efface le texte pré-rempli avant de taper le nouveau
            for keys, y in kb._rows():
                for kx, kw, kid, _label in keys:
                    if kid == "back":
                        assert kb.on_tap(kx + kw // 2, y + appkit.KEY_H // 2) is True
                        break
                else:
                    continue
                break
        for ch in word:
            for keys, y in kb._rows():
                for kx, kw, kid, _label in keys:
                    if kid == ("space" if ch == " " else ch):
                        assert kb.on_tap(kx + kw // 2, y + appkit.KEY_H // 2) is True
                        break
                else:
                    continue
                break
        ok_x, ok_y = appkit.W - 110 + 50, appkit.FIELD_Y + 42 + 15
        assert kb.on_tap(ok_x, ok_y) is True
        assert kb.done == "ok"
        return kb.text
    return scripted


# ---------- 1. Démarrage : onglet Tâches par défaut, Notes vide ----------
app = N.App()
appkit.header(app.display_title())
app.draw()
phone.flush()
assert app.tab == N.TAB_TASKS and app.data["notes"] == []
print("1. démarrage OK")

# ---------- 2. Onglet Notes -> ajouter une note (titre + description) ----------
app.on_tap(3 * appkit.W // 4, N.HEADER_H + 10)         # bascule sur Notes
shot("1_notes_empty")

appkit.prompt_text = make_scripted(["courses", "acheter du pain et du cafe"])
app.on_tap(120, N.H - 20)                              # "+ Nouvelle note"
appkit.prompt_text = real_prompt_text
release()
shot("2_note_added")
assert app.data["notes"] == [{"title": "courses", "body": "acheter du pain et du cafe"}], app.data["notes"]
print("2. ajout titre+description : OK ->", app.data["notes"][0])

# ---------- 3. Tap sur la ligne -> écran de consultation (pas d'édition directe) ----------
row_y = N.LIST_TOP + N.ROW // 2
app.on_tap(100, row_y)
assert app.viewing == 0
shot("3_view")
print("3. consultation ('voir') : OK")

# ---------- 4. Depuis la consultation : "Modifier" -> ré-édite titre + description ----------
appkit.prompt_text = make_scripted(["courses urgentes", "pain cafe et lait"])
app.on_tap(120, N.H - 20)                               # bouton "Modifier" (bas de l'écran de cons.)
appkit.prompt_text = real_prompt_text
shot("4_view_edited")
assert app.data["notes"][0] == {"title": "courses urgentes", "body": "pain cafe et lait"}, app.data["notes"][0]
assert app.viewing == 0                                  # on reste sur la consultation, mise à jour
print("4. édition depuis la consultation : OK ->", app.data["notes"][0])

# ---------- 5. "< Liste" -> retour à la liste (sans quitter l'appli) ----------
app.on_tap(20, N.HEADER_H + 10)
assert app.viewing is None
shot("5_back_to_list")
print("5. retour à la liste : OK")

# ---------- 6. Suppression (confirmation en 2 taps), comme pour les tâches ----------
del_x = appkit.W - N.DEL_W + 10
app.on_tap(del_x, row_y)
assert app.confirm_idx == 0
app.on_tap(del_x, row_y)
assert app.data["notes"] == []
print("6. suppression d'une note : OK")

# ---------- 7. Persistance : titre+description survivent à un rechargement ----------
appkit.prompt_text = make_scripted(["idee", "une description"])
app.on_tap(120, N.H - 20)
appkit.prompt_text = real_prompt_text
release()

app2 = N.App()
assert app2.data["notes"] == [{"title": "idee", "body": "une description"}], app2.data["notes"]
print("7. persistance titre+description : OK ->", app2.data["notes"])

# ---------- 8. Migration : anciennes notes {"text": ...} -> {"title", "body"} ----------
import json
with open("notes_data.json", "w") as f:
    json.dump({"tasks": [], "notes": [{"text": "ancienne note"}]}, f)
app3 = N.App()
assert app3.data["notes"] == [{"title": "ancienne note", "body": ""}], app3.data["notes"]
print("8. migration ancien format : OK ->", app3.data["notes"])

os.remove("notes_data.json")
print("TOUS LES TESTS NOTES OK")
