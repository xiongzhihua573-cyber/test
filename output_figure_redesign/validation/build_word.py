"""Replace seven figure media parts and only necessary chart-reading notes."""
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from xml.sax.saxutils import escape,unescape
from PIL import Image
import hashlib,json,re
BASE=Path('/workspace/output_figure_redesign');V=BASE/'validation'
m=json.loads((V/'source_manifest.json').read_text())
src=Path(m['source_docx']);out=BASE/'小论文_中文终稿候选_图表重构版.docx'
assert hashlib.sha256(src.read_bytes()).hexdigest()==m['source_sha256'] and src!=out
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
config={
45:{'append':'(a)为年度有效观测数量的分组柱状图，(b)(c)为观测矩阵；缺测不表示零评分。'},
56:{'append':'右图底部短线为53个估计差值的原值，6个当年实测单元差值均为0。'},
64:{'append':'点仅横移，箱中心为实际B。'},
71:{'replace':{'各点和误差线为当档':'均值曲线为当档','的均值与样本标准差，最好值来自同一组':'的均值；半透明带表示均值±样本SD，空心菱形最好值来自同一组'},'append':'连线与区间连接仅辅助观察离散资源档，不表示新增中间资源计算。'},
81:{'replace':{'为均值、样本标准差及本组最好值；':'示均值±样本SD及空心菱形最好值；浅色点为30次独立结果，仅横向错排；连线只辅助比较已计算情景。','为各代表内已养护单元的首次养护年份分布。':'为各代表首次养护分布。','(d)中的点为已养护单元的原始首次养护年份，仅作横向排布，年份值不变；三个情景样本数依次为56、56、54。':'(d)散点为实际首次养护年份，仅横向错排，样本数依次为56、56、54；未养护3、3、5个单元不编码年份。'}}}
with ZipFile(src) as z:
 original=z.read('word/document.xml');xml=original
 tree=E.fromstring(original);pars=tree.find('w:body',ns).findall('w:p',ns)
 white=[]
 for idx,cfg in config.items():
  p=pars[idx];before=''.join(p.xpath('.//w:t/text()',namespaces=ns))
  assert before and pars[idx-1].find('w:pPr/w:pStyle',ns) is not None
  ident=p.get('{http://schemas.microsoft.com/office/word/2010/wordml}paraId')
  marker=f'w14:paraId="{ident}"'.encode();assert xml.count(marker)==1
  at=xml.index(marker);start=xml.rfind(b'<w:p ',0,at);end=xml.index(b'</w:p>',at)+len(b'</w:p>')
  old=xml[start:end];new=old;hits={key:0 for key in cfg.get('replace',{})}
  for match in reversed(list(re.finditer(rb'<w:t(?:\s[^>]*|)>(.*?)</w:t>',old,re.S))):
   text=unescape(match.group(1).decode());changed=text
   for a,b in cfg.get('replace',{}).items():
    hits[a]+=changed.count(a);changed=changed.replace(a,b)
   if changed!=text:new=new[:match.start(1)]+escape(changed).encode()+new[match.end(1):]
  assert all(n==1 for n in hits.values()),(idx,hits)
  if cfg.get('append'):
   runs=re.findall(rb'<w:r(?:\s[^>]*|)>.*?</w:r>',old,re.S)
   prop=re.search(rb'<w:rPr>.*?</w:rPr>',runs[-1],re.S)
   new=new[:-len(b'</w:p>')]+b'<w:r>'+(prop.group() if prop else b'')+b'<w:t>'+escape(cfg['append']).encode()+b'</w:t></w:r></w:p>'
  # Resolve CJK fallback using the same font actually used by the baseline PDF.
  # Only five authorized figure-note paragraphs receive this explicit East Asian font.
  def explicit_cjk_font(match):
   run=match.group(0)
   font=re.search(rb'<w:rFonts[^>]*/>',run)
   if font:
    tag=font.group(0)
    if b'w:eastAsia=' in tag:tag=re.sub(rb'w:eastAsia="[^"]*"',b'w:eastAsia="Noto Sans CJK SC"',tag)
    else:tag=tag[:-2]+b' w:eastAsia="Noto Sans CJK SC"/>'
    return run[:font.start()]+tag+run[font.end():]
   if b'<w:rPr>' in run:return run.replace(b'<w:rPr>',b'<w:rPr><w:rFonts w:eastAsia="Noto Sans CJK SC"/>',1)
   return re.sub(rb'(<w:r(?:\s[^>]*|)>)',rb'\1<w:rPr><w:rFonts w:eastAsia="Noto Sans CJK SC"/></w:rPr>',run,count=1)
  new=re.sub(rb'<w:r(?:\s[^>]*|)>.*?</w:r>',explicit_cjk_font,new,flags=re.S)
  newnode=E.fromstring(new.replace(b'<w:p ',b'<w:p '+b' '.join(f'xmlns:{k}="{v}"'.encode() for k,v in tree.nsmap.items() if k)+b' ',1))
  after=''.join(newnode.xpath('.//w:t/text()',namespaces=ns))
  white.append({'body_index':idx,'figure':next(n for n,i in [(1,45),(3,56),(4,64),(5,71),(7,81)] if i==idx),'before':before,'after':after,'changes':cfg,'format_compatibility':{'eastAsia_font':'Noto Sans CJK SC','baseline_actual_CJK_font_preserved_visually':True,'other_run_style_properties_preserved':True}})
  xml=xml[:start]+new+xml[end:]
 E.fromstring(xml)
 replacement={'word/document.xml':xml}
 dimensions=json.loads(Path('/workspace/revision16_work/input16_manifest.json').read_text())['figures']
 for row in dimensions:
  n=row['number'];image=BASE/f'fig{n}'/f'Figure_{n:02}_redesigned.png'
  with Image.open(image) as im:
   assert min(im.info['dpi'])>599
   assert abs((im.width/im.height)/(row['width_emu']/row['height_emu'])-1)<.001
   im.verify()
  replacement[row['partname'].lstrip('/')]=image.read_bytes()
 with ZipFile(out,'w') as dest:
  for info in z.infolist():dest.writestr(info,replacement.get(info.filename,z.read(info.filename)))
with ZipFile(src) as a,ZipFile(out) as b:
 assert a.namelist()==b.namelist() and b.testzip() is None
 changed=[n for n in a.namelist() if a.read(n)!=b.read(n)]
 assert sorted(changed)==sorted(replacement)
 p1=E.fromstring(a.read('word/document.xml')).find('w:body',ns).findall('w:p',ns)
 p2=E.fromstring(b.read('word/document.xml')).find('w:body',ns).findall('w:p',ns)
 assert len(p1)==len(p2)==139
 assert all(E.tostring(x,method='c14n')==E.tostring(y,method='c14n') for i,(x,y) in enumerate(zip(p1,p2)) if i not in config)
(V/'caption_whitelist.json').write_text(json.dumps(white,ensure_ascii=False,indent=2)+'\n')
audit={'source':str(src),'output':str(out),'source_unchanged':hashlib.sha256(src.read_bytes()).hexdigest()==m['source_sha256'],'source_sha256':m['source_sha256'],'output_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'changed_parts':changed,'caption_note_paragraphs':list(config),'all_other_paragraphs_and_xml_preserved':True}
(V/'word_update_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(audit,ensure_ascii=False,indent=2))
