"""Point d'entrée : MicroPython l'exécute automatiquement au démarrage de la carte."""
import time
import phone
import appkit
import i18n

phone.init()
i18n.load()                         # relit la langue choisie précédemment (lang.txt), sinon FR
i18n.push_to_home()                 # traduit accueil/options/toutes-les-apps avant le 1er dessin
phone.loading(i18n.t("starting"), 1, 2)
phone.backlight(255)
time.sleep_ms(150)

phone.home()
while True:
    app_id = phone.home_poll()          # None, ou l'identifiant de l'icône touchée
    if app_id:
        time.sleep_ms(120)              # laisse voir l'icône s'allumer
        appkit.launch(app_id)           # exécute apps/<app_id>.py
        phone.home()                    # retour à l'accueil
    time.sleep_ms(10)
