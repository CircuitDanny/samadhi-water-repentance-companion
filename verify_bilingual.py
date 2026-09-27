"""Verify paired-page identity and complete Markdown text coverage."""
from pathlib import Path
import argparse,hashlib,json,re,unicodedata
from pypdf import PdfReader
import pdfplumber
import build_guides as g
from build_bilingual import TARGET,VI,structure

def normalise(s):
    return ''.join(c for c in unicodedata.normalize('NFC',s).casefold() if c.isalnum())

def inline_text(tokens):
    out=[]
    for t in tokens or []:
        if t.type in ('text','code_inline'): out.append(t.content)
        elif t.type in ('softbreak','hardbreak'): out.append(' ')
    return ''.join(out)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pdf',type=Path,default=TARGET);parser.add_argument('--render',action='store_true');args=parser.parse_args()
    target=args.pdf
    manifest=json.loads(target.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    reader=PdfReader(target)
    texts=[p.extract_text() or '' for p in reader.pages]
    errors=[]
    if len(texts)%2: errors.append('Odd total page count')
    corpus={lang:normalise('\n'.join(texts[i::2])) for i,lang in enumerate(('en','vi'))}
    checked={lang:0 for lang in ('en','vi')}
    missing=[]
    for source in manifest['sources']:
        name=source['file']
        for lang,folder in (('en',g.ROOT),('vi',VI)):
            data=(folder/name).read_text(encoding='utf-8')
            if re.search(r'ZXQ\w*XZ|\[\[BR\]\]|\ufffd',data):
                errors.append(f'Unresolved placeholder: {lang}/{name}')
            expected=source[lang+'_sha256']
            if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=expected: errors.append(f'Stale source: {lang}/{name}')
            first_heading=True
            previous=None
            for token in g.MD.parse(data):
                if token.type=='inline':
                    if previous=='heading_open' and first_heading:
                        first_heading=False;previous=token.type;continue
                    text=inline_text(token.children)
                    value=normalise(text)
                    if value:
                        checked[lang]+=1
                        if value not in corpus[lang]:
                            missing.append({'language':lang,'source':name,'text':text[:160]})
                previous=token.type
    pages=manifest['page_map']
    for a,b in zip(pages[::2],pages[1::2]):
        if a['units']!=b['units'] or a['pair']!=b['pair'] or a['page']+1!=b['page'] or a['language']!='en' or b['language']!='vi': errors.append(f"Pair mismatch: {a['page']}")
    if missing:errors.append(f'{len(missing)} source text blocks not located')
    bad_bounds=[];bad_glyph=[]
    with pdfplumber.open(target) as doc:
        for page in doc.pages:
            for char in page.chars:
                if char['text']=='\ufffd' or char['text'].startswith('(cid:'):bad_glyph.append(page.page_number)
                if char['x0']<-1 or char['x1']>page.width+1 or char['top']<-1 or char['bottom']>page.height+1:
                    bad_bounds.append(page.page_number);break
    if bad_bounds:errors.append(f'Text beyond page: {bad_bounds}')
    if bad_glyph:errors.append(f'Bad extracted glyph: {bad_glyph}')
    ids={page.indirect_reference.idnum for page in reader.pages}
    annotations=0
    for number,page in enumerate(reader.pages,1):
        for ref in page.get('/Annots',[]):
            annotations+=1;annotation=ref.get_object();dest=annotation.get('/Dest')
            if isinstance(dest,list) and hasattr(dest[0],'idnum') and dest[0].idnum not in ids:
                errors.append(f'Broken internal link on page {number}')
    def outlines(nodes):
        for node in nodes:
            if isinstance(node,list):yield from outlines(node)
            else:yield node
    destinations=list(outlines(reader.outline))
    if any(reader.get_destination_page_number(d) is None for d in destinations):errors.append('Invalid bookmark destination')
    report={'file':target.name,'complete':manifest['complete'],'pages':len(texts),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'source_blocks_checked':checked,'missing':missing,'pair_records':len(pages)//2,'annotations':annotations,'outline_destinations':len(destinations),'errors':errors}
    if args.render and not errors:
        if target.resolve()!=TARGET.resolve():raise ValueError('--render requires the final edition')
        from verify_guides import render
        report['render_folder']=render(g.Edition(TARGET.stem,'English-Vietnamese Edition','',()))
    output=(g.ROOT/'downloads/bilingual-validation.json') if target.resolve()==TARGET.resolve() else target.with_suffix('.validation.json')
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='missing'},ensure_ascii=False))
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
