"""
Test du clavier tactile appkit.Keyboard :
  1. logique pure (taper des lettres, majuscule, chiffres, effacer)
  2. correspondance tactile (on_tap sur les vraies coordonnées de touches)
  3. intégration réelle : accueil -> Notes -> "+ Nouvelle note" -> taper au doigt -> OK -> note ajoutée
Capture des écrans dans /tmp/kb_*.ppm.
"""
import sys, time
sys.path.append(".")
import phone, appkit

OUT = "/tmp/kb_"


def shot(n):
    assert phone.sim_screenshot(OUT + n + ".ppm")


def release():
    phone.sim_touch()
    phone.tap()


phone.init()

# ---------- 1. Logique pure ----------
kb = appkit.Keyboard("")
for ch in "bonjour":
    kb._key(ch)
assert kb.text == "bonjour", kb.text
kb._key("shift"); kb._key("X")                  # on_tap enverrait "X" (majuscule) quand shift est actif
assert kb.text == "bonjourX", kb.text          # majuscule ponctuelle puis retour minuscule
assert kb.shift is False, "shift doit se désactiver après une lettre"
kb._key("back")
assert kb.text == "bonjour", kb.text
kb._key("space"); kb._key("a")
assert kb.text == "bonjour a", kb.text
print("1. logique pure : OK ->", repr(kb.text))

# ---------- 2. Correspondance tactile (coordonnées réelles des touches) ----------
kb2 = appkit.Keyboard("")


def key_center(letter):
    for keys, y in kb2._rows():
        for x, w, kid, _label in keys:
            if kid == letter:
                return x + w // 2, y + appkit.KEY_H // 2
    raise AssertionError("touche introuvable : " + letter)


for ch in "salut":
    x, y = key_center(ch)
    assert kb2.on_tap(x, y) is True
assert kb2.text == "salut", kb2.text
sx, sy = key_center("space")
kb2.on_tap(sx, sy)
bx, by = key_center("back")
kb2.on_tap(bx, by)
assert kb2.text == "salut", kb2.text            # espace tapé puis effacé
kb2.draw()
phone.flush()
shot("2_keyboard_layout")
print("2. correspondance tactile : OK ->", repr(kb2.text))

# ---------- 3. Intégration réelle via Notes, boucle prompt_text pilotée au doigt ----------
phone.home()
phone.sim_touch(120, 70)                        # icône Notes
for _ in range(3):
    phone.home_poll(); time.sleep_ms(10)
release()

import apps.notes as N
app = N.App()
app.tab = N.TAB_NOTES                                # onglet Notes (texte libre), pas Tâches
n_before = len(app.items())
appkit.header(app.display_title())
app.draw()
phone.flush()
shot("3_notes_before")

WORD = "essai clavier"

# On ne peut pas monkeypatcher time.sleep_ms (module C intégré, attributs figés) ; on remplace
# donc appkit.prompt_text par une version qui rejoue EXACTEMENT la même logique (déjà vérifiée
# par les parties 1 et 2 ci-dessus : Keyboard.on_tap / .draw), mais pilotée par un plan de taps
# au lieu du vrai doigt. C'est un vrai appui simulé sur chaque touche, coordonnée par coordonnée.
real_prompt_text = appkit.prompt_text


def scripted_prompt_text(title="Texte", initial=""):
    appkit.header(title)
    kb = appkit.Keyboard(initial)
    kb.draw()
    phone.flush()
    for ch in WORD:
        x, y = key_center("space") if ch == " " else key_center(ch)
        assert kb.on_tap(x, y) is True
        phone.flush()
    ok_x, ok_y = appkit.W - 110 + 50, appkit.FIELD_Y + 42 + 15
    assert kb.on_tap(ok_x, ok_y) is True
    assert kb.done == "ok"
    return kb.text


appkit.prompt_text = scripted_prompt_text
app.on_tap(120, N.H - 20)                          # tap sur "+ Nouvelle note" -> déclenche le clavier ci-dessus
appkit.prompt_text = real_prompt_text
release()

shot("4_notes_after")
print("items :", app.items())
assert len(app.items()) == n_before + 1, app.items()
assert app.items()[-1]["title"] == WORD, app.items()[-1]
print("3. intégration clavier + Notes : OK -> note ajoutée :", repr(app.items()[-1]))

print("TOUS LES TESTS CLAVIER OK")

# ---------- 4. Page chiffres/symboles + majuscule ----------
kb3 = appkit.Keyboard("")
kb3._key("shift")
assert kb3.shift is True
r1, _ = kb3._rows()[0]
assert r1[0][2] == "A", r1[0]                   # rangée 1 en majuscules pendant que shift est actif
kb3._key("shift")                                # 2e appui : on annule la majuscule (pas de saisie)
assert kb3.shift is False
kb3._key("to_digits")                            # bascule vers la page chiffres (comme le bouton "123")
assert kb3.page == appkit.Keyboard.DIGITS
r1, _ = kb3._rows()[0]
assert r1[0][2] == "1", r1[0]
print("4. page chiffres + majuscule : OK")

# ---------- 5. Bascule 123/ABC/accents au doigt (tap réel), capture d'écran ----------
kb4 = appkit.Keyboard("")
kb4.draw()


def tap(kid):
    for keys, y in kb4._rows():
        for x, w, k, _label in keys:
            if k == kid:
                assert kb4.on_tap(x + w // 2, y + appkit.KEY_H // 2) is True
                return
    raise AssertionError("touche introuvable : " + kid)


tap("to_digits")
assert kb4.page == appkit.Keyboard.DIGITS
tap("7"); tap("9")
assert kb4.text == "79", kb4.text
tap("to_letters")
assert kb4.page == appkit.Keyboard.LETTERS
tap("b"); tap("o"); tap("n")
assert kb4.text == "79bon", kb4.text
phone.flush()
shot("5_keyboard_digits_then_letters")
print("5. bascule 123/ABC au doigt : OK ->", repr(kb4.text))

# ---------- 6. Page accents (touche « é ») : taper un mot accentué au doigt ----------
kb5 = appkit.Keyboard("")
kb5.draw()


def tap5(kid):
    for keys, y in kb5._rows():
        for x, w, k, _label in keys:
            if k == kid:
                assert kb5.on_tap(x + w // 2, y + appkit.KEY_H // 2) is True
                return
    raise AssertionError("touche introuvable : " + kid)


tap5("to_accents")
assert kb5.page == appkit.Keyboard.ACCENTS
tap5("é")
tap5("to_letters")
assert kb5.page == appkit.Keyboard.LETTERS
tap5("t")
tap5("to_accents")
tap5("é")
tap5("to_letters")
assert kb5.text == "été", kb5.text
phone.flush()
shot("6_keyboard_accents")
print("6. page accents au doigt : OK ->", repr(kb5.text))

print("TOUS LES TESTS CLAVIER OK")
