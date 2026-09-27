"""Check publication integrity and render pages for human visual review."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

import pdfplumber
from PIL import Image, ImageDraw
from pypdf import PdfReader

from build_guides import EDITIONS, MD, ROOT, OUT, inline


def normalise(value):
    value = html.unescape(re.sub(r"<[^>]*>", " ", value))
    value = unicodedata.normalize("NFKD", value).lower()
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", value))


def all_destinations(items):
    for item in items:
        if isinstance(item, list): yield from all_destinations(item)
        else: yield item


def check(edition):
    target = OUT / (edition.stem + ".pdf")
    reader = PdfReader(target)
    texts = [page.extract_text() or "" for page in reader.pages]
    (ROOT / "tmp" / "pdfs" / (edition.stem + "-final.txt")).write_text("\n\n".join(f"=== PDF PAGE {i} ===\n{text}" for i, text in enumerate(texts, 1)), encoding="utf-8")
    full = normalise(" ".join(texts))
    compact = full.replace(" ", "")
    missing = []
    checked = 0
    for filename, _, _ in edition.sections:
        source = (ROOT / filename).read_text(encoding="utf-8")
        first_inline = True
        for token in MD.parse(source):
            if token.type != "inline" or any(t.type == "image" for t in token.children or []): continue
            if first_inline:
                # The build replaces each component's first title with its edition heading.
                first_inline = False
                continue
            phrase = normalise(inline(token.children))
            words = phrase.split()
            if len(words) < 8: continue
            prefix = " ".join(words[:8])
            checked += 1
            # PDF extraction can insert a newline inside a long Sanskrit syllable.
            if prefix not in full and prefix.replace(" ", "") not in compact:
                missing.append({"source": filename, "phrase": prefix})
    destinations = list(all_destinations(reader.outline))
    bad_destinations = [str(d.title) for d in destinations if reader.get_destination_page_number(d) not in range(len(reader.pages))]
    page_ids = {p.indirect_reference.idnum for p in reader.pages}
    broken_links = []
    for n, page in enumerate(reader.pages, 1):
        for ref in page.get("/Annots", []):
            annot = ref.get_object()
            dest = annot.get("/Dest")
            if isinstance(dest, list) and hasattr(dest[0], "idnum") and dest[0].idnum not in page_ids:
                broken_links.append(n)
    margins = []
    with pdfplumber.open(target) as pdf:
        for n, page in enumerate(pdf.pages, 1):
            outside = [c for c in page.chars if c.get("text", "").strip() and (c["x0"] < 12 or c["x1"] > page.width - 12 or c["top"] < 10 or c["bottom"] > page.height - 10)]
            if outside: margins.append({"page": n, "characters": "".join(c["text"] for c in outside)[:120]})
    result = {
        "file": target.name, "pages": len(reader.pages), "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "source_prefixes_checked": checked, "missing_source_prefixes": missing,
        "outline_destinations": len(destinations), "invalid_outline_destinations": bad_destinations,
        "broken_internal_link_pages": broken_links, "text_outside_page_safe_area": margins,
        "empty_text_pages": [n for n, t in enumerate(texts, 1) if not t.strip()],
        "unresolved_markup_pages": [n for n, t in enumerate(texts, 1) if "[[BR]]" in t or "\ufffd" in t],
    }
    return result


def render(edition):
    folder = ROOT / "tmp" / "pdfs" / "final" / edition.stem
    folder.mkdir(parents=True, exist_ok=True)
    for stale in [*folder.glob("page-*.png"), *folder.glob("contact-*.jpg")]:
        if stale.resolve().parent != folder.resolve():
            raise RuntimeError(f"Unexpected render path: {stale}")
        stale.unlink()
    poppler = shutil.which("pdftoppm")
    if not poppler: raise RuntimeError("pdftoppm is required")
    subprocess.run([poppler, "-png", "-scale-to", "1100", str(OUT / (edition.stem + ".pdf")), str(folder / "page")], check=True, capture_output=True)
    files = sorted(folder.glob("page-*.png"))
    for start in range(0, len(files), 12):
        group = files[start:start + 12]
        contact = Image.new("RGB", (960, 4 * 470), "#d7d7d7")
        draw = ImageDraw.Draw(contact)
        for i, p in enumerate(group):
            with Image.open(p) as original:
                thumb = original.convert("RGB"); thumb.thumbnail((310, 440))
                x, y = (i % 3) * 320, (i // 3) * 470
                contact.paste(thumb, (x + 5, y + 22)); draw.text((x + 8, y + 6), f"PDF page {start+i+1}", fill="black")
        contact.save(folder / f"contact-{start+1:03d}-{start+len(group):03d}.jpg", quality=92)
    return str(folder)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--render", action="store_true")
    parser.add_argument("--edition", choices=[e.stem for e in EDITIONS]); args = parser.parse_args()
    records = []
    for edition in EDITIONS:
        if args.edition and edition.stem != args.edition: continue
        record = check(edition)
        if args.render: record["render_folder"] = render(edition)
        records.append(record)
        print(json.dumps({k: v if not isinstance(v, list) else len(v) for k, v in record.items()}, ensure_ascii=False), flush=True)
    report = ROOT / "tmp" / "pdfs" / ("verification-" + (args.edition or "all") + ".json")
    report.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if any(r["missing_source_prefixes"] or r["invalid_outline_destinations"] or r["broken_internal_link_pages"] or r["text_outside_page_safe_area"] or r["empty_text_pages"] or r["unresolved_markup_pages"] for r in records):
        raise SystemExit("PDF integrity check needs attention; see report")


if __name__ == "__main__": main()
