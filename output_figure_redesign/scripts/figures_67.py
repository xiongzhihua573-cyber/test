#!/usr/bin/env python3
"""Reconstruct Figures 6–7 from frozen annual, independent-run, and timing results.

Presentation and data validation only: no prediction, optimization, smoothing, or KDE.
Usage: python figures_67.py --language zh --figures 6 7
"""
from pathlib import Path
import argparse
import json
import hashlib
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/fig17_mpl')
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.colors import to_rgba
import figure_style as style

FILES=['representative_annual_metrics_15y.csv','deterioration_summary_15y.csv',
       'deterioration_annual_15y.csv','deterioration_timing_15y.csv']
DVALUES=[.45,.65,.85]
REPORTS={}
LAST_FIGURES={}

def t(zh,en):return style.t(zh,en)
def colors_d():return [style.COLORS['d045'],style.COLORS['d065'],style.COLORS['d085']]

def file_hashes():return {name:hashlib.sha256((style.RESULTS/name).read_bytes()).hexdigest() for name in FILES+['deterioration_runs_15y.csv']}

def numeric_lines(ax):return [np.asarray(line.get_xydata()).tolist() for line in ax.lines]

def snapshot6(fig):
    return {'lines':[numeric_lines(ax) for ax in fig.axes],
      'bars':[[[float(p.get_x()),float(p.get_y()),float(p.get_width()),float(p.get_height())]
            for p in ax.patches] for ax in fig.axes]}

def figure6():
    """Three aligned panels from the saved 2025–2039 representative plan."""
    source=style.RESULTS/FILES[0]
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    g=pd.read_csv(source);g=g.loc[g.initial_condition.eq('LOCF')].sort_values('year')
    assert len(g)==15 and g.year.tolist()==list(range(2025,2040))
    assert g.run_id.nunique()==1
    assert g.maintenance_count.ge(0).all() and g.maintenance_count.le(8).all()
    assert np.all(g.maintenance_count==np.rint(g.maintenance_count))
    assert int(g.loc[g.year.eq(2039),'maintenance_count'].iloc[0])==0
    fig,axs=plt.subplots(3,1,figsize=style.figsize(6),sharex=True,
                         gridspec_kw={'height_ratios':[1,1.12,1]})
    fig.subplots_adjust(left=.112,right=.976,bottom=.098,top=.937,hspace=.35)
    blue=style.COLORS['LOCF'];muted=style.COLORS['muted']
    threshold='#8B979F'
    titles=[t('网络平均状态','Network mean condition'),t('最弱单元状态','Lowest unit condition'),
            t('年度养护安排','Annual maintenance allocation')]
    curve_mean=axs[0].plot(g.year,g.mean_score,color=blue,marker='o',ms=3.0,lw=1.35,zorder=4)[0]
    axs[0].set(ylabel=t('平均评分（分）','Mean score (points)'),ylim=(90.0,92.75),yticks=[90,91,92])
    curve_min=axs[1].plot(g.year,g.minimum_score,color=blue,marker='s',ms=2.9,lw=1.35,zorder=4)[0]
    threshold_lines=[axs[1].axhline(75,color=threshold,ls=(0,(4,2.3)),lw=.7,zorder=2),
                     axs[1].axhline(60,color=threshold,ls=(0,(1.6,2.3)),lw=.7,zorder=2)]
    axs[1].set(ylabel=t('最低评分（分）','Minimum score (points)'),ylim=(56.9,85.0),yticks=[60,70,75,80,85])
    threshold_labels=[t('75分｜1、2/3类边界','75: grades 1–2 / 3 boundary'),
                      t('60分｜3/4类边界','60: grades 3 / 4 boundary')]
    for value,label in zip([75,60],threshold_labels):
        axs[1].text(2025.0,value+1.0,label,ha='left',va='bottom',fontsize=6.8,color=muted,
                    bbox={'facecolor':'white','edgecolor':'none','pad':.35},zorder=3)
    # The bars show actual allocations, while the gray dashed line is the capacity.
    bars=axs[2].bar(g.year,g.maintenance_count,width=.66,color=blue,
                    edgecolor=blue,lw=.4,zorder=3)
    capacity=axs[2].axhline(8,color=threshold,ls=(0,(4,2.3)),lw=.8,zorder=4)
    axs[2].set(ylabel=t('养护数（个）','Maintenance count'),xlabel=t('年份（年）','Year'),
               ylim=(0,9.65),yticks=[0,2,4,6,8],xticks=list(range(2025,2040,2)))
    for row in g.itertuples():
        axs[2].annotate(f'{row.maintenance_count:d}',(row.year,row.maintenance_count),
                        xytext=(0,4.8 if row.maintenance_count==8 else 3.5),textcoords='offset points',
                        ha='center',va='bottom',fontsize=7.0,color=blue,zorder=5,
                        bbox={'facecolor':'white','edgecolor':'none','pad':.25})
    axs[2].legend(handles=[Patch(facecolor=blue,edgecolor=blue,label=t('实际养护数','Actual maintenance count')),
                          Line2D([],[],color=threshold,ls=(0,(4,2.3)),lw=.8,
                                 label=t('年度能力上限 = 8','Annual capacity = 8'))],
                  loc='upper right',bbox_to_anchor=(1.005,1.23),ncol=2,fontsize=6.7,
                  handlelength=1.4,handleheight=.7,columnspacing=1.1,handletextpad=.4)
    for i,(ax,title) in enumerate(zip(axs,titles)):
        style.panel(ax,'abc'[i],title)
        ax.set_xlim(2024.48,2040.35)
        ax.set_xticks(np.arange(2025,2040),minor=True)
        ax.grid(axis='x',which='both',color='#EDF0F2',lw=.35,zorder=0)
        style.grid(ax)
        ax.tick_params(axis='x',which='minor',length=0)
        ax.set_axisbelow(True)
        ax.spines['left'].set_visible(False)
        ax.tick_params(axis='y',length=0,pad=4)
    endpoints=[]
    for ax,col in [(axs[0],'mean_score'),(axs[1],'minimum_score')]:
        end=g.iloc[-1];value=float(end[col])
        ax.scatter([end.year],[value],s=25,facecolors='white',edgecolors=blue,lw=1,zorder=5)
        ax.text(2039.25,value,f'{value:.2f}',ha='left',va='center',fontsize=7.6,color=blue,
                bbox={'facecolor':'white','edgecolor':'none','pad':.5},zorder=6)
        endpoints.append({'year':int(end.year),'metric':col,'raw_value':value,'printed':f'{value:.2f}'})
    np.testing.assert_array_equal(curve_mean.get_xydata(),g[['year','mean_score']].to_numpy())
    np.testing.assert_array_equal(curve_min.get_xydata(),g[['year','minimum_score']].to_numpy())
    np.testing.assert_array_equal([p.get_height() for p in bars],g.maintenance_count.to_numpy())
    np.testing.assert_array_equal([p.get_x()+p.get_width()/2 for p in bars],g.year.to_numpy())
    for line,value in zip(threshold_lines,[75,60]):
        np.testing.assert_array_equal(line.get_ydata(),[value,value])
    np.testing.assert_array_equal(capacity.get_ydata(),[8,8])
    assert float(g.minimum_score.iloc[-1])>60
    np.testing.assert_allclose(g.minimum_score.iloc[-1],74.89,rtol=0,atol=1e-10)
    export=style.save(fig,6)
    assert not export['clipped_text'],export['clipped_text']
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    REPORTS[6]={'export':export,'snapshot':snapshot6(fig),'endpoint_annotations':endpoints,
        'count_labels':g.maintenance_count.astype(int).tolist(),
        'redesign':['shared 2025–2039 axis for three annual panels',
                    'same LOCF blue for mean and minimum condition, distinguished with circle and square markers',
                    '75/60 grade boundaries explicitly labeled without implying a universal 75-point floor',
                    'actual-count bars versus a separate capacity=8 dashed line and key',
                    'all fifteen annual count labels retained, including the zero in 2039'],
        'scientific_rows':g[['year','mean_score','minimum_score','maintenance_count']].to_dict(orient='records')}
    report={'all_passed':True,'figure':6,'language':style.LANGUAGE,
            'source_csv':str(source),'source_csv_sha256':{FILES[0]:before},'source_csv_unchanged':True,
            'planning_years':g.year.astype(int).tolist(),'planning_horizon':15,
            'representative_run_id':str(g.run_id.iloc[0]),
            'exact_mean_score_artist_coordinates':curve_mean.get_xydata().tolist(),
            'exact_minimum_score_artist_coordinates':curve_min.get_xydata().tolist(),
            'actual_annual_maintenance_counts':g.maintenance_count.astype(int).tolist(),
            'maintenance_bar_count':len(bars),'year_2039_maintenance_zero_retained':True,
            'score_thresholds':[75,60],'score_threshold_labels':threshold_labels,
            'annual_capacity':8,'terminal_minimum_score':float(g.minimum_score.iloc[-1]),
            'no_universal_75_point_floor_claimed':True,
            'new_models_fitted':0,'new_optimization_runs':0,'report':REPORTS[6],
            'output_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (style.OUTPUT/'fig6').glob('Figure_06_redesigned.*')}}
    target=style.OUTPUT/'validation'/'fig6_data_audit.json';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    LAST_FIGURES[6]=fig
    return fig


def validate_figure7_data(summary,annual,timing,runs):
    """Validate saved statistics against the exact independent runs; no model execution."""
    assert len(runs)==90
    checks=[]
    for value,expected_n in zip(DVALUES,[56,56,54]):
        s=summary.loc[np.isclose(summary.d,value)].iloc[0]
        r=runs.loc[np.isclose(runs.d,value)]
        assert len(r)==30 and r.run_id.nunique()==30
        assert r.feasible.all() and r.planning_horizon.eq(15).all()
        assert r.start_year.eq(2025).all() and r.end_year.eq(2039).all()
        metric_checks={}
        for metric in ['J','Delta_J']:
            observed=np.array([r[metric].mean(),r[metric].std(ddof=1),r[metric].max()])
            saved=np.array([s[metric+'_mean'],s[metric+'_sd'],s[metric+'_best']])
            np.testing.assert_allclose(observed,saved,rtol=0,atol=1e-10)
            metric_checks[metric]={'raw_run_mean_sample_SD_best':observed.tolist(),
                                  'saved_mean_sample_SD_best':saved.tolist(),
                                  'absolute_tolerance':1e-10,'verified':True}
        a=annual.loc[np.isclose(annual.d,value)].sort_values('year')
        assert a.year.tolist()==list(range(2025,2040))
        assert a.run_id.nunique()==1 and a.run_id.iloc[0]==s.best_run_id
        ts=timing.loc[np.isclose(timing.d,value)]
        vals=ts.first_year.dropna().to_numpy()
        assert len(ts)==59 and ts.unit_id.nunique()==59 and len(vals)==expected_n
        assert np.all(vals==np.rint(vals)) and np.all((vals>=2025)&(vals<=2039))
        assert ts.loc[ts.first_year.isna(),'maintenance_count'].eq(0).all()
        assert ts.loc[ts.first_year.notna(),'maintenance_count'].gt(0).all()
        checks.append({'d':value,'independent_runs':30,'statistics':metric_checks,
                       'annual_years':a.year.astype(int).tolist(),
                       'representative_run_id':str(s.best_run_id),
                       'maintained_units':expected_n,'unmaintained_NA_units':int(ts.first_year.isna().sum()),
                       'raw_first_years':vals.tolist()})
    return checks


def figure7():
    """Parameter responses → representative trajectories → actual timing distributions."""
    names=FILES[1:]+['deterioration_runs_15y.csv']
    before={name:hashlib.sha256((style.RESULTS/name).read_bytes()).hexdigest() for name in names}
    d=pd.read_csv(style.RESULTS/FILES[1]).sort_values('d')
    annual=pd.read_csv(style.RESULTS/FILES[2]);timing=pd.read_csv(style.RESULTS/FILES[3])
    runs=pd.read_csv(style.RESULTS/'deterioration_runs_15y.csv')
    checks=validate_figure7_data(d,annual,timing,runs)
    dc=colors_d();muted=style.COLORS['muted'];ink=style.COLORS['ink']
    markers=['o','s','^'];linestyles=['-','--',':'];x=d.d.to_numpy()
    np.testing.assert_allclose(x,DVALUES,atol=1e-14,rtol=0)
    fig,axs=plt.subplots(2,2,figsize=style.figsize(7),
                         gridspec_kw={'height_ratios':[1,1.16]})
    fig.subplots_adjust(left=.109,right=.975,bottom=.126,top=.861,wspace=.35,hspace=.64)
    mean_annotations=[];artist_points={}
    for ax,metric,ylabel,letter,title in [
        (axs[0,0],'J',t('$J$（分）','$J$ (points)'),'a',t('长期平均评分响应','Long-term mean response')),
        (axs[0,1],'Delta_J',t('$\\Delta J$（分）','$\\Delta J$ (points)'),'b',t('相对养护增益响应','Maintenance-gain response'))]:
        # Only the three evaluated d values are connected. There is no interpolation.
        link=ax.plot(x,d[metric+'_mean'],color='#9DA8AF',lw=.8,zorder=2)[0]
        means=[];bests=[];segments=[];raw_run_points=[]
        for k,row in enumerate(d.itertuples()):
            value=float(getattr(row,metric+'_mean'));sd=float(getattr(row,metric+'_sd'))
            best=float(getattr(row,metric+'_best'));dv=float(row.d)
            r=runs.loc[np.isclose(runs.d,dv)].sort_values('run_id')
            raw_y=r[metric].to_numpy()
            # Deterministic display-only x offsets; no change to the actual metric values.
            permutation=(np.arange(len(r))*11)%len(r)
            display_x=dv+np.linspace(-.016,.016,len(r))[permutation]
            raw=ax.scatter(display_x,raw_y,s=7,c=dc[k],alpha=.26,marker='o',
                           edgecolors='none',zorder=2.1)
            np.testing.assert_array_equal(np.asarray(raw.get_offsets())[:,1],raw_y)
            raw_run_points.append({'d':dv,'n':len(r),'run_ids':r.run_id.tolist(),
                                   'original_metric_values':raw_y.tolist(),
                                   'display_only_x_offsets':(display_x-dv).tolist(),
                                   'actual_artist_offsets':np.asarray(raw.get_offsets()).tolist()})
            eb=ax.errorbar([dv],[value],yerr=[sd],color=dc[k],marker=markers[k],
                          ms=4.4,mec='white',mew=.55,lw=0,elinewidth=1.05,
                          capsize=3.0,capthick=.85,zorder=4)
            mean=np.asarray(eb.lines[0].get_xydata());means.append(mean.tolist())
            segments.append(np.asarray(eb.lines[2][0].get_segments()).tolist())
            point=ax.scatter([dv],[best],edgecolors=dc[k],facecolors='white',marker='D',
                             s=27,lw=1.05,zorder=5)
            bests.append(np.asarray(point.get_offsets()).tolist())
            # Saved mean labels are set beside the points, clear of the SD segments.
            ax.annotate(f'{value:.2f}',(dv,value),xytext=(6,-1),textcoords='offset points',
                        ha='left',va='center',fontsize=7.05,color=dc[k],
                        bbox={'facecolor':'white','edgecolor':'none','pad':.4},zorder=6)
            mean_annotations.append({'metric':metric,'d':dv,'raw_value':value,'printed':f'{value:.2f}'})
            np.testing.assert_array_equal(mean,np.array([[dv,value]]))
            np.testing.assert_array_equal(np.asarray(point.get_offsets()),[[dv,best]])
        np.testing.assert_array_equal(link.get_xydata(),np.c_[x,d[metric+'_mean']])
        artist_points[metric]={'mean_line':link.get_xydata().tolist(),'mean_points':means,
                              'sample_SD_segments':segments,'independent_best_points':bests,'raw_run_points':raw_run_points}
        ax.set(xlabel=t('年评分下降量 $d$（分/年）','Annual deterioration $d$ (points/year)'),
               ylabel=ylabel,xlim=(.40,.925),xticks=DVALUES)
        ax.set_xticklabels(['0.45','0.65','0.85'])
        ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
        style.grid(ax);style.panel(ax,letter,title)
    axs[0,0].set_ylim(89.2,93.48);axs[0,0].set_yticks([89.5,90.5,91.5,92.5,93.5])
    axs[0,1].set_ylim(5.30,6.285);axs[0,1].set_yticks([5.4,5.7,6.0,6.3])
    fig.legend(handles=[Line2D([],[],color=c,marker=m,lw=1.2,ls=ls,ms=3.8,
                              label=f'$d$ = {v:.2f}')
                        for v,c,m,ls in zip(DVALUES,dc,markers,linestyles)],
               loc='upper center',bbox_to_anchor=(.535,.997),ncol=3,fontsize=7.4,
               columnspacing=1.6,handletextpad=.4,borderaxespad=.15)
    # Statistic key is independent of the scenario colors and symbols.
    errkey=axs[0,0].errorbar([],[],yerr=[],marker='o',color=muted,lw=.8,
                            capsize=2.5,ms=3.2)
    fig.legend(handles=[Line2D([],[],color=muted,marker='o',markeredgewidth=0,alpha=.5,
                                   ls='none',ms=3),errkey,
                        Line2D([],[],color=muted,marker='D',markerfacecolor='white',ls='none',ms=3.7)],
               labels=[t('独立运行结果（每情景30次）','Individual runs ($n$ = 30/scenario)'),
                       t('均值 ± 样本SD','Mean ± sample SD'),
                       t('本情景独立最好值','Within-scenario best')],
               loc='upper center',bbox_to_anchor=(.535,.950),ncol=3,fontsize=6.65,
               columnspacing=1.15,handletextpad=.4,borderaxespad=.15)
    ax=axs[1,0];annual_artist_rows=[];endpoint_annotations=[]
    for value,c,ls,m in zip(DVALUES,dc,linestyles,markers):
        g=annual.loc[np.isclose(annual.d,value)].sort_values('year')
        curve=ax.plot(g.year,g.mean_score,color=c,ls=ls,marker=m,ms=2.65,lw=1.25,zorder=3)[0]
        np.testing.assert_array_equal(curve.get_xydata(),g[['year','mean_score']].to_numpy())
        endpoint=float(g.mean_score.iloc[-1]);last_year=int(g.year.iloc[-1])
        ax.annotate(f'{endpoint:.2f}',(last_year,endpoint),xytext=(5,0),textcoords='offset points',
                    ha='left',va='center',fontsize=7.0,color=c,
                    bbox={'facecolor':'white','edgecolor':'none','pad':.35},zorder=5)
        endpoint_annotations.append({'d':value,'year':last_year,'mean_score':endpoint,'printed':f'{endpoint:.2f}'})
        annual_artist_rows.append({'d':value,'actual_artist_year_score':curve.get_xydata().tolist()})
    ax.set(xlabel=t('年份（年）','Year'),ylabel=t('网络平均评分（分）','Network mean score (points)'),
           xticks=[2025,2032,2039],xlim=(2024.4,2041.6),ylim=(87.1,95.08),yticks=[88,90,92,94])
    ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
    style.grid(ax);style.panel(ax,'c',t('代表方案年度轨迹','Representative annual trajectories'))
    ax=axs[1,1]
    data=[timing.loc[np.isclose(timing.d,v),'first_year'].dropna().to_numpy() for v in DVALUES]
    # Numeric positions retain the same d meaning as the upper response panels.
    b=ax.boxplot(data,positions=DVALUES,widths=.092,patch_artist=True,showfliers=True,manage_ticks=False,
                 medianprops={'color':ink,'linewidth':1.3},boxprops={'linewidth':.9},
                 whiskerprops={'linewidth':.8},capprops={'linewidth':.8},
                 flierprops={'marker':'o','markersize':2.5,'markerfacecolor':'white'})
    raw_offsets=[];box_statistics=[]
    from matplotlib.cbook import boxplot_stats
    for j,(patch,c,vals,marker) in enumerate(zip(b['boxes'],dc,data,markers)):
        patch.set(facecolor=to_rgba(c,.09),edgecolor=c)
        for a in b['whiskers'][2*j:2*j+2]+b['caps'][2*j:2*j+2]:a.set_color(c)
        b['fliers'][j].set_markeredgecolor(c)
        offsets=np.zeros(len(vals),dtype=float)
        for year in np.unique(vals):
            indices=np.flatnonzero(vals==year)
            offsets[indices]=np.linspace(-.029,.029,len(indices)) if len(indices)>1 else 0
        pts=ax.scatter(DVALUES[j]+offsets,vals,s=5.3,c=c,marker=marker,
                       alpha=.5,edgecolors='none',zorder=3)
        np.testing.assert_array_equal(np.asarray(pts.get_offsets())[:,1],vals)
        stats=boxplot_stats(vals,whis=1.5)[0]
        box_statistics.append({'d':DVALUES[j],**{k:float(stats[k]) for k in ['q1','med','q3','whislo','whishi']},
                               'fliers':stats['fliers'].tolist()})
        raw_offsets.append({'d':DVALUES[j],'n':int(len(vals)),'original_years':vals.tolist(),
                            'actual_artist_offsets':np.asarray(pts.get_offsets()).tolist()})
    ax.set_xticks(DVALUES,[f'{v:.2f}\n$n$ = {len(vals)}' for v,vals in zip(DVALUES,data)])
    ax.set(xlabel=t('年评分下降量 $d$（分/年）','Annual deterioration $d$ (points/year)'),
           ylabel=t('首次养护年份（年）','First maintenance year'),
           xlim=(.37,.93),ylim=(2024.4,2037.2),yticks=[2025,2028,2031,2034,2037])
    ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
    style.grid(ax);style.panel(ax,'d',t('实际首次养护分布','Observed first-maintenance timing'))
    export=style.save(fig,7)
    assert not export['clipped_text'],export['clipped_text']
    after={name:hashlib.sha256((style.RESULTS/name).read_bytes()).hexdigest() for name in names}
    assert before==after
    REPORTS[7]={'export':export,'mean_annotations':mean_annotations,
        'numeric_response_coordinates':artist_points,'endpoint_annotations':endpoint_annotations,
        'raw_first_year_strip':raw_offsets,'box_statistics':box_statistics,
        'redesign':['numeric d response axes replacing categorical comparisons',
                    'ninety actual independent runs in each upper response panel, with narrow display-only horizontal offsets',
                    'three evaluated means linked without smoothing; scenario-specific marker/color and sample SD',
                    'separate independent-best diamonds retained on both responses',
                    'actual 15-point representative annual curves with observed 2039 score labels',
                    'numeric-d boxplots plus all integer first-year observations; unmaintained units remain NA'],
        'summary_rows':d[['d','J_mean','J_sd','J_best','Delta_J_mean','Delta_J_sd','Delta_J_best']].to_dict(orient='records'),
        'annual_rows':annual[['d','year','mean_score']].to_dict(orient='records')}
    audit={'all_passed':True,'figure':7,'language':style.LANGUAGE,'source_csv_sha256':before,
           'source_csv_unchanged':True,'raw_run_statistical_checks':checks,
           'all_annual_points_exactly_preserved':True,'all_first_year_y_values_exactly_preserved':True,
           'all_90_raw_run_metric_y_values_exactly_preserved_in_both_response_panels':True,
           'new_models_fitted':0,'new_optimization_runs':0,'interpolated_or_smoothed_points':0,
           'statistics_only_validated_against_frozen_raw_runs':True,'report':REPORTS[7],
           'output_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in (style.OUTPUT/'fig7').glob('Figure_07_redesigned.*')}}
    dest=style.OUTPUT/'validation'/'fig7_data_audit.json';dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    LAST_FIGURES[7]=fig
    return fig

def build_all():
    """Standalone drawing and exact frozen-data validation; no historic plotter dependency."""
    before=file_hashes()
    figure6();figure7()
    assert file_hashes()==before
    return {'all_passed':True,'language':style.LANGUAGE,'figures':REPORTS,
            'source_csv_sha256':before,'source_csv_unchanged':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language',choices=['zh','en'],default='zh')
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--project',type=Path,default=style.PROJECT)
    parser.add_argument('--figures',type=int,nargs='+',choices=[6,7],default=[6,7])
    args=parser.parse_args();style.configure(args.language,args.output,args.project)
    before=file_hashes()
    for number in args.figures:
        globals()[f'figure{number}']()
        plt.close(LAST_FIGURES[number])
    assert file_hashes()==before
    print(json.dumps({'all_passed':True,'figures':args.figures,
                      'source_csv_unchanged':True,'output':str(style.OUTPUT)},ensure_ascii=False))


if __name__=='__main__':main()
