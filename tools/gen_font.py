#!/usr/bin/env python3
"""
Génère phone/font_data.c : polices bitmap anti-aliasées (alpha 8 bits) pour l'écran.
  - Glyphes ASCII + Latin-1 (0x20-0x7E, 0xA0-0xFF) : DejaVu Sans Bold, comme avant.
  - Glyphes "larges" (CJK...) : uniquement ceux réellement utilisés par les traductions de
    python/i18n.py (recherche dichotomique sur le codepoint, voir font.h). On n'embarque PAS
    une police CJK complète (des dizaines de Mo) : juste le vocabulaire de l'interface.

Usage (depuis la racine du projet) :
    python3 tools/gen_font.py [DejaVuSans-Bold.ttf] [police CJK]
Dépendance : pip install pillow
"""
import pathlib
import sys
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(HERE / "python"))
import i18n   # noqa: E402  (juste pour la liste des chaînes traduites -> codepoints CJK à embarquer)

LATIN_TTF = sys.argv[1] if len(sys.argv) > 1 else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
CJK_TTF = sys.argv[2] if len(sys.argv) > 2 else "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
CJK_TTC_INDEX = 0   # 0 = premier visage du .ttc (Noto Sans CJK JP dans NotoSansCJK-*.ttc)

FONTS = [("font_bold13", 13), ("font_small10", 10), ("font_tiny9", 9)]
LATIN_CODEPOINTS = list(range(0x20, 0x7F)) + list(range(0xA0, 0x100))
OX, OY, CANVAS = 12, 28, 48   # origine (ligne de base) dans le canevas de rendu


def wide_codepoints():
    """Tous les codepoints > U+00FF utilisés quelque part dans i18n.STRINGS ou i18n.LANG_NAMES
    (CJK...), triés."""
    cps = set()
    texts = [t for entry in i18n.STRINGS.values() for t in entry.values()]
    texts += list(i18n.LANG_NAMES.values())
    for text in texts:
        for ch in text:
            if ord(ch) > 0xFF:
                cps.add(ord(ch))
    return sorted(cps)


def render_glyph(font, ch):
    adv = int(round(font.getlength(ch)))
    img = Image.new("L", (CANVAS, CANVAS), 0)
    ImageDraw.Draw(img).text((OX, OY), ch, font=font, fill=255, anchor="ls")
    bb = img.getbbox()
    if bb is None:
        return (0, 0, 0, 0, adv), b""
    crop = img.crop(bb)
    w, h = crop.size
    return (w, h, bb[0] - OX, bb[1] - OY, adv), crop.tobytes()


def build(size, cjk_font):
    latin = ImageFont.truetype(LATIN_TTF, size)
    ascent, descent = latin.getmetrics()
    glyphs, blob = [], bytearray()

    for cp in LATIN_CODEPOINTS:
        (w, h, xo, yo, adv), data = render_glyph(latin, chr(cp))
        glyphs.append((len(blob), w, h, xo, yo, adv))
        blob.extend(data)

    wide = []
    wcps = wide_codepoints()
    if wcps and cjk_font:
        for cp in wcps:
            (w, h, xo, yo, adv), data = render_glyph(cjk_font.font_variant(size=size + 1), chr(cp))
            wide.append((cp, len(blob), w, h, xo, yo, adv))
            blob.extend(data)

    assert len(blob) < 65536, "offset uint16 dépassé (%d octets) - réduire le vocabulaire ?" % len(blob)
    return ascent, descent, glyphs, wide, blob


def main():
    try:
        cjk_font = ImageFont.truetype(CJK_TTF, 10, index=CJK_TTC_INDEX)
        print(f"police CJK : {CJK_TTF} (visage {CJK_TTC_INDEX})")
    except OSError:
        cjk_font = None
        print("!! aucune police CJK trouvée -> le japonais/chinois s'afficheront en '?' sur la carte.")
        print("   installez p.ex. fonts-noto-cjk, ou passez le chemin en 2e argument.")

    out = ["/* Fichier généré par tools/gen_font.py - ne pas éditer à la main. */",
           '#include "font.h"', ""]
    for name, size in FONTS:
        ascent, descent, glyphs, wide, blob = build(size, cjk_font)
        out.append(f"static const uint8_t {name}_bmp[{len(blob)}] = {{")
        for i in range(0, len(blob), 24):
            out.append("    " + ",".join(str(b) for b in blob[i:i + 24]) + ",")
        out.append("};")
        out.append(f"static const Glyph {name}_glyphs[{len(glyphs)}] = {{")
        for off, w, h, xo, yo, adv in glyphs:
            out.append(f"    {{{off},{w},{h},{xo},{yo},{adv}}},")
        out.append("};")
        if wide:
            out.append(f"static const WideGlyph {name}_wide[{len(wide)}] = {{")
            for cp, off, w, h, xo, yo, adv in wide:
                out.append(f"    {{{cp},{{{off},{w},{h},{xo},{yo},{adv}}}}},")
            out.append("};")
            wide_ref = f"{name}_wide"
            wide_count = str(len(wide))
        else:
            wide_ref = "0"
            wide_count = "0"
        out.append(f"const Font {name} = {{ {name}_glyphs, {name}_bmp, {ascent + descent}, {ascent}, "
                    f"{wide_ref}, {wide_count} }};")
        out.append("")
        print(f"{name}: {size}px, {len(glyphs)} glyphes Latin + {len(wide)} glyphes larges, {len(blob)} octets")

    dst = HERE / "phone" / "font_data.c"
    dst.write_text("\n".join(out), encoding="utf-8")
    print(f"-> {dst}")


if __name__ == "__main__":
    main()
