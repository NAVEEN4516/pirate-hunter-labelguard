"""Create a portable PDF from the measured plain report; reportlab is authoring-only."""

import html
import re
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon

ROOT = Path(__file__).resolve().parents[1]
NAVY = colors.HexColor("#14283a")
TEAL = colors.HexColor("#007e76")
MUTED = colors.HexColor("#667b87")
PALE = colors.HexColor("#edf5f2")
styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="ReportBody", fontName="Helvetica", fontSize=9.5, leading=14.5, textColor=NAVY, spaceAfter=8
    )
)
styles.add(
    ParagraphStyle(
        name="ReportHeading",
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=21,
        textColor=NAVY,
        spaceBefore=17,
        spaceAfter=11,
        keepWithNext=True,
    )
)
styles.add(ParagraphStyle(name="ReportCell", fontName="Helvetica", fontSize=8, leading=11, textColor=NAVY))
styles.add(
    ParagraphStyle(
        name="ReportHeaderCell", fontName="Helvetica-Bold", fontSize=8, leading=11, textColor=colors.white
    )
)
styles.add(
    ParagraphStyle(
        name="CoverTitle", fontName="Helvetica-Bold", fontSize=38, leading=42, textColor=NAVY, spaceAfter=15
    )
)
styles.add(
    ParagraphStyle(
        name="CoverSub", fontName="Helvetica", fontSize=19, leading=26, textColor=TEAL, spaceAfter=24
    )
)
styles.add(
    ParagraphStyle(
        name="Caption", fontName="Helvetica", fontSize=8, leading=12, textColor=MUTED, spaceAfter=10
    )
)


def clean(text):
    text = (
        text.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2192", "->")
        .replace("\u2264", "<=")
        .replace("\u2265", ">=")
    )
    return html.escape(text)


def architecture():
    drawing = Drawing(475, 208)

    def box(x, y, w, h, title, subtitle):
        drawing.add(
            Rect(x, y, w, h, rx=5, fillColor=PALE, strokeColor=colors.HexColor("#bfd8cf"), strokeWidth=0.7)
        )
        drawing.add(
            String(
                x + w / 2,
                y + h - 17,
                title,
                textAnchor="middle",
                fontName="Helvetica-Bold",
                fontSize=8.5,
                fillColor=NAVY,
            )
        )
        drawing.add(
            String(
                x + w / 2,
                y + 10,
                subtitle,
                textAnchor="middle",
                fontName="Helvetica",
                fontSize=7,
                fillColor=MUTED,
            )
        )

    def arrow(x1, y1, x2, y2):
        drawing.add(Line(x1, y1, x2, y2, strokeColor=TEAL, strokeWidth=1))
        if x2 > x1:
            points = [x2, y2, x2 - 5, y2 + 3, x2 - 5, y2 - 3]
        elif x2 < x1:
            points = [x2, y2, x2 + 5, y2 + 3, x2 + 5, y2 - 3]
        else:
            points = [x2, y2, x2 - 3, y2 + 5, x2 + 3, y2 + 5]
        drawing.add(Polygon(points, fillColor=TEAL, strokeColor=TEAL))

    box(0, 150, 103, 45, "API + web client", "validation / submission")
    box(176, 150, 123, 45, "Durable task runner", "SQLite WAL / shared volume")
    box(372, 150, 103, 45, "Research workers x N", "LangGraph / own container")
    box(176, 75, 123, 45, "Verification worker", "LangGraph / own container")
    box(372, 75, 103, 45, "Provider stub", "HTTP / own container")
    box(0, 75, 103, 45, "Corpus + FAISS", "LangChain / index volume")
    box(
        66,
        0,
        343,
        43,
        "Prometheus + Grafana + Jaeger",
        "separate containers / metrics + OTLP / correlation IDs",
    )
    arrow(103, 172, 176, 172)
    arrow(299, 172, 372, 172)
    arrow(237, 150, 237, 120)
    arrow(424, 150, 424, 120)
    arrow(176, 97, 103, 97)
    arrow(237, 75, 237, 43)
    drawing.add(
        String(
            5,
            135,
            "Each box is a deployment boundary or explicitly named shared volume.",
            fontName="Helvetica",
            fontSize=7,
            fillColor=MUTED,
        )
    )
    return drawing


def table(lines):
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    rows = [r for r in rows if not all(re.fullmatch(r":?-+:?", c or " ") for c in r)]
    data = [
        [Paragraph(clean(cell), styles["ReportHeaderCell" if i == 0 else "ReportCell"]) for cell in row]
        for i, row in enumerate(rows)
    ]
    count = len(data[0])
    if count == 2:
        widths = [240, 235]
    elif count == 3:
        widths = [265, 105, 105]
    elif count == 8:
        widths = [47, 43, 43, 49, 56, 56, 78, 103]
    else:
        widths = [475 / count] * count
    total = sum(widths)
    widths = [w * 475 / total for w in widths]
    result = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7f8")]),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, NAVY),
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#dce5e9")),
            ]
        )
    )
    return result


def footer(canvas, doc):
    width, height = doc.pagesize
    canvas.setStrokeColor(colors.HexColor("#dce5e9"))
    canvas.line(20 * mm, 18 * mm, width - 20 * mm, 18 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 13 * mm, "PIRATE HUNTER  /  LABELGUARD  |  UE24AM342AA5")
    canvas.drawRightString(width - 20 * mm, 13 * mm, str(doc.page))
    if doc.page > 1:
        canvas.setFont("Helvetica", 7)
        canvas.drawString(20 * mm, height - 14 * mm, "FINAL PROJECT REPORT")
        canvas.drawRightString(width - 20 * mm, height - 14 * mm, "27 OCTOBER 2026")


def main():
    target = ROOT / "output/pdf/Pirate_Hunter_Final_Report.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    story = [
        Spacer(1, 25 * mm),
        Paragraph("PIRATE HUNTER", styles["Caption"]),
        Spacer(1, 7 * mm),
        Paragraph("Evidence before<br/>every label.", styles["CoverTitle"]),
        Paragraph("LabelGuard<br/>Packaged Food Label Compliance<br/>Check Service", styles["CoverSub"]),
        Paragraph("FINAL PROJECT REPORT  /  MINI PROJECT 10", styles["Caption"]),
        Spacer(1, 9 * mm),
        Paragraph(
            "ML System Design &amp; AgentOps (UE24AM342AA5)<br/>Department of CSE (AI &amp; ML), PES University<br/>27 October 2026",
            styles["ReportBody"],
        ),
        Spacer(1, 12 * mm),
        table(
            [
                "| Team member | SRN |",
                "|---|---|",
                "| Naveen Prasad M | PES1UG24AM379 |",
                "| Nishanth Nag | PES1UG24AM381 |",
                "| Sateesh | PES1UG24AM397 |",
            ]
        ),
        Spacer(1, 15 * mm),
        Paragraph(
            "Advisory findings with exact regulatory evidence.<br/>A regulatory affairs professional decides whether to print.<br/>Measured profile: local deterministic planner stub.",
            styles["Caption"],
        ),
        PageBreak(),
    ]
    text = (ROOT / "docs/REPORT.md").read_text(encoding="utf-8")
    # The cover replaces the Markdown title, date and team table.
    text = text[text.index("## 1.") :]
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("## "):
            title = line[3:]
            if title.startswith(("3.", "5.", "6.", "7.", "8.", "9.")):
                story.append(PageBreak())
            story.append(Paragraph(clean(title), styles["ReportHeading"]))
            if title.startswith("3."):
                story.extend([architecture(), Spacer(1, 10)])
            i += 1
        elif line.startswith("|"):
            group = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                group.append(lines[i].strip())
                i += 1
            story.extend([table(group), Spacer(1, 12)])
        else:
            paragraph = []
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(("## ", "|")):
                paragraph.append(lines[i].strip())
                i += 1
            value = " ".join(paragraph)
            story.append(Paragraph(clean(value), styles["ReportBody"]))
    document = SimpleDocTemplate(
        str(target),
        pagesize=(210 * mm, 297 * mm),
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=23 * mm,
        bottomMargin=25 * mm,
        title="Pirate Hunter - LabelGuard Final Project Report",
        author="Naveen Prasad M; Nishanth Nag; Sateesh",
    )
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    print(target)


if __name__ == "__main__":
    main()
