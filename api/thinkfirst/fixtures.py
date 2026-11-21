"""Demo course fixture: 'MATH 101 — Algebra Foundations'. Original text written for this project (permission-cleared,
labelled Demo data). Rendered as a real text PDF so the normal upload/extraction path is exercised."""

from __future__ import annotations

DEMO_COURSE_FILENAME = "MATH101-algebra-foundations-DEMO.pdf"

DEMO_COURSE_PAGES: list[list[str]] = [
    [
        "MATH 101 - Algebra Foundations (Demo course: original fixture, free to use)",
        "Unit 1: Expressions",
        "F1 Order of operations",
        "Objective: Evaluate expressions using the order of operations.",
        "Brackets are evaluated first, then multiplication, then addition: 2 * (4 + 1) = 2 * 5 = 10.",
        "1.1 Variables and terms",
        "Objective: Identify terms, coefficients and constants in an expression.",
        "In 3x + 5 the terms are 3x and 5; 3 is the coefficient of x and 5 is a constant.",
        "Exercise 1.1: Name the terms of 4y + 7.",
    ],
    [
        "1.2 The distributive property",
        "Objective: Expand a product a(b + c) into ab + ac.",
        "Prerequisites: 1.1, F1",
        "A number in front of brackets multiplies every term inside the brackets: a(b + c) = ab + ac.",
        "Why it works: 3(x + 2) means three groups of (x + 2), so (x + 2) + (x + 2) + (x + 2) = 3x + 6.",
        "Example: 5(a - 1) = 5a - 5.",
        "Limits: distribution works over addition and subtraction inside the brackets.",
        "It does not apply to a product inside the brackets: 2(xy) = 2xy, not (2x)(2y).",
        "Exercise 1.2: Expand 2(x + 3).",
    ],
    [
        "1.3 Combining like terms",
        "Objective: Simplify expressions by adding terms with the same variable part.",
        "Prerequisites: 1.2",
        "Like terms have the same variable part: 3x and 2x are like terms, so 3x + 2x = 5x.",
        "Exercise 1.3: Simplify 3x + 2x + 4.",
    ],
    [
        "Unit 2: Linear equations",
        "2.1 Solving one-step equations",
        "Objective: Solve equations such as x + 4 = 9 using inverse operations.",
        "Prerequisites: 1.3",
        "2.2 Solving two-step equations",
        "Objective: Solve equations such as 2x + 3 = 11.",
        "Prerequisites: 2.1, 1.2",
    ],
]


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[list[str]]) -> bytes:
    """Minimal valid PDF 1.4 with Helvetica text (no dependencies)."""
    objects: list[bytes] = []
    n_pages = len(pages)
    page_ids = [4 + 2 * i for i in range(n_pages)]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for i, lines in enumerate(pages):
        content_id = page_ids[i] + 1
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> "
                       f"/Contents {content_id} 0 R >>".encode())
        ops = ["BT", "/F1 11 Tf", "14 TL", "56 740 Td"]
        for line in lines:
            ops.append(f"({_esc(line)}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{idx} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def demo_course_pdf() -> bytes:
    return make_pdf(DEMO_COURSE_PAGES)
