"""
Tests de tools/sync_pronote.py (CPython, sans réseau ni carte : pronotepy et mpremote sont simulés).

    python3 host/cpython/test_sync_pronote.py            # ajoutez -v pour le détail
    UPDATE_FIXTURES=1 python3 host/cpython/test_sync_pronote.py   # régénère host/fixtures/edt/

Si pronotepy est installé, les appels de l'outil sont aussi vérifiés contre ses signatures réelles.
"""
import contextlib
import datetime
import importlib.util
import inspect
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "host" / "fixtures" / "edt"

spec = importlib.util.spec_from_file_location("sync_pronote", ROOT / "tools" / "sync_pronote.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

DT = datetime.datetime


def lesson(start, end, subject="Maths", room="B12", teacher="M. Dupont", canceled=False, status=None, num=0, **extra):
    return SimpleNamespace(start=start, end=end, subject=SimpleNamespace(name=subject) if subject else None,
                           classroom=room, teacher_name=teacher, canceled=canceled, status=status, num=num, **extra)


def run_main(argv, env=None):
    """Exécute main() ; renvoie (code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    old = dict(os.environ)
    os.environ.update(env or {})
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = S.main(argv)
    finally:
        os.environ.clear()
        os.environ.update(old)
    return code, out.getvalue(), err.getvalue()


class FakeClient:
    """Imite pronotepy.Client : le jeton change à chaque connexion, comme sur un vrai serveur."""

    calls = []
    lessons_result = []
    logins = 0

    def __init__(self, creds):
        FakeClient.logins += 1
        self.logged_in = True
        self.info = SimpleNamespace(name="Élève Test")
        self._creds = dict(creds, password="JETON-%d" % FakeClient.logins)     # un jeton neuf à chaque connexion

    @classmethod
    def qrcode_login(cls, qr_code, pin, uuid, account_pin=None, client_identifier=None, device_name=None,
                     skip_2fa=False):
        cls.calls.append(("qrcode_login", qr_code, pin, uuid))
        return cls({"pronote_url": qr_code["url"], "username": qr_code["login"], "password": qr_code["jeton"],
                    "uuid": uuid, "client_identifier": "ci"})

    @classmethod
    def token_login(cls, pronote_url, username, password, uuid, account_pin=None, client_identifier=None,
                    device_name=None):
        cls.calls.append(("token_login", pronote_url, username, password, uuid))
        return cls({"pronote_url": pronote_url, "username": username, "password": password, "uuid": uuid,
                    "client_identifier": client_identifier})

    def export_credentials(self):
        return dict(self._creds)

    def lessons(self, date_from, date_to=None):
        FakeClient.calls.append(("lessons", date_from, date_to))
        return FakeClient.lessons_result


class Convert(unittest.TestCase):
    def test_lesson_fields(self):
        d = S.lesson_to_dict(lesson(DT(2026, 10, 28, 8, 0), DT(2026, 10, 28, 8, 55), status="Salle changée"))
        self.assertEqual(d, {"start": "08:00", "end": "08:55", "subject": "Maths", "room": "B12",
                             "teacher": "M. Dupont", "cancelled": False, "note": "Salle changée"})

    def test_missing_and_list_fields(self):
        ls = SimpleNamespace(start=DT(2026, 10, 28, 9, 5), end=DT(2026, 10, 28, 10, 0), subject=None, classroom=None,
                             classrooms=["A1", "A2"], teacher_name=None, teacher_names=["Mme X", "M. Y"],
                             canceled=True, status=None)
        d = S.lesson_to_dict(ls)
        self.assertEqual((d["subject"], d["room"], d["teacher"], d["cancelled"], d["note"]),
                         ("", "A1/A2", "Mme X, M. Y", True, ""))

    def test_clean_whitespace_and_length(self):
        d = S.lesson_to_dict(lesson(DT(2026, 1, 1, 8), DT(2026, 1, 1, 9), subject="  A \n  B\t" + "x" * 100,
                                    room="salle  très   longue 123456", teacher="t" * 80))
        self.assertTrue(d["subject"].startswith("A B x") and len(d["subject"]) == S.SUBJECT_LEN)
        self.assertEqual(len(d["room"]), S.ROOM_LEN)
        self.assertEqual(len(d["teacher"]), S.TEACHER_LEN)

    def test_group_sort_and_dedupe(self):
        a = lesson(DT(2026, 10, 28, 10, 0), DT(2026, 10, 28, 11, 0), subject="B", num=0)
        b = lesson(DT(2026, 10, 28, 8, 0), DT(2026, 10, 28, 9, 0), subject="A")
        c = lesson(DT(2026, 10, 28, 10, 0), DT(2026, 10, 28, 11, 0), subject="B-groupe", num=2)   # même heure : num le plus grand
        e = lesson(DT(2026, 10, 27, 8, 0), DT(2026, 10, 27, 9, 0), subject="Veille")
        days = S.group_by_day([a, b, c, e])
        self.assertEqual(list(days), ["2026-10-27", "2026-10-28"])
        self.assertEqual([x["subject"] for x in days["2026-10-28"]], ["A", "B-groupe"])

    def test_build_files_meta_last_and_schema(self):
        days = S.group_by_day([lesson(DT(2026, 10, 28, 8), DT(2026, 10, 28, 9)),
                               lesson(DT(2026, 10, 26, 8), DT(2026, 10, 26, 9))])
        files = S.build_files(days, DT(2026, 10, 28, 8, 12))
        self.assertEqual(list(files), ["2026-10-26.json", "2026-10-28.json", "meta.json"])        # meta en dernier
        self.assertEqual(files["meta.json"], {"v": 1, "synced": "2026-10-28T08:12", "source": "pronote",
                                              "days": ["2026-10-26", "2026-10-28"]})

    def test_too_many_lessons_warns_and_caps(self):
        many = [lesson(DT(2026, 10, 28, 6, 0) + datetime.timedelta(minutes=i * 5),
                       DT(2026, 10, 28, 6, 4) + datetime.timedelta(minutes=i * 5)) for i in range(S.MAX_LESSONS + 4)]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            files = S.build_files(S.group_by_day(many), DT(2026, 10, 28, 8))
        self.assertEqual(len(files["2026-10-28.json"]["lessons"]), S.MAX_LESSONS)
        self.assertIn("attention", err.getvalue())


class Fixtures(unittest.TestCase):
    """host/fixtures/edt/ est la sortie figée du mode démo : test_edt.py (MicroPython) la lit avec le vrai
    chargeur de l'appli, ce qui vérifie que l'outil et l'appli parlent le même format."""

    def test_demo_matches_committed_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_main(["demo", "--today", "2026-10-26", "--now", "2026-10-26T08:00",
                                     "--days", "14", "--back", "0", "--out", tmp])
            self.assertEqual(code, 0, err)
            if os.environ.get("UPDATE_FIXTURES"):
                FIXTURES.mkdir(parents=True, exist_ok=True)
                for f in FIXTURES.glob("*.json"):
                    f.unlink()
                for f in Path(tmp).glob("*.json"):
                    (FIXTURES / f.name).write_bytes(f.read_bytes())
            got = {f.name: f.read_bytes() for f in Path(tmp).glob("*.json")}
        want = {f.name: f.read_bytes() for f in FIXTURES.glob("*.json")}
        self.assertEqual(sorted(got), sorted(want), "jeux de fichiers différents : UPDATE_FIXTURES=1")
        for name in got:
            self.assertEqual(got[name], want[name], name + " : UPDATE_FIXTURES=1 pour régénérer")
        meta = json.loads(got["meta.json"])
        self.assertEqual(meta["days"][0], "2026-10-26")
        self.assertTrue(all(d + ".json" in got for d in meta["days"]))
        self.assertNotIn("2026-10-31", meta["days"])                                  # samedi : pas de cours


class Credentials(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {"PICOPHONE_PRONOTE_CREDENTIALS": str(Path(self.tmp.name) / "cfg" / "pronote.json")}
        FakeClient.calls = []
        FakeClient.logins = 0
        FakeClient.lessons_result = [lesson(DT(2026, 10, 28, 8), DT(2026, 10, 28, 9))]
        self._saved = sys.modules.get("pronotepy")
        sys.modules["pronotepy"] = SimpleNamespace(Client=FakeClient)

    def tearDown(self):
        if self._saved is None:
            sys.modules.pop("pronotepy", None)
        else:
            sys.modules["pronotepy"] = self._saved
        self.tmp.cleanup()

    def qr_file(self):
        p = Path(self.tmp.name) / "qr.json"
        p.write_text(json.dumps({"login": "u", "jeton": "JETON-QR", "url": "https://x.example/pronote/"}))
        return str(p)

    def test_login_then_sync_renews_token_and_never_prints_it(self):
        code, out, err = run_main(["login", "--qr", self.qr_file(), "--pin", "1234"], self.env)
        self.assertEqual(code, 0, err)
        path = Path(self.env["PICOPHONE_PRONOTE_CREDENTIALS"])
        creds = json.loads(path.read_text())
        self.assertEqual(creds["password"], "JETON-1")                   # le jeton exporté, pas celui du QR code
        self.assertTrue(creds["uuid"])
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        for secret in ("JETON-QR", "JETON-1", creds["uuid"]):
            self.assertNotIn(secret, out + err)

        outdir = Path(self.tmp.name) / "out"
        code, out, err = run_main(["sync", "--out", str(outdir), "--today", "2026-10-28", "--days", "3"], self.env)
        self.assertEqual(code, 0, err)
        self.assertEqual(FakeClient.calls[-2][:5], ("token_login", "https://x.example/pronote/", "u", "JETON-1",
                                                    creds["uuid"]))        # reconnexion avec le jeton enregistré
        self.assertEqual(FakeClient.calls[-1], ("lessons", datetime.date(2026, 10, 27), datetime.date(2026, 10, 31)))
        self.assertTrue((outdir / "meta.json").exists() and (outdir / "2026-10-28.json").exists())
        renewed = json.loads(path.read_text())
        self.assertEqual(renewed["password"], "JETON-2")                   # le jeton renouvelé est réenregistré
        self.assertEqual(renewed["uuid"], creds["uuid"])                   # l'uuid ne change jamais
        code, _, err = run_main(["sync", "--out", str(outdir), "--today", "2026-10-28"], self.env)
        self.assertEqual(code, 0, err)
        self.assertEqual(FakeClient.calls[-2][3], "JETON-2")               # la synchro suivante utilise le jeton neuf
        self.assertEqual(json.loads(path.read_text())["password"], "JETON-3")
        for secret in ("JETON-1", "JETON-2"):
            self.assertNotIn(secret, out + err)

    def test_errors_exit_1_with_short_message(self):
        code, _, err = run_main(["sync", "--out", self.tmp.name], self.env)           # jamais connecté
        self.assertEqual(code, 1)
        self.assertIn("login", err)
        self.assertNotIn("Traceback", err)
        code, _, err = run_main(["login", "--qr", self.qr_file(), "--pin", "12"], self.env)
        self.assertEqual(code, 1)
        self.assertIn("4 chiffres", err)
        bad = Path(self.tmp.name) / "bad.json"
        bad.write_text('{"login": "u"}')
        code, _, err = run_main(["login", "--qr", str(bad), "--pin", "1234"], self.env)
        self.assertEqual(code, 1)
        self.assertIn("jeton", err)
        code, _, err = run_main(["sync", "--days", "99", "--out", self.tmp.name], self.env)
        self.assertEqual(code, 1)

    def test_no_lessons_sends_nothing(self):
        run_main(["login", "--qr", self.qr_file(), "--pin", "1234"], self.env)
        FakeClient.lessons_result = []
        code, _, err = run_main(["sync", "--push", "--out", str(Path(self.tmp.name) / "o")], self.env)
        self.assertEqual(code, 1)
        self.assertIn("rien n'est envoyé", err)

    def test_pronote_exception_message_has_no_traceback(self):
        run_main(["login", "--qr", self.qr_file(), "--pin", "1234"], self.env)

        class Unreachable(FakeClient):
            @classmethod
            def token_login(cls, *args, **kwargs):
                raise RuntimeError("serveur injoignable")
        sys.modules["pronotepy"] = SimpleNamespace(Client=Unreachable)
        code, _, err = run_main(["sync", "--out", self.tmp.name], self.env)
        self.assertEqual(code, 1)
        self.assertIn("RuntimeError", err)
        self.assertNotIn("Traceback", err)


class VenvRelaunch(unittest.TestCase):
    """Sans pronotepy, l'outil se relance dans .venv (créé par setup-deps.sh) au lieu de demander d'activer le venv."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / ".venv" / "bin").mkdir(parents=True)
        (self.repo / ".venv" / "bin" / "python").write_text("")
        self._saved = sys.modules.get("pronotepy", "absent")
        sys.modules["pronotepy"] = None                      # « import pronotepy » lève ImportError

    def tearDown(self):
        if self._saved == "absent":
            sys.modules.pop("pronotepy", None)
        else:
            sys.modules["pronotepy"] = self._saved
        self.tmp.cleanup()

    def test_relaunches_in_project_venv(self):
        from unittest import mock
        with mock.patch.object(S, "REPO", self.repo), mock.patch.object(S.os, "execv", side_effect=SystemExit(0)) as ex:
            with self.assertRaises(SystemExit):
                S.import_pronotepy()
        self.assertEqual(ex.call_args[0][0], str(self.repo / ".venv" / "bin" / "python"))

    def test_no_loop_when_already_in_that_venv(self):
        from unittest import mock
        with mock.patch.object(S, "REPO", self.repo), mock.patch.object(S.sys, "prefix", str(self.repo / ".venv")), \
                mock.patch.object(S.os, "execv") as ex:
            with self.assertRaises(S.SyncError):
                S.import_pronotepy()
        ex.assert_not_called()

    def test_clear_message_without_venv(self):
        from unittest import mock
        (self.repo / ".venv" / "bin" / "python").unlink()
        with mock.patch.object(S, "REPO", self.repo), mock.patch.object(S.os, "execv") as ex:
            with self.assertRaisesRegex(S.SyncError, "setup-deps.sh"):
                S.import_pronotepy()
        ex.assert_not_called()


class RealSignatures(unittest.TestCase):
    """Si pronotepy est installé : nos appels doivent correspondre à ses signatures réelles."""

    def test_calls_bind_to_real_pronotepy(self):
        try:
            import pronotepy
        except ImportError:
            self.skipTest("pronotepy non installé")
        creds = {"pronote_url": "u", "username": "n", "password": "p", "uuid": "i", "client_identifier": "c"}
        inspect.signature(pronotepy.Client.token_login).bind(**creds)              # load_credentials -> token_login(**creds)
        inspect.signature(pronotepy.Client.qrcode_login).bind({"login": 1}, "1234", "uuid")
        inspect.signature(pronotepy.Client.lessons).bind(object(), datetime.date.today(), datetime.date.today())
        for attr in ("start", "end", "subject", "classroom", "classrooms", "teacher_name", "teacher_names",
                     "canceled", "status", "num"):
            self.assertIn(attr, inspect.getsource(pronotepy.Lesson), attr)         # attributs lus par lesson_to_dict
        self.assertIn("export_credentials", dir(pronotepy.Client))


class Push(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        self.log = Path(self.tmp.name) / "args.json"
        fake = self.bin / "mpremote"
        fake.write_text("#!%s\nimport json, os, sys\n"
                        "open(%r, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
                        "print('cp x :y')\n"
                        "print('edt : 2 jour(s)')\n"
                        "sys.exit(int(os.environ.get('FAKE_MPREMOTE_RC', '0')))\n" % (sys.executable, str(self.log)))
        fake.chmod(0o755)
        self.files = S.build_files(S.group_by_day([lesson(DT(2026, 10, 28, 8), DT(2026, 10, 28, 9)),
                                                   lesson(DT(2026, 10, 29, 8), DT(2026, 10, 29, 9))]), DT(2026, 10, 28, 8))

    def tearDown(self):
        self.tmp.cleanup()

    def env(self, **extra):
        return dict({"PATH": str(self.bin) + os.pathsep + os.environ["PATH"]}, **extra)

    def test_command_sequence(self):
        code, out, err = run_main(["demo", "--today", "2026-10-26", "--days", "3", "--back", "0", "--push",
                                   "--out", str(Path(self.tmp.name) / "o")], self.env())
        self.assertEqual(code, 0, err)
        self.assertIn("edt : 2 jour(s)", out)                                # le retour du script de la carte est affiché
        self.assertNotIn("cp x", out)                                        # pas le détail des copies
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(len(calls), 1)                                      # UNE seule connexion à la carte
        a = calls[0]
        self.assertEqual(a[0], "exec")                                       # crée edt/ d'abord
        cps = [a[i + 2] for i, x in enumerate(a) if x == "cp"]
        self.assertTrue(cps[-1].endswith(":edt/meta.json.tmp"))              # meta en dernier
        self.assertTrue(all(c.startswith(":edt/") and c.endswith(".tmp") for c in cps))
        script = [x for x in a if "DAYS" in x][0]
        self.assertIn("'2026-10-26.json'", script)
        self.assertEqual(a[-2:], ["rtc", "--set"])                           # l'heure du PC est donnée à la carte
        self.assertEqual(a.count("+"), len(cps) + 2)                         # exec + n copies + exec + rtc, chaînés

    def test_no_rtc_and_device(self):
        old_path = os.environ["PATH"]
        os.environ["PATH"] = self.env()["PATH"]
        try:
            S.push(Path(self.tmp.name), self.files, set_rtc=False, device="/dev/ttyACM0")
        finally:
            os.environ["PATH"] = old_path
        a = json.loads(self.log.read_text().splitlines()[-1])
        self.assertEqual(a[:3], ["connect", "/dev/ttyACM0", "+"])
        self.assertNotIn("rtc", a)

    def test_mpremote_failure_is_reported(self):
        code, _, err = run_main(["demo", "--today", "2026-10-26", "--days", "3", "--back", "0", "--push",
                                 "--out", str(Path(self.tmp.name) / "o")], self.env(FAKE_MPREMOTE_RC="1"))
        self.assertEqual(code, 1)
        self.assertIn("carte", err)


class BoardScript(unittest.TestCase):
    """Le script exécuté sur la carte, joué ici avec CPython dans un dossier temporaire."""

    def run_script(self, day_files, setup):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                os.mkdir("edt")
                for name in setup:
                    Path("edt", name).write_text(name)
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(S.board_script(day_files), {})
                return sorted(os.listdir("edt")), {n: Path("edt", n).read_text() for n in os.listdir("edt")}
            finally:
                os.chdir(cwd)

    def test_commit_and_cleanup(self):
        names, content = self.run_script(
            ["2026-10-28.json", "2026-10-29.json"],
            ["2026-10-28.json.tmp", "2026-10-29.json.tmp", "meta.json.tmp",            # fichiers qui viennent d'être envoyés
             "2026-10-20.json", "2026-10-28.json", "meta.json", "vieux.tmp"])          # restes d'une synchro précédente
        self.assertEqual(names, ["2026-10-28.json", "2026-10-29.json", "meta.json"])
        self.assertEqual(content["2026-10-28.json"], "2026-10-28.json.tmp")             # le nouveau contenu a gagné
        self.assertEqual(content["meta.json"], "meta.json.tmp")


if __name__ == "__main__":
    unittest.main()
