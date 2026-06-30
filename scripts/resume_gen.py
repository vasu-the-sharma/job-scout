#!/usr/bin/env python3
"""Career Pilot — Resume PDF Generator

Converts a markdown resume to an ATS-optimized, 1-page PDF.
Auto-fits: tries progressively tighter spacing until content lands on page 1.

Usage:
    python resume_gen.py resume/base_resume.md
    python resume_gen.py tailored/company_role.md --output out.pdf
    python resume_gen.py resume/base_resume.md --preview
"""

import argparse
import re
import sys
import shutil
import tempfile
from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable, KeepTogether,
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


COLORS = {
    "heading":    HexColor("#1a1a2e") if HAS_REPORTLAB else None,
    "subheading": HexColor("#16213e") if HAS_REPORTLAB else None,
    "body":       HexColor("#2d2d2d") if HAS_REPORTLAB else None,
    "accent":     HexColor("#0f3460") if HAS_REPORTLAB else None,
    "light":      HexColor("#555555") if HAS_REPORTLAB else None,
    "rule":       HexColor("#cccccc") if HAS_REPORTLAB else None,
}


# ── Styles (all size/spacing values driven by `scale`) ────────────────────────

def get_styles(scale: float = 1.0):
    """Return ParagraphStyles scaled for the current compression pass."""
    S = getSampleStyleSheet()
    sp = scale  # spacing scale
    fs = scale  # font scale (same for now — looks natural)

    def add(name, **kw):
        S.add(ParagraphStyle(name, parent=S["Normal"], **kw))

    add("ResumeName",
        fontSize=round(16 * fs, 1), leading=round(20 * sp, 1),
        textColor=COLORS["heading"], spaceAfter=round(3 * sp, 1),
        alignment=TA_CENTER, fontName="Helvetica-Bold")

    add("ResumeContact",
        fontSize=round(8.5 * fs, 1), leading=round(11 * sp, 1),
        textColor=COLORS["light"], spaceAfter=round(5 * sp, 1),
        alignment=TA_CENTER, fontName="Helvetica")

    add("SectionHeading",
        fontSize=round(9.5 * fs, 1), leading=round(12 * sp, 1),
        textColor=COLORS["accent"], spaceBefore=round(6 * sp, 1),
        spaceAfter=round(2 * sp, 1), fontName="Helvetica-Bold",
        borderWidth=0, borderPadding=0)

    add("JobTitle",
        fontSize=round(9.5 * fs, 1), leading=round(12 * sp, 1),
        textColor=COLORS["heading"], spaceBefore=round(4 * sp, 1),
        spaceAfter=round(1 * sp, 1), fontName="Helvetica-Bold")

    add("JobMeta",
        fontSize=round(8.5 * fs, 1), leading=round(10 * sp, 1),
        textColor=COLORS["light"], spaceAfter=round(2 * sp, 1),
        fontName="Helvetica-Oblique")

    add("BulletText",
        fontSize=round(9 * fs, 1), leading=round(11.5 * sp, 1),
        textColor=COLORS["body"], leftIndent=10,
        spaceAfter=round(1.5 * sp, 1), fontName="Helvetica")

    add("SkillsText",
        fontSize=round(9 * fs, 1), leading=round(11.5 * sp, 1),
        textColor=COLORS["body"], spaceAfter=round(2 * sp, 1),
        fontName="Helvetica")

    add("Summary",
        fontSize=round(9 * fs, 1), leading=round(12 * sp, 1),
        textColor=COLORS["body"], spaceAfter=round(4 * sp, 1),
        fontName="Helvetica")

    return S


# ── Markdown parser ────────────────────────────────────────────────────────────

def parse_markdown_resume(md_path):
    """Parse markdown resume into structured sections."""
    with open(md_path) as f:
        content = f.read()

    sections = {}
    current_section = None
    current_entries = []

    lines = content.strip().split("\n")
    name = ""
    contact = ""
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("# ") and not name:
            name = line[2:].strip()
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines) and not lines[i].startswith("#"):
                contact = lines[i].strip()
            i += 1
            continue

        if line.startswith("## "):
            if current_section:
                sections[current_section] = current_entries
            current_section = line[3:].strip()
            current_entries = []
            i += 1
            continue

        if line.startswith("### "):
            entry = {"title": line[4:].strip(), "meta": "", "bullets": [], "text": ""}
            i += 1
            while i < len(lines):
                nl = lines[i].strip()
                if nl.startswith("*") and nl.endswith("*"):
                    entry["meta"] = nl.strip("*").strip()
                    i += 1
                elif nl.startswith("- ") or nl.startswith("* "):
                    entry["bullets"].append(nl[2:].strip())
                    i += 1
                elif nl.startswith("### ") or nl.startswith("## "):
                    break
                elif nl:
                    entry["text"] += nl + " "
                    i += 1
                else:
                    i += 1
                    while i < len(lines) and not lines[i].strip():
                        i += 1
                    if i < len(lines) and not lines[i].strip().startswith("#"):
                        continue
                    break
            current_entries.append(entry)
            continue

        if line.startswith("- ") or line.startswith("* "):
            current_entries.append({"bullet": line[2:].strip()})
            i += 1
            continue

        if line.startswith("**") and ":" in line:
            current_entries.append({"skill_line": line})
            i += 1
            continue

        if line and current_section:
            current_entries.append({"text": line})

        i += 1

    if current_section:
        sections[current_section] = current_entries

    return {"name": name, "contact": contact, "sections": sections}


# ── PDF builder (one pass at a given scale) ───────────────────────────────────

def _md(text: str) -> str:
    """Convert markdown bold/italic to reportlab XML tags."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    return text


def build_pdf(parsed, output_path, scale: float = 1.0, page_size=None):
    """Build PDF at the given scale (1.0 = default tight, <1.0 = compressed)."""
    if page_size is None:
        page_size = A4

    if not HAS_REPORTLAB:
        print("❌ reportlab not installed. Run: pip install reportlab --break-system-packages")
        return False

    styles = get_styles(scale)
    sp = scale  # spacing scale alias

    # Margins scale mildly — less aggressive than font/leading
    base_side = 0.55
    base_tb   = 0.45
    side_margin = max(0.35, base_side * (0.7 + 0.3 * scale)) * inch
    tb_margin   = max(0.30, base_tb   * (0.7 + 0.3 * scale)) * inch

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=page_size,
        leftMargin=side_margin,
        rightMargin=side_margin,
        topMargin=tb_margin,
        bottomMargin=tb_margin,
    )

    story = []

    # Name
    if parsed["name"]:
        story.append(Paragraph(parsed["name"], styles["ResumeName"]))

    # Contact line — strip markdown hyperlinks to plain text
    if parsed["contact"]:
        contact = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', parsed["contact"])
        story.append(Paragraph(contact, styles["ResumeContact"]))

    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=COLORS["rule"], spaceAfter=round(5 * sp, 1), spaceBefore=1,
    ))

    for section_name, entries in parsed["sections"].items():
        story.append(Paragraph(section_name.upper(), styles["SectionHeading"]))
        story.append(HRFlowable(
            width="100%", thickness=0.3,
            color=COLORS["rule"], spaceAfter=round(3 * sp, 1), spaceBefore=0,
        ))

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            if "title" in entry and (entry.get("bullets") or entry.get("text") or entry.get("meta")):
                block = []
                block.append(Paragraph(_md(entry["title"].replace("—", "–")),
                                        styles["JobTitle"]))
                if entry.get("meta"):
                    block.append(Paragraph(entry["meta"], styles["JobMeta"]))
                for bullet in entry.get("bullets", []):
                    block.append(Paragraph(f"• {_md(bullet)}", styles["BulletText"]))
                if entry.get("text"):
                    block.append(Paragraph(_md(entry["text"].strip()), styles["Summary"]))
                story.append(KeepTogether(block))

            elif "skill_line" in entry:
                story.append(Paragraph(_md(entry["skill_line"]), styles["SkillsText"]))

            elif "bullet" in entry:
                story.append(Paragraph(f"• {_md(entry['bullet'])}", styles["BulletText"]))

            elif "text" in entry:
                story.append(Paragraph(_md(entry["text"]), styles["Summary"]))

        story.append(Spacer(1, round(3 * sp, 1)))

    try:
        doc.build(story)
        return True
    except Exception as e:
        print(f"❌ PDF build failed: {e}", file=sys.stderr)
        return False


# ── Page counter ──────────────────────────────────────────────────────────────

def count_pages(pdf_path: Path) -> int:
    """Return number of pages in a PDF. Uses pypdf if available."""
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(pdf_path)).pages)
    except ImportError:
        pass
    try:
        from PyPDF2 import PdfReader
        return len(PdfReader(str(pdf_path)).pages)
    except ImportError:
        pass
    # Byte-scan fallback (counts /Type /Page objects)
    data = pdf_path.read_bytes()
    count = data.count(b"/Type /Page\n") + data.count(b"/Type/Page\n")
    return max(1, count)


# ── Auto-fit entry point ───────────────────────────────────────────────────────

def auto_build(parsed, output_path, page_size=None):
    """Build PDF, auto-compressing until it fits on exactly 1 page."""
    if page_size is None:
        page_size = A4

    # Try scales from 1.0 down to 0.72 in steps of ~0.07
    scales = [1.0, 0.93, 0.86, 0.79, 0.72]

    for scale in scales:
        tmp = Path(tempfile.mktemp(suffix=".pdf"))
        ok = build_pdf(parsed, tmp, scale=scale, page_size=page_size)
        if not ok:
            tmp.unlink(missing_ok=True)
            return False

        pages = count_pages(tmp)

        if pages <= 1:
            shutil.move(str(tmp), str(output_path))
            label = f"scale={scale:.0%}" if scale < 1.0 else "no compression needed"
            print(f"✅ PDF generated ({label}, {pages} page): {output_path}")
            return True

        tmp.unlink(missing_ok=True)

    # All scales tried — keep tightest result
    ok = build_pdf(parsed, output_path, scale=scales[-1], page_size=page_size)
    if ok:
        pages = count_pages(output_path)
        print(f"⚠️  PDF generated but has {pages} page(s) at maximum compression: {output_path}")
    return ok


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate ATS-friendly 1-page resume PDF")
    parser.add_argument("input", help="Path to markdown resume")
    parser.add_argument("--output", "-o", help="Output PDF path (default: same dir as input)")
    parser.add_argument("--preview", action="store_true", help="Print parsed structure as JSON")
    parser.add_argument("--letter", action="store_true", help="Use US Letter size (default: A4)")
    parser.add_argument("--scale", type=float, default=None,
                        help="Force a specific scale (0.72–1.0). Default: auto-fit.")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        sys.exit(1)

    parsed = parse_markdown_resume(input_path)

    if args.preview:
        import json
        print(json.dumps(parsed, indent=2, default=str))
        return

    output_path = Path(args.output) if args.output else input_path.with_suffix(".pdf")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not HAS_REPORTLAB:
        print("❌ reportlab not installed. Run: pip install reportlab --break-system-packages")
        sys.exit(1)

    page_size = letter if args.letter else A4

    if args.scale is not None:
        ok = build_pdf(parsed, output_path, scale=args.scale, page_size=page_size)
        if ok:
            pages = count_pages(output_path)
            print(f"✅ PDF generated (scale={args.scale:.0%}, {pages} page(s)): {output_path}")
    else:
        ok = auto_build(parsed, output_path, page_size=page_size)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
