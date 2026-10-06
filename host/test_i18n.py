"""
Test du sélecteur de langue : accueil dans les 6 langues + écran Paramètres, captures dans
/tmp/i18n_*.ppm. Vérifie aussi que la persistance (lang.txt) fonctionne entre deux "démarrages".
"""
import sys, os, time
sys.path.append(".")
import phone, appkit, i18n

OUT = "/tmp/i18n_"


def shot(n):
    assert phone.sim_screenshot(OUT + n + ".ppm")


try:
    os.remove("lang.txt")
except OSError:
    pass

phone.init()

# ---------- 1. FR par défaut au 1er démarrage (pas de lang.txt) ----------
i18n.load()
assert i18n.get_lang() == "FR", i18n.get_lang()
i18n.push_to_home()
phone.home()
shot("00_fr_home")
print("1. langue par défaut FR (pas de lang.txt) : OK")

# ---------- 2. Accueil + Paramètres dans chaque langue ----------
import apps.parametres as P

for code in i18n.LANGS:
    i18n.set_lang(code)                     # persiste + retraduit l'accueil (C)
    phone.home()
    shot("home_%s" % code)

    app = P.App()
    appkit.header(app.display_title())
    app.draw()
    phone.flush()
    shot("params_%s" % code)
    print("2. langue %s (%s) : accueil + paramètres capturés" % (code, i18n.LANG_NAMES[code]))

# ---------- 3. Persistance : "redémarrage" doit relire la dernière langue choisie (CN) ----------
assert i18n.get_lang() == "CN"
i18n._current = "FR"                        # on simule un redémarrage : état mémoire perdu
lang = i18n.load()                          # doit relire lang.txt -> CN
assert lang == "CN", lang
print("3. persistance après \"redémarrage\" : OK -> relu", lang)

# ---------- 4. Tap réel sur un bouton de langue (Paramètres), pas juste set_lang() direct ----------
i18n.set_lang("FR")
app = P.App()
appkit.header(app.display_title())
app.draw()
phone.flush()
# on cherche la cellule "English" et on tape dessus comme un vrai doigt
idx = i18n.LANGS.index("EN")
cx, cy, cw, ch = app.lang_cell(idx)
app.on_tap(cx + cw // 2, cy + ch // 2)
assert i18n.get_lang() == "EN", i18n.get_lang()
shot("04_tap_english")
print("4. tap réel sur \"English\" dans Paramètres : OK -> langue =", i18n.get_lang())

i18n.set_lang("FR")   # on remet le français pour ne pas perturber d'autres tests
print("TOUS LES TESTS I18N OK")
