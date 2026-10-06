#pragma once
#include <stdint.h>

/* Glyphe anti-aliasé : bitmap alpha 8 bits (w*h octets) stocké dans le flash. */
typedef struct {
    uint16_t off;      /* offset dans bitmap[]                                    */
    uint8_t  w, h;     /* taille du bitmap                                        */
    int8_t   xo, yo;   /* x = pen + xo ; y (haut du bitmap) = ligne de base + yo  */
    uint8_t  adv;      /* avance horizontale                                      */
} Glyph;

/* Glyphe "hors Latin-1" (CJK...), retrouvé par recherche dichotomique sur cp. */
typedef struct {
    uint16_t cp;
    Glyph    g;
} WideGlyph;

typedef struct {
    const Glyph    *glyphs;    /* ASCII 0x20-0x7E puis Latin-1 0xA0-0xFF (191 entrées) */
    const uint8_t  *bitmap;
    uint8_t         line_h;    /* hauteur de ligne (équivalent TTF_SizeUTF8().h) */
    uint8_t         ascent;
    const WideGlyph *wide;     /* glyphes étendus (CJK), triés par codepoint croissant ; NULL si aucun */
    uint16_t         wide_count;
} Font;

extern const Font font_bold13, font_small10, font_tiny9;

const Glyph *font_glyph(const Font *f, uint32_t codepoint);
