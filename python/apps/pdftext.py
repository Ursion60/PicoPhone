"""
pdftext : lit un PDF sur le système de fichiers de la carte et en extrait le texte, page par page.

    from apps import pdftext
    pdf = pdftext.PDF("pdfs/mon_doc.pdf")     # lève PDFError si illisible / chiffré
    pdf.n_pages                               # nombre de pages
    texte = pdf.page_text(0)                  # texte de la page 1 (str)
    pdf.truncated, pdf.unreadable             # page coupée (trop longue) / octets de texte non décodables
    pdf.close()

Conçu pour MicroPython (RP2350) : le fichier n'est jamais chargé en entier, seul le contenu de la
page affichée est décompressé (plafonné). Gère : table xref classique ou flux xref, flux d'objets
(PDF 1.5+), FlateDecode (+ prédicteurs PNG), polices simples (WinAnsi, MacRoman, /Differences) et
composites avec table /ToUnicode.
Ne gère pas : PDF chiffrés, images/OCR, polices Type0 sans ToUnicode, XObjects de formulaire,
fichiers dont la table xref est cassée.
"""
import io
from array import array

try:
    import deflate
except ImportError:                      # CPython (tests hors carte)
    deflate = None
    import zlib

MAX_RAW = 200000          # octets compressés lus en mémoire pour un flux
MAX_CONTENT = 120000      # octets décompressés d'une page (au-delà : page tronquée)
MAX_OBJS = 15000          # nombre d'objets maximum (table xref en RAM : 5 octets/objet)


_ISZ = len(bytes(array("I", [0])))     # taille d'un élément 'I' (pas d'itemsize en MicroPython)


class PDFError(Exception):
    pass


class Incomplete(Exception):
    """Le tampon s'arrête au milieu d'un objet."""


class Kw:
    def __init__(self, v):
        self.v = v


class Ref:
    def __init__(self, n):
        self.n = n


class Stream:
    def __init__(self, d, pos, length):
        self.d = d
        self.pos = pos
        self.length = length


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------
_WIN80 = '€\x00‚ƒ„…†‡ˆ‰Š‹Œ\x00Ž\x00\x00‘’“”•–—˜™š›œ\x00žŸ'
_MAC = 'ÄÅÇÉÑÖÜáàâäãåçéèêëíìîïñóòôöõúùûü†°¢£§•¶ß®©™´¨≠ÆØ∞±≤≥¥µ∂∑∏π∫ªºΩæø¿¡¬√ƒ≈∆«»…\xa0ÀÃÕŒœ–—“”‘’÷◊ÿŸ⁄€‹›ﬁﬂ‡·‚„‰ÂÊÁËÈÍÎÏÌÓÔ\uf8ffÒÚÛÙıˆ˜¯˘˙˚¸˝˛ˇ'
_GLYPHS = (
    'exclam:! quotedbl:" numbersign:# dollar:$ percent:% ampersand:& quotesingle:\' parenleft:( parenright:) '
    'asterisk:* plus:+ comma:, hyphen:- period:. slash:/ zero:0 one:1 two:2 three:3 four:4 five:5 '
    'six:6 seven:7 eight:8 nine:9 colon:: semicolon:; less:< equal:= greater:> question:? at:@ bracketleft:[ '
    'backslash:\\ bracketright:] asciicircum:^ underscore:_ grave:` braceleft:{ bar:| braceright:} '
    'asciitilde:~ exclamdown:¡ cent:¢ sterling:£ currency:¤ yen:¥ brokenbar:¦ section:§ dieresis:¨ '
    'copyright:© ordfeminine:ª guillemotleft:« logicalnot:¬ sfthyphen: registered:® macron:¯ degree:° '
    'plusminus:± twosuperior:² threesuperior:³ acute:´ mu:µ paragraph:¶ periodcentered:· cedilla:¸ '
    'onesuperior:¹ ordmasculine:º guillemotright:» onequarter:¼ onehalf:½ threequarters:¾ questiondown:¿ '
    'multiply:× divide:÷ Agrave:À Aacute:Á Acircumflex:Â Atilde:Ã Adieresis:Ä Aring:Å AE:Æ Ccedilla:Ç '
    'Egrave:È Eacute:É Ecircumflex:Ê Edieresis:Ë Igrave:Ì Iacute:Í Icircumflex:Î Idieresis:Ï Eth:Ð '
    'Ntilde:Ñ Ograve:Ò Oacute:Ó Ocircumflex:Ô Otilde:Õ Odieresis:Ö Oslash:Ø Ugrave:Ù Uacute:Ú Ucircumflex:Û '
    'Udieresis:Ü Yacute:Ý Thorn:Þ germandbls:ß agrave:à aacute:á acircumflex:â atilde:ã adieresis:ä '
    'aring:å ae:æ ccedilla:ç egrave:è eacute:é ecircumflex:ê edieresis:ë igrave:ì iacute:í icircumflex:î '
    'idieresis:ï eth:ð ntilde:ñ ograve:ò oacute:ó ocircumflex:ô otilde:õ odieresis:ö oslash:ø ugrave:ù '
    'uacute:ú ucircumflex:û udieresis:ü yacute:ý thorn:þ ydieresis:ÿ OE:Œ oe:œ Scaron:Š scaron:š '
    'Zcaron:Ž zcaron:ž Ydieresis:Ÿ Lslash:Ł lslash:ł dotlessi:ı endash:– emdash:— quoteleft:‘ quoteright:’ '
    'quotesinglbase:‚ quotedblleft:“ quotedblright:” quotedblbase:„ dagger:† daggerdbl:‡ bullet:• '
    'ellipsis:… perthousand:‰ guilsinglleft:‹ guilsinglright:› Euro:€ euro:€ trademark:™ fi:ﬁ fl:ﬂ '
    'ff:ﬀ ffi:ﬃ ffl:ﬄ florin:ƒ circumflex:ˆ minus:− fraction:⁄ nbspace:  nonbreakingspace:  softhyphen:'
)
_glyph_map = None

_CLS = bytearray(256)                    # 1 = blanc, 2 = délimiteur
for _c in b"\x00\t\n\x0c\r ":
    _CLS[_c] = 1
for _c in b"()<>[]{}/%":
    _CLS[_c] = 2


def _glyph(name):
    """Nom de glyphe PDF -> texte (ou None si inconnu)."""
    global _glyph_map
    if _glyph_map is None:
        _glyph_map = {}
        for item in _GLYPHS.split(" "):
            k, _, v = item.partition(":")
            _glyph_map[k] = v
    if name == "space":
        return " "
    v = _glyph_map.get(name)
    if v is not None:
        return v
    if len(name) == 1:
        return name
    if "." in name:
        return _glyph(name.split(".")[0]) if name[0] != "." else None
    if "_" in name:
        out = ""
        for part in name.split("_"):
            g = _glyph(part)
            if g is None:
                return None
            out += g
        return out
    try:
        if name.startswith("uni") and len(name) >= 7:
            return chr(int(name[3:7], 16))
        if name[0] == "u" and 5 <= len(name) <= 7:
            return chr(int(name[1:], 16))
    except ValueError:
        pass
    return None


# ---------------------------------------------------------------------------
# Analyseur de syntaxe PDF
# ---------------------------------------------------------------------------
def _skip(s, i):
    n = len(s)
    while i < n:
        c = s[i]
        if _CLS[c] == 1:
            i += 1
        elif c == 37:                                   # % commentaire
            while i < n and s[i] != 10 and s[i] != 13:
                i += 1
        else:
            break
    return i


def _name(b):
    if 35 in b:                                         # #xx
        out = bytearray()
        k = 0
        while k < len(b):
            if b[k] == 35 and k + 2 < len(b):
                try:
                    out.append(int(b[k + 1:k + 3], 16))
                    k += 3
                    continue
                except ValueError:
                    pass
            out.append(b[k])
            k += 1
        b = bytes(out)
    try:
        return b.decode()
    except (UnicodeError, ValueError):
        return "?"


def _lit(s, i):
    n = len(s)
    i += 1
    depth = 1
    out = bytearray()
    while i < n:
        c = s[i]
        i += 1
        if c == 92:
            if i >= n:
                break
            c = s[i]
            i += 1
            if c == 110:
                out.append(10)
            elif c == 114:
                out.append(13)
            elif c == 116:
                out.append(9)
            elif c == 98:
                out.append(8)
            elif c == 102:
                out.append(12)
            elif 48 <= c <= 55:
                v = c - 48
                for _ in range(2):
                    if i < n and 48 <= s[i] <= 55:
                        v = v * 8 + s[i] - 48
                        i += 1
                    else:
                        break
                out.append(v & 255)
            elif c == 13:
                if i < n and s[i] == 10:
                    i += 1
            elif c != 10:
                out.append(c)
        elif c == 40:
            depth += 1
            out.append(c)
        elif c == 41:
            depth -= 1
            if depth == 0:
                return bytes(out), i
            out.append(c)
        else:
            out.append(c)
    raise Incomplete()


def _hex(s, i):
    n = len(s)
    out = bytearray()
    hi = -1
    while i < n:
        c = s[i]
        i += 1
        if c == 62:
            if hi >= 0:
                out.append(hi << 4)
            return bytes(out), i
        if 48 <= c <= 57:
            d = c - 48
        elif 65 <= c <= 70:
            d = c - 55
        elif 97 <= c <= 102:
            d = c - 87
        else:
            continue
        if hi < 0:
            hi = d
        else:
            out.append((hi << 4) | d)
            hi = -1
    raise Incomplete()


def _array(s, i, refs):
    out = []
    while True:
        i = _skip(s, i)
        if i >= len(s):
            raise Incomplete()
        if s[i] == 93:
            return out, i + 1
        v, i = parse(s, i, refs)
        out.append(v)


def _dict(s, i, refs):
    d = {}
    while True:
        i = _skip(s, i)
        n = len(s)
        if i >= n:
            raise Incomplete()
        if s[i] == 62:
            if i + 1 >= n:
                raise Incomplete()
            return d, i + 2
        k, i = parse(s, i, refs)
        if type(k) is not str:
            continue
        i = _skip(s, i)
        if i >= n:
            raise Incomplete()
        if s[i] == 62:
            d[k] = None
            continue
        v, i = parse(s, i, refs)
        if type(v) is Kw:                               # objet mal formé (endobj...)
            return d, i
        d[k] = v


def parse(s, i, refs=False):
    """Lit un objet PDF dans s à partir de i -> (valeur, nouvel indice).
    nom -> str, chaîne -> bytes, tableau -> list, dict -> dict, référence -> Ref, mot-clé -> Kw."""
    n = len(s)
    i = _skip(s, i)
    if i >= n:
        raise Incomplete()
    c = s[i]
    if c == 47:
        j = i + 1
        while j < n and _CLS[s[j]] == 0:
            j += 1
        return _name(s[i + 1:j]), j
    if c == 40:
        return _lit(s, i)
    if c == 60:
        if i + 1 < n and s[i + 1] == 60:
            return _dict(s, i + 2, refs)
        return _hex(s, i + 1)
    if c == 91:
        return _array(s, i + 1, refs)
    if _CLS[c] == 2:                                    # ) > ] { } égarés
        return Kw(chr(c)), i + 1
    j = i + 1
    while j < n and _CLS[s[j]] == 0:
        j += 1
    tok = s[i:j]
    if c < 58 and (c > 47 or c == 43 or c == 45 or c == 46):
        try:
            v = int(tok)
        except ValueError:
            try:
                return float(tok.decode()), j
            except ValueError:
                return Kw(tok.decode()), j
        if refs and v >= 0:
            k = _skip(s, j)
            e = k
            while e < n and 48 <= s[e] <= 57:
                e += 1
            if e > k:
                e2 = _skip(s, e)
                if e2 < n and s[e2] == 82 and (e2 + 1 >= n or _CLS[s[e2 + 1]] != 0):
                    return Ref(v), e2 + 1
        return v, j
    if tok == b"true":
        return True, j
    if tok == b"false":
        return False, j
    if tok == b"null":
        return None, j
    try:
        return Kw(tok.decode()), j
    except (UnicodeError, ValueError):
        return Kw("?"), j


# ---------------------------------------------------------------------------
# Décompression
# ---------------------------------------------------------------------------
def _inflate(data, limit):
    if deflate is None:
        return zlib.decompressobj().decompress(data, limit)
    r = deflate.DeflateIO(io.BytesIO(data), deflate.ZLIB)
    out = bytearray()
    try:
        while len(out) < limit:
            chunk = r.read(min(4096, limit - len(out)))
            if not chunk:
                break
            out += chunk
    except (OSError, ValueError, EOFError):
        if not out:
            raise PDFError("flux corrompu")
    return bytes(out)


def _a85(data):
    out = bytearray()
    grp = []
    i = 0
    n = len(data)
    if data[:2] == b"<~":
        i = 2
    while i < n:
        c = data[i]
        i += 1
        if c == 126:                                    # ~> fin
            break
        if _CLS[c] == 1:
            continue
        if c == 122 and not grp:                        # z = 4 octets nuls
            out += b"\0\0\0\0"
            continue
        grp.append(c - 33)
        if len(grp) == 5:
            v = 0
            for d in grp:
                v = v * 85 + d
            out += bytes(((v >> 24) & 255, (v >> 16) & 255, (v >> 8) & 255, v & 255))
            grp = []
    k = len(grp)
    if k > 1:
        for _ in range(5 - k):
            grp.append(84)
        v = 0
        for d in grp:
            v = v * 85 + d
        out += bytes(((v >> 24) & 255, (v >> 16) & 255, (v >> 8) & 255, v & 255))[:k - 1]
    return bytes(out)


def _ahex(data):
    k = data.find(b">")
    s, _ = _hex(data[:k] + b">" if k >= 0 else data + b">", 0)
    return s


def _unpredict(data, parms):
    p = parms.get("Predictor", 1)
    if not isinstance(p, int) or p < 10:
        return data
    cols = parms.get("Columns", 1)
    colors = parms.get("Colors", 1)
    bpc = parms.get("BitsPerComponent", 8)
    bpp = max(1, colors * bpc // 8)
    rl = (cols * colors * bpc + 7) // 8
    rows = len(data) // (rl + 1)
    out = bytearray(rows * rl)
    prev = bytearray(rl)
    pos = 0
    for r in range(rows):
        ft = data[pos]
        row = bytearray(data[pos + 1:pos + 1 + rl])
        pos += rl + 1
        if ft == 1:
            for k in range(bpp, rl):
                row[k] = (row[k] + row[k - bpp]) & 255
        elif ft == 2:
            for k in range(rl):
                row[k] = (row[k] + prev[k]) & 255
        elif ft == 3:
            for k in range(rl):
                left = row[k - bpp] if k >= bpp else 0
                row[k] = (row[k] + ((left + prev[k]) >> 1)) & 255
        elif ft == 4:
            for k in range(rl):
                a = row[k - bpp] if k >= bpp else 0
                b = prev[k]
                c = prev[k - bpp] if k >= bpp else 0
                pa = abs(b - c)
                pb = abs(a - c)
                pc = abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                row[k] = (row[k] + pr) & 255
        out[r * rl:(r + 1) * rl] = row
        prev = row
    return bytes(out)


# ---------------------------------------------------------------------------
# Polices
# ---------------------------------------------------------------------------
def _code(b):
    v = 0
    for x in b:
        v = (v << 8) | x
    return v


def _u16(b):
    if len(b) == 1:
        return chr(b[0])
    out = []
    i = 0
    n = len(b)
    while i + 1 < n:
        u = (b[i] << 8) | b[i + 1]
        i += 2
        if 0xD800 <= u < 0xDC00 and i + 1 < n:
            lo = (b[i] << 8) | b[i + 1]
            if 0xDC00 <= lo < 0xE000:
                i += 2
                u = 0x10000 + ((u - 0xD800) << 10) + (lo - 0xDC00)
        if 0xD800 <= u < 0xE000:
            continue
        out.append(chr(u))
    return "".join(out)


class Font:
    def __init__(self, pdf, fd):
        self.tu = None
        self.rng = None
        self.two = False
        self.ucs2 = False
        self.mac = False
        self.diff = None
        enc = pdf.res(fd.get("Encoding"))
        if fd.get("Subtype") == "Type0":
            self.two = True
            if isinstance(enc, str) and ("UCS2" in enc or "UTF16" in enc):
                self.ucs2 = True
        elif isinstance(enc, str):
            self.mac = enc == "MacRomanEncoding"
        elif isinstance(enc, dict):
            be = pdf.res(enc.get("BaseEncoding"))
            self.mac = be == "MacRomanEncoding"
            diffs = pdf.res(enc.get("Differences"))
            if isinstance(diffs, list):
                self.diff = {}
                code = 0
                for it in diffs:
                    if type(it) is int:
                        code = it
                    elif type(it) is str:
                        self.diff[code] = _glyph(it) or ""
                        code += 1
        tu = pdf.res(fd.get("ToUnicode"))
        if isinstance(tu, Stream):
            try:
                self._cmap(pdf.stream_data(tu, 200000))
            except (PDFError, OSError, ValueError, KeyError):
                self.tu = None
        self.unreadable = self.two and not self.ucs2 and self.tu is None and not self.rng

    def _cmap(self, data):
        tu = {}
        rng = []
        i = 0
        st = []
        mode = 0
        while True:
            try:
                v, i = parse(data, i)
            except Incomplete:
                break
            if type(v) is Kw:
                k = v.v
                if k == "beginbfchar":
                    mode, st = 1, []
                elif k == "beginbfrange":
                    mode, st = 2, []
                elif k == "endbfchar":
                    for j in range(0, len(st) - 1, 2):
                        if type(st[j]) is bytes and type(st[j + 1]) is bytes:
                            tu[_code(st[j])] = _u16(st[j + 1])
                    mode = 0
                elif k == "endbfrange":
                    for j in range(0, len(st) - 2, 3):
                        lo, hi, dst = st[j], st[j + 1], st[j + 2]
                        if type(lo) is bytes and type(hi) is bytes:
                            lo, hi = _code(lo), _code(hi)
                            if type(dst) is bytes and dst:
                                rng.append((lo, hi, dst))
                            elif type(dst) is list:
                                for q, d in enumerate(dst):
                                    if lo + q <= hi and type(d) is bytes:
                                        tu[lo + q] = _u16(d)
                    mode = 0
            elif mode:
                st.append(v)
        if tu or rng:
            self.tu = tu
            self.rng = rng

    def _lookup(self, code):
        s = self.tu.get(code)
        if s is not None:
            return s
        for lo, hi, dst in self.rng:
            if lo <= code <= hi:
                base = _u16(dst)
                if not base:
                    return ""
                return base[:-1] + chr(ord(base[-1]) + code - lo)
        return None

    def _base(self, c):
        if c < 128:
            return chr(c)
        if self.mac:
            return _MAC[c - 128]
        if c < 160:
            return _WIN80[c - 128]
        return chr(c)

    def decode(self, b):
        if self.two:
            out = []
            for p in range(0, len(b) - 1, 2):
                code = (b[p] << 8) | b[p + 1]
                if self.ucs2:
                    s = chr(code) if not 0xD800 <= code < 0xE000 else ""
                elif self.tu is not None:
                    s = self._lookup(code)
                else:
                    s = None
                if s is None:
                    self.miss += 1
                else:
                    out.append(s)
            return "".join(out)
        if self.tu is None and self.diff is None and not self.mac:
            try:
                s = b.decode()
                if len(s) == len(b):
                    return s
            except (UnicodeError, ValueError):
                pass
        out = []
        diff = self.diff
        for c in b:
            if diff is not None and c in diff:
                out.append(diff[c])
            elif self.tu is not None:
                s = self._lookup(c)
                out.append(s if s is not None else self._base(c))
            else:
                out.append(self._base(c))
        return "".join(out)

    miss = 0


# ---------------------------------------------------------------------------
# Interprète de flux de contenu (texte seulement)
# ---------------------------------------------------------------------------
class _Interp:
    def __init__(self, pdf, fonts):
        self.pdf = pdf
        self.fdict = fonts
        self.font = None
        self.size = 1.0
        self.out = []
        self.last = ""
        self.cy = None
        self.lead = 0
        self.lx = self.ly = 0
        self.sc = 1.0
        self.ctm = [1, 0, 0, 1, 0, 0]
        self.stack = []
        self.miss = 0

    def feed(self, data):
        i = 0
        st = []
        while True:
            try:
                v, i = parse(data, i)
            except Incomplete:
                break
            if type(v) is Kw:
                o = v.v
                if o == "ID":                           # image en ligne : on saute les données
                    j = data.find(b"EI", i)
                    if j < 0:
                        break
                    i = j + 2
                else:
                    self.op(o, st)
                st = []
            else:
                st.append(v)
                if len(st) > 64:
                    del st[0]

    def _y(self):
        c = self.ctm
        return self.lx * c[1] + self.ly * c[3] + c[5]

    def emit(self, t):
        if not t:
            return
        y = self._y()
        eff = max(abs(self.size * self.sc * self.ctm[3]), 0.5)
        if self.cy is not None:
            dy = abs(y - self.cy)
            if dy > 0.6 * eff:
                self.out.append("\n\n" if dy > 2.2 * eff else "\n")
            elif self.last and self.last[-1] != " " and t[0] != " ":
                self.out.append(" ")
        self.cy = y
        self.out.append(t)
        self.last = t

    def _font(self, name):
        cache = self.pdf.font_cache
        ref = self.fdict.get(name)
        key = ref.n if isinstance(ref, Ref) else None
        if key is not None and key in cache:
            return cache[key]
        fd = self.pdf.res(ref)
        if not isinstance(fd, dict):
            return None
        f = Font(self.pdf, fd)
        if key is not None:
            if len(cache) > 8:
                cache.clear()
            cache[key] = f
        return f

    def show(self, b):
        f = self.font
        if f is not None and type(b) is bytes:
            f.miss = 0
            self.emit(f.decode(b))
            self.miss += f.miss

    def op(self, o, st):
        n = len(st)
        if o == "Tj":
            if n:
                self.show(st[-1])
        elif o == "TJ":
            f = self.font
            if f is not None and n and type(st[-1]) is list:
                parts = []
                f.miss = 0
                for it in st[-1]:
                    if type(it) is bytes:
                        parts.append(f.decode(it))
                    elif (type(it) is int or type(it) is float) and it < -180:
                        if parts and not parts[-1].endswith(" "):
                            parts.append(" ")
                self.miss += f.miss
                self.emit("".join(parts))
        elif o == "Tf":
            if n >= 2 and type(st[-2]) is str:
                self.font = self._font(st[-2])
                try:
                    self.size = float(st[-1])
                except (TypeError, ValueError):
                    pass
        elif o == "Td" or o == "TD":
            if n >= 2:
                self.lx += st[-2] * self.sc
                self.ly += st[-1] * self.sc
                if o == "TD":
                    self.lead = -st[-1]
        elif o == "Tm":
            if n >= 6:
                self.lx, self.ly = st[-2], st[-1]
                self.sc = abs(st[-3]) or 1.0
        elif o == "T*":
            self.ly -= self.lead * self.sc
        elif o == "'" or o == '"':
            self.ly -= self.lead * self.sc
            if n:
                self.show(st[-1])
        elif o == "TL":
            if n:
                self.lead = st[-1]
        elif o == "BT":
            self.lx = self.ly = 0
            self.sc = 1.0
        elif o == "q":
            self.stack.append(list(self.ctm))
            if len(self.stack) > 40:
                del self.stack[0]
        elif o == "Q":
            if self.stack:
                self.ctm = self.stack.pop()
        elif o == "cm":
            if n >= 6:
                a, b, c, d, e, f = st[-6:]
                A, B, C, D, E, F = self.ctm
                try:
                    self.ctm = [a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D,
                                e * A + f * C + E, e * B + f * D + F]
                except TypeError:
                    pass

    def result(self):
        text = "".join(self.out)
        keep = []
        for ch in text:
            if ch == "\n" or ch >= " ":
                keep.append(ch)
        return "".join(keep).strip()


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------
class PDF:
    def __init__(self, path):
        self.f = open(path, "rb")
        self.truncated = False
        self.unreadable = 0
        self.font_cache = {}
        self._os = None
        try:
            self._open()
        except Exception:
            self.close()
            raise

    def close(self):
        try:
            self.f.close()
        except Exception:
            pass

    # ----- ouverture -----
    def _open(self):
        f = self.f
        f.seek(0)
        head = f.read(1024)
        h = head.find(b"%PDF-")
        if h < 0:
            raise PDFError("pas un PDF")
        self.base = h
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 2048))
        tail = f.read(2048)
        k = tail.rfind(b"startxref")
        if k < 0:
            raise PDFError("xref introuvable")
        try:
            pos, _ = parse(tail, k + 9)
        except Incomplete:
            raise PDFError("xref introuvable")
        if type(pos) is not int:
            raise PDFError("xref introuvable")
        self.xt = array("B")
        self.xa = array("I")
        self.trailer = None
        seen = set()
        while type(pos) is int and pos not in seen:
            seen.add(pos)
            tr = self._xref_at(pos)
            if self.trailer is None:
                self.trailer = tr
            xs = tr.get("XRefStm")
            if type(xs) is int and xs not in seen:
                seen.add(xs)
                self._xref_at(xs)
            pos = tr.get("Prev")
        if "Encrypt" in self.trailer:
            raise PDFError("chiffré")
        root = self.res(self.trailer.get("Root"))
        if not isinstance(root, dict):
            raise PDFError("catalogue introuvable")
        top = self.res(root.get("Pages"))
        if not isinstance(top, dict):
            raise PDFError("pages introuvables")
        kids = self.res(top.get("Kids"))
        self.page_nums = array("I")
        if isinstance(kids, list):
            self._stack = [(kids, 0)]
            cnt = self.res(top.get("Count"))
        else:
            ref = root.get("Pages")
            self.page_nums.append(ref.n if isinstance(ref, Ref) else 0)
            self._stack = []
            cnt = 1
        if type(cnt) is not int or cnt < 1:
            while self._advance():
                pass
            cnt = len(self.page_nums)
        self.n_pages = cnt

    def _grow(self, n):
        if n > MAX_OBJS:
            raise PDFError("PDF trop volumineux")
        k = n - len(self.xt)
        if k > 0:
            self.xt.extend(array("B", bytes(k)))
            self.xa.extend(array("I", bytes(k * _ISZ)))

    def _set(self, num, typ, a):
        if num >= len(self.xt):
            self._grow(num + 1)
        if self.xt[num] == 0:
            self.xt[num] = typ
            self.xa[num] = a

    def _xref_at(self, pos):
        f = self.f
        f.seek(self.base + pos)
        head = f.read(64)
        j = _skip(head, 0)
        if head[j:j + 4] == b"xref":
            return self._table(self.base + pos + j + 4)
        return self._xstream(pos)

    def _table(self, fpos):
        f = self.f
        f.seek(fpos)
        num = 0
        while True:
            line = f.readline()
            if not line:
                raise PDFError("xref tronquée")
            if line.lstrip().startswith(b"trailer"):
                rest = line[line.find(b"trailer") + 7:] + f.read(8192)
                try:
                    d, _ = parse(rest, 0, True)
                except Incomplete:
                    raise PDFError("trailer illisible")
                if not isinstance(d, dict):
                    raise PDFError("trailer illisible")
                return d
            parts = line.split()
            if len(parts) == 2:
                num = int(parts[0])
                self._grow(num + int(parts[1]))
            elif len(parts) >= 3:
                if parts[2][:1] == b"n":
                    off = int(parts[0])
                    if off > 0:
                        self._set(num, 1, off)
                num += 1

    def _xstream(self, pos):
        st = self._load_at(pos, None)
        if not isinstance(st, Stream) or st.d.get("Type") != "XRef":
            raise PDFError("xref illisible")
        d = st.d
        data = self.stream_data(st, 400000)
        w = d.get("W")
        if not isinstance(w, list) or len(w) != 3:
            raise PDFError("xref illisible")
        w0, w1, w2 = w
        rl = w0 + w1 + w2
        index = d.get("Index")
        if not isinstance(index, list):
            index = [0, d.get("Size", 0)]
        p = 0
        for s in range(0, len(index) - 1, 2):
            num = index[s]
            for _ in range(index[s + 1]):
                if p + rl > len(data):
                    break
                t = _code(data[p:p + w0]) if w0 else 1
                a = _code(data[p + w0:p + w0 + w1])
                b = _code(data[p + w0 + w1:p + rl])
                p += rl
                if t == 1:
                    self._set(num, 1, a)
                elif t == 2:
                    if b >= 4096 or a >= 1048576:
                        raise PDFError("flux d'objets trop gros")
                    self._set(num, 2, (a << 12) | b)
                num += 1
        return d

    # ----- objets -----
    def res(self, v):
        for _ in range(8):
            if not isinstance(v, Ref):
                return v
            v = self.obj(v.n)
        return None

    def obj(self, num):
        if num >= len(self.xt):
            return None
        t = self.xt[num]
        if t == 1:
            return self._load_at(self.xa[num], num)
        if t == 2:
            return self._in_stream(self.xa[num] >> 12, self.xa[num] & 4095, num)
        return None

    def _load_at(self, off, num):
        f = self.f
        size = 2048
        while True:
            f.seek(self.base + off)
            buf = f.read(size)
            try:
                a, i = parse(buf, 0)
                _, i = parse(buf, i)
                k, i = parse(buf, i)
                if type(k) is not Kw or k.v != "obj":
                    raise PDFError("objet introuvable")
                v, i = parse(buf, i, True)
                if len(buf) - i < 16 and len(buf) == size:
                    raise Incomplete()
                break
            except Incomplete:
                if len(buf) < size or size >= 262144:
                    raise PDFError("objet tronqué")
                size *= 4
        if isinstance(v, dict):
            j = _skip(buf, i)
            if buf[j:j + 6] == b"stream":
                p = j + 6
                if buf[p:p + 1] == b"\r":
                    p += 1
                if buf[p:p + 1] == b"\n":
                    p += 1
                ln = self.res(v.get("Length")) if num != -1 else None
                return Stream(v, self.base + off + p, ln if type(ln) is int else None)
        return v

    def _raw(self, st):
        f = self.f
        f.seek(st.pos)
        ln = st.length
        if ln is not None:
            if ln > MAX_RAW:
                raise PDFError("flux trop gros")
            data = f.read(ln)
            if b"endstream" in f.read(16) or ln == 0:
                return data
        f.seek(st.pos)                                   # /Length faux : on cherche endstream
        data = b""
        while len(data) < MAX_RAW:
            chunk = f.read(4096)
            if not chunk:
                break
            data += chunk
            k = data.find(b"endstream")
            if k >= 0:
                data = data[:k]
                if data.endswith(b"\r\n"):
                    return data[:-2]
                return data[:-1] if data[-1:] in (b"\n", b"\r") else data
        raise PDFError("flux trop gros")

    def stream_data(self, st, limit=MAX_CONTENT):
        d = st.d
        flt = self.res(d.get("Filter"))
        names = flt if isinstance(flt, list) else ([flt] if flt else [])
        parms = self.res(d.get("DecodeParms"))
        plist = parms if isinstance(parms, list) else [parms] * len(names)
        data = self._raw(st)
        for idx, nm in enumerate(names):
            nm = self.res(nm)
            if nm == "FlateDecode" or nm == "Fl":
                data = _inflate(data, limit)
                if len(data) >= limit:
                    self.truncated = True
                p = self.res(plist[idx]) if idx < len(plist) else None
                if isinstance(p, dict):
                    data = _unpredict(data, p)
            elif nm == "ASCII85Decode" or nm == "A85":
                data = _a85(data)
            elif nm == "ASCIIHexDecode" or nm == "AHx":
                data = _ahex(data)
            else:
                raise PDFError("filtre non géré : %s" % nm)
        return data

    def _in_stream(self, snum, idx, num):
        c = self._os
        if c is None or c[0] != snum:
            self._os = None
            st = self.obj(snum)
            if not isinstance(st, Stream):
                return None
            data = self.stream_data(st, 400000)
            cnt = st.d.get("N", 0)
            first = st.d.get("First", 0)
            nums = array("I")
            offs = array("I")
            i = 0
            for _ in range(cnt):
                a, i = parse(data, i)
                b, i = parse(data, i)
                nums.append(a)
                offs.append(b)
            c = self._os = (snum, data, nums, offs, first)
        _, data, nums, offs, first = c
        if idx >= len(nums) or nums[idx] != num:
            idx = -1
            for k in range(len(nums)):
                if nums[k] == num:
                    idx = k
                    break
            if idx < 0:
                return None
        try:
            v, _ = parse(data, first + offs[idx], True)
        except Incomplete:
            return None
        return v

    # ----- pages -----
    def _advance(self):
        while self._stack:
            kids, i = self._stack[-1]
            if i >= len(kids):
                self._stack.pop()
                continue
            self._stack[-1] = (kids, i + 1)
            k = kids[i]
            if not isinstance(k, Ref):
                continue
            node = self.obj(k.n)
            if not isinstance(node, dict):
                continue
            sub = self.res(node.get("Kids"))
            if isinstance(sub, list) and node.get("Type") != "Page":
                if len(self._stack) > 40:
                    raise PDFError("arbre de pages trop profond")
                self._stack.append((sub, 0))
            else:
                self.page_nums.append(k.n)
                return True
        return False

    def _inherited(self, node, key):
        for _ in range(32):
            v = self.res(node.get(key))
            if v is not None:
                return v
            p = node.get("Parent")
            if not isinstance(p, Ref):
                return None
            node = self.obj(p.n)
            if not isinstance(node, dict):
                return None
        return None

    def page_text(self, k):
        """Texte de la page k (0 = première). Lève PDFError si la page est illisible."""
        self.truncated = False
        while len(self.page_nums) <= k:
            if not self._advance():
                self.n_pages = len(self.page_nums)
                raise PDFError("page absente")
        page = self.obj(self.page_nums[k])
        if not isinstance(page, dict):
            raise PDFError("page illisible")
        res = self._inherited(page, "Resources")
        fonts = self.res(res.get("Font")) if isinstance(res, dict) else None
        if not isinstance(fonts, dict):
            fonts = {}
        c = page.get("Contents")
        c = self.res(c) if isinstance(c, Ref) else c
        items = c if isinstance(c, list) else [c]
        it = _Interp(self, fonts)
        for ref in items:
            st = self.res(ref)
            if isinstance(st, Stream):
                data = self.stream_data(st, MAX_CONTENT)
                it.feed(data)
                data = None
        self.unreadable = it.miss
        return it.result()
