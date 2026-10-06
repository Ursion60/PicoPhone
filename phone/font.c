#include "font.h"

const Glyph *font_glyph(const Font *f, uint32_t cp) {
    if (cp >= 0x20 && cp <= 0x7E) return &f->glyphs[cp - 0x20];
    if (cp >= 0xA0 && cp <= 0xFF) return &f->glyphs[cp - 0xA0 + 95];
    if (f->wide && f->wide_count) {                    /* recherche dichotomique (CJK...) */
        int lo = 0, hi = (int)f->wide_count - 1;
        while (lo <= hi) {
            int mid = (lo + hi) / 2;
            if (f->wide[mid].cp == cp) return &f->wide[mid].g;
            if (f->wide[mid].cp < (uint16_t)cp) lo = mid + 1; else hi = mid - 1;
        }
    }
    return &f->glyphs['?' - 0x20];
}
