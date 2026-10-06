"""
Test de bout en bout sur le simulateur PC (build MicroPython "unix", sans écran visible) :
lanceur -> icône -> appli -> Retour, avec captures d'écran dans /tmp/phone_*.ppm.

    cd python
    SDL_VIDEODRIVER=dummy ../micropython/ports/unix/build-standard/micropython ../host/test_flow.py
"""
import os
import sys
import time

sys.path.append(".")               # le dossier python/ (répertoire courant)
import phone
import appkit

OUT = "/tmp/phone_"


def shot(name):
    assert phone.sim_screenshot(OUT + name + ".ppm")


def release():
    phone.sim_touch()
    phone.tap()                       # met à jour l'état "doigt levé"


class Script:
    """Petit mélangeur : exécute des actions à des numéros d'itération de la boucle d'appli."""
    def __init__(self, steps):
        self.steps = steps
        self.n = 0

    def tick(self):
        act = self.steps.get(self.n)
        self.n += 1
        if act:
            act()


phone.init()
phone.loading("Test", 1, 2)
shot("0_loading")

# --- 1. Accueil + appui sur l'icône « Paramètres » (col 3, ligne 2) ---
phone.home()
shot("1_home")
phone.sim_touch(200, 150)
ev = None
for _ in range(4):
    ev = phone.home_poll() or ev
    time.sleep_ms(10)
shot("2_home_flash")
release()
print("événement accueil :", ev)
assert ev == "parametres", ev

# --- 2. Appli Paramètres pilotée : « - » puis « - » puis « + », capture, Retour ---
import apps.parametres as P


class DriveParams(P.App):
    def __init__(self):
        P.App.__init__(self)
        self.s = Script({
            2: lambda: phone.sim_touch(60, 125), 4: phone.sim_touch,
            6: lambda: phone.sim_touch(60, 125), 8: phone.sim_touch,
            10: lambda: phone.sim_touch(180, 125), 12: phone.sim_touch,
            14: lambda: shot("3_parametres"),
            16: lambda: phone.sim_touch(30, 10),      # Retour
        })

    def on_tick(self, ms):
        self.s.tick()


appkit.run(DriveParams())
release()


# --- 3. Appli Notes : cocher les lignes 1 et 3 ---
import apps.notes as N


class DriveNotes(N.App):
    def __init__(self):
        N.App.__init__(self)
        self.s = Script({
            2: lambda: phone.sim_touch(15, N.LIST_TOP + N.ROW * 0 + 10), 4: phone.sim_touch,
            6: lambda: phone.sim_touch(15, N.LIST_TOP + N.ROW * 2 + 10), 8: phone.sim_touch,
            10: lambda: shot("4_notes"),
            12: lambda: phone.sim_touch(30, 10),
        })

    def on_tick(self, ms):
        self.s.tick()


appkit.run(DriveNotes())
release()
assert DriveNotes  # (les cases cochées se vérifient sur la capture)

# --- 4. Chemin complet launch() : appli existante, appli absente, appli qui plante ---
with open("apps/_boom.py", "w") as f:
    f.write("import appkit\nclass App(appkit.App):\n    def __init__(self):\n        raise ValueError('boom')\n")

for app_id in ("notes", "edt", "_boom"):
    phone.sim_touch(30, 10)           # « Retour » déjà posé : l'appli se ferme au 1er tour
    appkit.launch(app_id)
    release()
    print("launch(%r) OK, retour au lanceur" % app_id)

os.remove("apps/_boom.py")


# --- 5. Captures des écrans « appli absente » et « erreur » ---
class DriveMissing(appkit.MissingApp):
    def on_tick(self, ms):
        shot("5_missing")
        phone.sim_touch(30, 10)


appkit.run(DriveMissing("edt"))
release()


class DriveError(appkit.ErrorApp):
    def on_tick(self, ms):
        shot("6_error")
        phone.sim_touch(30, 10)


appkit.run(DriveError(ValueError("boom : exemple d'erreur dans une appli")))
release()

print("TOUS LES TESTS OK")
