"""Modify only requested second-level heading text and remove two divider headings."""
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from xml.sax.saxutils import escape
import hashlib,json,re
BASE=Path('/workspace');WORK=BASE/'directory_revision_work'
source=BASE/'output_final/小论文_中文终稿候选_最终图表精修版.docx'
target=BASE/'output_outline_final/小论文_中文终稿候选_目录优化版.docx'
target.parent.mkdir(exist_ok=True)
expected_hash='c6abd40e9b690ecf81991e4b859cc863683e7c267b2a5df750e5e5ffd6ffcfbc'
assert hashlib.sha256(source.read_bytes()).hexdigest()==expected_hash
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
changes={
'2.1 检测数据与预测样本':'2.1 检测数据与预测样本',
'2.2 时间外状态预测':'2.2 全桥评分预测与时间外验证',
'2.3 候选规划初始状态':'2.3 规划初始状态构建',
'2.4 养护行动、状态递推与资源':'2.4 养护规划模型',
'2.5 共同资源水平与下降量情景':'2.5 情景设置与优化求解',
'2.6 养护时机求解与方案比较':None,
'3.1 检测数据与状态预测结果':'3.1 检测覆盖与评分预测结果',
'3.2 规划初始状态与养护时机':'3.2 规划初始状态与养护时机',
'3.3 资源水平与长期状态':'3.3 资源水平与长期养护结果',
'3.4 代表性养护排程':None,
'3.5 年评分下降量敏感性':'3.4 年评分下降量敏感性分析',
'4.1 低频检测条件下的状态推断':'4.1 低频检测与状态估计',
'4.2 规划初始状态与具体养护年份':'4.2 规划初始状态与排程差异',
'4.3 资源与评分下降情景的作用':'4.3 资源约束与情景参数',
'4.4 适用范围与限制':'4.4 研究局限性与实际应用'}
with ZipFile(source) as z:
 original=z.read('word/document.xml');xml=original
 root=E.fromstring(original);pars=root.find('w:body',ns).findall('w:p',ns)
 records=[]
 for idx,p in enumerate(pars):
  before=''.join(p.xpath('.//w:t/text()',namespaces=ns))
  if before not in changes:continue
  after=changes[before]
  assert p.find('w:pPr/w:pStyle',ns).get('{'+ns['w']+'}val')=='21'
  ident=p.get('{http://schemas.microsoft.com/office/word/2010/wordml}paraId')
  marker=f'w14:paraId="{ident}"'.encode();assert xml.count(marker)==1
  at=xml.index(marker);start=xml.rfind(b'<w:p ',0,at);end=xml.index(b'</w:p>',at)+len(b'</w:p>')
  old=xml[start:end]
  if after is None:
   assert not p.xpath('.//w:br|.//w:sectPr|.//w:drawing|.//w:bookmarkStart|.//m:oMath',namespaces=ns)
   replacement=b''
  elif before==after:replacement=old
  else:
   text_nodes=list(re.finditer(rb'<w:t(?:\s[^>]*|)>(.*?)</w:t>',old,re.S));assert len(text_nodes)==2
   number,title=after.split(' ',1);values=[number+' ',title];replacement=old
   for m,v in reversed(list(zip(text_nodes,values))):replacement=replacement[:m.start(1)]+escape(v).encode()+replacement[m.end(1):]
  xml=xml[:start]+replacement+xml[end:]
  records.append({'source_paragraph_index':idx,'paragraph_id':ident,'before':before,'after':after,'action':'remove_merged_heading' if after is None else ('unchanged' if before==after else 'rename')})
 assert len(records)==15
 with ZipFile(target,'w') as out:
  for info in z.infolist():out.writestr(info,xml if info.filename=='word/document.xml' else z.read(info.filename))
with ZipFile(source) as a,ZipFile(target) as b:
 assert a.namelist()==b.namelist() and b.testzip() is None
 assert [n for n in a.namelist() if a.read(n)!=b.read(n)]==['word/document.xml']
 old=E.fromstring(original);new=E.fromstring(xml)
 for x in [old,new]:
  for p in list(x.find('w:body',ns).findall('w:p',ns)):
   if p.find('w:pPr/w:pStyle',ns) is not None and p.find('w:pPr/w:pStyle',ns).get('{'+ns['w']+'}val')=='21':p.getparent().remove(p)
 assert E.tostring(old,method='c14n')==E.tostring(new,method='c14n')
report={'source':str(source),'target':str(target),'source_sha256':expected_hash,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==expected_hash,'output_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'changed_package_parts':['word/document.xml'],'other_25_parts_byte_identical':True,'all_non_heading_xml_identical':True,'heading_records':records,'body_order_unchanged':True,'body_text_moved':False,'old_section_references_requiring_changes':0,'models_fitted':0,'optimizations_run':0}
(WORK/'outline_update_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
rows=[]
for r in records:
 old=r['before'];new=r['after'];merge='无'
 if old.startswith('2.5 '):merge='与原2.6合并'
 if old.startswith('2.6 '):new='并入2.5 情景设置与优化求解';merge='删除原2.6标题'
 if old.startswith('3.3 '):merge='与原3.4合并'
 if old.startswith('3.4 '):new='并入3.3 资源水平与长期养护结果';merge='删除原3.4标题'
 if old.startswith('3.5 '):merge='重新编号为3.4'
 rows.append(f'| {old} | {new} | {merge} | 未移动，原顺序保留 |')
note='''# 目录调整对照说明

| 原小节标题 | 新小节标题 | 合并关系 | 正文是否移动 |
|---|---|---|---|
'''+ '\n'.join(rows)+'''

原2.5的情景设置在前、原2.6的求解与方案比较在后；原3.3的资源结果在前、原3.4的代表性排程及年度状态在后。原文已经依次相邻，本次仅删除两个旧标题，实现章节合并，正文未移动、未改写、未增删。第2、3、4章二级标题数分别为5、4、4；没有新增目录页或三级标题。

图1—图7及表1—表6全部完整，内容与编号保持原样。Word内8个物理表对应表1—表5及表6的A/B/C三部分，全部保留；公式、图题、表题和参考文献未改。科研数据和结果数字未发生变化，未训练模型或运行GJO。未发现需要更正的旧小节编号引用。

原有未编号文末“补充材料说明”及其内容、样式保持不变。题目、摘要、正文、字体字号、页眉页脚、手动分页和投稿模板排版均保留。
'''
(target.parent/'目录调整对照说明.md').write_text(note)
print(json.dumps({'output':str(target),'renamed_headings':sum(r['action']=='rename' for r in records),'removed_heading_paragraphs':sum(r['after'] is None for r in records),'non_heading_xml_identical':True,'source_preserved':True,'sha256':report['output_sha256']},ensure_ascii=False,indent=2))
