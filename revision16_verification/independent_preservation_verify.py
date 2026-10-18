"""Independent read-only audit of manuscript's image-only replacement.
No model evaluations; no source or delivered document mutations.
"""
import argparse,hashlib,json,zipfile,re
from pathlib import Path
from io import BytesIO
from lxml import etree as ET
from PIL import Image,ImageDraw
import fitz

def digest(x):return hashlib.sha256(x).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('docx',type=Path);p.add_argument('pdf',type=Path);args=p.parse_args()
 root=Path(__file__).resolve().parent
 baseline=json.loads((root/'independent_preservation_baseline.json').read_text())
 expected={f'word/media/image{i}.png' for i in range(1,8)}
 report={'baseline_docx':baseline['source_docx'],'output_docx':str(args.docx),'output_pdf':str(args.pdf),'checks':{},'images':[],'pdf_pages':[]}
 checks=report['checks']
 checks['author_input_unchanged']=digest(Path(baseline['source_docx']).read_bytes())==baseline['source_docx_sha256']
 with zipfile.ZipFile(args.docx) as z:
  names=set(z.namelist());checks['docx_member_set_identical']=names==set(baseline['docx_members'])
  changed={name for name in names if name in baseline['docx_members'] and digest(z.read(name))!=baseline['docx_members'][name]}
  report['changed_docx_members']=sorted(changed)
  checks['only_and_all_seven_media_changed']=changed==expected
  checks['all_nonmedia_members_byte_identical']=all(digest(z.read(name))==oldsha for name,oldsha in baseline['docx_members'].items() if name not in expected)
  ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
  doc=ET.fromstring(z.read('word/document.xml'))
  pars=[''.join(node.xpath('.//w:t/text()',namespaces=ns)) for node in doc.xpath('//w:body/w:p',namespaces=ns)]
  checks['all_body_paragraph_text_identical']=pars==[r['text'] for r in baseline['paragraphs']]
  checks['title_abstract_author_format_xml_unchanged']=digest(z.read('word/document.xml'))==baseline['docx_members']['word/document.xml']
  for index,name in enumerate(sorted(expected)):
   img=Image.open(BytesIO(z.read(name)));width,height=img.size
   drawing=baseline['drawings'][index]
   display_ratio=drawing['width_emu']/drawing['height_emu'];pixel_ratio=width/height
   width_inch=drawing['width_emu']/914400;height_inch=drawing['height_emu']/914400
   row={'image':name,'pixel_size':[width,height],'png_dpi_metadata':img.info.get('dpi'),'effective_dpi_at_inserted_size':[width/width_inch,height/height_inch],'aspect_ratio_relative_error':abs(pixel_ratio/display_ratio-1),'white_corner_pixels':all(img.convert('RGB').getpixel(pos)==(255,255,255) for pos in [(0,0),(width-1,0),(0,height-1),(width-1,height-1)])}
   report['images'].append(row)
  checks['no_visual_image_deformation']=all(i['aspect_ratio_relative_error']<0.001 for i in report['images'])
  checks['all_source_png_at_least_300dpi']=all(min(i['effective_dpi_at_inserted_size'])>=300 for i in report['images'])
  checks['all_image_background_corners_white']=all(i['white_corner_pixels'] for i in report['images'])
 pdf=fitz.open(args.pdf)
 checks['pdf_page_count_unchanged']=len(pdf)==baseline['pdf_page_count']
 report['actual_pdf_page_count']=len(pdf)
 thumbs=[]
 for index,page in enumerate(pdf):
  if index>=len(baseline['pdf_pages']):break
  before=baseline['pdf_pages'][index]
  data=page.get_text('dict')['blocks']
  texts=[{'bbox':list(b['bbox']),'text':'\n'.join(''.join(s['text'] for s in line['spans']) for line in b.get('lines',[]))} for b in data if b['type']==0]
  imgs=[{'bbox':list(b['bbox']),'width':b['width'],'height':b['height']} for b in data if b['type']==1]
  beforeimg=before['image_blocks']
  imagepos=len(imgs)==len(beforeimg) and all(max(abs(x-y) for x,y in zip(a['bbox'],b['bbox']))<0.01 for a,b in zip(imgs,beforeimg))
  textpos=len(texts)==len(before['text_blocks']) and all(a['text']==b['text'] and max(abs(x-y) for x,y in zip(a['bbox'],b['bbox']))<0.01 for a,b in zip(texts,before['text_blocks']))
  row={'page':index+1,'body_and_header_footer_text_identical':page.get_text(sort=True)==before['text'],'text_block_positions_identical':textpos,'image_positions_identical':imagepos,'image_blocks':imgs,'captions':[a['text'] for a in texts if re.match(r'^图[1-7]\s',a['text'])]}
  report['pdf_pages'].append(row)
  pix=page.get_pixmap(matrix=fitz.Matrix(.5,.5));im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
  canv=Image.new('RGB',(im.width,im.height+24),'#e8e8e8');canv.paste(im,(0,24));ImageDraw.Draw(canv).text((5,5),str(index+1),fill='black');thumbs.append(canv)
 checks['all_pdf_page_text_identical']=all(p['body_and_header_footer_text_identical'] for p in report['pdf_pages']) and len(report['pdf_pages'])==len(baseline['pdf_pages'])
 checks['all_pdf_text_positions_unchanged']=all(p['text_block_positions_identical'] for p in report['pdf_pages'])
 checks['all_pdf_image_positions_unchanged']=all(p['image_positions_identical'] for p in report['pdf_pages'])
 captions=[(p['page'],c) for p in report['pdf_pages'] for c in p['captions']]
 report['figure_caption_pages']=captions
 checks['seven_figures_with_correct_captions_on_same_pages']=len(captions)==7 and all(page==number+4 and cap.startswith(f'图{number} ') for number,(page,cap) in enumerate(captions,1))
 w=max(i.width for i in thumbs);h=max(i.height for i in thumbs);sheet=Image.new('RGB',(w*4,h*((len(thumbs)+3)//4)),'#ccc')
 for j,im in enumerate(thumbs):sheet.paste(im,((j%4)*w,(j//4)*h))
 sheet.save(root/'independent_after_contact_sheet.jpg',quality=95)
 report['all_automated_checks_passed']=all(checks.values())
 (root/'independent_preservation_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps({'all_automated_checks_passed':report['all_automated_checks_passed'],'checks':checks,'page_count':len(pdf),'image_sizes':[i['pixel_size'] for i in report['images']]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
