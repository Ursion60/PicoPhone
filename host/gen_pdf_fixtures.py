"""Régénère host/fixtures/*.pdf (pip install reportlab fpdf2 pikepdf). Lancer depuis host/fixtures/."""
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from fpdf import FPDF
import pikepdf

LOREM = ("Le lecteur PDF de la carte Pico 2 extrait le texte des pages et l'affiche sur l'écran tactile. "
         "Voici des accents : é è ê à ç ù ï ô œ, des guillemets « français », une apostrophe l’été, un tiret – long, "
         "des ligatures ﬁnales et le symbole € pour tester la translittération. ")

# 1. reportlab : xref classique, Type1 de base WinAnsi, Flate
c = canvas.Canvas("classic.pdf", pagesize=A4)
for p in range(1, 4):
    c.setFont("Helvetica-Bold", 16); c.drawString(60, 780, f"Chapitre {p} - Test classique")
    c.setFont("Helvetica", 11)
    y = 750
    for i in range(14):
        c.drawString(60, y, f"Ligne {i+1} de la page {p}. " + LOREM[:70]); y -= 16
    c.showPage()
c.save()

# 2. fpdf2 : TrueType Identity-H + ToUnicode
f = FPDF()
f.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
for p in range(1, 3):
    f.add_page(); f.set_font("DejaVu", size=12)
    f.multi_cell(0, 7, f"Page {p} — police TrueType (Type0)\n\n" + (LOREM * 6))
f.output("truetype.pdf")

# 3. pikepdf : mêmes pages mais xref stream + object streams
with pikepdf.open("classic.pdf") as pdf:
    pdf.save("objstm.pdf", object_stream_mode=pikepdf.ObjectStreamMode.generate,
             compress_streams=True)

# 4. PDF sans texte (image seule) : une page vide
c = canvas.Canvas("vide.pdf", pagesize=A4); c.rect(50, 50, 200, 200); c.showPage(); c.save()

# 5. Chiffré
with pikepdf.open("classic.pdf") as pdf:
    pdf.save("chiffre.pdf", encryption=pikepdf.Encryption(owner="a", user="b"))

# 6. gros document (60 pages) pour tester la pagination
c = canvas.Canvas("long.pdf", pagesize=A4)
for p in range(1, 61):
    c.setFont("Helvetica", 11); y = 780
    for i in range(40):
        c.drawString(40, y, f"p{p} l{i+1} " + LOREM[:90]); y -= 14
    c.showPage()
c.save()

# 7. Type0 sans /ToUnicode (texte non décodable)
with pikepdf.open("truetype.pdf") as pdf:
    for page in pdf.pages:
        for name, f in page.Resources.Font.items():
            if "/ToUnicode" in f:
                del f["/ToUnicode"]
    pdf.save("sansunicode.pdf")
