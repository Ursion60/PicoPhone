# PicoPhone en Rust

Réécriture complète de PicoPhone en Rust, **système compris** : plus de MicroPython, un seul firmware
Rust pour la Waveshare Core2350B (RP2350B). Ce travail vit sur la branche `rust`, séparée de `main` et
`develop`. Le code C/MicroPython reste dans le dépôt comme référence tant que le port n'a pas rattrapé
toutes ses fonctions.

## Organisation

| Crate | Cible | Rôle |
|---|---|---|
| `crates/picophone-gfx` | `no_std`, sans allocation | framebuffer RGB565 240x320, zone sale, formes, texte UTF-8, icônes (port de `phone/gfx.c`) ; polices et icônes générées |
| `crates/picophone-ui` | `no_std`, sans allocation | écran d'accueil traduisible, écran de chargement, écran provisoire « pas encore portée » (port de `phone/ui.c`) |
| `crates/picophone-sim` | PC | simulateur sans fenêtre : rend les écrans et écrit des captures PPM |
| `crates/picophone-parity` | PC, tests | compile le moteur C historique (`phone/*.c`) et vérifie que Rust produit **les mêmes pixels** |
| `firmware/` | `thumbv8m.main-none-eabihf` | firmware RP2350B ([embassy-rp](https://github.com/embassy-rs/embassy) 0.10) : ILI9341 en SPI0 + DMA, FT6336U en I2C0, accueil |

Le firmware est un workspace à part (sa cible et son `.cargo/config.toml`). Les broches sont celles de
`phone/config.h` (constantes en tête de `firmware/src/main.rs`, `display.rs`, `touch.rs`).

## Construire et tester

```bash
cd rust
cargo test --workspace                     # tests + parité pixel avec le moteur C
cargo run -p picophone-sim -- /tmp/captures  # captures PPM de l'accueil, du chargement...

cd firmware
cargo build --release                      # ELF pour le RP2350B
cargo run --release                        # flashe avec picotool (carte en mode BOOTSEL)
```

La toolchain (stable, `thumbv8m.main-none-eabihf`, rustfmt, clippy) est fixée par `rust-toolchain.toml`.
Pour flasher : [picotool](https://github.com/raspberrypi/picotool) dans le PATH.

**Polices et icônes** : `tools/gen_font.py` et `tools/gen_icons.py` écrivent en même temps les données C
(`phone/*_data.c`) et Rust (`crates/picophone-gfx/src/*_data.rs`, `data/*.bin`), à partir des mêmes tableaux.
Ne modifiez pas ces fichiers à la main.

## Ce qui est vérifié (étape 1)

- **Parité pixel avec le C** (`crates/picophone-parity`) : 4 000 opérations tirées au hasard (graine fixe :
  rectangles, cercles, arrondis, transparence, icônes à moitié hors écran, texte latin, accents, CJK, caractères
  absents de la police), puis l'accueil dans 4 langues avec taps sur toute la grille, flashs, fins de flash et
  débordement de l'horloge 32 bits. Après **chaque** opération : framebuffers identiques et zones sales identiques.
  8 erreurs volontaires introduites dans le port Rust ont toutes été détectées.
- Le firmware **compile et se lie** pour le RP2350B, sans avertissement (`clippy -D warnings`) : bloc `IMAGE_DEF`
  dans les 4 premiers Ko de flash, framebuffer de 150 Ko en RAM statique.
- **Pas encore essayé sur la carte.**

Différences voulues avec le C :

- Un libellé trop long est coupé sur une frontière de caractère (le C coupait à l'octet et pouvait casser un
  caractère UTF-8).
- Un caractère hors du plan de base (emoji) s'affiche « ? » une fois, et non une fois par octet.
- Le SPI d'embassy-rp est en 8 bits : chaque ligne est convertie en octets avant l'envoi en DMA (le C passait le
  SPI en 16 bits).

## Feuille de route

1. ~~Moteur graphique, polices, icônes, accueil, simulateur, squelette du firmware~~ (fait).
2. Simulateur avec fenêtre (souris = doigt) et boucle d'événements commune au simulateur et à la carte.
3. Cadre d'applis (`trait App` : dessin, taps, retour, minuterie) et clavier tactile AZERTY (accents compris).
4. Traductions en Rust (générées depuis la même source que les chaînes actuelles) et paramètres (luminosité, langue).
5. Stockage en flash (système de fichiers ou journal clé-valeur résistant aux coupures) : Notes, EDT, réglages.
6. Liaison USB avec le PC (CDC série) : remplace `mpremote` pour la synchro EDT (`tools/sync_pronote.py`) et le
   dépôt de PDF.
7. Lecteur PDF (décompression `miniz_oxide`, lecture page par page comme `pdftext.py`).
8. Quand tout est porté et validé sur la carte : retrait du code C/MicroPython de cette branche.
