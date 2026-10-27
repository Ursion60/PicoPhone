# phone - interface de téléphone, applis en MicroPython (Waveshare Core2350B)

```
 applis Python (apps/*.py)      <- vous écrivez ça, sur la carte, sans recompiler
 lanceur (main.py) + appkit.py
 ─────────────────────────────
 module C `phone`  (phone/)     <- dessin rapide + écran d'accueil + tactile
   gfx.c ui.c font*.c   (identiques sur PC et sur carte)
   hal_rp2.c  (carte : ILI9341 SPI+DMA, tactile FT6336U)   |  hal_sdl.c  (PC : fenêtre SDL2)
```

Le dessin (lent en Python pur) reste en C ; la logique des applis est en MicroPython.
Toucher une icône de l'accueil lance `apps/<id>.py`, « Retour » revient à l'accueil.
Si le fichier n'existe pas, un écran « pas encore disponible » s'affiche ; si une appli plante,
le lanceur affiche l'erreur et reste en vie.

## 1. Tester sur PC (recommandé d'abord)

```bash
tools/setup-deps.sh sim tools    # détecte apt/dnf/pacman/zypper/apk/xbps/emerge et installe tout
tools/build_sim.sh               # clone MicroPython et le compile avec le module (~2 min)
cd python && ../build/micropython/ports/unix/build-standard/micropython main.py
```

Souris = doigt, Échap pour quitter. Le test automatique (lanceur -> appli -> Retour, avec captures
`/tmp/phone_*.ppm`) : `cd python && SDL_VIDEODRIVER=dummy <micropython> ../host/test_flow.py` (idem pour `test_notes.py`, `test_notes_scroll.py`, `test_keyboard.py`, `test_i18n.py`, `test_pdf.py`).

## 2. Sur la carte

1. Maintenir **BOOT** en branchant l'USB-C, copier `firmware/phone_core2350b.uf2` sur le lecteur RPI-RP2 qui apparaît
   (carte MicroPython `WAVESHARE_RP2350B_CORE` + module `phone` ; recompilable avec `tools/build_firmware.sh`).
2. `tools/setup-deps.sh tools udev` (une fois : venv avec mpremote + droits USB sans sudo), puis `tools/deploy.sh` : copie `main.py`, `appkit.py` et `apps/` sur la carte.
3. Au démarrage, `main.py` s'exécute tout seul. Ctrl-C dans `mpremote` pour reprendre la main (REPL).

Broches et hypothèses matérielles : `phone/config.h` (écran **ILI9341**, tactile **FT6336U** - à adapter si votre module
est différent). Le module s'approprie `spi0` et `i2c0` : évitez `machine.SPI(0)` / `machine.I2C(0)` dans vos scripts.

### Compatibilité Linux

Les scripts ne supposent aucune distribution : `tools/setup-deps.sh [sim] [firmware] [tools] [udev]` choisit les
bons paquets pour Debian/Ubuntu, Fedora, Arch, openSUSE, Alpine, Void et Gentoo. Python (Pillow, mpremote) est
installé dans un venv local `.venv/` (évite l'erreur « externally-managed-environment » de pip sur les distros
récentes) que les scripts `tools/*.sh` activent seuls. `gen_font.py` trouve DejaVu/Noto CJK via `fc-match`, quel que
soit le dossier de polices de la distro. Testé : Ubuntu 24.04 (compilation du simulateur + 4 tests automatiques).

- **Carte non reconnue / `Permission denied` sur `/dev/ttyACM0`** : `tools/setup-deps.sh udev` (règle `uaccess`,
  désactive aussi ModemManager sur la carte), ou, sans systemd, ajoutez-vous au groupe `dialout` (Debian/Fedora)
  ou `uucp` (Arch), puis reconnectez-vous.
- **Lecteur RPI-RP2 non monté automatiquement** (WM sans automontage, serveur) : `picotool load -f firmware/phone_core2350b.uf2`
  ou `udisksctl mount -b /dev/disk/by-label/RP2350`, ou monter à la main puis `cp`.
- **Pas de SDL2 / session sans écran** : `SDL_VIDEODRIVER=dummy` exécute les tests sans fenêtre.

## 3. Écrire une appli

Créez `python/apps/<id>.py`, où `<id>` est l'identifiant de l'icône (`edt`, `notes`, `nfc`, `shop`, `synchro`,
`parametres`, `musique`, `lecteur_pdf`) :

```python
import phone, appkit
from appkit import BLACK

class App(appkit.App):
    title = "Bonjour"

    def draw(self):                       # contenu, sous la barre de titre
        appkit.clear()
        phone.text_c("Salut !", 120, 160, BLACK, phone.BOLD)
        appkit.button(60, 200, 120, 44, "Toucher")

    def on_tap(self, x, y):               # le doigt vient de se poser
        if appkit.inside(x, y, (60, 200, 120, 44)):
            phone.text_c("Touché !", 120, 270, BLACK, phone.SMALL)
```

Exemples fournis : `apps/notes.py` (deux onglets - Tâches à cocher et Notes en titre+description,
avec ajout/consultation/édition/suppression au clavier tactile, sauvegardé sur la carte dans
`notes_data.json` : survit à un redémarrage) et `apps/parametres.py` (luminosité, langue, infos
système). `appkit.prompt_text("Titre")` ouvre un
clavier AZERTY plein écran et renvoie le texte saisi, ou `None` si Annuler :
- page lettres : majuscule (^), page chiffres/symboles (123), **page accents (icône « é »)**
  pour taper é/è/ê/ë/à/â/ä/ù/û/ü/ï/î/ô/ö/ç/ñ quelle que soit la langue de l'interface.

## Lecteur PDF

`apps/lecteur_pdf.py` (icône « PDF ») liste les `.pdf` du dossier `pdfs/` de la carte et en affiche le **texte**,
page par page. Boutons du bas : ◀ ▶ changent de page, ▲ ▼ font défiler dans la page (▼ en bas de page passe à la
suivante, ▲ en haut revient à la fin de la précédente). « < Liste » revient à la liste ; la dernière page lue de
chaque fichier est mémorisée (`pdf_state.json`).

- Ajouter des PDF : `tools/push_pdf.sh livre.pdf notes.pdf` (ou `mpremote fs cp x.pdf :pdfs/`). `tools/deploy.sh`
  copie aussi `python/pdfs/*.pdf` (un PDF d'exemple, `bienvenue.pdf`, est fourni).
- Le travail est fait par `apps/pdftext.py` (utilisable seul : `pdftext.PDF(chemin).page_text(n)`), qui ne charge
  jamais le fichier entier : table xref classique ou en flux, flux d'objets (PDF 1.5+), Flate/ASCII85/ASCIIHex,
  polices WinAnsi/MacRoman/`/Differences` et polices composites avec table `/ToUnicode` (Word, Chrome, LibreOffice,
  LaTeX...). Seule la page affichée est décompressée.
- Guillemets typographiques, tirets, ligatures (ﬁ) et € sont convertis en équivalents de la police de l'écran
  (`'`, `"`, `-`, `fi`, `EUR`) ; les caractères hors Latin-1 (cyrillique, grec, CJK dans un PDF) s'affichent en `?`.
- Messages affichés : PDF chiffré (non géré), illisible, page sans texte (scan/image), texte non décodable (police
  composite sans `/ToUnicode`), page tronquée au-delà de ~120 Ko de contenu.
- Si l'ouverture échoue avec une `MemoryError` sur la carte (compilation de `pdftext.py` en RAM), précompilez-le :
  `build/micropython/mpy-cross/build/mpy-cross python/apps/pdftext.py` puis copiez `pdftext.mpy` dans `:apps/`
  et supprimez `pdftext.py` de la carte.

## Traduire l'interface (i18n)

Tout le texte de l'interface (accueil compris, qui est en C) passe par une fonction centrale,
`i18n.t(clé)`, définie dans `python/i18n.py` :

```python
import i18n
i18n.t("app_notes")      # -> "Notes" / "Notes" / "Notas" / "Notizen" / "メモ" / "笔记" selon la langue
i18n.set_lang("EN")      # persiste le choix (lang.txt) + retraduit l'accueil (C) immédiatement
```

6 langues : `FR EN ES AL JP CN` (AL = allemand ; codes choisis tels quels, pas les codes ISO).
Réglable dans **Paramètres -> Langue** (grille de 6 boutons, la langue en cours est mise en
surbrillance). Une appli affiche ses propres textes traduits en définissant `title_key` (une clé
de `i18n.STRINGS`) au lieu de `title`, et en appelant `i18n.t(...)` dans son `draw()` - voir
`apps/notes.py` et `apps/parametres.py`.

**Ajouter une chaîne à traduire** : ajoutez une entrée à `i18n.STRINGS` dans `python/i18n.py` (une
ligne par clé, une colonne par langue), puis utilisez `i18n.t("votre_clé")` où il faut. Si le texte
contient du japonais/chinois, relancez `tools/gen_font.py` pour embarquer les nouveaux glyphes
(voir plus bas) - sinon ces caractères s'afficheront en `?`.

**Ajouter une langue** : ajoutez son code à `i18n.LANGS`, son nom (dans SA langue) à
`i18n.LANG_NAMES`, et une colonne dans chaque entrée de `i18n.STRINGS`.

### API du module `phone`

| Fonction | Rôle |
|---|---|
| `rgb(r,g,b)` | couleur (entier RGB565) |
| `clear(c)`, `fill_rect(x,y,w,h,c)`, `rect(x,y,w,h,c)`, `round_rect(x,y,w,h,r,c)`, `circle(cx,cy,r,c)`, `hline(x0,x1,y,c)` | formes |
| `text(s,x,y,c,font)` | texte, (x,y) = coin haut-gauche |
| `text_c(s,cx,cy,c,font)` | texte centré sur (cx,cy) |
| `text_l(s,x,cy,c,font)` | texte aligné à gauche, centré verticalement sur cy |
| `text_w(s,font)` | largeur d'un texte en pixels |
| `tap()` | `(x,y)` au moment où le doigt se pose, sinon `None` |
| `touch()` | `(x,y)` tant que le doigt est posé (glisser), sinon `None` |
| `flush()` | envoie à l'écran la zone modifiée (fait par `appkit.run` à chaque tour) |
| `backlight(0..255)` | luminosité |
| `WIDTH`, `HEIGHT`, `BOLD`, `SMALL`, `TINY` | constantes (écran 240x320 ; 3 polices, accents Latin-1) |

`appkit` ajoute : palette (`BG`, `BLACK`, `ACCENT`...), `header`, `clear`, `button`, `inside`, la classe `App` et `run`.
Utilisez `tap()` **ou** `touch()` dans une même boucle, pas les deux.

## Outils

- `tools/gen_font.py` : régénère `phone/font_data.c` (DejaVu Sans Bold 13/10/9 px, ASCII+Latin-1) et
  embarque aussi les glyphes CJK (japonais/chinois) nécessaires aux traductions de `python/i18n.py`,
  rendus avec une police Noto Sans CJK - **uniquement les caractères réellement utilisés dans
  i18n.py** (pas une police CJK complète : trop volumineuse). (`tools/setup-deps.sh tools` installe Pillow et les polices Noto Sans CJK) pour que le japonais/chinois s'affichent -
  sans elle, gen_font.py le signale et ces langues s'afficheront en `?`.
- `host/sim.c` : simulateur de l'écran d'accueil seul (compile en 1 s, sans MicroPython). `host/preview.c` : export .ppm.

## Intégration continue

`.github/workflows/build.yml` (GitHub Actions), à chaque push sur `main`, pull request ou lancement manuel :
- **simulateur** : `tools/build_sim.sh`, compilation des applis avec `mpy-cross`, tous les `host/test_*.py`
  (`SDL_VIDEODRIVER=dummy`) ; artefacts `captures-simulateur` (`/tmp/*.ppm`) et `picophone-apps` (fichiers copiés par `deploy.sh`) ;
- **firmware** : `tools/build_firmware.sh` sur un clone de MicroPython épinglé (`MPY_REF`, même commit que
  `build/micropython`) ; artefact `firmware-uf2`.

Un tag `v*` (ex. `git tag v0.2 && git push origin v0.2`) crée en plus une release GitHub avec le `.uf2` et le zip des applis.
Le firmware est seulement compilé : la CI ne le teste pas sur la carte.

## Limites connues

- Non testé sur la vraie carte (pas de matériel ici) : le firmware compile et le module a été exécuté sur le simulateur PC,
  mais les pilotes `hal_rp2.c` (ILI9341, FT6336U, brochage) restent à valider chez vous.
- Les 8 Mo de PSRAM ne sont pas utilisés (le framebuffer de 150 Ko tient en SRAM) ; ils serviront aux icônes/PDF plus tard.
- Pas encore : lecteur PN532, carte SD, heure/batterie réelles (l'accueil affiche 12:30 et 75 % en dur).
- Traductions EN/ES/AL/JP/CN faites de mon mieux, sans relecture native - à corriger dans
  `i18n.STRINGS` si une formulation sonne mal, notamment le japonais/chinois.
- Clavier : la page accents couvre é è ê ë à â ä ù û ü ï î ô ö ç ñ (français/espagnol/allemand) -
  pas d'IME japonais/chinois (kana/hanzi) : au-delà de l'affichage traduit de l'interface, taper du
  texte reste en alphabet latin.
- Notes : chaque note a un titre et une description ("voir" ouvre la consultation, "Modifier"
  ré-ouvre le clavier pour les deux, à la suite) ; suppression sans annulation possible une fois
  confirmée (2e tap sur ×) ; au-delà de 6 lignes, deux flèches ▲▼ à côté du bouton « + » font défiler
  la liste (le nouvel élément ajouté est affiché automatiquement) ; texte tronqué avec « .. » plutôt que de
  passer sous le bouton ×, description longue coupée par « ... » ; sauvegarde atomique (`notes_data.json.tmp`
  puis renommage) : une coupure en pleine écriture ne perd plus les notes.
- PDF : texte seul (pas d'images ni de mise en page, colonnes lues dans l'ordre du fichier) ; pas de PDF chiffrés, pas
  de reconstruction d'une table xref cassée ; au plus 15 000 objets par fichier (la table xref tient en RAM) ; non testé
  sur la vraie carte (validé sur le simulateur avec PDF de reportlab, fpdf2 et pikepdf).
- Icônes : les 8 PNG fournis (`assets/icons/`) sont déjà convertis en `phone/icons_data.c` par
  `tools/gen_icons.py` (44x44, coins transparents) - relancez ce script si vous changez les images.

## Dépannage

**`Erreur de segmentation (core dumped)` au lancement du simulateur PC** : observé sur des systèmes
avec un pilote NVIDIA propriétaire, en conteneur (toolbox/distrobox) sous Wayland. Deux causes
possibles, toutes deux dans ce dossier :
1. Sous Wayland, quand le compositeur ne gère pas nativement les bordures, SDL dessine la barre de
   titre via `libdecor`, qui utilise elle-même OpenGL/EGL en interne - et c'est cette étape,
   indépendante de tout rendu applicatif, qui peut planter dans le pilote GPU. `phone/hal_sdl.c`
   désactive maintenant `libdecor` (`SDL_VIDEO_WAYLAND_ALLOW_LIBDECOR=0`) : la fenêtre est décorée
   par le compositeur lui-même (KDE Plasma, GNOME...) si celui-ci le permet, sinon simplement sans
   bordure - jamais de plantage pour cette raison.
2. Le rendu lui-même : `phone/hal_sdl.c` n'utilise plus `SDL_Renderer`/`SDL_Texture` (dont la
   configuration en logiciel s'est révélée silencieusement ignorée par `sdl2-compat`, la couche de
   compatibilité SDL2-sur-SDL3 de Fedora, une fois lié dans un gros binaire comme MicroPython), et
   dessine directement sur la surface de la fenêtre.

Si votre copie est plus ancienne, reconstruisez (`rm -rf build && tools/build_sim.sh`). Si ça
plante encore, un backtrace précis reste le plus efficace pour avancer : `coredumpctl gdb` juste
après le plantage (Fedora capture le core automatiquement), puis `bt` une fois dans gdb ; ou `gdb
--batch -ex run -ex bt --args ../build/micropython/ports/unix/build-standard/micropython main.py`.
En dernier recours, `SDL_VIDEO_DRIVER=x11` et/ou forcer une fenêtre sans bordure évitent tout
recours à `libdecor`.
