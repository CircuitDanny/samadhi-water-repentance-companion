"""Build complete aligned English/Vietnamese master pages from matching Markdown.

Both languages are measured before a page break is selected. Paragraphs and
table rows are never assigned independently, preventing translation drift.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from io import BytesIO
import argparse, copy, hashlib, html, json, re
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle, Image, PageBreak, Spacer
from pypdf import PdfReader
import build_guides as g

ROOT=g.ROOT
TARGET=ROOT/'downloads/04-master-english-vietnamese-edition.pdf'
VI=ROOT/'translations/vi'
FRAME_H=g.CH-4
TITLES=[
('Định hướng','Đọc phần này trước'),
('Bắt đầu tu học Phật pháp','Giáo lý cốt lõi và bước đầu thực hành'),
('Phần I - Quyển Một','Nguồn gốc, quy y, phiền não, phát nguyện và trí tuệ'),
('Phần II - Quyển Hai','Nghiệp, hành vi và sáu căn'),
('Phần III - Quyển Ba','Quả báo, hồi hướng và tưởng niệm'),
('Phần IV - Các khái niệm cốt lõi','Thế giới Phật giáo sau những thuật ngữ'),
('Phần V - Chư Phật và Bồ-tát','Danh hiệu, câu chuyện, nhận diện và tu tập'),
('Phần VI - Phát âm','Danh hiệu, thuật ngữ và các câu tụng'),
('Phần VII - Từ điển thuật ngữ','Giải nghĩa dễ hiểu cho cả ba quyển'),
('Phần VIII - Tài liệu tham khảo','Nguồn tư liệu, hình ảnh và giới hạn biên soạn'),
]

@dataclass
class Pair:
    en: list
    vi: list
    key: str
    heading: tuple|None=None
    table: bool=False

class Renderer(g.Renderer):
    def __init__(self, language):
        super().__init__(); self.language=language
    def image(self, token):
        if self.language=='vi' and '/diagrams/' in token.attrGet('src'):
            token=copy.deepcopy(token)
            token.attrSet('src',token.attrGet('src').replace('/diagrams/','/diagrams/vi/'))
        return super().image(token)

class Divider(g.SectionDivider):
    def __init__(self,label,subtitle,language):
        super().__init__(label,subtitle);self.language=language
    def draw(self):
        super().draw()
        if self.language=='vi':
            c=self.canv;c.setFillColor(g.OCHRE)
            c.roundRect(12*g.mm,207*g.mm,67*g.mm,8*g.mm,4*g.mm,fill=1,stroke=0)
            c.setFont('Arial-Bold',7.3);c.setFillColor(g.colors.white)
            c.drawString(17*g.mm,210*g.mm,'SÁCH ĐỒNG HÀNH ĐẦY ĐỦ')

def structure(text):
    return [(t.type,t.tag,t.nesting) for t in g.MD.parse(text) if t.type!='html_block']

def height(flows, canvas):
    total=0
    for f in flows:
        _, h=f.wrapOn(canvas,g.CW,FRAME_H)
        total+=f.getSpaceBefore()+h+f.getSpaceAfter()
    return total

def table_slice(table, first, last):
    rows=[table._cellvalues[0]]+table._cellvalues[first:last]
    obj=Table(rows,colWidths=table._argW,hAlign='LEFT',spaceBefore=5,spaceAfter=10)
    obj.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),g.TEAL),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[g.colors.white,g.MIST] if first%2 else [g.MIST,g.colors.white]),
        ('BOX',(0,0),(-1,-1),.45,g.RULE),('INNERGRID',(0,0),(-1,-1),.3,g.RULE),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),
        ('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
    ]))
    return obj

def paired_flows(filename):
    source=(ROOT/filename).read_text(encoding='utf-8')
    translated=(VI/filename).read_text(encoding='utf-8')
    a,b=structure(source),structure(translated)
    if a!=b:
        mismatch=next((i for i in range(min(len(a),len(b))) if a[i]!=b[i]),min(len(a),len(b)))
        raise ValueError(f'{filename}: Markdown structure mismatch at {mismatch}: {a[mismatch:mismatch+5]} vs {b[mismatch:mismatch+5]} (lengths {len(a)}/{len(b)})')
    en=Renderer('en').markdown(source,'paired.md')
    vi=Renderer('vi').markdown(translated,'paired.md')
    assert len(en)==len(vi),(filename,len(en),len(vi))
    result=[]
    for i,(e,v) in enumerate(zip(en,vi)):
        assert type(e)==type(v),(filename,i,type(e),type(v))
        if isinstance(e,Paragraph):
            original=v
            v=Paragraph(original.text,e.style)
            if hasattr(original,'_anchor'):v._anchor=original._anchor
        heading=None
        if hasattr(e,'_anchor'):
            heading=(e._anchor[1],v._anchor[1],1)
        result.append(Pair([e],[v],f'{Path(filename).stem}-{i}',heading,isinstance(e,Table)))
    # A profile title and its recognition cues belong beside the artwork.
    # Keeping only the heading with the cues strands both on the previous page.
    if filename == 'FIGURES.md':
        for i, pair in enumerate(result[:-1]):
            if isinstance(pair.en[0], Paragraph) and isinstance(result[i+1].en[0], Image):
                if 'Say it like:' in pair.en[0].getPlainText():
                    pair.en[0].keepWithNext = True
                    pair.vi[0].keepWithNext = True
    return result

def paginate(pairs,canvas):
    pages=[]; current=[]; used=[0.,0.]
    def flush():
        nonlocal current,used
        if current: pages.append(current)
        current=[];used=[0.,0.]
    def place(item):
        nonlocal used
        hs=[height(item.en,canvas),height(item.vi,canvas)]
        if max(hs)>FRAME_H+.01: raise ValueError(f'Oversized aligned unit: {item.key} {hs}')
        if any(used[l]+hs[l]>FRAME_H for l in range(2)): flush()
        current.append(item);used=[used[l]+hs[l] for l in range(2)]
    i=0
    while i<len(pairs):
        item=pairs[i]
        if item.table:
            en,vi=item.en[0],item.vi[0]
            assert len(en._cellvalues)==len(vi._cellvalues),(item.key,'rows')
            first=1; count=len(en._cellvalues)
            while first<count:
                last=first
                while last<count:
                    trial=[table_slice(t,first,last+1) for t in (en,vi)]
                    hs=[height([t],canvas) for t in trial]
                    if any(used[l]+hs[l]>FRAME_H for l in range(2)): break
                    last+=1
                if last==first:
                    if not current: raise ValueError(f'Table row cannot fit: {item.key} row {first}')
                    flush();continue
                place(Pair([table_slice(en,first,last)],[table_slice(vi,first,last)],f'{item.key}:rows-{first}-{last-1}'))
                first=last
                if first<count: flush()
            i+=1;continue
        # Keep headings and illustrations with a meaningful following block.
        group=[item]; j=i
        while j+1<len(pairs) and any(getattr(f,'keepWithNext',False) or getattr(getattr(f,'style',None),'keepWithNext',False) for f in group[-1].en):
            if pairs[j+1].table:
                nxt=pairs[j+1]
                minimum=[height([table_slice(t,1,2)],canvas) for t in (nxt.en[0],nxt.vi[0])]
                group_h=[sum(height(getattr(x,l),canvas) for x in group) for l in ('en','vi')]
                if any(used[l]+group_h[l]+minimum[l]>FRAME_H for l in range(2)): flush()
                break
            j+=1;group.append(pairs[j])
        heights=[sum(height(getattr(x,l),canvas) for x in group) for l in ('en','vi')]
        if max(heights)<=FRAME_H and any(used[l]+heights[l]>FRAME_H for l in range(2)): flush()
        for x in group: place(x)
        i=j+1
    flush()
    return pages

def clean_label(s):
    return html.unescape(re.sub(r'<[^>]+>','',s))

def furniture(c,page,section,lang,pair_no):
    c.setFillColor(g.PAPER);c.rect(0,0,g.W,g.H,fill=1,stroke=0)
    c.setStrokeColor(g.RULE);c.setLineWidth(.4);c.line(g.MX,g.H-12*g.mm,g.W-g.MX,g.H-12*g.mm)
    label=clean_label(section)
    style=ParagraphStyle('header',parent=g.SMALL,fontSize=6.6,leading=7.5,spaceAfter=0)
    p=Paragraph(g.escaped(label),style);_,ph=p.wrap(g.CW-75,20);p.drawOn(c,g.MX,g.H-10*g.mm)
    c.setFillColor(g.OCHRE);c.setFont('Arial-Bold',7)
    c.drawRightString(g.W-g.MX,g.H-9.8*g.mm,'ENGLISH' if lang=='en' else 'TIẾNG VIỆT')
    c.setStrokeColor(g.RULE);c.line(g.MX,13*g.mm,g.W-g.MX,13*g.mm)
    c.setFillColor(g.MUTED);c.setFont('Arial',6.5)
    footer=f'English-Vietnamese Edition | Pair {pair_no}' if lang=='en' else f'Ấn bản Anh-Việt | Cặp trang {pair_no}'
    c.drawString(g.MX,9*g.mm,footer)
    c.setFillColor(g.OCHRE);c.circle(g.W-g.MX,10*g.mm,4.2*g.mm,fill=1,stroke=0)
    c.setFillColor(g.colors.white);c.setFont('Arial-Bold',6.5);c.drawCentredString(g.W-g.MX,9.15*g.mm,str(page))

def draw_flows(c,flows):
    y=g.H-g.MT
    for f in flows:
        w,h=f.wrapOn(c,g.CW,FRAME_H)
        y-=f.getSpaceBefore()+h
        x=g.MX
        if getattr(f,'hAlign',None)=='CENTER': x+=(g.CW-w)/2
        f.drawOn(c,x,y)
        y-=f.getSpaceAfter()
    assert y>=g.MB-1,(y,g.MB)

def cover(c,lang):
    c.setFillColor(g.DEEP);c.rect(0,0,g.W,g.H,fill=1,stroke=0)
    c.setStrokeColor(g.GOLD);c.setLineWidth(1);c.roundRect(9*g.mm,9*g.mm,g.W-18*g.mm,g.H-18*g.mm,5*g.mm,stroke=1,fill=0)
    c.setFillColor(g.GOLD);c.roundRect(54*g.mm,270*g.mm,102*g.mm,10*g.mm,5*g.mm,fill=1,stroke=0)
    c.setFillColor(g.DEEP);c.setFont('Arial-Bold',8)
    c.drawCentredString(g.W/2,273.5*g.mm,'ENGLISH-VIETNAMESE EDITION' if lang=='en' else 'ẤN BẢN ANH-VIỆT')
    c.drawImage(str(ROOT/'assets/cover-art.png'),g.W/2-36*g.mm,192*g.mm,72*g.mm,72*g.mm,preserveAspectRatio=True,mask='auto')
    title='THE SAMĀDHI WATER<br/>REPENTANCE COMPANION' if lang=='en' else 'SÁCH ĐỒNG HÀNH<br/>TỪ BI TAM MUỘI THỦY SÁM'
    p=Paragraph(g.escaped(title).replace('&lt;br/&gt;','<br/>'),ParagraphStyle('ct',parent=g.H1,fontSize=25,leading=32,alignment=TA_CENTER,textColor=g.colors.white))
    _,h=p.wrap(g.CW,150);p.drawOn(c,g.MX,167*g.mm-h)
    sub='Three scrolls, one continuous path of repentance and reform' if lang=='en' else 'Ba quyển, một con đường sám hối và sửa đổi liên tục'
    p=Paragraph(sub,ParagraphStyle('cs',parent=g.LEAD,alignment=TA_CENTER,textColor=g.GOLD));_,h=p.wrap(g.CW,80);p.drawOn(c,g.MX,121*g.mm-h)
    c.setStrokeColor(g.GOLD);c.line(27*g.mm,104*g.mm,g.W-27*g.mm,104*g.mm)
    terms=['AFFLICTIONS','KARMA','RESULTS'] if lang=='en' else ['PHIỀN NÃO','NGHIỆP','QUẢ BÁO']
    for i,term in enumerate(terms):
        x=(54+i*51)*g.mm;c.setFillColor(g.GOLD);c.circle(x,87*g.mm,8*g.mm,fill=1,stroke=0)
        c.setFillColor(g.DEEP);c.setFont('Cambria-Bold',10);c.drawCentredString(x,86*g.mm,['I','II','III'][i])
        c.setFillColor(g.colors.white);c.setFont('Arial-Bold',7);c.drawCentredString(x,73*g.mm,term)
    note='Complete master | Core teachings, practice, figures and glossary' if lang=='en' else 'Bản đầy đủ | Giáo lý, tu tập, chư Phật và từ điển thuật ngữ'
    p=Paragraph(note,ParagraphStyle('cn',parent=g.SMALL,alignment=TA_CENTER,textColor=g.colors.white));_,h=p.wrap(g.CW,50);p.drawOn(c,g.MX,53*g.mm-h)
    c.setFont('Arial-Bold',8);c.drawString(20*g.mm,29*g.mm,('Prepared by ' if lang=='en' else 'Biên soạn: ')+'Daniel Franjkovic')
    c.setFont('Arial',7);c.drawString(20*g.mm,23*g.mm,'September 2026' if lang=='en' else 'Tháng 9 năm 2026')
    c.drawImage(str(ROOT/'assets/repository-qr.png'),g.W-46*g.mm,19*g.mm,25*g.mm,25*g.mm,mask='auto')

def title_pair():
    en=[('About this edition',g.H1),('English-Vietnamese Edition',g.LEAD),
    ('Each English page is followed immediately by its complete Vietnamese counterpart. Pair numbers help you compare the same passage. Table rows and paragraphs stay together across the languages; the new page numbers differ from the English-only edition.',g.BODY),
    ('Vietnamese wording uses standard spelling and Buddhist vocabulary familiar to Southern readers. It translates the companion commentary, not a Vietnamese temple liturgy. Follow your temple’s own text and officiant for chanting. Your teacher’s local terminology may differ.',g.BODY),
    ('The translation has been prepared with AI assistance and editorial checks. It has not yet been reviewed by a Vietnamese-speaking Buddhist teacher. Corrections from teachers and fluent readers are welcome.',g.BODY),
    ('Source edition',g.H2),
    ('Fo Guang Shan Hsi Lai Temple, Electronic Edition 3.0, April 2022. English translation, editing and design by Andrew Nguy and Raymond Kong. References to source PDF pages still point to those original files, not to the pages of this companion.',g.BODY),
    ('Prepared by Daniel Franjkovic. This independent educational companion does not replace primary scriptures, living teachers or temple guidance. Original liturgies remain copyrighted by Fo Guang Shan Hsi Lai Temple; artwork credits and licences are retained beside the images.',g.BODY),
    ('Begin with “Beginning a Buddhist practice”, then use the scroll guide, figure profiles and glossary as you need them. English sound cues remain explicitly identified as English approximations on Vietnamese pages.',g.BODY)]
    vi=[('Về ấn bản này',g.H1),('Ấn bản Anh-Việt',g.LEAD),
    ('Ngay sau mỗi trang tiếng Anh là trang tiếng Việt tương ứng, dịch đầy đủ cùng nội dung. Số cặp trang giúp bạn đối chiếu. Các hàng trong bảng và đoạn văn luôn đi cùng nhau ở hai ngôn ngữ; số trang mới khác với ấn bản chỉ có tiếng Anh.',g.BODY),
    ('Bản tiếng Việt dùng chính tả chuẩn và từ ngữ Phật giáo quen thuộc với người đọc miền Nam. Đây là bản dịch lời giải thích của sách đồng hành, không phải bản nghi lễ tiếng Việt của một ngôi chùa. Khi tụng niệm, hãy theo kinh bản và vị chủ lễ ở chùa. Cách dùng từ của thầy bạn có thể khác.',g.BODY),
    ('Bản dịch được thực hiện với sự hỗ trợ của AI và có kiểm tra biên tập. Bản này chưa được một vị giáo thọ Phật giáo thông thạo tiếng Việt duyệt lại. Chúng tôi trân trọng những góp ý từ chư vị giáo thọ và người đọc thông thạo tiếng Việt.',g.BODY),
    ('Kinh bản làm tài liệu gốc',g.H2),
    ('Phật Quang Sơn Tây Lai Tự, ấn bản điện tử 3.0, tháng 4 năm 2022. Andrew Nguy và Raymond Kong phụ trách dịch tiếng Anh, biên tập và thiết kế. Các số trang PDF nguồn vẫn dẫn tới những tập gốc ấy, không phải các trang trong sách đồng hành này.',g.BODY),
    ('Daniel Franjkovic biên soạn. Sách hướng dẫn học tập độc lập này không thay thế kinh điển gốc, các vị thầy đang giảng dạy hay sự hướng dẫn ở chùa. Bản quyền nghi lễ gốc thuộc Phật Quang Sơn Tây Lai Tự; nguồn và giấy phép hình ảnh được giữ bên cạnh mỗi hình.',g.BODY),
    ('Hãy bắt đầu với phần “Bắt đầu tu học Phật pháp”, rồi dùng phần hướng dẫn từng quyển, các hồ sơ chư Phật và Bồ-tát, cùng từ điển khi cần. Trên trang tiếng Việt, các gợi âm theo tiếng Anh vẫn được ghi rõ là cách đọc gần đúng bằng tiếng Anh.',g.BODY)]
    return Pair([Paragraph(g.escaped(t),s) for t,s in en],[Paragraph(g.escaped(t),s) for t,s in vi],'edition-note')

def build(partial=False):
    g.register_fonts(Path('C:/Windows/Fonts'))
    measure=Canvas(BytesIO())
    sections=next(e for e in g.EDITIONS if e.master).sections
    content=[];coverage=[]
    for index,((filename,title,subtitle),(vtitle,vsubtitle)) in enumerate(zip(sections,TITLES)):
        if not (VI/filename).exists():
            if partial: continue
            raise FileNotFoundError(VI/filename)
        divider=Pair([Divider(title,subtitle,'en')],[Divider(vtitle,vsubtitle,'vi')],f'part-{index}',(title,vtitle,0))
        content.append({'items':[divider],'section':(title,vtitle),'divider':True})
        try:
            pairs=paired_flows(filename)
        except ValueError:
            if partial:
                content.pop()
                continue
            raise
        pages=paginate(pairs,measure)
        for page in pages: content.append({'items':page,'section':(title,vtitle),'divider':False})
        coverage.append({'file':filename,'blocks':len(pairs),'page_pairs':len(pages),'en_sha256':hashlib.sha256((ROOT/filename).read_bytes()).hexdigest(),'vi_sha256':hashlib.sha256((VI/filename).read_bytes()).hexdigest()})
    dedication=Pair([Paragraph('May the benefit of this work support understanding, compassionate reform and the awakening of all beings.',g.LEAD)],[Paragraph('Nguyện lợi ích của công việc này nâng đỡ sự hiểu biết, sự sửa đổi đầy lòng từ bi và sự giác ngộ của tất cả chúng sanh.',g.LEAD)],'dedication')
    if content:
        last=content[-1]
        if all(height([f for item in last['items'] for f in getattr(item,lang)]+getattr(dedication,lang),measure)<=FRAME_H for lang in ('en','vi')):
            last['items'].append(dedication)
        else:
            content.append({'items':[dedication],'section':('Dedication','Hồi hướng'),'divider':False})
    # Contents pages use one row per heading and shared physical page numbers.
    entries=[]
    for offset,page in enumerate(content):
        for item in page['items']:
            if item.heading: entries.append((item.heading,item.key,offset))
    toc_pairs=[]
    # Fixed rows make page count independent of the eventual page-number digits.
    for i,(heading,key,offset) in enumerate(entries):
        style=g.TOC0 if heading[2]==0 else g.TOC1
        fs=[]
        for lang in range(2):
            fs.append(Paragraph(f'<link href="#{key}-{lang}">{g.escaped(heading[lang])}</link>',style))
        toc_pairs.append(Pair([fs[0]],[fs[1]],f'toc-{i}'))
    toc_pages=paginate(toc_pairs,measure)
    front_pairs=2+len(toc_pages)  # cover and edition note, then contents
    # Add physical page numbers with enough reserved width and repaginate.
    for i,((heading,key,offset),pair) in enumerate(zip(entries,toc_pairs)):
        style=g.TOC0 if heading[2]==0 else g.TOC1
        for lang,name in enumerate(('en','vi')):
            pg=(front_pairs+offset)*2+1+lang
            setattr(pair,name,[Paragraph(f'<link href="#{key}-{lang}">{g.escaped(heading[lang])} <font color="#b97839"> · {pg}</font></link>',style)])
    new_toc=paginate(toc_pairs,measure)
    if len(new_toc)!=len(toc_pages): raise ValueError('TOC page count changed after numbering')
    toc_pages=new_toc
    target=TARGET if not partial else g.TMP/'bilingual-preview.pdf'
    target.parent.mkdir(parents=True,exist_ok=True)
    c=Canvas(str(target),pagesize=g.A4,pageCompression=1)
    c.setTitle('The Samādhi Water Repentance Companion: English-Vietnamese Edition');c.setAuthor('Daniel Franjkovic')
    manifest=[]
    for lang in ('en','vi'):cover(c,lang);c.showPage()
    for langnum,lang in enumerate(('en','vi')):
        furniture(c,3+langnum,'About this edition' if lang=='en' else 'Về ấn bản này',lang,2)
        draw_flows(c,getattr(title_pair(),lang));c.showPage()
    for i,items in enumerate(toc_pages):
        for langnum,lang in enumerate(('en','vi')):
            page=c.getPageNumber();furniture(c,page,'Contents' if lang=='en' else 'Mục lục',lang,(page+1)//2)
            draw_flows(c,[f for p in items for f in getattr(p,lang)]);c.showPage()
    for offset,page_data in enumerate(content):
        pair_no=front_pairs+offset+1
        for langnum,lang in enumerate(('en','vi')):
            page=c.getPageNumber();furniture(c,page,page_data['section'][langnum],lang,pair_no)
            for item in page_data['items']:
                if item.heading:
                    key=f'{item.key}-{langnum}';c.bookmarkPage(key)
                    # Flat bilingual outline remains predictable across both pages.
                    c.addOutlineEntry(item.heading[langnum]+(' [EN]' if langnum==0 else ' [VI]'),key,level=0,closed=False)
            draw_flows(c,[f for item in page_data['items'] for f in getattr(item,lang)])
            manifest.append({'page':page,'language':lang,'pair':pair_no,'section':page_data['section'][langnum],'units':[x.key for x in page_data['items']]})
            c.showPage()
    c.save()
    report={'file':target.name,'pages':len(PdfReader(target).pages),'pairs':len(PdfReader(target).pages)//2,'complete':not partial,'sources':coverage,'page_map':manifest}
    target.with_suffix('.manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('sources','page_map')},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');args=parser.parse_args();build(args.partial)
