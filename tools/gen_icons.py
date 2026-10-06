#!/usr/bin/env python3
"""
Génère phone/icons_data.c à partir des PNG dans assets/icons/ (44x44, RGBA -> RGB565 + alpha 8 bits,
comme les glyphes de gen_font.py). Les coins transparents du PNG laissent voir le fond gris de l'accueil.

Usage (depuis la racine du projet) :
    python3 tools/gen_icons.py
Dépendance : pip install pillow
"""
import pathlib
from PIL import Image

SIZE = 44   # = iconSize dans ui.c (taille de la case colorée)
SRC = pathlib.Path(__file__).parent.parent / "assets" / "icons"
DST = pathlib.Path(__file__).parent.parent / "phone" / "icons_data.c"

# Nom de fichier (sans .png) -> identifiant C (doit correspondre aux apps de ui.c)
NAMES = {
    "EDT": "edt", "Notes": "notes", "NFC": "nfc", "Shop": "shop",
    "Synchro": "synchro", "Paramètres": "parametres", "Musique": "musique", "PDF": "lecteur_pdf",
}


def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def main():
    files = sorted(SRC.glob("*.png"))
    if not files:
        raise SystemExit(f"aucun .png dans {SRC}")

    out = ["/* Fichier généré par tools/gen_icons.py - ne pas éditer à la main. */",
           '#include "gfx.h"', ""]
    order = []
    for f in files:
        cid = NAMES.get(f.stem)
        if not cid:
            print(f"ignoré (pas dans NAMES) : {f.name}")
            continue
        im = Image.open(f).convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)
        pix, alpha = [], []
        for y in range(SIZE):
            for x in range(SIZE):
                r, g, b, a = im.getpixel((x, y))
                pix.append(rgb565(r, g, b))
                alpha.append(a)
        out.append(f"static const uint16_t icon_{cid}_px[{SIZE * SIZE}] = {{")
        for i in range(0, len(pix), 16):
            out.append("    " + ",".join(str(v) for v in pix[i:i + 16]) + ",")
        out.append("};")
        out.append(f"static const uint8_t icon_{cid}_a[{SIZE * SIZE}] = {{")
        for i in range(0, len(alpha), 24):
            out.append("    " + ",".join(str(v) for v in alpha[i:i + 24]) + ",")
        out.append("};")
        out.append(f"const Icon icon_{cid} = {{ {SIZE}, {SIZE}, icon_{cid}_px, icon_{cid}_a }};")
        out.append("")
        order.append(cid)
        print(f"icon_{cid}: {SIZE}x{SIZE}, {2 * SIZE * SIZE} + {SIZE * SIZE} octets")

    DST.parent.mkdir(exist_ok=True)
    DST.write_text("\n".join(out), encoding="utf-8")
    print(f"-> {DST}  ({len(order)} icônes : {', '.join(order)})")


if __name__ == "__main__":
    main()
