#!/usr/bin/env python3
"""Read-only independent DOCX package and PDF layout audit for figure redesign.

Use --prepare to freeze the uploaded source baseline. Final audit additionally
requires an explicit JSON whitelist of necessary caption paragraph edits; no
other document changes are permitted. This script never edits either Word.
"""
import argparse, hashlib, json, re
from collections import Counter
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from PIL import Image, ImageDraw
import fitz

BASE=Path(__file__).resolve().parent
SOURCE=Path('/workspace/attachments/de14efc9-2a87-42c9-85c7-d55cf3324699/小论文_中文终稿候选_目录优化版.docx')
EXPECTED_SOURCE_SHA='b0ca9b0ab9f1bbc9d37665ef696f66662bbf43cab0e60ecae05ed7cd00465c5f'
TARGET=BASE.parent/'小论文_中文终稿候选_图表重构版.docx'
BASEPDF=BASE/'render_before/小论文_中文终稿候选_目录优化版.pdf'
FINALPDF=BASE/'render_final/小论文_中文终稿候选_图表重构版.pdf'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
W='{'+NS['w']+'}'

def sha(data): return hashlib.sha256(data).hexdigest()
def canonical(node): return E.tostring(node,method='c14n',with_comments=True)
def text(node): return ''.join(node.xpath('.//w:t/text()',namespaces=NS))
def norm(s): return re.sub(r'\s+','',s.replace('\u00ad',''))
def textless(node):
    node=E.fromstring(E.tostring(node))
    for t in node.xpath('.//w:t',namespaces=NS): t.text=None
    return canonical(node)
def load(path):
    with ZipFile(path) as z: parts={n:z.read(n) for n in z.namelist()}
    root=E.fromstring(parts['word/document.xml']); body=root.find('w:body',NS)
    rels=E.fromstring(parts['word/_rels/document.xml.rels'])
    rmap={x.get('Id'):x.get('Target') for x in rels}
    drawings=[]
    for i,node in enumerate(body):
        for inline in node.xpath('.//wp:inline',namespaces=NS):
            ext=inline.find('wp:extent',NS); rid=inline.xpath('.//a:blip/@r:embed',namespaces=NS)[0]
            media='word/'+rmap[rid].lstrip('/')
            cap=text(body[i+1]) if i+1<len(body) else ''
            note=text(body[i+2]) if i+2<len(body) else ''
            drawings.append({'body_index':i,'rid':rid,'media':media,'width_emu':int(ext.get('cx')),'height_emu':int(ext.get('cy')),'caption':cap,'note':note})
    return {'parts':parts,'root':root,'body':body,'drawings':drawings}
def pdf_data(path):
    pdf=fitz.open(path); rows=[]
    for p in pdf:
        rows.append({'page':p.number+1,'size':[p.rect.width,p.rect.height], 'text':p.get_text(sort=True),
         'text_blocks':[{'bbox':list(b['bbox']),'text':'\n'.join(''.join(s['text'] for s in l['spans']) for l in b.get('lines',[]))} for b in p.get_text('dict')['blocks'] if b['type']==0],
         'images':[{'bbox':list(b['bbox']),'width':b['width'],'height':b['height']} for b in p.get_text('dict')['blocks'] if b['type']==1]})
    return rows

def prepare():
    s=load(SOURCE)
    assert sha(SOURCE.read_bytes())==EXPECTED_SOURCE_SHA,'Uploaded source SHA mismatch'
    baseline={'source':str(SOURCE),'source_sha256':sha(SOURCE.read_bytes()),'source_pdf':str(BASEPDF),
      'parts':{k:sha(v) for k,v in s['parts'].items()},'body_count':len(s['body']),
      'body':[{'index':i,'tag':E.QName(n).localname,'text':text(n),'canonical_sha256':sha(canonical(n))} for i,n in enumerate(s['body'])],
      'drawings':s['drawings'],'pdf':pdf_data(BASEPDF) if BASEPDF.exists() else None}
    path=BASE/'independent_document_baseline.json'
    if path.exists():
        old=json.loads(path.read_text())
        assert old['source_sha256']==baseline['source_sha256']
        assert old['parts']==baseline['parts']
        if old.get('pdf') is None and baseline['pdf'] is not None:path.write_text(json.dumps(baseline,ensure_ascii=False,indent=2))
    else:path.write_text(json.dumps(baseline,ensure_ascii=False,indent=2))
    return baseline

def audit(whitelist):
    baseline=prepare(); s=load(SOURCE); d=load(TARGET)
    changes=json.loads(whitelist.read_text()) if whitelist else []
    if isinstance(changes,dict): changes=changes.get('changes',changes.get('paragraph_changes',[]))
    for x in changes:
        candidates=[i for i,n in enumerate(s['body']) if text(n)==x['before']]
        assert len(candidates)==1, 'Whitelist before text must identify one existing paragraph'
        x['declared_paragraph_index']=x['body_index']
        x['body_index']=candidates[0]
    allow={x['body_index']:x for x in changes}
    checks={}; report={'source':str(SOURCE),'target':str(TARGET),'checks':checks,'allowed_caption_changes':changes,'image_exports':[]}
    checks['source_sha256_unchanged']=sha(SOURCE.read_bytes())==EXPECTED_SOURCE_SHA
    checks['docx_member_set_identical']=set(s['parts'])==set(d['parts'])
    changed=[k for k in s['parts'] if s['parts'][k]!=d['parts'].get(k)]
    report['changed_parts']=changed
    expected_media={f'word/media/image{i}.png' for i in range(1,8)}
    checks['only_document_and_seven_media_changed']=set(changed)==expected_media|({'word/document.xml'} if changes else set())
    checks['all_other_18_parts_byte_identical']=all(s['parts'][k]==d['parts'].get(k) for k in s['parts'] if k not in expected_media|{'word/document.xml'})
    checks['body_node_count_identical']=len(s['body'])==len(d['body'])
    node_changes=[]
    for i,(a,b) in enumerate(zip(s['body'],d['body'])):
        if canonical(a)!=canonical(b): node_changes.append({'body_index':i,'before':text(a),'after':text(b)})
    report['actual_body_changes']=node_changes
    checks['only_explicit_caption_nodes_changed']={x['body_index'] for x in node_changes}==set(allow)
    checks['explicit_caption_before_after_exact']=all(text(s['body'][i])==x['before'] and text(d['body'][i])==x['after'] for i,x in allow.items())
    checks['whitelisted_nodes_all_are_existing_figure_caption_or_note']=all(i in {draw['body_index']+off for draw in s['drawings'] for off in (1,2)} for i in allow)
    def caption_format_preserved(a,b):
        ap=a.find('w:pPr',NS);bp=b.find('w:pPr',NS)
        if (canonical(ap) if ap is not None else None)!=(canonical(bp) if bp is not None else None):return False
        def rpr(r,documented_CJK_fallback_fix=False):
            p=r.find('w:rPr',NS)
            if p is None:return b''
            p=E.fromstring(E.tostring(p))
            fonts=p.find('w:rFonts',NS)
            if documented_CJK_fallback_fix and fonts is not None and fonts.get(W+'eastAsia') == 'Noto Sans CJK SC':
                del fonts.attrib[W+'eastAsia']
                if not fonts.attrib and len(fonts)==0:p.remove(fonts)
            return canonical(p)
        old=[rpr(r) for r in a.findall('w:r',NS)];new=[rpr(r,True) for r in b.findall('w:r',NS)]
        # Caption wording additions can add runs using an already-present style.
        def collapsed(seq):
            return [v for i,v in enumerate(seq) if i==0 or v!=seq[i-1]]
        return collapsed(old)==collapsed(new) and set(new)<=set(old)
    checks['caption_pPr_and_other_ordered_run_style_groups_preserved_allow_documented_CJK_font_fix']=all(caption_format_preserved(s['body'][i],d['body'][i]) for i in allow)
    report['documented_caption_CJK_font_fallback_fix']=[{'body_index':i,'explicit_eastAsia_fonts':sorted(set(d['body'][i].xpath('.//w:rFonts/@w:eastAsia',namespaces=NS)))} for i in allow]
    report['caption_formatting_scope']='Only necessary caption text/run splitting and explicit Noto CJK eastAsia fallback are allowed; all paragraph properties and other ordered run style groups remain source-identical.'
    checks['all_nonwhitelisted_nodes_c14n_exact']=all(canonical(a)==canonical(b) for i,(a,b) in enumerate(zip(s['body'],d['body'])) if i not in allow)
    checks['all_tables_exact']=[canonical(x) for x in s['body'].findall('w:tbl',NS)]==[canonical(x) for x in d['body'].findall('w:tbl',NS)]
    checks['all_math_exact']=[canonical(x) for x in s['root'].xpath('.//m:oMath',namespaces=NS)]==[canonical(x) for x in d['root'].xpath('.//m:oMath',namespaces=NS)]
    checks['manual_page_breaks_and_section_properties_exact']=[canonical(x) for x in s['root'].xpath(".//w:br[@w:type='page']|.//w:sectPr|.//w:pageBreakBefore",namespaces=NS)]==[canonical(x) for x in d['root'].xpath(".//w:br[@w:type='page']|.//w:sectPr|.//w:pageBreakBefore",namespaces=NS)]
    sf=[{k:v for k,v in x.items() if k not in ('caption','note')} for x in s['drawings']]
    df=[{k:v for k,v in x.items() if k not in ('caption','note')} for x in d['drawings']]
    checks['all_seven_figure_placements_relationships_extents_exact']=sf==df and len(sf)==7
    for n,draw in enumerate(d['drawings'],1):
        im=Image.open(BytesIO(d['parts'][draw['media']]))
        folder=BASE.parent/f'fig{n}'; stem=f'Figure_{n:02d}_redesigned'
        exports={ext:folder/(stem+'.'+ext) for ext in ['png','pdf','tiff','svg']}
        row={'figure':n,'media':draw['media'],'caption':draw['caption'],'png_pixels':list(im.size),'png_dpi_metadata':im.info.get('dpi'),
             'effective_dpi':[im.width/(draw['width_emu']/914400),im.height/(draw['height_emu']/914400)],'files':{k:str(v) for k,v in exports.items()},'export_exists':{k:v.exists() for k,v in exports.items()}}
        row['inserted_aspect_error']=abs((im.width/im.height)/(draw['width_emu']/draw['height_emu'])-1)
        row['embedded_png_matches_export']=exports['png'].exists() and sha(d['parts'][draw['media']])==sha(exports['png'].read_bytes())
        if exports['tiff'].exists():
            ti=Image.open(exports['tiff']);row['tiff_pixels']=list(ti.size);row['tiff_dpi']=[float(x) for x in ti.info.get('dpi',[])];row['tiff_pixel_content_equals_png']=ti.convert('RGB').tobytes()==im.convert('RGB').tobytes()
        if exports['pdf'].exists():
            vp=fitz.open(exports['pdf']);row['pdf_pages']=len(vp);row['pdf_vector_drawing_count']=sum(len(p.get_drawings()) for p in vp);row['pdf_raster_image_count']=sum(len(p.get_images()) for p in vp)
        if exports['svg'].exists():
            sv=exports['svg'].read_text();row['svg_has_paths']='<path' in sv;row['svg_has_embedded_raster']='<image' in sv
        report['image_exports'].append(row)
    checks['all_seven_embedded_pngs_match_final_exports']=all(r['embedded_png_matches_export'] for r in report['image_exports'])
    checks['all_seven_png_tiff_pdf_svg_exist']=all(all(r['export_exists'].values()) for r in report['image_exports'])
    checks['all_pngs_effectively_600dpi_allow_integer_rounding']=all(min(r['effective_dpi'])>=599 and max(r['effective_dpi'])<=601 for r in report['image_exports'])
    checks['all_tiffs_metadata_600dpi']=all(len(r.get('tiff_dpi',[]))==2 and all(abs(x-600)<.05 for x in r['tiff_dpi']) for r in report['image_exports'])
    checks['all_tiffs_same_image_pixels_as_png']=all(r.get('tiff_pixel_content_equals_png',False) for r in report['image_exports'])
    checks['all_image_aspect_errors_below_0_1percent']=all(r['inserted_aspect_error']<.001 for r in report['image_exports'])
    checks['all_pdfs_have_vector_drawings']=all(r.get('pdf_pages')==1 and r.get('pdf_vector_drawing_count',0)>0 for r in report['image_exports'])
    checks['all_svgs_have_vector_paths']=all(r.get('svg_has_paths',False) for r in report['image_exports'])
    report['source_sha256']=sha(SOURCE.read_bytes());report['target_sha256']=sha(TARGET.read_bytes())
    if FINALPDF.exists():
        old=baseline['pdf'];new=pdf_data(FINALPDF);report['pdf_pages']=[]
        checks['pdf_page_count_preserved_15']=len(old)==len(new)==15
        if len(old)==len(new):
            for a,b in zip(old,new):
                before=norm(a['text']);after=norm(b['text'])
                for x in changes:
                    before=before.replace(norm(x['before']),'');after=after.replace(norm(x['after']),'')
                ib=len(a['images'])==len(b['images']) and all(max(abs(x-y) for x,y in zip(ia['bbox'],ib['bbox']))<.02 for ia,ib in zip(a['images'],b['images']))
                outside=[]
                for word in fitz.open(FINALPDF)[b['page']-1].get_text('words'):
                    if word[0]<-0.5 or word[1]<-0.5 or word[2]>b['size'][0]+.5 or word[3]>b['size'][1]+.5:outside.append(word)
                report['pdf_pages'].append({'page':b['page'],'size':b['size'],'text_identical_excluding_allowed_captions':before==after,'image_boxes_identical':ib,'images':b['images'],'page_has_content':bool(norm(b['text']) or b['images']),'out_of_page_words':outside})
        checks['all_page_texts_exact_except_explicit_caption_edits']=len(report['pdf_pages'])==15 and all(r['text_identical_excluding_allowed_captions'] for r in report['pdf_pages'])
        checks['all_pdf_figure_boxes_identical']=len(report['pdf_pages'])==15 and all(r['image_boxes_identical'] for r in report['pdf_pages'])
        checks['no_blank_or_text_outside_pages']=len(report['pdf_pages'])==15 and all(r['page_has_content'] and not r['out_of_page_words'] for r in report['pdf_pages'])
        figpages=[]
        for n,draw in enumerate(d['drawings'],1):
            capnorm=norm(draw['caption']);notenorm=norm(draw['note']);pages=[r for r in new if capnorm in norm(r['text'])]
            row={'figure':n,'caption_pages':[r['page'] for r in pages],'caption_note_together_same_page':len(pages)==1 and notenorm in norm(pages[0]['text']),'image_same_page':len(pages)==1 and len(pages[0]['images'])==1,'expected_page':n+4}
            if len(pages)==1 and pages[0]['images']:
                row['caption_after_image']=any(capnorm[:12] in norm(tb['text']) and tb['bbox'][1]>=pages[0]['images'][0]['bbox'][3]-.5 for tb in pages[0]['text_blocks'])
            figpages.append(row)
        report['figure_caption_pages']=figpages
        checks['all_7_figures_captions_notes_together_correct_pages']=all(x['caption_pages']==[x['expected_page']] and x['caption_note_together_same_page'] and x['image_same_page'] and x.get('caption_after_image',False) for x in figpages)
        pdf=fitz.open(FINALPDF); visual=BASE/'independent_visual';visual.mkdir(exist_ok=True)
        thumbs=[]
        for p in pdf:
            out=visual/f'page_{p.number+1:02d}.png';p.get_pixmap(matrix=fitz.Matrix(1.3,1.3),alpha=False).save(out)
            im=Image.open(out).convert('RGB');im.thumbnail((300,425));tile=Image.new('RGB',(320,455),'#eeeeee');tile.paste(im,((320-im.width)//2,15));ImageDraw.Draw(tile).text((10,438),f'Page {p.number+1}',fill='black');thumbs.append(tile)
        for start in range(0,len(thumbs),5):
            sheet=Image.new('RGB',(320*5,455),'white')
            for i,im in enumerate(thumbs[start:start+5]):sheet.paste(im,(i*320,0))
            sheet.save(visual/f'contact_{start+1:02d}_{min(start+5,len(thumbs)):02d}.png')
        for n,row in enumerate(figpages,1):
            if len(row['caption_pages'])==1:
                page=pdf[row['caption_pages'][0]-1];box=page.get_image_info()[0]['bbox'];rect=fitz.Rect(box);rect.y1=min(page.rect.y1,rect.y1+62)
                page.get_pixmap(matrix=fitz.Matrix(1.7,1.7),clip=rect,alpha=False).save(visual/f'figure_{n:02d}_in_word.png')
        report['manual_visual_review']='prepared_pending_explicit_visual_inspection'
    else:report['pdf_status']='not_yet_available_not_verified'
    report['all_automated_checks_passed']=all(checks.values())
    (BASE/'independent_document_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'passed':report['all_automated_checks_passed'],'failed':[k for k,v in checks.items() if not v],'output':str(BASE/'independent_document_audit.json')},ensure_ascii=False))
    return report['all_automated_checks_passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--whitelist',type=Path);args=p.parse_args()
    if args.prepare:
        b=prepare();print(json.dumps({'status':'baseline prepared','source_sha256':b['source_sha256'],'body_nodes':b['body_count'],'pdf_pages':len(b['pdf']) if b['pdf'] else None},ensure_ascii=False))
    else:raise SystemExit(0 if audit(args.whitelist) else 2)
