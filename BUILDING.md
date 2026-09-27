# Building the companion editions

Edit the component Markdown files, then run the shared build. It creates all six PDFs and the combined master Markdown from the same current material.

```powershell
python -m pip install -r requirements.txt
python build_guides.py
```

The build expects licensed Cambria, Arial and SimSun font files in `C:/Windows/Fonts`. Use `--font-dir PATH` to provide the same fonts from another location. Fonts are not redistributed in the repository.

To rebuild one PDF while checking layout:

```powershell
python build_guides.py --edition 04-master-print-edition
```

The component files are `MASTER_OVERVIEW.md`, `STARTING_PRACTICE.md`, `PRACTICE_COMPANION.md`, `SCROLL_TWO_COMPANION.md`, `SCROLL_THREE_COMPANION.md`, `CONCEPTS.md`, `FIGURES.md`, `PRONUNCIATION.md`, `GLOSSARY.md` and `REFERENCES.md`. `SAMADHI_WATER_REPENTANCE_COMPANION.md` is generated; direct edits to it will be replaced by the next build.

The six original cover designs are preserved in `assets/covers/`. The glossary's cover count is updated from the current entry table during the build. The body uses the existing cream, teal and gold palette, Cambria and Arial typography, diagram PNGs and attributed figure artwork. PDF contents and bookmarks are rebuilt from headings. The original liturgies are not included in any build output.

Outputs are in `downloads/`. Once all six outputs exist, the build updates `downloads/build-manifest.json` with each PDF's actual page count, component files and the glossary entry count. Intermediate bodies are in the ignored `tmp/pdfs/` directory.

Before sharing a new edition, render its pages, check headings, tables, images and page references, and reconcile the download-page counts with the build manifest. Expanding one component can change pagination in several editions.

```powershell
python verify_guides.py --render
```

The verification command needs Poppler's `pdftoppm` on `PATH`. It extracts each PDF, checks source-content prefixes, bookmark and internal-link destinations, page margins and empty pages, then produces page images and contact sheets in `tmp/pdfs/final/`. Inspect the images and review any missing-content entries in `tmp/pdfs/verification-all.json`; automated checks cannot establish visual quality or doctrinal accuracy.

## Updating a diagram

The online Markdown uses SVG diagrams; PDFs use their matching PNG files. After editing an SVG, regenerate its PNG before rebuilding the affected editions. For the three-obstructions diagram, install the optional renderer with `python -m pip install resvg-py==0.5.0`, then run this Python from the repository root:

```python
from pathlib import Path
import resvg_py

diagram = Path("assets/diagrams/three-obstructions.svg")
fonts = [f"C:/Windows/Fonts/{name}" for name in ("arial.ttf", "arialbd.ttf")]
diagram.with_suffix(".png").write_bytes(resvg_py.svg_to_bytes(
    svg_path=str(diagram), width=3361, height=1589,
    skip_system_fonts=True, font_files=fonts, sans_serif_family="Arial",
))
```

Rebuild Scroll One and the master, then inspect PDF pages 10 and 22 respectively. Those page numbers apply to the September 2026 expanded English edition with the new practice chapter and can change after later content edits.
## English-Vietnamese master

The English master includes `STARTING_PRACTICE.md`. Its Vietnamese counterpart and the remaining translated chapters are under `translations/vi/`. Keep Markdown block structure and table row order aligned with the English source. Do not edit generated PDF text directly.

```powershell
python build_guides.py --edition 04-master-print-edition
python build_diagrams_vi.py
python build_bilingual.py
python verify_bilingual.py
```

The diagram command additionally requires `resvg-py`. It translates editable SVG text and renders PNGs with the same licensed Arial fonts used in the book. The bilingual builder uses existing styles and artwork, measures both languages, and starts a new page pair whenever either side would overflow. Long tables break at identical row boundaries with repeated headers. It never truncates content to fit.

`downloads/04-master-english-vietnamese-edition.manifest.json` records source hashes, page pairs and block identities. `downloads/bilingual-validation.json` records full text coverage and PDF checks. Rebuild when either language changes. The `--partial` option exists for local layout previews and never produces the final download filename.
