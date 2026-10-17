"""
Régressions de l'appli Notes : réaffichage après édition d'une tâche, listes plus longues que l'écran
(défilement), texte trop large (troncature / retour à la ligne en pixels), sauvegarde atomique.

    cd python
    SDL_VIDEODRIVER=dummy ../build/micropython/ports/unix/build-standard/micropython ../host/test_notes_scroll.py
"""
import os, sys
sys.path.append(".")
import phone, appkit

OUT = "/tmp/notes_scroll.ppm"


def pix(x, y):
    """Couleur (r,g,b) du pixel (x,y) de l'écran simulé."""
    assert phone.sim_screenshot(OUT)
    with open(OUT, "rb") as f:
        data = f.read()
    # en-tête "P6\n240 320\n255\n"
    off = data.index(b"255\n") + 4
    i = off + (y * phone.WIDTH + x) * 3
    return data[i], data[i + 1], data[i + 2]


def is_accent(c):
    return c[2] > 150 and c[0] < 130 and c[1] < 110


def release():
    phone.sim_touch()
    phone.tap()


for f in ("notes_data.json", "notes_data.json.tmp"):
    try:
        os.remove(f)
    except OSError:
        pass

phone.init()
import apps.notes as N

W, H = appkit.W, appkit.H
real_prompt = appkit.prompt_text


def fake_prompt(answer):
    def fp(title=None, initial=""):
        appkit.header(title)                                         # le clavier prend tout l'écran
        phone.fill_rect(0, appkit.HEADER_H, W, H - appkit.HEADER_H, phone.rgb(255, 255, 255))
        return answer
    return fp


# ---------- 1. Après l'édition d'une tâche (tap sur son texte), la liste est réaffichée ----------
app = N.App()
appkit.header(app.display_title())
app.draw()
appkit.prompt_text = fake_prompt("tache modifiee")
app.on_tap(100, N.LIST_TOP + N.ROW // 2)
appkit.prompt_text = real_prompt
assert app.items()[0]["text"] == "tache modifiee"
assert is_accent(pix(5, N.HEADER_H + 3)), "la liste n'a pas été redessinée après l'édition (clavier resté à l'écran)"
print("1. liste réaffichée après édition d'une tâche : OK")

# ---------- 2. Liste plus longue que l'écran : tout est atteignable par défilement ----------
app.data["tasks"] = [{"text": "t%d" % i, "done": False} for i in range(14)]
app.scroll = 0
app.draw()
assert N.VISIBLE >= 5
last = len(app.items()) - 1
for _ in range(10):                                        # flèche bas (en bas à droite)
    app.on_tap(W - 14 - 10, H - 20)
assert app.scroll == app.max_scroll() and app.max_scroll() == len(app.items()) - N.VISIBLE
row_y = N.LIST_TOP + (N.VISIBLE - 1) * N.ROW + N.ROW // 2     # dernière ligne visible = dernier élément
app.on_tap(14, row_y)                                      # case à cocher
assert app.items()[last]["done"] is True, "le dernier élément n'est pas atteignable"
for _ in range(10):                                        # flèche haut
    app.on_tap(W - 14 - 2 * N.ARROW_W - 4 + 10, H - 20)
assert app.scroll == 0
print("2. défilement (%d lignes visibles, %d éléments) : OK" % (N.VISIBLE, len(app.items())))

# ---------- 3. Ajout dans une liste pleine : le nouvel élément est visible (défilement en fin) ----------
appkit.prompt_text = fake_prompt("dernier ajout")
app.on_tap(30, H - 20)                                     # bouton "+ Nouvelle tâche" (à gauche des flèches)
appkit.prompt_text = real_prompt
assert app.items()[-1]["text"] == "dernier ajout"
assert app.scroll == app.max_scroll()
print("3. nouvel élément visible après ajout : OK")

# ---------- 4. Suppression en bas de liste : le défilement reste valide ----------
n = len(app.items())
delx = W - N.DEL_W + 10
row_y = N.LIST_TOP + (N.VISIBLE - 1) * N.ROW + N.ROW // 2
app.on_tap(delx, row_y)
app.on_tap(delx, row_y)
assert len(app.items()) == n - 1 and 0 <= app.scroll <= app.max_scroll()
print("4. suppression + défilement : OK")

# ---------- 5. Texte trop large : jamais plus large que la zone ----------
s = "Wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww"
assert phone.text_w(N._fit(s, 150, phone.SMALL), phone.SMALL) <= 150
body = "un_mot_vraiment_tres_long_sans_aucun_espace_" * 3 + " et des mots normaux ensuite"
lines = N._wrap_px(body, W - 24, phone.SMALL)
assert all(phone.text_w(l, phone.SMALL) <= W - 24 for l in lines), lines
assert "".join(lines).replace(" ", "") == body.replace(" ", "")
print("5. troncature / retour à la ligne en pixels : OK")

# ---------- 6. Sauvegarde atomique : pas de fichier .tmp qui traîne, rechargement correct ----------
app.save()
assert not os.path.exists("notes_data.json.tmp") if hasattr(os, "path") else True
app2 = N.App()
assert app2.items() == app.items()
print("6. sauvegarde atomique : OK")

# ---------- 7. Fichier corrompu / structure inattendue : pas de plantage ----------
for junk in ("[1, 2, 3]", '{"tasks": "oups", "notes": [5, {"title": 3}]}', "{pas du json"):
    with open("notes_data.json", "w") as f:
        f.write(junk)
    a = N.App()
    appkit.header(a.display_title())
    a.draw()
    a.on_tap(3 * W // 4, N.HEADER_H + 10)
print("7. fichier corrompu : OK")

os.remove("notes_data.json")
print("TOUS LES TESTS NOTES (DEFILEMENT) OK")
