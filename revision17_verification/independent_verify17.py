"""Independent read-only final QA for instruction 17.

Only seven figure PNG parts and three pre-agreed figure-note paragraphs may change.
This script never writes a manuscript or modifies a scientific data file.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, re, zipfile
from io import BytesIO
from pathlib import Path
from lxml import etree as ET
from PIL import Image, ImageDraw
import fitz

ROOT = Path(__file__).resolve().parent
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
NOTES = [65, 72, 83]
MEDIA = [f'word/media/image{i}.png' for i in range(1, 8)]
def sha(data): return hashlib.sha256(data).hexdigest()
def c14n(node): return ET.tostring(node, method='c14n') if node is not None else None
def text(node): return ''.join(node.xpath('.//w:t/text()', namespaces=NS))
def normalized(s): return re.sub(r'\s+', '', s)
def without_notes(tree):
    tree = copy.deepcopy(tree)
    pars = tree.xpath('//w:body/w:p', namespaces=NS)
    for i in reversed(NOTES): pars[i].getparent().remove(pars[i])
    return c14n(tree)
def draw_contact(images, output, columns=4):
    width = max(im.width for im in images); height = max(im.height for im in images)
    sheet = Image.new('RGB', (width * columns, height * ((len(images) + columns - 1) // columns)), '#c8c8c8')
    for j, im in enumerate(images): sheet.paste(im, ((j % columns) * width, (j // columns) * height))
    sheet.save(output, quality=94)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('docx', type=Path)
    ap.add_argument('pdf', type=Path)
    ap.add_argument('--allowed-texts', type=Path, required=True, help='JSON object keyed by 65,72,83 with exact expected new text')
    args = ap.parse_args()
    base = json.loads((ROOT/'independent_baseline17.json').read_text())
    allowed = json.loads(args.allowed_texts.read_text())
    report = {'source_docx': base['source_docx'], 'final_docx': str(args.docx), 'final_pdf': str(args.pdf),
              'allowed_figure_note_paragraph_indices': NOTES, 'checks': {}, 'images': [], 'figure_notes': [], 'pdf_pages': []}
    checks = report['checks']
    source = Path(base['source_docx'])
    checks['source_manuscript_unchanged'] = sha(source.read_bytes()) == base['source_docx_sha256']
    checks['source_pdf_unchanged'] = sha(Path(base['source_pdf']).read_bytes()) == base['source_pdf_sha256']
    with zipfile.ZipFile(source) as z0, zipfile.ZipFile(args.docx) as z1:
        checks['package_member_set_identical'] = set(z0.namelist()) == set(z1.namelist())
        changed = sorted(n for n in z0.namelist() if z0.read(n) != z1.read(n))
        report['changed_package_parts'] = changed
        checks['only_seven_pngs_and_document_xml_changed'] = set(changed) == set(MEDIA + ['word/document.xml'])
        frozen = [n for n in z0.namelist() if n not in MEDIA + ['word/document.xml']]
        report['frozen_other_package_part_count'] = len(frozen)
        checks['all_other_package_parts_byte_identical'] = all(z0.read(n) == z1.read(n) for n in frozen)
        d0 = ET.fromstring(z0.read('word/document.xml')); d1 = ET.fromstring(z1.read('word/document.xml'))
        p0 = d0.xpath('//w:body/w:p', namespaces=NS); p1 = d1.xpath('//w:body/w:p', namespaces=NS)
        checks['top_level_paragraph_count_identical'] = len(p0) == len(p1) == base['paragraph_count']
        checks['all_xml_outside_three_figure_notes_identical'] = without_notes(d0) == without_notes(d1)
        checks['all_other_paragraphs_text_and_format_xml_identical'] = all(c14n(a) == c14n(b) for i,(a,b) in enumerate(zip(p0,p1)) if i not in NOTES)
        checks['all_figure_note_paragraph_properties_identical'] = all(c14n(p0[i].find('w:pPr',NS)) == c14n(p1[i].find('w:pPr',NS)) for i in NOTES)
        for i in NOTES:
            report['figure_notes'].append({'paragraph_index': i, 'before': text(p0[i]), 'after': text(p1[i]),
                                          'exact_expected_new_text': text(p1[i]) == allowed[str(i)]})
        checks['three_note_changes_match_exact_reviewed_whitelist'] = all(r['exact_expected_new_text'] for r in report['figure_notes'])
        checks['all_physical_tables_identical'] = [c14n(n) for n in d0.xpath('//w:tbl',namespaces=NS)] == [c14n(n) for n in d1.xpath('//w:tbl',namespaces=NS)]
        checks['all_manual_breaks_and_section_properties_identical'] = [c14n(n) for n in d0.xpath('//w:br|//w:sectPr',namespaces=NS)] == [c14n(n) for n in d1.xpath('//w:br|//w:sectPr',namespaces=NS)]
        drawings = d0.xpath('//wp:extent', namespaces=NS)
        checks['image_display_frames_identical'] = [c14n(n) for n in drawings] == [c14n(n) for n in d1.xpath('//wp:extent', namespaces=NS)]
        for i,name in enumerate(MEDIA):
            raw=z1.read(name); im=Image.open(BytesIO(raw)); w,h=im.size
            ew,eh=int(drawings[i].get('cx')),int(drawings[i].get('cy'))
            expected=Path('/workspace/output_figures_final')/f'Figure_{i+1:02d}_final.png'
            rgb=im.convert('RGB')
            report['images'].append({'number':i+1,'media':name,'pixel_size':[w,h],'png_dpi_metadata':im.info.get('dpi'),
                'effective_dpi_at_word_size':[w/(ew/914400),h/(eh/914400)],
                'aspect_ratio_relative_error':abs((w/h)/(ew/eh)-1),
                'matches_exported_final_png':expected.exists() and expected.read_bytes()==raw,
                'four_corners_white':all(rgb.getpixel(p)==(255,255,255) for p in [(0,0),(w-1,0),(0,h-1),(w-1,h-1)]),
                'different_from_previous_figure':raw!=z0.read(name)})
        checks['all_seven_pngs_match_final_exports'] = all(r['matches_exported_final_png'] for r in report['images'])
        checks['all_seven_pngs_visually_changed'] = all(r['different_from_previous_figure'] for r in report['images'])
        checks['all_seven_figures_at_least_599dpi'] = all(min(r['effective_dpi_at_word_size'])>599 for r in report['images'])
        checks['all_seven_figures_display_without_ratio_deformation'] = all(r['aspect_ratio_relative_error']<0.001 for r in report['images'])
        checks['all_seven_background_corners_pure_white'] = all(r['four_corners_white'] for r in report['images'])
    before=fitz.open(base['source_pdf']); after=fitz.open(args.pdf)
    report['actual_pdf_page_count']=len(after)
    report['baseline_pdf_page_count']=len(before)
    report['page_count_unchanged']=len(before)==len(after)
    thumbs=[]; figure_context=[]; figure_rows=[]
    for pi,page in enumerate(after):
        blocks=page.get_text('dict')['blocks']; imgs=[b for b in blocks if b['type']==1]
        page_text=page.get_text(sort=True)
        caps=[(int(m.group(1)),m.group(0)) for m in re.finditer(r'图([1-7])\s+[^\n]+', page_text)]
        # Figure captions start at line boundaries and title text, excluding body citations.
        caps=[(num,cap) for num,cap in caps if re.search(r'^图'+str(num)+r'\s',cap)]
        row={'page':pi+1,'figure_image_count':len(imgs),'caption_numbers':[n for n,_ in caps],
             'page_media_box':list(page.rect),'all_image_bboxes_inside_page':all(fitz.Rect(b['bbox']) in page.rect for b in imgs)}
        report['pdf_pages'].append(row)
        pix=page.get_pixmap(matrix=fitz.Matrix(.55,.55));im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
        canvas=Image.new('RGB',(im.width,im.height+24),'#e8e8e8');canvas.paste(im,(0,24));ImageDraw.Draw(canvas).text((8,6),f'Page {pi+1}',fill='black');thumbs.append(canvas)
        for num,cap in caps:
            found=page.search_for(cap)
            caprect=found[0] if found else None
            samepage=len(imgs)==1 and (caprect is None or imgs[0]['bbox'][3] <= caprect.y1+1)
            figure_rows.append({'figure':num,'page':pi+1,'caption':cap,'same_page_as_image':samepage,
                                'image_bbox':list(imgs[0]['bbox']) if imgs else None,'caption_bbox':list(caprect) if caprect else None})
            pix=page.get_pixmap(matrix=fitz.Matrix(1.4,1.4));im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
            dest=ROOT/f'independent_final17_figure{num}_in_context.png';im.save(dest);figure_context.append(str(dest))
    report['figure_caption_pages']=figure_rows
    checks['seven_figures_and_captions_on_same_pages'] = len(figure_rows)==7 and sorted(r['figure'] for r in figure_rows)==list(range(1,8)) and all(r['same_page_as_image'] for r in figure_rows)
    checks['all_rendered_images_inside_page'] = all(r['all_image_bboxes_inside_page'] for r in report['pdf_pages'])
    old_full=normalized(''.join(p.get_text(sort=True) for p in before)); new_full=normalized(''.join(p.get_text(sort=True) for p in after))
    for note in report['figure_notes']:
        old_full=old_full.replace(normalized(note['before']),'',1)
        new_full=new_full.replace(normalized(note['after']),'',1)
    checks['all_rendered_non_note_text_identical'] = old_full==new_full
    report['rendered_non_note_text_lengths']=[len(old_full),len(new_full)]
    checks['all_three_edited_caption_notes_complete_on_their_figure_pages'] = all(
        normalized(row['after']) in normalized(after[page-1].get_text(sort=True))
        for row,page in zip(report['figure_notes'],[8,9,11]))
    manifest=json.loads((ROOT/'input17_manifest.json').read_text())
    expected_csvs={p:v for p,v in manifest['input_scripts'].items() if p.startswith('project_data/')}
    checks['all_22_bundled_scientific_csv_files_identical_to_frozen_input'] = len(expected_csvs)==22 and all(
        sha((Path('/workspace/output_scripts_final')/p).read_bytes())==v for p,v in expected_csvs.items())
    report['independent_scientific_source_file_count']=len(expected_csvs)
    numeric_paths=[ROOT/n for n in ['f123_final_audit.json','f45_final_audit.json','f67_final_audit.json']]
    numeric=[json.loads(p.read_text()) for p in numeric_paths]
    checks['seven_figure_numeric_data_audits_passed'] = (numeric[0]['all_input_arrays_match_original'] and
        numeric[0]['all_scientific_arrays_identical_to_round16'] and numeric[1]['all_passed'] and
        numeric[2]['all_passed'] and numeric[2]['source_csv_unchanged'])
    report['numeric_data_audit_paths']=[str(p) for p in numeric_paths]
    checks['all_21_required_figure_exports_present'] = all(
        (Path('/workspace/output_figures_final')/f'Figure_{n:02d}_final.{ext}').is_file()
        for n in range(1,8) for ext in ['png','svg','pdf'])
    draw_contact(thumbs,ROOT/'independent_final17_all_pages.jpg')
    report['review_artifacts']={'all_page_contact_sheet':str(ROOT/'independent_final17_all_pages.jpg'),'figure_context_pngs':figure_context}
    report['visual_inspection_completed']=False
    report['all_automated_checks_passed']=all(checks.values())
    (ROOT/'independent_final17_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'all_automated_checks_passed':report['all_automated_checks_passed'],'checks':checks,'actual_pdf_pages':len(after),'figure_caption_pages':[(r['figure'],r['page']) for r in figure_rows]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
