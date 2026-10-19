"""Update only seven image parts and three explicitly requested figure notes."""
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from PIL import Image
from xml.sax.saxutils import escape
import re,json,hashlib
ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'input17_manifest.json').read_text())
source=Path(manifest['source_docx'])
out=Path('/workspace/output_final/小论文_中文终稿候选_最终图表精修版.docx')
assert source!=out and hashlib.sha256(source.read_bytes()).hexdigest()==manifest['source_sha256']
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
additions={65:'菱形为均值。',72:'已验证可行下界单独展示，不计入当档30次独立运行统计，亦非全局最优；LOCF在B=1.915337时独立最好值低于该下界，反映有限搜索不足。',83:'(d)中的点为已养护单元的原始首次养护年份，仅作横向排布，年份值不变；三个情景样本数依次为56、56、54。'}
with ZipFile(source) as z:
 xml=z.read('word/document.xml')
 doc=etree.fromstring(xml)
 pars=doc.find('w:body',ns).findall('w:p',ns)
 edits=[]
 for idx,addition in additions.items():
  p=pars[idx]
  ident=p.get('{http://schemas.microsoft.com/office/word/2010/wordml}paraId')
  assert ident
  marker=f'w14:paraId="{ident}"'.encode()
  assert xml.count(marker)==1
  pos=xml.index(marker);start=xml.rfind(b'<w:p ',0,pos);end=xml.index(b'</w:p>',pos)+len(b'</w:p>')
  old=xml[start:end]
  runs=re.findall(rb'<w:r(?:\s[^>]*|)>.*?</w:r>',old,re.S)
  assert runs
  props=re.search(rb'<w:rPr>.*?</w:rPr>',runs[-1],re.S)
  rpr=props.group() if props else b''
  new=old[:-len(b'</w:p>')]+b'<w:r>'+rpr+b'<w:t>'+escape(addition).encode()+b'</w:t></w:r></w:p>'
  xml=xml[:start]+new+xml[end:]
  before=''.join(p.xpath('.//w:t/text()',namespaces=ns))
  edits.append({'paragraph_index':idx,'para_id':ident,'before':before,'addition':addition,'after':before+addition})
 etree.fromstring(xml)
 replacements={'word/document.xml':xml}
 mapping=json.loads(Path('/workspace/revision16_work/input16_manifest.json').read_text())['figures']
 for m in mapping:
  p=Path('/workspace/output_figures_final')/f"Figure_{m['number']:02d}_final.png"
  with Image.open(p) as im:
   assert abs((im.width/im.height)/(m['width_emu']/m['height_emu'])-1)<.001
   assert min(im.info['dpi'])>599
   im.verify()
  replacements[m['partname'].lstrip('/')]=p.read_bytes()
 with ZipFile(out,'w') as dest:
  for info in z.infolist():dest.writestr(info,replacements.get(info.filename,z.read(info.filename)))
with ZipFile(source) as a,ZipFile(out) as b:
 changed=[n for n in a.namelist() if a.read(n)!=b.read(n)]
 assert sorted(changed)==sorted(replacements)
 assert b.testzip() is None
 p1=etree.fromstring(a.read('word/document.xml')).find('w:body',ns).findall('w:p',ns)
 p2=etree.fromstring(b.read('word/document.xml')).find('w:body',ns).findall('w:p',ns)
 assert len(p1)==len(p2)
 assert all(etree.tostring(x,method='c14n')==etree.tostring(y,method='c14n') for i,(x,y) in enumerate(zip(p1,p2)) if i not in additions)
report={'source':str(source),'output':str(out),'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==manifest['source_sha256'],'changed_parts':changed,'caption_edits':edits,'all_other_paragraphs_and_formats_exact':True,'source_sha256':manifest['source_sha256'],'output_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
(ROOT/'word_update17_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(ROOT/'caption_edits17.json').write_text(json.dumps(edits,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'output':str(out),'changed_parts':changed,'only_three_requested_notes_extended':True,'output_sha256':report['output_sha256']},ensure_ascii=False,indent=2))
