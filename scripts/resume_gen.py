#!/usr/bin/env python3
"""Career Pilot — Resume PDF Generator

Converts a markdown resume to an ATS-optimized PDF.
Uses reportlab for clean, parseable output (no tables, no columns).

Usage:
    python resume_gen.py resume/base_resume.md                    # Generate PDF
    python resume_gen.py tailored/company_role.md --output out.pdf # Custom output
    python resume_gen.py resume/base_resume.md --preview          # Print parsed structure
"""

import argparse
import re
import sys
from pathlib import Path
from datetime import datetime

try:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
        KeepTogether, ListFlowable, ListItem
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


# ATS-friendly styling
COLORS = {
    "heading": HexColor("#1a1a2e") if HAS_REPORTLAB else None,
    "subheading": HexColor("#16213e") if HAS_REPORTLAB else None,
    "body": HexColor("#2d2d2d") if HAS_REPORTLAB else None,
    "accent": HexColor("#0f3460") if HAS_REPORTLAB else None,
    "light": HexColor("#666666") if HAS_REPORTLAB else None,
    "rule": HexColor("#cccccc") if HAS_REPORTLAB else None,
}


def get_styles():
    """Define document styles."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "ResumeName",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        textColor=COLORS["heading"],
        spaceAfter=4,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    ))

    styles.add(ParagraphStyle(
        "ResumeContact",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=COLORS["light"],
        spaceAfter=8,
        alignment=TA_CENTER,
        fontName="Helvetica",
    ))

    styles.add(ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=11,
        leading=14,
        textColor=COLORS["accent"],
        spaceBefore=10,
        spaceAfter=4,
        fontName="Helvetica-Bold",
        borderWidth=0,
        borderPadding=0,
        textTransform="uppercase",
    ))

    styles.add(ParagraphStyle(
        "JobTitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        textColor=COLORS["heading"],
        spaceBefore=6,
        spaceAfter=1,
        fontName="Helvetica-Bold",
    ))

    styles.add(ParagraphStyle(
        "JobMeta",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        textColor=COLORS["light"],
        spaceAfter=3,
        fontName="Helvetica-Oblique",
    ))

    styles.add(ParagraphStyle(
        "BulletText",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=12,
        textColor=COLORS["body"],
        leftIndent=12,
        spaceAfter=2,
        fontName="Helvetica",
        bulletIndent=0,
        bulletFontSize=9,
    ))

    styles.add(ParagraphStyle(
        "SkillsText",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=12,
        textColor=COLORS["body"],
        spaceAfter=2,
        fontName="Helvetica",
    ))

    styles.add(ParagraphStyle(
        "Summary",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13,
        textColor=COLORS["body"],
        spaceAfter=6,
        fontName="Helvetica",
    ))

    return styles


def parse_markdown_resume(md_path):
    """Parse a markdown resume into structured sections.

    Expected format:
    # Name
    contact line (email | phone | location | linkedin | github)

    ## Professional Summary
    text...

    ## Experience
    ### Company — Role
    *Location | Date Range*
    - Bullet point
    - Bullet point

    ## Skills
    **Category**: skill1, skill2

    ## Education
    ### University — Degree
    *Year*
    """
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

        # Name (H1)
        if line.startswith("# ") and not name:
            name = line[2:].strip()
            i += 1
            # Next non-empty line is contact info
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines) and not lines[i].startswith("#"):
                contact = lines[i].strip()
            i += 1
            continue

        # Section header (H2)
        if line.startswith("## "):
            if current_section:
                sections[current_section] = current_entries
            current_section = line[3:].strip()
            current_entries = []
            i += 1
            continue

        # Entry header (H3) — job title, education entry
        if line.startswith("### "):
            entry = {"title": line[4:].strip(), "meta": "", "bullets": [], "text": ""}
            # Look for meta line (italic)
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if next_line.startswith("*") and next_line.endswith("*"):
                    entry["meta"] = next_line.strip("*").strip()
                    i += 1
                elif next_line.startswith("- ") or next_line.startswith("* "):
                    entry["bullets"].append(next_line[2:].strip())
                    i += 1
                elif next_line.startswith("### ") or next_line.startswith("## "):
                    break
                elif next_line:
                    entry["text"] += next_line + " "
                    i += 1
                else:
                    i += 1
                    # Check if next non-empty line is still part of this entry
                    while i < len(lines) and not lines[i].strip():
                        i += 1
                    if i < len(lines) and not lines[i].strip().startswith("#"):
                        continue
                    break
            current_entries.append(entry)
            continue

        # Bullet points outside of H3 entries
        if line.startswith("- ") or line.startswith("* "):
            current_entries.append({"bullet": line[2:].strip()})
            i += 1
            continue

        # Bold label lines (for skills)
        if line.startswith("**") and ":" in line:
            current_entries.append({"skill_line": line})
            i += 1
            continue

        # Plain text
        if line and current_section:
            current_entries.append({"text": line})

        i += 1

    if current_section:
        sections[current_section] = current_entries

    return {"name": name, "contact": contact, "sections": sections}


def build_pdf(parsed, output_path, page_size=A4):
    """Build PDF from parsed resume structure."""
    if not HAS_REPORTLAB:
        print("❌ reportlab not installed. Run: pip install reportlab --break-system-packages")
        return False

    styles = get_styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=page_size,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    story = []

    # Name
    if parsed["name"]:
        story.append(Paragraph(parsed["name"], styles["ResumeName"]))

    # Contact
    if parsed["contact"]:
        # Clean markdown links
        contact = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', parsed["contact"])
        story.append(Paragraph(contact, styles["ResumeContact"]))

    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=COLORS["rule"], spaceAfter=6, spaceBefore=2
    ))

    # Sections
    for section_name, entries in parsed["sections"].items():
        # Section heading
        story.append(Paragraph(section_name.upper(), styles["SectionHeading"]))
        story.append(HRFlowable(
            width="100%", thickness=0.3,
            color=COLORS["rule"], spaceAfter=4, spaceBefore=0
        ))

        for entry in entries:
            if isinstance(entry, dict):
                # Structured entry (job, education)
                if "title" in entry and (entry.get("bullets") or entry.get("text")):
                    block = []
                    block.append(Paragraph(
                        entry["title"].replace("—", "–"),
                        styles["JobTitle"]
                    ))
                    if entry.get("meta"):
                        block.append(Paragraph(entry["meta"], styles["JobMeta"]))
                    for bullet in entry.get("bullets", []):
                        # Clean markdown bold/italic
                        bullet = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', bullet)
                        bullet = re.sub(r'\*(.+?)\*', r'<i>\1</i>', bullet)
                        block.append(Paragraph(
                            f"• {bullet}",
                            styles["BulletText"]
                        ))
                    if entry.get("text"):
                        block.append(Paragraph(entry["text"].strip(), styles["Summary"]))
                    story.append(KeepTogether(block))

                # Skill line
                elif "skill_line" in entry:
                    line = entry["skill_line"]
                    line = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line)
                    story.append(Paragraph(line, styles["SkillsText"]))

                # Standalone bullet
                elif "bullet" in entry:
                    bullet = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', entry["bullet"])
                    story.append(Paragraph(f"• {bullet}", styles["BulletText"]))

                # Plain text
                elif "text" in entry:
                    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', entry["text"])
                    story.append(Paragraph(text, styles["Summary"]))

        story.append(Spacer(1, 4))

    # Build
    try:
        doc.build(story)
        print(f"✅ PDF generated: {output_path}")
        return True
    except Exception as e:
        print(f"❌ PDF generation failed: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Generate ATS-friendly resume PDF")
    parser.add_argument("input", help="Path to markdown resume")
    parser.add_argument("--output", "-o", help="Output PDF path")
    parser.add_argument("--preview", action="store_true", help="Print parsed structure")
    parser.add_argument("--letter", action="store_true", help="Use US Letter size (default: A4)")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        sys.exit(1)

    # Parse
    parsed = parse_markdown_resume(input_path)

    if args.preview:
        import json
        # Convert to JSON-serializable format
        print(json.dumps(parsed, indent=2, default=str))
        return

    # Output path
    if args.output:
        output_path = Path(args.output)
    else:
        stem = input_path.stem
        output_path = input_path.parent / f"{stem}.pdf"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not HAS_REPORTLAB:
        print("❌ reportlab not installed.")
        print("   Run: pip install reportlab --break-system-packages")
        sys.exit(1)

    page_size = letter if args.letter else A4
    success = build_pdf(parsed, output_path, page_size)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
