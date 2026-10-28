"""
Test de l'appli Lecteur PDF : liste, ouverture, pagination, défilement, erreurs (vide / chiffré /
police sans ToUnicode), mémorisation de la page lue. Captures dans /tmp/pdf_*.ppm.

Les PDF de test sont dans host/fixtures/ (régénérables : host/gen_pdf_fixtures.py) ; PDF_FIXTURES pour un autre dossier.
"""
import os, sys
sys.path.append(".")
import phone, appkit, i18n

FIX = os.getenv("PDF_FIXTURES", "../host/fixtures")
TMP = "/tmp/pdftest_dir"
OUT = "/tmp/pdf_"


def shot(n):
    assert phone.sim_screenshot(OUT + n + ".ppm")


def sh(cmd):
    os.system(cmd)


sh("rm -rf %s && mkdir -p %s" % (TMP, TMP))
for f in ("pdf_state.json",):
    try:
        os.remove(f)
    except OSError:
        pass

phone.init()
import apps.lecteur_pdf as L
L.PDF_DIR = TMP


def fresh():
    a = L.App()
    appkit.header(a.display_title())
    a.draw()
    phone.flush()
    return a


def tap_nav(app, zone):
    app.on_tap(zone * 60 + 30, L.H - 20)


def row_y(i):
    return L.LIST_TOP + i * L.ROW + 10


# ---------- 1. Dossier vide ----------
app = fresh()
assert app.files == []
shot("1_empty")
print("1. dossier vide : OK")

# ---------- 2. Liste ----------
for n in ("classic", "objstm", "truetype", "vide", "chiffre", "sansunicode", "long"):
    with open("%s/%s.pdf" % (FIX, n), "rb") as src, open("%s/%s.pdf" % (TMP, n), "wb") as dst:
        dst.write(src.read())
app = fresh()
names = [f[0] for f in app.files]
assert names == sorted(names) and len(names) == 7, names
shot("2_list")
print("2. liste triée :", names)

# ---------- 3. Ouvrir classic.pdf ----------
app.on_tap(100, row_y(names.index("classic.pdf")))
assert app.pdf is not None and app.pdf.n_pages == 3 and app.page == 0
assert app.lines and app.lines[0].startswith("Chapitre 1"), app.lines[:2]
shot("3_classic_p1")
print("3. ouverture :", app.lines[0], "| %d lignes" % len(app.lines))

# ---------- 4. Page suivante / précédente ----------
tap_nav(app, 3)
assert app.page == 1 and app.lines[0].startswith("Chapitre 2"), app.lines[0]
tap_nav(app, 3)
assert app.page == 2
tap_nav(app, 3)                       # dernière page : sans effet
assert app.page == 2
tap_nav(app, 0)
assert app.page == 1
print("4. pages suivante/précédente : OK")

# ---------- 5. « < Liste » ----------
app.on_tap(20, L.HEADER_H + 10)
assert app.pdf is None and app.name is None
shot("5_back_list")
print("5. retour liste : OK")

# ---------- 6. long.pdf : défilement dans la page puis passage à la page suivante ----------
app.on_tap(100, row_y(names.index("long.pdf")))
assert app.pdf.n_pages == 60
n_lines = len(app.lines)
assert n_lines > L.LINES, n_lines
tap_nav(app, 2)                       # ▼
assert app.top == L.STEP, app.top
shot("6_long_scrolled")
while app.top + L.LINES < len(app.lines):
    tap_nav(app, 2)
assert app.page == 0
tap_nav(app, 2)                       # ▼ en bas de page -> page suivante, en haut
assert app.page == 1 and app.top == 0
tap_nav(app, 1)                       # ▲ en haut de page -> fin de la page précédente
assert app.page == 0 and app.top == len(app.lines) - L.LINES, (app.page, app.top)
print("6. défilement et enchaînement de pages : OK")

# ---------- 7. Mémorisation de la page ----------
app.goto_page(41, 0)
assert app.dirty
app.on_tick(1000)
app.on_tick(1000 + L.SAVE_DELAY_MS + 100)
assert not app.dirty and app.state["long.pdf"] == 41
app.on_tap(20, L.HEADER_H + 10)
app2 = fresh()
app2.on_tap(100, row_y(names.index("long.pdf")))
assert app2.page == 41, app2.page
shot("7_resume_p42")
app2.on_tap(20, L.HEADER_H + 10)
print("7. reprise à la page 42 : OK")

# ---------- 8. Cas d'erreur ----------
app = fresh()
app.on_tap(100, row_y(names.index("vide.pdf")))
assert app.msg and app.msg[0] == "pdf_no_text", app.msg
shot("8a_no_text")
app.on_tap(20, L.HEADER_H + 10)
app.on_tap(100, row_y(names.index("chiffre.pdf")))
assert app.pdf is None and app.msg[0] == "pdf_encrypted", app.msg
shot("8b_encrypted")
app.on_tap(20, L.HEADER_H + 10)
assert app.name is None
app.on_tap(100, row_y(names.index("sansunicode.pdf")))
assert app.msg and app.msg[0] == "pdf_garbled", app.msg
shot("8c_garbled")
app.on_tap(20, L.HEADER_H + 10)
print("8. vide / chiffré / sans ToUnicode : OK")

# ---------- 9. TrueType (Type0 + ToUnicode) et translittération ----------
app.on_tap(100, row_y(names.index("truetype.pdf")))
txt = "\n".join(app.lines)
assert "é è ê à ç ù" in txt and "'" in txt and "fi" in txt and "EUR" in txt, txt[:300]
assert "?" not in txt
shot("9_truetype")
print("9. police TrueType, accents et ligatures : OK")

# ---------- 10. Langues : le titre et les messages existent partout ----------
for code in i18n.LANGS:
    for key in ("app_lecteur_pdf", "pdf_none", "pdf_hint", "pdf_page", "pdf_unit_kb", "pdf_loading",
                "pdf_no_text", "pdf_garbled", "pdf_encrypted", "pdf_bad", "pdf_truncated"):
        assert i18n.STRINGS[key].get(code), (key, code)
print("10. traductions complètes : OK")

# ---------- 11. Texte d'une page : caractères de contrôle filtrés sans liste d'un élément par caractère ----------
from apps import pdftext


def page_result(parts):
    it = pdftext._Interp(None, {})
    it.out = list(parts)
    return it.result()


assert page_result(["Bonjour", " ", "monde\n", "suite"]) == "Bonjour monde\nsuite"      # aucun contrôle
assert page_result(["  a\x00b\tc\x07\nd  "]) == "abc\nd"                                  # contrôles retirés
big = "é" * 300 + "\x01" + "x" * 300 + "\n" + "y" * 700                                  # plusieurs blocs de 256
assert page_result([big]) == "é" * 300 + "x" * 300 + "\n" + "y" * 700
assert page_result([]) == ""
print("11. filtrage des caractères de contrôle : OK")

try:
    os.remove("pdf_state.json")
except OSError:
    pass
print("TOUS LES TESTS PDF OK")
