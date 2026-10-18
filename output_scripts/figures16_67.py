#!/usr/bin/env python3
"""Publication redraw of Figures 6–7 from frozen, saved scientific results.

Presentation only: no prediction, optimization, smoothing, KDE, or new statistics.
Usage: python figures16_67.py --language zh --output /workspace/output_figures_redrawn
"""
from pathlib import Path
import argparse
import json
import hashlib
import importlib.util
import sys
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/fig16_mpl')
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.colors import to_rgba
import figure16_style as style

FILES=['representative_annual_metrics_15y.csv','deterioration_summary_15y.csv',
       'deterioration_annual_15y.csv','deterioration_timing_15y.csv']
DVALUES=[.45,.65,.85]
REPORT_PATH=Path('/workspace/revision16_work/f67_redrawn_audit.json')
REPORTS={}
LAST_FIGURES={}

def t(zh,en):return style.t(zh,en)
def colors_d():return [style.COLORS['d045'],style.COLORS['d065'],style.COLORS['d085']]

def file_hashes():return {name:hashlib.sha256((style.RESULTS/name).read_bytes()).hexdigest() for name in FILES}

def numeric_lines(ax):return [np.asarray(line.get_xydata()).tolist() for line in ax.lines]

def snapshot6(fig):
    return {'lines':[numeric_lines(ax) for ax in fig.axes],
      'bars':[[[float(p.get_x()),float(p.get_y()),float(p.get_width()),float(p.get_height())]
            for p in ax.patches] for ax in fig.axes]}

def snapshot7(fig,extra_mean_scatter=False):
    out={'lines':[numeric_lines(ax) for ax in fig.axes],
         'error_segments':[], 'best_points':[], 'boxes':[]}
    for ax in fig.axes[:2]:
        out['error_segments'].append([np.asarray(seg).tolist() for col in ax.collections
                      if hasattr(col,'get_segments') for seg in col.get_segments()])
        pointcols=[col for col in ax.collections if hasattr(col,'get_offsets') and not hasattr(col,'get_segments')]
        out['best_points'].append(np.asarray(pointcols[-1].get_offsets()).tolist())
        if extra_mean_scatter:
            np.testing.assert_array_equal(np.asarray(pointcols[0].get_offsets()),ax.lines[0].get_xydata())
    out['boxes']=[patch.get_path().vertices.tolist() for patch in fig.axes[3].patches]
    return out

def old_snapshots():
    path=style.PROJECT/'scripts/plot_figures_sci.py'
    spec=importlib.util.spec_from_file_location('frozen_old_plot67',path)
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    old.setup('zh');captured={}
    old.save=lambda fig,out,name:captured.update({name:fig})
    old.figure7(style.RESULTS,style.OUTPUT);old.figure8(style.RESULTS,style.OUTPUT)
    baseline={6:snapshot6(captured['Figure_07_15y']),7:snapshot7(captured['Figure_08_15y'])}
    for fig in captured.values():plt.close(fig)
    return baseline

def figure6():
    g=pd.read_csv(style.RESULTS/FILES[0]);g=g[g.initial_condition.eq('LOCF')].sort_values('year')
    assert len(g)==15 and g.year.tolist()==list(range(2025,2040))
    fig,axs=plt.subplots(3,1,figsize=style.figsize(6),sharex=True,
                         gridspec_kw={'height_ratios':[1,1.07,1]})
    fig.subplots_adjust(left=.112,right=.976,bottom=.098,top=.937,hspace=.33)
    blue=style.COLORS['LOCF'];green=style.COLORS['XGBoost'];ink=style.COLORS['ink'];muted=style.COLORS['muted']
    titles=[t('网络平均状态','Network mean condition'),t('最弱单元状态','Lowest unit condition'),
            t('年度养护安排','Annual maintenance allocation')]
    # Curves retain the exact fifteen original annual observations.
    axs[0].plot(g.year,g.mean_score,color=blue,marker='o',ms=2.9,lw=1.35,zorder=4)
    axs[0].set(ylabel=t('平均评分（分）','Mean score (points)'),ylim=(90.05,92.65),yticks=[90.5,91.5,92.5])
    axs[1].plot(g.year,g.minimum_score,color=green,marker='o',ms=2.9,lw=1.35,zorder=4)
    axs[1].axhline(75,color='#8C949A',ls=(0,(4,2.3)),lw=.8,zorder=2)
    axs[1].axhline(60,color='#A7AFB5',ls=(0,(1,2.1)),lw=.8,zorder=2)
    axs[1].set(ylabel=t('最低评分（分）','Minimum score (points)'),ylim=(56.9,88.0),yticks=[60,70,75,80])
    axs[1].text(2025,76.05,t('75分：1、2类与3类边界','75: boundary between grades 1–2 and 3'),
                ha='left',va='bottom',fontsize=7.15,color=muted)
    axs[1].text(2025,61.05,t('60分：3类与4类边界','60: boundary between grades 3 and 4'),
                ha='left',va='bottom',fontsize=7.15,color=muted)
    # Dark bars encode reaching the already fixed capacity of eight; pale bars remain visible.
    cap=(g.maintenance_count.to_numpy()==8)
    faces=[blue if full else style.COLORS['blue_light'] for full in cap]
    axs[2].bar(g.year,g.maintenance_count,width=.72,color=faces,edgecolor=blue,lw=.45,zorder=3)
    axs[2].axhline(8,color='#8C949A',ls=(0,(4,2.3)),lw=.8,zorder=2)
    axs[2].set(ylabel=t('养护数（个）','Maintenance count'),xlabel=t('年份（年）','Year'),
               ylim=(0,10.0),yticks=[0,2,4,6,8],xticks=list(range(2025,2040,2)))
    for row in g.itertuples():
        # The zero in 2039 is intentionally printed rather than omitted.
        axs[2].text(row.year,row.maintenance_count+.19,f'{row.maintenance_count:d}',ha='center',va='bottom',
                    fontsize=7.2,color=blue if row.maintenance_count==8 else muted)
    axs[2].text(2038.9,8.43,t('年度能力上限 = 8','Annual capacity = 8'),ha='right',va='bottom',fontsize=7.15,color=muted)
    for i,(ax,title) in enumerate(zip(axs,titles)):
        style.panel(ax,'abc'[i],title)
        ax.set_xlim(2024.48,2040.15)
        ax.set_xticks(np.arange(2025,2040),minor=True)
        ax.grid(axis='x',which='minor',color='#EDF0F2',lw=.35,zorder=0)
        ax.grid(axis='x',which='major',color='#EDF0F2',lw=.35,zorder=0)
        style.grid(ax)
        ax.tick_params(axis='x',which='minor',length=0)
        ax.set_axisbelow(True)
        ax.spines['left'].set_visible(False)
        ax.tick_params(axis='y',length=0,pad=4)
    # Values are existing annual endpoint values, printed with display rounding only.
    endpoints=[]
    for ax,col,color in [(axs[0],'mean_score',blue),(axs[1],'minimum_score',green)]:
        end=g.iloc[-1];value=float(end[col])
        ax.scatter([end.year],[value],s=25,facecolors='white',edgecolors=color,lw=1,zorder=5)
        ax.text(2039.22,value,f'{value:.2f}',ha='left',va='center',fontsize=7.6,color=color,
                bbox={'facecolor':'white','edgecolor':'none','pad':.5},zorder=6)
        endpoints.append({'year':int(end.year),'metric':col,'raw_value':value,'printed':f'{value:.2f}'})
    axs[0].text(.995,1.035,t('LOCF · 代表性方案','LOCF · representative schedule'),transform=axs[0].transAxes,
                ha='right',va='bottom',fontsize=7.2,color=muted,clip_on=False)
    if style.LANGUAGE=='zh':
        axs[2].legend(handles=[Patch(facecolor=blue,edgecolor=blue,label='达到年度能力上限'),
                         Patch(facecolor=style.COLORS['blue_light'],edgecolor=blue,label='低于年度能力上限')],
                      loc='upper right',bbox_to_anchor=(1.005,1.225),ncol=2,fontsize=6.7,
                      handlelength=1.0,handleheight=.65,columnspacing=1.05,handletextpad=.4)
    else:
        axs[2].legend(handles=[Patch(facecolor=blue,edgecolor=blue,label='At annual capacity'),
                         Patch(facecolor=style.COLORS['blue_light'],edgecolor=blue,label='Below annual capacity')],
                      loc='upper right',bbox_to_anchor=(1.005,1.225),ncol=2,fontsize=6.7,
                      handlelength=1.0,handleheight=.65,columnspacing=1.05,handletextpad=.4)
    export=style.save(fig,6)
    REPORTS[6]={'export':export,'snapshot':snapshot6(fig),'endpoint_annotations':endpoints,
        'count_labels':g.maintenance_count.astype(int).tolist(),
        'redesign':['three aligned annual panels with common fine year grid',
                    'separate panel headings and restrained end-point labels from original annual values',
                    'grey 75/60 thresholds with complete grade-boundary labels',
                    'capacity-coded bars, original counts on all fifteen years including 2039 zero'],
        'scientific_rows':g[['year','mean_score','minimum_score','maintenance_count']].to_dict(orient='records')}
    LAST_FIGURES[6]=fig
    return fig

def figure7():
    d=pd.read_csv(style.RESULTS/FILES[1]).sort_values('d')
    annual=pd.read_csv(style.RESULTS/FILES[2]);timing=pd.read_csv(style.RESULTS/FILES[3])
    dc=colors_d();ink=style.COLORS['ink'];muted=style.COLORS['muted']
    fig,axs=plt.subplots(2,2,figsize=style.figsize(7))
    fig.subplots_adjust(left=.107,right=.98,bottom=.119,top=.875,wspace=.38,hspace=.56)
    x=np.arange(3);labels=['0.45','0.65','0.85']
    annotations=[]
    for ax,metric,ylabel,letter,title in [
        (axs[0,0],'J',t('$J$（分）','$J$ (points)'),'a',t('长期平均评分','Long-term mean condition')),
        (axs[0,1],'Delta_J',t('$\\Delta J$（分）','$\\Delta J$ (points)'),'b',t('相对养护增益','Gain over no maintenance'))]:
        errors=ax.errorbar(x,d[metric+'_mean'],yerr=d[metric+'_sd'].fillna(0),
               color='#9EA8AF',marker='none',lw=.8,ecolor='#9EA8AF',elinewidth=1.15,
               capsize=3.2,capthick=.9,zorder=2)
        errors.lines[2][0].set_color(dc)
        ax.scatter(x,d[metric+'_mean'],c=dc,marker='o',s=24,edgecolors='white',linewidths=.45,zorder=4)
        ax.scatter(x,d[metric+'_best'],edgecolors=dc,facecolors='white',marker='D',s=27,lw=1.1,zorder=4)
        for k,row in enumerate(d.itertuples()):
            v=float(getattr(row,metric+'_mean'))
            # Label the exact saved mean using two decimal places; no recomputed mean.
            ax.text(k+.115,v,f'{v:.2f}',ha='left',va='center',fontsize=7.1,color=dc[k],
                    bbox={'facecolor':'white','edgecolor':'none','pad':.4},zorder=5)
            annotations.append({'metric':metric,'d':float(row.d),'raw_value':v,'printed':f'{v:.2f}'})
        ax.set_xticks(x,labels)
        for label,color in zip(ax.get_xticklabels(),dc):label.set_color(color)
        ax.set(xlabel=t('年评分下降量 $d$（分/年）','Annual deterioration $d$ (points/year)'),
               ylabel=ylabel,xlim=(-.28,2.42))
        ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
        style.grid(ax);style.panel(ax,letter,title)
    axs[0,0].set_ylim(89.25,93.5);axs[0,0].set_yticks([89.5,90.5,91.5,92.5,93.5])
    axs[0,1].set_ylim(5.52,6.23);axs[0,1].set_yticks([5.6,5.8,6.0,6.2])
    # A two-tier key separates scenario from statistic without invading data panels.
    fig.legend(handles=[Line2D([],[],color=c,marker=m,lw=1.2,ls=ls,ms=3.1,label=f'$d$ = {v:.2f}')
              for v,c,m,ls in zip(DVALUES,dc,['o','s','^'],['-','--',':'])],
               loc='upper center',bbox_to_anchor=(.53,.998),ncol=3,fontsize=7.3,
               columnspacing=1.9,handletextpad=.45)
    fig.legend(handles=[Line2D([],[],color=muted,marker='o',markerfacecolor=muted,ls='none',ms=3.4,
                              label=t('均值 ± 样本SD（30次）','Mean ± sample SD (30 runs)')),
                        Line2D([],[],color=muted,marker='D',markerfacecolor='white',ls='none',ms=3.5,
                              label=t('本情景30次最好值','Best of 30 runs in this scenario'))],
               loc='upper center',bbox_to_anchor=(.53,.956),ncol=2,fontsize=7.1,
               columnspacing=1.7,handletextpad=.4)
    ax=axs[1,0]
    for v,c,ls,m in zip(DVALUES,dc,['-','--',':'],['o','s','^']):
        g=annual[np.isclose(annual.d,v)].sort_values('year')
        ax.plot(g.year,g.mean_score,color=c,ls=ls,marker=m,ms=2.3,lw=1.25)
        ax.text(2039.3,float(g.mean_score.iloc[-1]),f'{v:.2f}',ha='left',va='center',fontsize=7.2,color=c,
                bbox={'facecolor':'white','edgecolor':'none','pad':.3})
    ax.set(xlabel=t('年份（年）','Year'),ylabel=t('平均评分（分）','Mean score (points)'),
           xticks=[2025,2032,2039],xlim=(2024.4,2041.8),ylim=(87.25,95.05),yticks=[88,90,92,94])
    ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
    style.grid(ax);style.panel(ax,'c',t('各情景代表方案','Scenario representatives'))
    ax=axs[1,1]
    data=[timing.loc[np.isclose(timing.d,v),'first_year'].dropna().to_numpy() for v in DVALUES]
    b=ax.boxplot(data,patch_artist=True,showfliers=True,
       medianprops={'color':ink,'linewidth':1.35},boxprops={'linewidth':1},
       whiskerprops={'linewidth':.9},capprops={'linewidth':.9},
       flierprops={'marker':'o','markersize':2.5,'markerfacecolor':'white'})
    raw_offsets=[]
    for j,(patch,c,vals) in enumerate(zip(b['boxes'],dc,data)):
        patch.set(facecolor=to_rgba(c,.14),edgecolor=c)
        for artist in b['whiskers'][2*j:2*j+2]+b['caps'][2*j:2*j+2]:artist.set_color(c)
        b['fliers'][j].set_markeredgecolor(c)
        # Deterministic horizontal-only spreading: all observed integer years stay exact.
        # Ties are laid side-by-side; this is display placement, not an estimated density.
        offsets=np.zeros(len(vals),dtype=float)
        for year in np.unique(vals):
            indices=np.flatnonzero(vals==year)
            offsets[indices]=np.linspace(-.105,.105,len(indices)) if len(indices)>1 else 0
        collection=ax.scatter(j+1+offsets,vals,s=4.2,c=c,alpha=.65,edgecolors='none',zorder=3)
        np.testing.assert_array_equal(np.asarray(collection.get_offsets())[:,1],vals)
        raw_offsets.append({'d':DVALUES[j],'n':int(len(vals)),
                            'original_years':vals.tolist(),
                            'actual_artist_offsets':np.asarray(collection.get_offsets()).tolist()})
    ax.set_xticks([1,2,3],[label+f'\n$n$ = {len(vals)}' for label,vals in zip(labels,data)])
    for label,c in zip(ax.get_xticklabels(),dc):label.set_color(c)
    ax.set(xlabel=t('年评分下降量 $d$（分/年）','Annual deterioration $d$ (points/year)'),
       ylabel=t('首次养护年份（年）','First maintenance year'),
       ylim=(2024.5,2037.8),yticks=[2026,2028,2030,2032,2034,2036])
    ax.text(.98,.985,t('点：已养护单元原值','Points: maintained units'),ha='right',va='top',
            transform=ax.transAxes,fontsize=6.9,color=muted)
    ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
    style.grid(ax);style.panel(ax,'d',t('首次养护分布','First-maintenance distribution'))
    export=style.save(fig,7)
    REPORTS[7]={'export':export,'snapshot':snapshot7(fig,True),'mean_annotations':annotations,
       'raw_first_year_strip':raw_offsets,
       'redesign':['two-tier scenario/statistic legend outside all data panels',
                   'point-range mean/sample-SD comparison with saved-mean labels and hollow best-value diamonds',
                   'consistent scenario colors and grayscale-distinct annual curve line/marker encodings',
                   'direct annual-curve scenario labels instead of an internal legend',
                   'transparent scenario-colored original boxplots plus every saved individual first year, horizontal display spread only'],
       'summary_rows':d[['d','J_mean','J_sd','J_best','Delta_J_mean','Delta_J_sd','Delta_J_best']].to_dict(orient='records'),
       'annual_rows':annual[['d','year','mean_score']].to_dict(orient='records')}
    LAST_FIGURES[7]=fig
    return fig

def build_all(audit_original=False):
    initial_hashes=file_hashes()
    language,output,project=style.LANGUAGE,style.OUTPUT,style.PROJECT
    baseline=old_snapshots() if audit_original else None
    style.configure(language,output,project)
    figure6();figure7()
    for n in [6,7]:
        if baseline is not None:
            assert baseline[n]==REPORTS[n]['snapshot'],f'Figure {n}: scientific artist coordinates changed'
        assert not REPORTS[n]['export']['clipped_text'],f'Figure {n}: clipped text'
    assert file_hashes()==initial_hashes
    counts=[item['n'] for item in REPORTS[7]['raw_first_year_strip']]
    assert counts==[56,56,54]
    report={'all_passed':True,'language':language,
       'scope':'presentation-only redraw; no Word edits or scientific computation',
       'source_csv_sha256':initial_hashes,'source_csv_unchanged':True,
       'old_plotter_sha256':hashlib.sha256((style.PROJECT/'scripts/plot_figures_sci.py').read_bytes()).hexdigest() if audit_original else None,
       'old_artist_coordinates':baseline,'figures':REPORTS,
       'checks':{'exact_old_new_curves_errorbars_best_markers_box_geometry_and_bar_coordinates':bool(audit_original),
            'all_fifteen_annual_maintenance_counts_retained':True,
            'all_first_year_samples_retained_without_y_jitter_or_density_estimate':True,
            'sample_counts':counts,'no_text_outside_fixed_canvas':True},
       'output_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in style.OUTPUT.iterdir()
                         if p.name.startswith(('Figure_06_redrawn.','Figure_07_redrawn.'))}}
    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language',choices=['zh','en'],default='zh')
    parser.add_argument('--output',type=Path,default=Path('/workspace/output_figures_redrawn'))
    parser.add_argument('--project',type=Path,default=style.PROJECT)
    parser.add_argument('--audit-original',action='store_true',help='Local audit against the frozen original plotting script; ordinary redraw does not require that script.')
    args=parser.parse_args();style.configure(args.language,args.output,args.project)
    report=build_all(audit_original=args.audit_original)
    print(json.dumps({'all_passed':report['all_passed'],'figures':[6,7],
                      'sample_counts':report['checks']['sample_counts'],'audit':str(REPORT_PATH)},ensure_ascii=False))

if __name__=='__main__':main()
