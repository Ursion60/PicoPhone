#!/usr/bin/env python3
"""
Synchronise l'emploi du temps Pronote avec la carte (appli EDT), depuis le PC, par USB.

La connexion Pronote (chiffrée, avec jeton) ne tourne pas sur la carte : ce script, lui, tourne sur le PC
avec la bibliothèque pronotepy, convertit les cours au format lu par python/apps/edt.py (voir son en-tête)
puis les envoie à la carte avec mpremote.

    tools/setup-deps.sh tools pronote           # une fois : installe pronotepy et mpremote dans .venv

    # 1re fois : connexion par QR code (compatible avec les comptes qui passent par un ENT)
    #   Pronote (navigateur) -> Paramètres -> Application mobile -> générer le QR code + un code à 4 chiffres.
    #   Décodez le QR code en texte JSON (ex. zbarimg --raw qr.png > qr.json), puis :
    tools/sync_pronote.py login --qr qr.json --pin 1234

    tools/sync_pronote.py sync --push           # récupère 14 jours et les envoie à la carte
    tools/sync_pronote.py demo --push           # données fictives, sans réseau (pour essayer l'appli)

Les identifiants (URL, jeton, uuid) restent dans ~/.config/picophone/pronote.json (droits 0600), jamais dans le
dépôt. Le jeton est renouvelé par Pronote à chaque connexion : il est réenregistré aussitôt.
Le QR code contient un jeton à usage unique : ne le versionnez pas (qr*.json est ignoré par git).

Ce programme utilise l'API non officielle de Pronote via pronotepy : elle peut changer sans préavis.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid as uuidlib
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

# Mêmes bornes que python/apps/edt.py (la carte retronque de toute façon, mais autant ne pas envoyer plus).
MAX_LESSONS = 16
MAX_DAYS = 120
SUBJECT_LEN, ROOM_LEN, TEACHER_LEN, NOTE_LEN = 40, 12, 32, 40
FORMAT_VERSION = 1


class SyncError(Exception):
    """Erreur attendue (identifiants absents, carte introuvable...) : message court, sans traceback."""


# ---------------------------------------------------------------------------
# Conversion : cours Pronote -> format de la carte
# ---------------------------------------------------------------------------
def _clean(value, n):
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()[:n]


def lesson_to_dict(lesson):
    """Un cours pronotepy (ou tout objet ayant les mêmes attributs) -> dictionnaire du fichier jour."""
    subject = getattr(lesson, "subject", None)
    room = getattr(lesson, "classroom", None) or "/".join(getattr(lesson, "classrooms", None) or [])
    teacher = getattr(lesson, "teacher_name", None) or ", ".join(getattr(lesson, "teacher_names", None) or [])
    return {
        "start": lesson.start.strftime("%H:%M"),
        "end": lesson.end.strftime("%H:%M"),
        "subject": _clean(getattr(subject, "name", None), SUBJECT_LEN),
        "room": _clean(room, ROOM_LEN),
        "teacher": _clean(teacher, TEACHER_LEN),
        "cancelled": bool(getattr(lesson, "canceled", False)),
        "note": _clean(getattr(lesson, "status", None), NOTE_LEN),
    }


def group_by_day(lessons):
    """{"AAAA-MM-JJ": [cours triés]}, avec un seul cours par heure de début : Pronote affiche celui dont
    `num` est le plus grand quand plusieurs se superposent."""
    best = {}
    for ls in lessons:
        key = (ls.start.date(), ls.start.strftime("%H:%M"))
        if key not in best or getattr(ls, "num", 0) > getattr(best[key], "num", 0):
            best[key] = ls
    days = {}
    for (day, _), ls in best.items():
        days.setdefault(day.isoformat(), []).append(lesson_to_dict(ls))
    for items in days.values():
        items.sort(key=lambda d: (d["start"], d["end"]))
    return dict(sorted(days.items()))


def build_files(days, now, source="pronote"):
    """{nom de fichier: contenu}. meta.json est le dernier : la carte ne le voit qu'une fois les jours écrits."""
    days = dict(list(days.items())[:MAX_DAYS])
    files = {}
    for iso, items in days.items():
        if len(items) > MAX_LESSONS:
            print("attention : %s a %d cours, la carte n'en affiche que %d" % (iso, len(items), MAX_LESSONS),
                  file=sys.stderr)
        files[iso + ".json"] = {"lessons": items[:MAX_LESSONS]}
    files["meta.json"] = {"v": FORMAT_VERSION, "synced": now.strftime("%Y-%m-%dT%H:%M"),
                          "source": source, "days": list(days)}
    return files


def write_dir(files, outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("*.json"):                  # pas de jours périmés d'une synchro précédente
        old.unlink()
    for name, obj in files.items():
        (outdir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Envoi à la carte (mpremote)
# ---------------------------------------------------------------------------
def board_script(day_files):
    """Code exécuté sur la carte : crée edt/, renomme les fichiers .tmp (meta en dernier), supprime les
    jours périmés. Les fichiers sont d'abord envoyés en .tmp : une coupure ne laisse jamais un fichier tronqué."""
    return (
        "import os\n"
        "DAYS = %r\n"
        "def mv(a, b):\n"
        "    try:\n"
        "        os.rename(a, b)\n"
        "    except OSError:\n"
        "        os.remove(b)\n"
        "        os.rename(a, b)\n"
        "for n in DAYS:\n"
        "    mv('edt/' + n + '.tmp', 'edt/' + n)\n"
        "mv('edt/meta.json.tmp', 'edt/meta.json')\n"
        "for n in os.listdir('edt'):\n"
        "    if n != 'meta.json' and n not in DAYS:\n"
        "        os.remove('edt/' + n)\n"
        "print('edt : %%d jour(s)' %% len(DAYS))\n"
    ) % (sorted(day_files),)


MKDIR_SCRIPT = "import os\ntry:\n    os.mkdir('edt')\nexcept OSError:\n    pass\n"


def find_mpremote():
    found = shutil.which("mpremote")
    if found:
        return found
    for cand in (REPO / ".venv" / "bin" / "mpremote", REPO / ".venv" / "Scripts" / "mpremote.exe"):
        if cand.exists():
            return str(cand)
    raise SyncError("mpremote introuvable : lancez tools/setup-deps.sh tools")


def mpremote_args(outdir, files, set_rtc=True, device=None):
    """Arguments d'UN seul appel mpremote (les commandes sont chaînées avec « + » : une seule connexion)."""
    args = []
    if device:
        args += ["connect", device, "+"]
    args += ["exec", MKDIR_SCRIPT]
    day_files = [n for n in files if n != "meta.json"]
    for name in day_files + ["meta.json"]:
        args += ["+", "fs", "cp", str(Path(outdir) / name), ":edt/" + name + ".tmp"]
    args += ["+", "exec", board_script(day_files)]
    if set_rtc:                                       # la carte n'a pas d'horloge : on lui donne l'heure du PC
        args += ["+", "rtc", "--set"]
    return args


def push(outdir, files, set_rtc=True, device=None):
    cmd = [find_mpremote()] + mpremote_args(outdir, files, set_rtc, device)
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise SyncError("envoi à la carte impossible (carte branchée ? appli arrêtée ?) :\n"
                        + (res.stderr or res.stdout).strip()[-500:])
    out = "\n".join(l for l in res.stdout.splitlines() if l.strip() and not l.startswith("cp "))   # sans le détail des copies
    if out:
        print(out)


# ---------------------------------------------------------------------------
# Identifiants Pronote
# ---------------------------------------------------------------------------
def credentials_path():
    env = os.environ.get("PICOPHONE_PRONOTE_CREDENTIALS")
    if env:
        return Path(env)
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "picophone" / "pronote.json"


def save_credentials(creds):
    """Écriture atomique, droits 0600 : le jeton donne accès au compte Pronote."""
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(creds, f)
    os.replace(str(tmp), str(path))


def load_credentials():
    try:
        creds = json.loads(credentials_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SyncError("pas d'identifiants Pronote : lancez d'abord « login » (voir --help)")
    need = ("pronote_url", "username", "password", "uuid")
    if not isinstance(creds, dict) or any(not isinstance(creds.get(k), str) or not creds[k] for k in need):
        raise SyncError("fichier d'identifiants invalide (%s) : refaites « login »" % credentials_path())
    return creds


def import_pronotepy():
    try:
        import pronotepy
        return pronotepy
    except ImportError:
        venv = REPO / ".venv"
        venv_python = venv / "bin" / "python"
        # .venv/bin/python est un lien vers le Python système : on compare le préfixe du venv, pas le chemin résolu
        if venv_python.exists() and Path(sys.prefix).resolve() != venv.resolve():
            os.execv(str(venv_python), [str(venv_python)] + sys.argv)        # relance dans le venv du projet
        raise SyncError("pronotepy manque : lancez tools/setup-deps.sh tools pronote")


def pronote_login(qr_path, pin):
    pronotepy = import_pronotepy()
    try:
        raw = sys.stdin.read() if qr_path == "-" else Path(qr_path).read_text(encoding="utf-8")
        qr = json.loads(raw)
    except (OSError, ValueError) as e:
        raise SyncError("QR code illisible (attendu : le JSON décodé du QR code) : %s" % e)
    if not isinstance(qr, dict) or not all(k in qr for k in ("login", "jeton", "url")):
        raise SyncError("le JSON du QR code doit contenir « login », « jeton » et « url »")
    if not re.fullmatch(r"\d{4}", pin or ""):
        raise SyncError("le code PIN du QR code a 4 chiffres")
    client = pronotepy.Client.qrcode_login(qr, pin, uuidlib.uuid4().hex)
    if not client.logged_in:
        raise SyncError("connexion Pronote refusée")
    save_credentials(client.export_credentials())          # tout de suite : le jeton vient de changer
    return client


def fetch_lessons(date_from, date_to):
    pronotepy = import_pronotepy()
    client = pronotepy.Client.token_login(**load_credentials())
    if not client.logged_in:
        raise SyncError("connexion Pronote refusée : le jeton a peut-être expiré, refaites « login »")
    save_credentials(client.export_credentials())          # Pronote renouvelle le jeton à chaque connexion
    return client.lessons(date_from, date_to)


# ---------------------------------------------------------------------------
# Données fictives (mode démo, tests)
# ---------------------------------------------------------------------------
_DEMO_WEEK = [
    [("08:00", "08:55", "Mathématiques", "B12", "M. Dupont"), ("09:00", "09:55", "Français", "A03", "Mme Martin"),
     ("10:10", "11:05", "Anglais LV1", "C21", "Mr Smith"), ("11:10", "12:05", "Histoire-Géographie", "A01", "Mme Roux"),
     ("14:00", "14:55", "EPS", "Gymnase", "M. Leroy"), ("15:00", "15:55", "EPS", "Gymnase", "M. Leroy")],
    [("08:00", "08:55", "Physique-Chimie", "L2", "Mme Bernard"), ("09:00", "09:55", "Mathématiques", "B12", "M. Dupont"),
     ("10:10", "11:05", "SVT", "L3", "M. Petit"), ("13:00", "13:55", "Technologie", "T1", "M. Moreau")],
    [("08:00", "08:55", "Français", "A03", "Mme Martin"), ("09:00", "09:55", "Anglais LV1", "C21", "Mr Smith"),
     ("10:10", "11:05", "Mathématiques", "B12", "M. Dupont"), ("11:10", "12:05", "Espagnol LV2", "C14", "Mme Garcia"),
     ("13:00", "13:55", "Histoire-Géographie", "A01", "Mme Roux"), ("14:00", "14:55", "Physique-Chimie", "L2", "Mme Bernard"),
     ("15:10", "16:05", "SVT", "L3", "M. Petit"), ("16:10", "17:05", "Étude", "", "")],
    [("08:00", "08:55", "Espagnol LV2", "C14", "Mme Garcia"), ("09:00", "09:55", "Mathématiques", "B12", "M. Dupont"),
     ("10:10", "11:05", "Français", "A03", "Mme Martin")],
    [("08:00", "08:55", "Anglais LV1", "C21", "Mr Smith"), ("09:00", "09:55", "Technologie", "T1", "M. Moreau"),
     ("10:10", "11:05", "Physique-Chimie", "L2", "Mme Bernard")],
]


def demo_lessons(today, days=14):
    """Cours fictifs pour les jours ouvrés de `today` à `today + days`, avec les mêmes attributs que pronotepy
    (ils passent donc par le même code de conversion que les vrais cours)."""
    out = []
    for offset in range(days + 1):
        day = today + datetime.timedelta(days=offset)
        if day.weekday() > 4:
            continue
        for k, (s, e, subject, room, teacher) in enumerate(_DEMO_WEEK[day.weekday()]):
            sh, sm = map(int, s.split(":"))
            eh, em = map(int, e.split(":"))
            out.append(SimpleNamespace(
                start=datetime.datetime(day.year, day.month, day.day, sh, sm),
                end=datetime.datetime(day.year, day.month, day.day, eh, em),
                subject=SimpleNamespace(name=subject), classroom=room or None, teacher_name=teacher or None,
                canceled=(day.weekday() == 0 and k == 1),
                status="Cours annulé" if (day.weekday() == 0 and k == 1) else
                       ("Salle changée" if (day.weekday() == 2 and k == 2) else None),
                num=0))
    return out


# ---------------------------------------------------------------------------
# Ligne de commande
# ---------------------------------------------------------------------------
def _date(text):
    return datetime.date.fromisoformat(text)


def _now(text):
    return datetime.datetime.fromisoformat(text) if text else datetime.datetime.now().replace(second=0, microsecond=0)


def _finish(lessons, args):
    now = _now(args.now)
    files = build_files(group_by_day(lessons), now, source="demo" if args.cmd == "demo" else "pronote")
    n_days = len(files) - 1
    if not n_days:
        raise SyncError("aucun cours sur la période demandée : rien n'est envoyé (la carte garde ses données)")
    outdir = args.out or tempfile.mkdtemp(prefix="picophone-edt-")
    write_dir(files, outdir)
    print("%d jour(s), %d cours -> %s" % (n_days, sum(len(v["lessons"]) for k, v in files.items() if k != "meta.json"),
                                          outdir))
    if args.push:
        push(outdir, files, set_rtc=not args.no_rtc, device=args.device)


def main(argv=None):
    p = argparse.ArgumentParser(description="Synchronise l'emploi du temps Pronote avec la carte (appli EDT).")
    sub = p.add_subparsers(dest="cmd", required=True)

    lg = sub.add_parser("login", help="première connexion par QR code, enregistre le jeton")
    lg.add_argument("--qr", required=True, help="fichier JSON du QR code décodé (« - » : entrée standard)")
    lg.add_argument("--pin", required=True, help="code à 4 chiffres choisi à la création du QR code")

    for name, help_ in (("sync", "récupère l'emploi du temps sur Pronote"), ("demo", "données fictives, sans réseau")):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--days", type=int, default=14, help="jours à récupérer après aujourd'hui (défaut 14)")
        sp.add_argument("--back", type=int, default=1, help="jours passés à inclure (défaut 1)")
        sp.add_argument("--out", help="dossier des fichiers générés (défaut : dossier temporaire)")
        sp.add_argument("--push", action="store_true", help="envoie les fichiers à la carte (mpremote)")
        sp.add_argument("--no-rtc", action="store_true", help="ne règle pas l'heure de la carte")
        sp.add_argument("--device", help="port série de la carte (défaut : détection automatique de mpremote)")
        sp.add_argument("--today", type=_date, default=None, help=argparse.SUPPRESS)
        sp.add_argument("--now", default=None, help=argparse.SUPPRESS)
    args = p.parse_args(argv)

    try:
        if args.cmd == "login":
            client = pronote_login(args.qr, args.pin)
            name = getattr(getattr(client, "info", None), "name", "")
            print("Connecté%s. Jeton enregistré dans %s" % (" (%s)" % name if name else "", credentials_path()))
            return 0
        if not 1 <= args.days <= 60 or not 0 <= args.back <= 14:
            raise SyncError("--days doit être entre 1 et 60, --back entre 0 et 14")
        today = args.today or datetime.date.today()
        start, end = today - datetime.timedelta(days=args.back), today + datetime.timedelta(days=args.days)
        lessons = demo_lessons(start, args.days + args.back) if args.cmd == "demo" else fetch_lessons(start, end)
        _finish(lessons, args)
        return 0
    except SyncError as e:
        print("erreur : %s" % e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    except Exception as e:                                   # erreur Pronote / réseau : jamais d'identifiant dans le message
        print("erreur : %s : %s" % (type(e).__name__, e), file=sys.stderr)
        print("(si le jeton a expiré ou a été révoqué, refaites « login »)", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
