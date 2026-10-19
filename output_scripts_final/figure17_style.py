"""Shared plotting system for instruction17; presentation only, no model execution."""
from pathlib import Path
import os,json,re
os.environ.setdefault('MPLCONFIGDIR','/tmp/fig17_mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.text import Text
import numpy as np

HERE=Path(__file__).resolve().parent
WORK=HERE.parent/'revision17_work'
PROJECT=HERE/'project_data'
SOURCE=PROJECT/'source_data'
RESULTS=PROJECT/'results'
OUTPUT=HERE.parent/'output_figures_final'
LANGUAGE='zh'
COLORS={'LOCF':'#285F82','Ridge':'#C1764D','XGBoost':'#4D8065','ink':'#273744','muted':'#687782','grid':'#E8ECF0','missing':'#F4F6F7','blue_light':'#DEE9F0','orange_light':'#F1E4DC','green_light':'#E0ECE5','d045':'#4D8065','d065':'#285F82','d085':'#C1764D'}
DIMENSIONS={1:(17,10.696733333333333),2:(17,15.01393888888889),3:(17,6.782488888888889),4:(17,7.1798222222222225),5:(17,6.902683333333333),6:(17,12.738388888888888),7:(17,12.48353611111111)}
CJK_PATH='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
CJK_NAME=font_manager.FontProperties(fname=CJK_PATH).get_name()


def configure(language='zh',output=None,project=None):
    global LANGUAGE,OUTPUT,PROJECT,SOURCE,RESULTS
    LANGUAGE=language
    if output is not None:OUTPUT=Path(output)
    if project is not None:PROJECT=Path(project);SOURCE=PROJECT/'source_data';RESULTS=PROJECT/'results'
    OUTPUT.mkdir(parents=True,exist_ok=True)
    for p in [CJK_PATH,'/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyretermes-regular.otf']:
        if Path(p).exists():font_manager.fontManager.addfont(p)
    available={f.name for f in font_manager.fontManager.ttflist}
    latin='TeX Gyre Termes' if 'TeX Gyre Termes' in available else 'Liberation Serif'
    plt.rcParams.update({'font.family':[latin,CJK_NAME],'font.size':8.5,'axes.labelsize':8.3,'axes.titlesize':9,
      'xtick.labelsize':7.5,'ytick.labelsize':7.5,'legend.fontsize':7.2,
      'axes.linewidth':.55,'axes.edgecolor':COLORS['ink'],'text.color':COLORS['ink'],
      'axes.labelcolor':COLORS['ink'],'xtick.color':COLORS['ink'],'ytick.color':COLORS['ink'],
      'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False,
      'figure.facecolor':'white','axes.facecolor':'white','savefig.facecolor':'white',
      'grid.color':COLORS['grid'],'grid.linewidth':.4,'lines.linewidth':1.25,'lines.markersize':3.5,
      'xtick.major.size':2.4,'ytick.major.size':2.4,'xtick.major.width':.55,'ytick.major.width':.55,
      'xtick.major.pad':2.4,'ytick.major.pad':2.4,'legend.frameon':False,'legend.handlelength':2,
      'mathtext.fontset':'stix','svg.fonttype':'path','pdf.fonttype':42,'ps.fonttype':42,'savefig.dpi':600})


def t(zh,en):return en if LANGUAGE=='en' else zh

def figsize(number):return tuple(x/2.54 for x in DIMENSIONS[number])

def panel(ax,letter,title=None):
    letter=letter.strip('()')
    ax.text(0,1.035,f'({letter})',transform=ax.transAxes,ha='left',va='bottom',fontweight='bold',fontsize=9.5,clip_on=False)
    if title:ax.text(.11,1.035,title,transform=ax.transAxes,ha='left',va='bottom',fontsize=8.7,fontweight='medium',clip_on=False)


def grid(ax,axis='y'):
    ax.grid(axis=axis,color=COLORS['grid'],lw=.4,zorder=0);ax.set_axisbelow(True)


def format_text(fig):
    for item in fig.findobj(Text):
        if re.search(r'[\u3400-\u9fff]',item.get_text()):item.set_fontfamily(CJK_NAME)


def save(fig,number):
    fig.set_size_inches(*figsize(number),forward=True)
    fig.patch.set_facecolor('white');format_text(fig)
    fig.canvas.draw()
    for ext in ['png','svg','pdf']:
        fig.savefig(OUTPUT/f'Figure_{number:02}_final.{ext}',dpi=600,bbox_inches=None,facecolor='white')
    # Return text-boundary issues for a concrete layout check before manuscript replacement.
    renderer=fig.canvas.get_renderer();W,H=fig.get_size_inches()*fig.dpi
    clipped=[]
    for x in fig.findobj(Text):
        if not x.get_visible() or not x.get_text():continue
        b=x.get_window_extent(renderer=renderer)
        if b.x0<-.8 or b.y0<-.8 or b.x1>W+.8 or b.y1>H+.8:clipped.append(x.get_text())
    return {'number':number,'clipped_text':clipped,'physical_size_cm':DIMENSIONS[number],'formats':['PNG600dpi','SVG','PDF']}


def array(data):
    x=np.asarray(data,dtype=float)
    return {'shape':list(x.shape),'values':np.nan_to_num(x,nan=-999999).tolist()}
