"""Build the six consistent companion editions from the maintained Markdown.

The original covers are preserved as PDF assets. The body is rebuilt with the
established Cambria/Arial, cream, teal and gold visual system. Source liturgies
are never bundled. The combined Markdown is generated, not an editing source.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path

from markdown_it import MarkdownIt
from PIL import Image as PILImage
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, NameObject, TextStringObject
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, HRFlowable, Image,
    LongTable, PageBreak, PageTemplate, Paragraph, Spacer,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "downloads"
TMP = ROOT / "tmp" / "pdfs"
W, H = A4
MX, MT, MB = 18 * mm, 19 * mm, 18 * mm
CW, CH = W - 2 * MX, H - MT - MB
TEAL = colors.HexColor("#174f4b")
DEEP = colors.HexColor("#0d3534")
SEA = colors.HexColor("#397b75")
PAPER = colors.HexColor("#fcfaf4")
MIST = colors.HexColor("#edf6f2")
RULE = colors.HexColor("#b5d5cd")
GOLD = colors.HexColor("#d7b374")
OCHRE = colors.HexColor("#b97839")
INK = colors.HexColor("#263b37")
MUTED = colors.HexColor("#58716b")
REPO_URL = "https://github.com/CircuitDanny/samadhi-water-repentance-companion/blob/main/"
MD = MarkdownIt("commonmark").enable("table")


@dataclass(frozen=True)
class Edition:
    stem: str
    title: str
    subtitle: str
    sections: tuple[tuple[str, str, str], ...]
    master: bool = False


EDITIONS = (
    Edition("01-scroll-one-practice-companion", "Scroll One Practice Companion", "Origins, refuge, afflictions, vows and wisdom", (("PRACTICE_COMPANION.md", "Scroll One", "What each part is doing and why"), ("REFERENCES.md", "References", "Sources and editorial limits"))),
    Edition("02-scroll-two-practice-companion", "Scroll Two Practice Companion", "Karma, ethical conduct, speech and the six senses", (("SCROLL_TWO_COMPANION.md", "Scroll Two", "What each part is doing and why"), ("REFERENCES.md", "References", "Sources and editorial limits"))),
    Edition("03-scroll-three-practice-companion", "Scroll Three Practice Companion", "Results, vows, dedication and memorial practice", (("SCROLL_THREE_COMPANION.md", "Scroll Three", "What each part is doing and why"), ("REFERENCES.md", "References", "Sources and editorial limits"))),
    Edition("04-master-print-edition", "The Samādhi Water Repentance Companion", "An illustrated English companion to all three scrolls", (
        ("MASTER_OVERVIEW.md", "Orientation", "Read this first"),
        ("STARTING_PRACTICE.md", "Beginning a Buddhist practice", "Core teachings and a practical first step"),
        ("PRACTICE_COMPANION.md", "Part I - Scroll One", "Origins, refuge, afflictions, vows and wisdom"),
        ("SCROLL_TWO_COMPANION.md", "Part II - Scroll Two", "Karma, conduct and the six senses"),
        ("SCROLL_THREE_COMPANION.md", "Part III - Scroll Three", "Results, dedication and memorial practice"),
        ("CONCEPTS.md", "Part IV - Core concepts", "The Buddhist world behind the words"),
        ("FIGURES.md", "Part V - Buddhas and bodhisattvas", "Names, stories, recognition and practice"),
        ("PRONUNCIATION.md", "Part VI - Pronunciation", "Names, terms and chant formulas"),
        ("GLOSSARY.md", "Part VII - Glossary", "Plain-English reference for all three scrolls"),
        ("REFERENCES.md", "Part VIII - References", "Sources, artwork and editorial limits"),
    ), True),
    Edition("05-buddhas-and-bodhisattvas-guide", "Buddhas and Bodhisattvas", "Stories, symbols and their place in the Water Repentance", (("FIGURES.md", "Buddhas and bodhisattvas", "A visual companion to the three scrolls"), ("REFERENCES.md", "References", "Sources and artwork records"))),
    Edition("06-glossary-reference", "Water Repentance Glossary", "Plain-English meanings, difficult phrases and useful distinctions", (("GLOSSARY.md", "Glossary", "Terms from all three scrolls"), ("PRONUNCIATION.md", "Pronunciation", "A companion to the glossary"), ("REFERENCES.md", "References", "Sources and editorial limits"))),
)


def register_fonts(font_dir: Path) -> None:
    specifications = {
        "Cambria": ("cambria.ttc", 0), "Cambria-Bold": ("cambriab.ttf", None),
        "Cambria-Italic": ("cambriai.ttf", None), "Cambria-BoldItalic": ("cambriaz.ttf", None),
        "Arial": ("arial.ttf", None), "Arial-Bold": ("arialbd.ttf", None),
        "Arial-Italic": ("ariali.ttf", None), "Arial-BoldItalic": ("arialbi.ttf", None),
        "CJK": ("simsun.ttc", 0),
    }
    for name, (filename, index) in specifications.items():
        path = font_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Required font missing: {path}. Supply --font-dir with licensed fonts.")
        kw = {"subfontIndex": index} if index is not None else {}
        pdfmetrics.registerFont(TTFont(name, str(path), **kw))
    for family in ("Cambria", "Arial"):
        pdfmetrics.registerFontFamily(family, normal=family, bold=family + "-Bold", italic=family + "-Italic", boldItalic=family + "-BoldItalic")


BODY = ParagraphStyle("Body", fontName="Cambria", fontSize=9.6, leading=13.2, textColor=INK, spaceAfter=6, splitLongWords=True, allowWidows=0, allowOrphans=0)
LEAD = ParagraphStyle("Lead", parent=BODY, fontSize=11.2, leading=15.4, textColor=TEAL, spaceAfter=10)
H1 = ParagraphStyle("H1", parent=BODY, fontName="Cambria-Bold", fontSize=20, leading=24, textColor=TEAL, spaceBefore=14, spaceAfter=10, keepWithNext=True)
H2 = ParagraphStyle("H2", parent=H1, fontSize=15.5, leading=19, spaceBefore=13, spaceAfter=8)
H3 = ParagraphStyle("H3", parent=H1, fontName="Arial-Bold", fontSize=10.4, leading=13.5, textColor=OCHRE, spaceBefore=9, spaceAfter=5)
H4 = ParagraphStyle("H4", parent=H3, fontSize=9.4, leading=12.5)
SMALL = ParagraphStyle("Small", parent=BODY, fontName="Arial", fontSize=7.7, leading=10.4, spaceAfter=5)
CAPTION = ParagraphStyle("Caption", parent=SMALL, fontName="Arial-Italic", fontSize=7.2, leading=9.7, textColor=MUTED, alignment=TA_CENTER)
SOURCE_LOC = ParagraphStyle("SourceLocation", parent=CAPTION, alignment=2, keepWithNext=True, spaceAfter=5)
CELL = ParagraphStyle("Cell", parent=SMALL, fontSize=7.9, leading=10.6, spaceAfter=0)
CELL_HEAD = ParagraphStyle("CellHead", parent=CELL, fontName="Arial-Bold", textColor=colors.white)
QUOTE = ParagraphStyle("Quote", parent=BODY, fontName="Arial", fontSize=8.6, leading=12, leftIndent=11, rightIndent=9, borderColor=RULE, borderWidth=.5, borderPadding=9, backColor=MIST, spaceBefore=12, spaceAfter=14)
BULLET = ParagraphStyle("Bullet", parent=BODY, leftIndent=12, firstLineIndent=-8, spaceAfter=4)
TOC0 = ParagraphStyle("TOC0", parent=BODY, fontName="Cambria-Bold", fontSize=10.5, leading=14, textColor=TEAL, spaceBefore=8, spaceAfter=4)
TOC1 = ParagraphStyle("TOC1", parent=BODY, fontSize=8.6, leading=11.6, leftIndent=12, firstLineIndent=0, spaceAfter=3)


def plain(value: str) -> str:
    return value.replace("\u2014", " - ").replace("\u2013", "-").replace("\u2011", "-")


def escaped(value: str) -> str:
    text = html.escape(plain(value))
    return re.sub(r"([\u3400-\u9fff]+)", r'<font name="CJK">\1</font>', text)


def inline(tokens) -> str:
    parts = []
    for token in tokens or []:
        kind = token.type
        if kind == "text": parts.append(escaped(token.content))
        elif kind in ("softbreak", "hardbreak"): parts.append("<br/>" if kind == "hardbreak" else " ")
        elif kind == "strong_open": parts.append("<b>")
        elif kind == "strong_close": parts.append("</b>")
        elif kind == "em_open": parts.append("<i>")
        elif kind == "em_close": parts.append("</i>")
        elif kind == "code_inline": parts.append(f'<font name="Arial">{escaped(token.content)}</font>')
        elif kind == "link_open":
            href = token.attrGet("href") or ""
            if not re.match(r"^(?:https?://|mailto:)", href): href = REPO_URL + href
            parts.append(f'<link href="{html.escape(href, quote=True)}" color="#397b75"><u>')
        elif kind == "link_close": parts.append("</u></link>")
        elif kind == "image": parts.append(escaped(token.content))
        elif kind == "html_inline": parts.append(escaped(token.content))
        else: raise ValueError(f"Unsupported inline Markdown: {kind}")
    return "".join(parts)


class SectionDivider(Flowable):
    def __init__(self, label, subtitle):
        super().__init__()
        self.label, self.subtitle = label, subtitle
        self.width, self.height = CW, CH - 8

    def draw(self):
        c = self.canv
        c.setFillColor(MIST); c.roundRect(0, 105 * mm, CW, 125 * mm, 8 * mm, fill=1, stroke=0)
        c.setFillColor(OCHRE); c.roundRect(12 * mm, 207 * mm, 43 * mm, 8 * mm, 4 * mm, fill=1, stroke=0)
        c.setFont("Arial-Bold", 7.3); c.setFillColor(colors.white); c.drawString(17 * mm, 210 * mm, "THE COMPLETE COMPANION")
        title = Paragraph(escaped(self.label), ParagraphStyle("Divider", parent=H1, fontSize=29, leading=35))
        _, th = title.wrap(CW - 26 * mm, 90 * mm); title.drawOn(c, 13 * mm, 180 * mm - th)
        subtitle = Paragraph(escaped(self.subtitle), LEAD)
        _, sh = subtitle.wrap(CW - 26 * mm, 45 * mm); subtitle.drawOn(c, 13 * mm, 165 * mm - th - sh)
        c.setStrokeColor(GOLD); c.setLineWidth(1.2); c.line(13 * mm, 122 * mm, CW - 13 * mm, 122 * mm)


class GuideDoc(BaseDocTemplate):
    def __init__(self, path, edition):
        super().__init__(str(path), pagesize=A4, leftMargin=MX, rightMargin=MX, topMargin=MT, bottomMargin=MB, title=edition.title, author="Daniel Franjkovic", allowSplitting=1)
        self.edition = edition
        self.section = edition.title
        self.addPageTemplates(PageTemplate("body", [Frame(MX, MB, CW, CH, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=self.background, onPageEnd=self.furniture))

    def beforeDocument(self):
        self.section = self.edition.title

    def background(self, canvas, doc):
        canvas.saveState(); canvas.setFillColor(PAPER); canvas.rect(0, 0, W, H, fill=1, stroke=0); canvas.restoreState()

    def furniture(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(RULE); canvas.setLineWidth(.4); canvas.line(MX, H - 12 * mm, W - MX, H - 12 * mm)
        canvas.setFont("Arial", 6.6); canvas.setFillColor(MUTED); canvas.drawString(MX, H - 9.8 * mm, plain(self.section))
        canvas.line(MX, 13 * mm, W - MX, 13 * mm)
        canvas.setFont("Arial", 6.5); canvas.drawString(MX, 9 * mm, "Expanded companion edition | September 2026")
        canvas.setFillColor(OCHRE); canvas.circle(W - MX, 10 * mm, 3.9 * mm, fill=1, stroke=0)
        canvas.setFont("Arial-Bold", 6.5); canvas.setFillColor(colors.white); canvas.drawCentredString(W - MX, 9.15 * mm, str(doc.page + 1))
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if hasattr(flowable, "_section"):
            self.section = flowable._section
        if hasattr(flowable, "_anchor"):
            key, title, level = flowable._anchor
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(plain(title), key, level=level, closed=level > 0)
            self.notify("TOCEntry", (level, escaped(title), self.page + 1, key))


class Renderer:
    def __init__(self):
        self.counter = 0

    def heading(self, text, style, toc_level=None, section=None):
        self.counter += 1
        paragraph = Paragraph(text, style)
        title = re.sub(r"<[^>]+>", "", html.unescape(text))
        if toc_level is not None: paragraph._anchor = (f"heading-{self.counter}", title, toc_level)
        if section: paragraph._section = section
        return paragraph

    def image(self, token):
        src = token.attrGet("src")
        path = ROOT / src
        if path.suffix.lower() == ".svg": path = path.with_suffix(".png")
        if not path.exists(): raise FileNotFoundError(f"Missing image: {src}")
        with PILImage.open(path) as im: iw, ih = im.size
        is_diagram = "diagrams" in path.parts
        maxw, maxh = (CW, 100 * mm) if is_diagram else (110 * mm, 80 * mm)
        scale = min(maxw / iw, maxh / ih)
        picture = Image(str(path), width=iw * scale, height=ih * scale)
        picture.hAlign = "CENTER"
        picture.spaceBefore = 3 * mm
        picture.spaceAfter = 4 * mm
        picture.keepWithNext = True
        return [picture]

    def table(self, tokens):
        rows, row, cell, is_header = [], [], "", False
        for t in tokens:
            if t.type == "tr_open": row = []
            elif t.type in ("th_open", "td_open"): cell = ""; is_header = t.type == "th_open"
            elif t.type == "inline": cell += inline(t.children)
            elif t.type in ("th_close", "td_close"): row.append(Paragraph(cell or " ", CELL_HEAD if is_header else CELL))
            elif t.type == "tr_close": rows.append(row)
        n = len(rows[0])
        if any(len(row) != n for row in rows): raise ValueError("Ragged Markdown table")
        fractions = {2: [.29, .71], 3: [.25, .33, .42], 4: [.17, .24, .27, .32]}.get(n, [1 / n] * n)
        table = LongTable(rows, colWidths=[CW * f for f in fractions], repeatRows=1, hAlign="LEFT", splitByRow=1, spaceBefore=5, spaceAfter=10)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TEAL), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, MIST]),
            ("BOX", (0, 0), (-1, -1), .45, RULE), ("INNERGRID", (0, 0), (-1, -1), .3, RULE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return table

    def markdown(self, text, filename):
        tokens = MD.parse(text)
        result, i, quote_depth, lists = [], 0, 0, []
        first_heading = True
        figure_group_heading = False
        figure_profile_titles = {"Śākyamuni Buddha", "Vairocana Buddha", "Amitābha Buddha", "Medicine Master Buddha", "Dīpaṃkara Buddha", "Maitreya", "Prabhūtaratna Buddha", "Avalokiteśvara Bodhisattva", "Mañjuśrī Bodhisattva", "Samantabhadra Bodhisattva", "Mahāsthāmaprāpta Bodhisattva", "Kṣitigarbha Bodhisattva", "Mahāvyūha Bodhisattva"}
        while i < len(tokens):
            t = tokens[i]
            if t.type == "heading_open":
                child = tokens[i + 1]; level = int(t.tag[1]); title = child.content
                if first_heading:
                    first_heading = False
                else:
                    if filename == "FIGURES.md":
                        if title in {"Principal bodhisattvas", "The Seven Ancient Buddhas", "Buddhas in the repeated litany"}:
                            result.append(PageBreak())
                        if title in figure_profile_titles:
                            if not figure_group_heading: result.append(PageBreak())
                            figure_group_heading = False
                        elif title in {"Principal Buddhas", "Principal bodhisattvas"}:
                            figure_group_heading = True
                    style = {1: H1, 2: H2, 3: H3}.get(level, H4)
                    toc_level = 1 if (level <= 2 and not (filename == "GLOSSARY.md" and level > 2)) else None
                    result.append(self.heading(inline(child.children), style, toc_level))
                i += 3; continue
            if t.type == "paragraph_open":
                child = tokens[i + 1]
                if child.type != "inline": raise ValueError("Unexpected Markdown paragraph")
                imgs = [x for x in child.children or [] if x.type == "image"]
                if imgs:
                    for img in imgs: result.extend(self.image(img))
                else:
                    value = inline(child.children)
                    style = QUOTE if quote_depth else BULLET if lists else BODY
                    if child.content.startswith("*Artwork:"): style = CAPTION
                    if child.content.lstrip("*").startswith(("Source pages", "Source page", "PDF page")): style = SOURCE_LOC
                    if lists:
                        current = lists[-1]
                        prefix = f"{current['number']}. " if current["ordered"] else "• "
                        value = prefix + value
                    if value.strip(): result.append(Paragraph(value, style))
                i += 3; continue
            if t.type == "table_open":
                end = i + 1
                while tokens[end].type != "table_close": end += 1
                result.append(self.table(tokens[i:end + 1])); i = end + 1; continue
            if t.type == "blockquote_open": quote_depth += 1
            elif t.type == "blockquote_close": quote_depth -= 1
            elif t.type in ("bullet_list_open", "ordered_list_open"):
                lists.append({"ordered": t.type == "ordered_list_open", "number": int(t.attrGet("start") or 1) - 1})
            elif t.type in ("bullet_list_close", "ordered_list_close"): lists.pop()
            elif t.type == "list_item_open": lists[-1]["number"] += 1
            elif t.type == "list_item_close": pass
            elif t.type == "hr": result.append(HRFlowable(width="100%", color=RULE, thickness=.6, spaceBefore=8, spaceAfter=8))
            elif t.type in ("fence", "code_block"): result.append(Paragraph(escaped(t.content).replace("\n", "<br/>"), SMALL))
            elif t.type == "html_block":
                if not t.content.lstrip().startswith("<!--"): result.append(Paragraph(escaped(t.content), BODY))
            else: raise ValueError(f"Unsupported block Markdown {t.type} in {filename}")
            i += 1
        return result


def title_flows(edition, renderer):
    return [
        Spacer(1, 27 * mm), Paragraph("EXPANDED COMPANION EDITION", ParagraphStyle("Edition", parent=SMALL, alignment=TA_CENTER, textColor=OCHRE)),
        Spacer(1, 9 * mm), Paragraph(escaped(edition.title), ParagraphStyle("Title", parent=H1, fontSize=30, leading=35, alignment=TA_CENTER)),
        Paragraph(escaped(edition.subtitle), ParagraphStyle("Subtitle", parent=LEAD, alignment=TA_CENTER)), Spacer(1, 12 * mm),
        HRFlowable(width="48%", color=GOLD, thickness=1, hAlign="CENTER"), Spacer(1, 13 * mm),
        Paragraph("Prepared by <b>Daniel Franjkovic</b>", ParagraphStyle("Author", parent=BODY, alignment=TA_CENTER)),
        Paragraph("daniel.franjkovic@outlook.com.au", ParagraphStyle("Email", parent=SMALL, alignment=TA_CENTER)),
        Spacer(1, 20 * mm), Paragraph("Source edition", H3),
        Paragraph("Fo Guang Shan Hsi Lai Temple, Electronic Edition 3.0, April 2022.<br/>English translation, editing and design by Andrew Nguy and Raymond Kong.", BODY),
        Paragraph("This independent companion explains the source liturgy. It is not a replacement translation or an official temple edition. Source-page references count PDF pages; printed page numbers are given where useful. In communal practice, follow the officiant's instructions.", BODY),
        Paragraph("The original liturgies remain copyrighted by Fo Guang Shan Hsi Lai Temple and are linked in the references. New explanations and reading notes are clearly distinguished from source wording.", SMALL),
        Spacer(1, 6 * mm), Paragraph('Further Buddhist terminology: <link href="https://www.fgsitc.org/glossary/" color="#397b75">www.fgsitc.org/glossary/</link>', SMALL),
        Paragraph("A4 print edition. Revised September 2026.", SMALL), PageBreak(),
    ]


def build_edition(edition):
    renderer = Renderer()
    flow = title_flows(edition, renderer)
    flow.append(Paragraph("Contents", H1))
    flow.append(Paragraph("Page numbers and PDF bookmarks lead to the main sections and reading aids.", SMALL))
    toc = TableOfContents(); toc.levelStyles = [TOC0, TOC1]; toc.dotsMinLevel = 0
    flow.extend([toc, PageBreak()])
    for index, (filename, title, subtitle) in enumerate(edition.sections):
        if index: flow.append(PageBreak())
        if edition.master:
            divider = SectionDivider(title, subtitle)
            divider._section = title
            divider._anchor = (f"part-{index}", title, 0)
            flow.extend([divider, PageBreak(), Paragraph(escaped(title), H3)])
        else:
            flow.append(renderer.heading(escaped(title), H1, 0, title))
        flow.append(Paragraph(escaped(subtitle), LEAD))
        flow.extend(renderer.markdown((ROOT / filename).read_text(encoding="utf-8"), filename))
    flow.extend([Spacer(1, 12 * mm), HRFlowable(width="50%", color=GOLD, thickness=1, hAlign="CENTER"), Spacer(1, 5 * mm), Paragraph("May the benefit of this work support understanding, compassionate reform and the awakening of all beings.", ParagraphStyle("Dedication", parent=LEAD, fontName="Cambria-Italic", alignment=TA_CENTER))])
    temp = TMP / (edition.stem + "-body.pdf")
    GuideDoc(temp, edition).multiBuild(flow)
    writer = PdfWriter(clone_from=str(temp))
    cover = PdfReader(ROOT / "assets" / "covers" / (edition.stem + ".pdf")).pages[0]
    if edition.stem == "06-glossary-reference":
        # Retain the original design while updating its former 373-entry label.
        content = ContentStream(cover.get_contents(), cover.pdf)
        replacements = 0
        for operands, operator in content.operations:
            if operator == b"Tj" and str(operands[0]) == "373":
                operands[0] = TextStringObject(str(glossary_count()))
                replacements += 1
        if replacements != 1:
            raise ValueError("The original glossary cover count could not be updated safely")
        cover[NameObject("/Contents")] = content
    writer.insert_page(cover, 0)
    writer.add_metadata({"/Title": edition.title, "/Author": "Daniel Franjkovic", "/Subject": edition.subtitle, "/Creator": "Samadhi companion shared Markdown build", "/Keywords": "Samadhi, Water Repentance, companion, September 2026"})
    writer.page_mode = "/UseOutlines"
    target = OUT / (edition.stem + ".pdf")
    with target.open("wb") as stream: writer.write(stream)
    pages = len(PdfReader(target).pages)
    return {"file": target.name, "pages": pages, "source_files": [s[0] for s in edition.sections]}


def glossary_count():
    text = (ROOT / "GLOSSARY.md").read_text(encoding="utf-8")
    section = text.split("## Consolidated glossary", 1)[1].split("\n## ", 1)[0]
    return sum(t.type == "tr_open" for t in MD.parse(section)) - 1


def build_markdown():
    master = next(e for e in EDITIONS if e.master)
    pieces = ["# The Samādhi Water Repentance Companion: Master Edition", "", "Prepared by Daniel Franjkovic", "", "Expanded companion edition, September 2026.", "", "<!-- Generated by build_guides.py from the component Markdown. Edit the components, then rebuild. -->", ""]
    for filename, title, _ in master.sections:
        body = (ROOT / filename).read_text(encoding="utf-8")
        lines = body.splitlines()
        if lines and lines[0].startswith("# "): lines = lines[1:]
        pieces.extend([f"# {title}", "", "\n".join(lines).strip(), ""])
    (ROOT / "SAMADHI_WATER_REPENTANCE_COMPANION.md").write_text(plain("\n".join(pieces)).rstrip() + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", choices=[e.stem for e in EDITIONS], help="Build one PDF; default builds all six")
    parser.add_argument("--font-dir", type=Path, default=Path("C:/Windows/Fonts"))
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True); TMP.mkdir(parents=True, exist_ok=True)
    register_fonts(args.font_dir)
    build_markdown()
    records = []
    for edition in EDITIONS:
        if args.edition and edition.stem != args.edition: continue
        record = build_edition(edition); records.append(record); print(json.dumps(record, ensure_ascii=False), flush=True)
    if all((OUT / (e.stem + ".pdf")).exists() for e in EDITIONS):
        records = [{"file": e.stem + ".pdf", "pages": len(PdfReader(OUT / (e.stem + ".pdf")).pages), "source_files": [s[0] for s in e.sections]} for e in EDITIONS]
        (OUT / "build-manifest.json").write_text(json.dumps({"edition": "Expanded companion edition, September 2026", "glossary_entries": glossary_count(), "outputs": records}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
