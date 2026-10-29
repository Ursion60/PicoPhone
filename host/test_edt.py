"""
Tests de l'appli EDT : pas de données, jour avec cours, navigation, défilement, cours annulé, fichiers
abîmés, textes trop longs, date de la carte non réglée, traductions. Captures dans /tmp/edt_*.ppm.

    cd python
    SDL_VIDEODRIVER=dummy ../build/micropython/ports/unix/build-standard/micropython ../host/test_edt.py
"""
import os, sys, json
sys.path.append(".")
import phone, appkit, i18n

OUT = "/tmp/edt_"
DIR = "edt"

phone.init()
import apps.edt as E

W, H = appkit.W, appkit.H


def clean():
    try:
        for name in os.listdir(DIR):
            os.remove(DIR + "/" + name)
        os.rmdir(DIR)
    except OSError:
        pass


def write(name, obj):
    try:
        os.mkdir(DIR)
    except OSError:
        pass
    with open(DIR + "/" + name, "w") as f:
        if isinstance(obj, str):
            f.write(obj)                           # contenu brut : fichier volontairement abîmé
        else:
            json.dump(obj, f)


def lesson(start, end, subject, room="", teacher="", cancelled=False, note=""):
    return {"start": start, "end": end, "subject": subject, "room": room, "teacher": teacher,
            "cancelled": cancelled, "note": note}


def open_app(today):
    E._today = lambda: today
    app = E.App()
    appkit.header(app.display_title())
    app.draw()
    return app


def shot(name):
    assert phone.sim_screenshot(OUT + name + ".ppm")
    with open(OUT + name + ".ppm", "rb") as f:
        data = f.read()
    return data, data.index(b"255\n") + 4          # en-tête "P6\n240 320\n255\n"


def pix(img, x, y):
    data, off = img
    i = off + (y * W + x) * 3
    return data[i], data[i + 1], data[i + 2]


def near(c, ref, tol=14):
    return all(abs(a - b) <= tol for a, b in zip(c, ref))


def count(img, x0, y0, x1, y1, ref, tol=14):
    return sum(1 for y in range(y0, y1) for x in range(x0, x1) if near(pix(img, x, y), ref, tol))


BG = (236, 236, 236)
RED = (225, 40, 40)
ACCENT = (90, 70, 200)


def row_y(r):
    return E.LIST_TOP + r * E.ROW


clean()

# ---------- 1. Fonctions de date / validation ----------
assert E._weekday(2026, 10, 28) == 2                      # mercredi
assert E._weekday(2000, 1, 1) == 5                        # samedi
assert E._weekday(2024, 2, 29) == 3                       # jeudi
assert E._weekday(2026, 10, 26) == 0                      # lundi
assert E._parse_date("2024-02-29") == (2024, 2, 29)
for bad in ("2026-02-29", "2026-13-01", "2026-00-10", "2026-1-01", "20261001", "abcd-ef-gh", "1999-01-01", None, 12):
    assert E._parse_date(bad) is None, bad
assert E._valid_time("08:00") and E._valid_time("23:59")
for bad in ("8:00", "24:00", "12:60", "ab:cd", "12-30", None, 830):
    assert not E._valid_time(bad), bad
print("1. dates et heures : OK")

# ---------- 2. Aucune donnée ----------
app = open_app("2026-10-28")
assert app.meta is None
app.on_tap(100, E.HEADER_H + 10)                          # ne plante pas
app.on_tap(100, H - 10)
img = shot("1_none")
assert count(img, 20, 110, W - 20, 200, (20, 20, 20), 40) > 30      # le message est bien écrit
print("2. aucune donnée : OK")

# ---------- 3. Jours : normal, vide, abîmé, absent ----------
mon = [lesson("08:00", "08:55", "Mathématiques", "B12", "M. Dupont"),
       lesson("09:00", "09:55", "Français", "A03", "Mme Martin"),
       lesson("10:10", "11:05", "Anglais", "C21", "Mr Smith")]
wed = [lesson("13:00", "13:55", "EPS", "Gymnase", "M. Leroy"),                 # désordonnés exprès
       lesson("08:00", "08:55", "Mathématiques", "B12", "M. Dupont"),
       lesson("09:00", "09:55", "Français", cancelled=True),
       lesson("10:10", "11:05", "Histoire-Géographie et enseignement moral et civique", "A01",
              "Mme Montgomery-Wellington-Duchesne"),
       lesson("11:10", "12:05", "Anglais LV1", "C21", "Mr Smith", note="Salle changée"),
       lesson("14:00", "14:55", "Physique-Chimie", "L2"),
       lesson("15:10", "16:05", "SVT", "L3"),
       lesson("16:10", "17:05", "Technologie", "T1"),
       lesson("17:10", "18:05", "Étude"),
       lesson("25:00", "26:00", "Heure invalide"),                              # ignorée
       "pas un dictionnaire"]                                                   # ignoré
write("meta.json", {"v": 1, "synced": "2026-10-28T08:12", "source": "pronote",
                    "days": ["2026-10-28", "2026-10-26", "2026-10-27", "2026-10-29", "2026-10-30", "pas une date"]})
write("2026-10-26.json", {"lessons": mon})
write("2026-10-27.json", {"lessons": []})
write("2026-10-28.json", {"lessons": wed})
write("2026-10-29.json", "{ceci n'est pas du json")
# 2026-10-30.json : absent

app = open_app("2026-10-28")
assert app.meta["days"] == ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"], app.meta
assert app.date() == "2026-10-28"                                   # ouvre sur aujourd'hui
assert len(app.lessons) == 9, len(app.lessons)                      # 11 entrées, 2 invalides ignorées
assert [x["start"] for x in app.lessons] == sorted(x["start"] for x in app.lessons)     # triées
assert E._date_label("2026-10-28") == "Mer 28 oct.", E._date_label("2026-10-28")
assert app.overflow() and app.max_scroll() == 9 - E.VISIBLE
img = shot("2_wed_fr")
# la date du jour est en couleur d'accent
assert count(img, 40, E.HEADER_H + 4, W - 40, E.HEADER_H + 28, ACCENT, 40) > 20
# le cours annulé (2e ligne, 09:00) a une barre rouge ; le 1er non
assert near(pix(img, E.TIME_W + 3, row_y(1) + 10), RED), pix(img, E.TIME_W + 3, row_y(1) + 10)
assert near(pix(img, E.TIME_W + 3, row_y(0) + 10), ACCENT), pix(img, E.TIME_W + 3, row_y(0) + 10)
# le texte long est tronqué : rien ne dépasse dans la marge de droite (cours 3 : matière et enseignante très longues)
assert count(img, W - 5, row_y(2), W, row_y(2) + E.ROW - 2, (60, 60, 60), 70) == 0
print("3. jour avec cours, tri, annulé, textes longs : OK")

# ---------- 4. Navigation ----------
app.on_tap(10, E.HEADER_H + 10)                                     # ◀
assert app.date() == "2026-10-27" and app.lessons == []
shot("3_empty")
app.on_tap(10, E.HEADER_H + 10)
assert app.date() == "2026-10-26" and len(app.lessons) == 3
app.on_tap(10, E.HEADER_H + 10)                                     # au début : reste sur place
assert app.date() == "2026-10-26"
for expect in ("2026-10-27", "2026-10-28", "2026-10-29"):
    app.on_tap(W - 10, E.HEADER_H + 10)                             # ▶
    assert app.date() == expect, app.date()
assert app.lessons is None                                          # JSON abîmé : signalé, pas d'exception
img = shot("4_bad")
assert count(img, 20, 110, W - 20, 150, (20, 20, 20), 40) > 30
app.on_tap(W - 10, E.HEADER_H + 10)
assert app.date() == "2026-10-30" and app.lessons is None           # fichier absent
app.on_tap(W - 10, E.HEADER_H + 10)
assert app.date() == "2026-10-30"                                   # à la fin : reste sur place
app.on_tap(W // 2, E.HEADER_H + 10)                                 # tap sur la date : retour à aujourd'hui
assert app.date() == "2026-10-28" and len(app.lessons) == 9
print("4. navigation (vide, abîmé, absent, bornes, retour à aujourd'hui) : OK")

# ---------- 5. Défilement ----------
up_x, down_x = app._arrow_x()
fy = H - E.FOOT_H + 8
app.on_tap(down_x + 5, fy)
assert app.scroll == E.STEP, app.scroll
app.on_tap(down_x + 5, fy)
assert app.scroll == app.max_scroll()                               # borné
app.on_tap(down_x + 5, fy)
assert app.scroll == app.max_scroll()
img = shot("5_scrolled")
app.on_tap(up_x + 5, fy)
assert app.scroll == app.max_scroll() - E.STEP or app.scroll == 0
app.on_tap(up_x + 5, fy)
app.on_tap(up_x + 5, fy)
assert app.scroll == 0
app.on_tap(20, fy)                                                  # à gauche des flèches : rien
assert app.scroll == 0
print("5. défilement : OK")

# ---------- 6. Horloge de la carte non réglée ----------
app = open_app(None)
assert app.today is None
assert app.date() == "2026-10-28"                                   # repli : date de la dernière synchro
img = shot("6_unset")
assert count(img, 8, H - E.FOOT_H + 14, 170, H - 2, RED, 40) > 5    # « Date non réglée » en rouge
app.on_tap(W // 2, E.HEADER_H + 10)                                 # pas de « aujourd'hui » : sans effet
assert app.date() == "2026-10-28"
print("6. date non réglée : OK")

# ---------- 7. Aujourd'hui hors de la plage : le prochain jour, sinon le dernier ----------
assert open_app("2026-10-27").date() == "2026-10-27"
assert open_app("2026-10-01").date() == "2026-10-26"                # avant : premier jour
assert open_app("2026-12-25").date() == "2026-10-30"                # après : dernier jour
print("7. choix du jour d'ouverture : OK")

# ---------- 8. Fichiers meta abîmés ----------
for raw in ("{pas du json", "[1, 2]", '{"days": "x"}', '{"days": []}', '{"days": ["abc", 12, null]}', ""):
    write("meta.json", raw)
    assert E._load_meta() is None, raw
write("meta.json", {"days": ["2026-10-%02d" % (1 + i % 28) for i in range(500)]})
assert len(E._load_meta()["days"]) <= 28                            # doublons retirés, borne MAX_DAYS
write("2026-10-26.json", {"lessons": [lesson("08:00", "08:55", "Cours %d" % i) for i in range(40)]})
assert len(E._load_day("2026-10-26")) == E.MAX_LESSONS              # plafonné
write("2026-10-26.json", {"lessons": [{"start": "08:00", "end": "09:00", "subject": 12, "room": None}]})
assert E._load_day("2026-10-26")[0]["subject"] == "?"               # type inattendu : valeur de repli
write("2026-10-26.json", '{"lessons": "x"}')
assert E._load_day("2026-10-26") is None
print("8. fichiers abîmés et bornes : OK")

# ---------- 9. Traductions : toutes les langues, jours/mois/format ----------
write("meta.json", {"v": 1, "synced": "2026-10-28T08:12", "days": ["2026-10-28"]})
write("2026-10-28.json", {"lessons": wed})
for key in ("edt_weekdays", "edt_months", "edt_date_fmt", "edt_none", "edt_hint", "edt_empty",
            "edt_bad_day", "edt_cancelled", "edt_synced", "edt_date_unset"):
    for code in i18n.LANGS:
        assert i18n.STRINGS[key].get(code), (key, code)
for code in i18n.LANGS:
    assert len(i18n.STRINGS["edt_weekdays"][code].split(" ")) == 7, code
    assert len(i18n.STRINGS["edt_months"][code].split(" ")) == 12, code
    fmt = i18n.STRINGS["edt_date_fmt"][code]
    assert "{wd}" in fmt and "{d}" in fmt and "{m}" in fmt, code
    assert "%s" in i18n.STRINGS["edt_synced"][code], code
    i18n._current = code
    label = E._date_label("2026-10-28")
    assert label and "{" not in label, (code, label)
    app = open_app("2026-10-28")
    shot("9_" + code)
    print("   ", code, "->", label)
i18n._current = "FR"
print("9. traductions (6 langues) : OK")

# ---------- 10. Fixture produite par tools/sync_pronote.py (mode démo) : l'outil et l'appli parlent le même format ----------
# (host/cpython/test_sync_pronote.py vérifie que host/fixtures/edt/ est bien la sortie actuelle de l'outil)
clean()
FIX = "../host/fixtures/edt"
for name in os.listdir(FIX):
    with open(FIX + "/" + name) as f:
        write(name, f.read())
meta = E._load_meta()
assert meta and len(meta["days"]) == 11 and meta["synced"] == "2026-10-26T08:00", meta
for d in meta["days"]:
    day = E._load_day(d)
    assert day, d                                                   # lisible et non vide
    assert all(x["subject"] != "?" and x["start"] < x["end"] for x in day), d
mon = E._load_day("2026-10-26")
assert len(mon) == 6 and [x["cancelled"] for x in mon] == [False, True, False, False, False, False], mon
assert E._load_day("2026-10-28")[2]["note"] == "Salle changée"
app = open_app("2026-10-26")
assert app.date() == "2026-10-26" and len(app.lessons) == 6
assert E._date_label(app.date()) == "Lun 26 oct."
shot("10_fixture")
print("10. fixture de l'outil de synchro lue par l'appli : OK")

clean()
print("TOUS LES TESTS EDT OK")
