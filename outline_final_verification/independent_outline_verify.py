#!/usr/bin/env python3
"""Read-only independent DOCX structural preservation and PDF review preparation."""
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from collections import Counter
import hashlib, json, re
import fitz

WORK=Path('/workspace/directory_revision_work')
SRC=Path('/workspace/output_final/小论文_中文终稿候选_最终图表精修版.docx')
DST=Path('/workspace/output_outline_final/小论文_中文终稿候选_目录优化版.docx')
BASEPDF=Path('/workspace/revision17_work/render_final/小论文_中文终稿候选_最终图表精修版.pdf')
PDF=WORK/'render_final/小论文_中文终稿候选_目录优化版.pdf'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
W='{'+NS['w']+'}'
EXPECTED=[
'2.1 检测数据与预测样本','2.2 全桥评分预测与时间外验证','2.3 规划初始状态构建','2.4 养护规划模型','2.5 情景设置与优化求解',
'3.1 检测覆盖与评分预测结果','3.2 规划初始状态与养护时机','3.3 资源水平与长期养护结果','3.4 年评分下降量敏感性分析',
'4.1 低频检测与状态估计','4.2 规划初始状态与排程差异','4.3 资源约束与情景参数','4.4 研究局限性与实际应用']
REMOVED=['2.6 养护时机求解与方案比较','3.4 代表性养护排程']

def sha(b):return hashlib.sha256(b).hexdigest()
def txt(x):return ''.join(x.xpath('.//w:t/text()',namespaces=NS))
def sty(x):
    s=x.find('w:pPr/w:pStyle',NS)
    return s.get(W+'val') if s is not None else None

def canonical(x):return E.tostring(x,method='c14n',with_comments=True)
def without_text(x):
    x=E.fromstring(E.tostring(x))
    for el in x.xpath('.//w:t',namespaces=NS):el.text=None
    return canonical(x)

def load(p):
    with ZipFile(p) as z:parts={n:z.read(n) for n in z.namelist()}
    root=E.fromstring(parts['word/document.xml'])
    body=root.find('w:body',NS)
    ps=body.findall('w:p',NS)
    return dict(parts=parts,root=root,body=body,ps=ps,h2=[x for x in ps if sty(x)=='21'])

s=load(SRC)
baseline={
'source':str(SRC),'source_sha256':sha(SRC.read_bytes()),'zip_parts':len(s['parts']),
'paragraph_count':len(s['ps']),'heading2':[txt(x) for x in s['h2']],
'physical_table_count':len(s['body'].findall('w:tbl',NS)),
'figure_captions':[txt(x) for x in s['ps'] if re.match(r'^图[1-7]\s',txt(x))],
'table_captions':[txt(x) for x in s['ps'] if re.match(r'^表[1-6]\s',txt(x))],
'media_sha256':{n:sha(b) for n,b in s['parts'].items() if n.startswith('word/media/')},
'math_count':len(s['root'].xpath('.//m:oMath',namespaces=NS)),
'baseline_pdf_pages':len(fitz.open(BASEPDF)) if BASEPDF.exists() else None,
'expected_heading2':EXPECTED,'removed_heading2':REMOVED
}
baseline_path=WORK/'independent_outline_baseline.json'
if baseline_path.exists():
    recorded_baseline=json.loads(baseline_path.read_text())
else:
    baseline_path.write_text(json.dumps(baseline,ensure_ascii=False,indent=2))
    recorded_baseline=baseline
if not DST.exists():
    print(json.dumps({'status':'baseline recorded; final DOCX not yet present','baseline':str(WORK/'independent_outline_baseline.json')},ensure_ascii=False))
    raise SystemExit(0)

d=load(DST); checks={}
checks['same_part_names']=set(s['parts'])==set(d['parts'])
changed=[n for n in s['parts'] if n not in d['parts'] or s['parts'][n]!=d['parts'][n]]
checks['only_document_xml_changed']=changed==['word/document.xml']
checks['all_25_other_parts_byte_identical']=sum(n!='word/document.xml' and s['parts'][n]==d['parts'].get(n) for n in s['parts'])==25
checks['source_sha_still_same']=sha(SRC.read_bytes())==recorded_baseline['source_sha256']
checks['paragraph_count_141_to_139']=len(s['ps'])==141 and len(d['ps'])==139
checks['13_fixed_heading2_exact']=[txt(x) for x in d['h2']]==EXPECTED
checks['heading2_counts_5_4_4']=[sum(txt(x).startswith(str(c)+'.') for x in d['h2']) for c in (2,3,4)]==[5,4,4]
checks['all_non_heading2_body_nodes_exact_same_order']=[canonical(x) for x in s['body'] if not (x.tag==W+'p' and sty(x)=='21')]==[canonical(x) for x in d['body'] if not(x.tag==W+'p' and sty(x)=='21')]
kept=[x for x in s['h2'] if txt(x) not in REMOVED]
checks['retained_heading2_all_formatting_and_xml_structure_preserved']=[without_text(x) for x in kept]==[without_text(x) for x in d['h2']]
checks['all_7_images_exact']=len(baseline['media_sha256'])==7 and all(d['parts'].get(n)==s['parts'][n] for n in baseline['media_sha256'])
checks['all_8_physical_tables_exact']=[canonical(x) for x in s['body'].findall('w:tbl',NS)]==[canonical(x) for x in d['body'].findall('w:tbl',NS)] and len(d['body'].findall('w:tbl',NS))==8
checks['all_6_logical_table_captions_exact']=baseline['table_captions']==[txt(x) for x in d['ps'] if re.match(r'^表[1-6]\s',txt(x))] and len(baseline['table_captions'])==6
checks['all_7_figure_captions_exact']=baseline['figure_captions']==[txt(x) for x in d['ps'] if re.match(r'^图[1-7]\s',txt(x))] and len(baseline['figure_captions'])==7
checks['all_math_objects_exact']=[canonical(x) for x in s['root'].xpath('.//m:oMath',namespaces=NS)]==[canonical(x) for x in d['root'].xpath('.//m:oMath',namespaces=NS)]
checks['same_first_level_heading_texts_and_styles']=[canonical(x) for x in s['ps'] if sty(x)=='1']==[canonical(x) for x in d['ps'] if sty(x)=='1']
nonheading_s=[txt(x) for x in s['ps'] if sty(x)!='21']
nonheading_d=[txt(x) for x in d['ps'] if sty(x)!='21']
checks['all_non_heading2_paragraph_texts_exact_same_order']=nonheading_s==nonheading_d
checks['no_inserted_or_omitted_nonheading_paragraphs']=Counter(nonheading_s)==Counter(nonheading_d)
oldrefs=[t for t in nonheading_d if re.search(r'(?:第\s*)?(?:2\.6|3\.5)\s*(?:小?节)',t)]
checks['no_explicit_obsolete_2_6_or_3_5_section_references']=not oldrefs
# Content of the two merged groups must be exactly the source, including tables/captions/images.
def interval(doc,start,end):
    body=list(doc['body']); a=next(i for i,x in enumerate(body) if x.tag==W+'p' and txt(x)==start); b=next(i for i,x in enumerate(body) if x.tag==W+'p' and txt(x)==end)
    return [canonical(x) for x in body[a+1:b] if not(x.tag==W+'p' and sty(x)=='21')]
checks['merged_method_2_5_and_2_6_all_content_same_order']=interval(s,'2.5 共同资源水平与下降量情景','3 结果')==interval(d,'2.5 情景设置与优化求解','3 结果')
checks['merged_results_3_3_and_3_4_all_content_same_order']=interval(s,'3.3 资源水平与长期状态','3.5 年评分下降量敏感性')==interval(d,'3.3 资源水平与长期养护结果','3.4 年评分下降量敏感性分析')
audit={'source':str(SRC),'output':str(DST),'source_sha256':sha(SRC.read_bytes()),'output_sha256':sha(DST.read_bytes()),'changed_parts':changed,'checks':checks,'all_structural_checks_passed':all(checks.values()),'old_section_references_flagged':oldrefs,'baseline':baseline,'final_heading2':[txt(x) for x in d['h2']]}
if PDF.exists():
    pdf=fitz.open(PDF); pd=[]; review=WORK/'independent_visual';review.mkdir(exist_ok=True)
    for i,p in enumerate(pdf):
        imgs=p.get_image_info(); words=p.get_text('words');
        pd.append({'page':i+1,'word_count':len(words),'images':len(imgs),'media_boxes':[list(x['bbox']) for x in imgs],'has_text_or_image':bool(words or imgs),'page_size':[p.rect.width,p.rect.height]})
        p.get_pixmap(matrix=fitz.Matrix(1.25,1.25),alpha=False).save(str(review/f'page_{i+1:02d}.png'))
    # Contacts provide an index; every page is separately available for actual visual review.
    from PIL import Image,ImageOps,ImageDraw
    thumbs=[]
    for i in range(len(pdf)):
        im=Image.open(review/f'page_{i+1:02d}.png').convert('RGB');im.thumbnail((280,400)); tile=Image.new('RGB',(300,430),'#e9e9e9');tile.paste(im,((300-im.width)//2,20));ImageDraw.Draw(tile).text((10,410),f'Page {i+1}',fill='black');thumbs.append(tile)
    for a in range(0,len(thumbs),6):
        group=thumbs[a:a+6];sheet=Image.new('RGB',(900,860),'white')
        for k,im in enumerate(group):sheet.paste(im,((k%3)*300,(k//3)*430))
        sheet.save(review/f'contact_{a+1:02d}_{a+len(group):02d}.png')
    audit['pdf']={'path':str(PDF),'pages':len(pdf),'per_page':pd,'all_pages_have_text_or_images':all(x['has_text_or_image'] for x in pd),'visual_review_status':'rendered_for_independent_manual_review','visual_directory':str(review)}
(WORK/'independent_outline_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
print(json.dumps({'all_structural_checks_passed':audit['all_structural_checks_passed'],'failed':[k for k,v in checks.items() if not v],'pdf_pages':audit.get('pdf',{}).get('pages'),'audit':str(WORK/'independent_outline_audit.json')},ensure_ascii=False))
if not all(checks.values()):raise SystemExit(2)
