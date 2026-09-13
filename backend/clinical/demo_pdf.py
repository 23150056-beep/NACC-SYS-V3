"""A small, valid PDF, assembled by hand.

No PDF library is installed and pulling one in for a demo fixture would be a
poor trade — reportlab is several megabytes to write eight lines of text that
nobody will ever read closely.

The part worth being careful about is the cross-reference table. A PDF ends
with `startxref` pointing at a table of byte offsets, one per object, and a
reader that follows a wrong offset refuses the file. So the offsets here are
MEASURED off the bytes as they are assembled, never counted by hand: the
failure mode of a hand-counted offset is a file that looks right in a hex dump
and will not open, which is the worst kind.

Deliberately plain: one page, one built-in font, no compression, no metadata.
Enough to be a real document, not enough to pretend to be a real referral.
"""

# Courier is one of the 14 fonts every reader has built in, so nothing has to
# be embedded. Monospaced keeps the hand-laid-out lines from drifting.
FONT = "Courier"
FONT_SIZE = 10
LEADING = 14
LEFT = 56
TOP = 780
PAGE = (612, 792)          # US Letter, in points


def _escape(line):
    """( ) and \\ are structural inside a PDF string literal."""
    return (line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)"))


def build_pdf(lines):
    """A one-page PDF containing `lines`, as bytes."""
    text = ["BT", f"/F1 {FONT_SIZE} Tf", f"{LEADING} TL", f"{LEFT} {TOP} Td"]
    for i, line in enumerate(lines):
        # The first line is placed by Td; the rest step down with T*.
        if i:
            text.append("T*")
        text.append(f"({_escape(line)}) Tj")
    text.append("ET")
    stream = "\n".join(text).encode("latin-1", "replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE[0]} {PAGE[1]}] "
         f"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>").encode(),
        f"<< /Type /Font /Subtype /Type1 /BaseFont /{FONT} >>".encode(),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    # Measured as we go. Counting these by hand is the mistake this avoids.
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n").encode()
    return bytes(out)
