"""Create Vietnamese versions of the seven editable source diagrams."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import resvg_py
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from translations.diagrams_vi import LABELS

ROOT = Path(__file__).resolve().parent
NS = '{http://www.w3.org/2000/svg}'
ET.register_namespace('', NS[1:-1])
fonts = [str(Path('C:/Windows/Fonts') / n) for n in ('arial.ttf', 'arialbd.ttf')]
pdfmetrics.registerFont(TTFont('DiagramArial', fonts[0]))
pdfmetrics.registerFont(TTFont('DiagramArialBold', fonts[1]))
target = ROOT / 'assets/diagrams/vi'
target.mkdir(exist_ok=True)
for source in sorted((ROOT / 'assets/diagrams').glob('*.svg')):
    tree = ET.parse(source)
    for node in tree.iter():
        if node.tag in (NS+'text', NS+'title', NS+'desc') and node.text:
            old = node.text.strip()
            if old not in LABELS and not re.fullmatch(r'[IVX\d]+', old):
                raise ValueError(f'Missing diagram translation: {old}')
            node.text = LABELS.get(old, old)
    svg = ET.tostring(tree.getroot(), encoding='unicode')
    svg = svg.replace("'Noto Sans',Arial", 'Arial')
    # Keep text within its original allocation, enlarging labels only through layout.
    # Vietnamese labels were worded to fit; a few narrow nodes need 1-3px less.
    root = ET.fromstring(svg)
    if source.stem == 'practice-flow':
        # Number badges sit on the top border, clear of Vietnamese tone marks.
        for node in root.iter(NS+'circle'):
            node.set('cy',str(float(node.get('cy'))-20))
        for node in root.iter(NS+'text'):
            if node.get('class')=='n':
                node.set('y',str(float(node.get('y'))-20))
    limits = {'three-scroll-journey': 365, 'three-obstructions': 190,
              'samsara-cycle': 160, 'six-realms': 180, 'practice-flow': 145}
    for node in root.iter(NS+'text'):
        if source.stem not in limits:
            continue
        x = float(node.get('x', '0'))
        cls = node.get('class', '')
        maxwidth = limits[source.stem]
        if source.stem == 'three-obstructions' and x == 550:
            maxwidth = 258 if float(node.get('y', '0')) < 300 else 190
        if source.stem == 'practice-flow' and x == 990:
            maxwidth = 270
        if source.stem == 'six-realms' and x == 962:
            maxwidth = 165
        if x in (550, 600, 800) and (float(node.get('y','0')) < 90 or float(node.get('y','0')) > 500):
            maxwidth = 1000
        style = node.get('style', '')
        match = re.search(r'(\d+(?:\.\d+)?)px', style)
        sizes = {'h':29, 't':24 if source.stem=='practice-flow' else 21, 's':16 if source.stem=='six-realms' else 18, 'w':23 if source.stem=='six-realms' else 17, 'n':18}
        size = float(node.get('font-size') or (match.group(1) if match else sizes.get(cls, 25)))
        bold = node.get('font-weight')=='700' or cls in ('h','t','n','w') and not (cls=='w' and source.stem=='three-obstructions') or '700' in style
        width = pdfmetrics.stringWidth(node.text or '', 'DiagramArialBold' if bold else 'DiagramArial', size)
        if width > maxwidth:
            newsize = round(size * maxwidth / width, 2)
            node.set('style', style + f';font-size:{newsize}px')
    outfile = target/source.name
    outfile.write_text(ET.tostring(root, encoding='unicode'), encoding='utf-8')
    width = int(float(root.get('width'))) * 2
    png = resvg_py.svg_to_bytes(svg_path=str(outfile), width=width, skip_system_fonts=True, font_files=fonts, sans_serif_family='Arial')
    outfile.with_suffix('.png').write_bytes(png)
    print(outfile.name)
