"""Second-round Figures 4/5: redesign only, using frozen saved results.

The original boxes and every mean/SD/best series are verified against the
original plotter. Added means and feasible lower bounds are read from saved
summary CSVs, never estimated or mixed into the 30 independent runs.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os
os.environ.setdefault('MPLCONFIGDIR','/tmp/fig16_45_mpl')
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.collections import LineCollection,PathCollection
from matplotlib.container import ErrorbarContainer
import figure16_style as st


SOURCE_NAMES=['paired_schedule_comparison_runs_15y.csv',
              'paired_schedule_comparison_summary_15y.csv',
              'resource_level_summary_15y.csv',
              'resource_lower_bound_summary_15y.csv']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def array(value):
    a=np.asarray(value,dtype=float)
    return {'shape':list(a.shape),'values':np.nan_to_num(a,nan=-999999.).tolist()}


def scientific_artists(fig):
    result=[]
    for ax in fig.axes:
        collections=[]
        for item in ax.collections:
            if isinstance(item,LineCollection):
                collections.append({'type':'error_segments','segments':[array(v) for v in item.get_segments()]})
            elif isinstance(item,PathCollection):
                collections.append({'type':'point_locations','offsets':array(item.get_offsets())})
            else:raise AssertionError(type(item))
        result.append({'lines':[{'x':array(line.get_xdata()),'y':array(line.get_ydata())} for line in ax.lines],
                       'collections':collections,'patches':[array(p.get_path().vertices) for p in ax.patches]})
    return result


def original_capture(number):
    spec=importlib.util.spec_from_file_location('original16_45',st.PROJECT/'scripts/plot_figures_sci.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    captured=[]
    def record(fig,out,name):captured.append(scientific_artists(fig));plt.close(fig)
    mod.save=record;mod.setup('zh');getattr(mod,f'figure{number}')(st.RESULTS,st.OUTPUT)
    assert len(captured)==1
    return captured[0]


def base_figure(number):
    fig=plt.figure(figsize=st.figsize(number))
    axes=[fig.add_axes([.087,.355,.385,.510]),
          fig.add_axes([.592,.355,.385,.510])]
    for ax in axes:st.grid(ax)
    return fig,axes


def resource_axis(ax,budgets):
    gap=np.min(np.diff(budgets))
    ax.set_xticks(budgets,[f'{x:.6f}' for x in budgets],rotation=40,ha='right',rotation_mode='anchor')
    ax.set_xlim(budgets.min()-.23*gap,budgets.max()+.23*gap)
    ax.set_xlabel(st.t('资源上限 $B$（全网络面积当量）',
                       'Resource limit $B$ (network-area equivalent)'),labelpad=3.5)


def figure4():
    raw=pd.read_csv(st.RESULTS/SOURCE_NAMES[0]);summary=pd.read_csv(st.RESULTS/SOURCE_NAMES[1])
    assert len(raw)==210
    raw=raw[raw.both_feasible.astype(str).str.lower().eq('true')]
    assert not raw.duplicated(['level_id','seed']).any()
    budgets=np.sort(raw.B_limit.unique());gap=np.min(np.diff(budgets))
    assert len(budgets)==7
    fig,axes=base_figure(4)
    specs=[('Jaccard','Jaccard_mean','Jaccard_n',st.COLORS['LOCF'],
            st.t('Jaccard 相似系数','Jaccard similarity'),st.t('排程重合度','Schedule overlap')),
           ('first_year_MAE','first_year_MAE_mean','first_year_MAE_n',st.COLORS['Ridge'],
            st.t('双方均养护单元首次养护年\n平均绝对差（年）','First-maintenance-year MAE\nwithin jointly maintained units (years)'),
            st.t('首次养护年差','First-maintenance-year difference'))]
    counts=[]
    for ax,spec,letter in zip(axes,specs,['a','b']):
        metric,mean_column,n_column,color,ylabel,title=spec
        values=[]
        for budget in budgets:
            v=raw.loc[np.isclose(raw.B_limit,budget),metric].dropna()
            values.append(v.to_numpy() if len(v) else np.array([np.nan]))
        counts.append([int(np.isfinite(v).sum()) for v in values])
        boxes=ax.boxplot(values,positions=budgets,widths=gap*.46,patch_artist=True,
                          showfliers=True,manage_ticks=False,whis=1.5,
                          medianprops={'color':st.COLORS['ink'],'linewidth':1.15},
                          boxprops={'edgecolor':color,'linewidth':.85},
                          whiskerprops={'color':color,'linewidth':.8},
                          capprops={'color':color,'linewidth':.8},
                          flierprops={'marker':'o','markersize':2.9,'markerfacecolor':'white',
                                      'markeredgecolor':color,'markeredgewidth':.7,'alpha':1})
        for box in boxes['boxes']:box.set_facecolor(color);box.set_alpha(.18)
        resource_axis(ax,budgets);ax.set_ylabel(ylabel,labelpad=5);st.panel(ax,letter,title)
    axes[0].set_ylim(-.02,1.02)
    old_series=scientific_artists(fig)
    assert counts==[[30]*7,[28,30,30,30,30,30,30]]
    added={}
    for ax,spec in zip(axes,specs):
        metric,mean_column,n_column,color,_,_=spec
        g=summary.sort_values('B_limit')
        np.testing.assert_array_equal(g.B_limit.to_numpy(),budgets)
        np.testing.assert_array_equal(g[n_column].to_numpy(),np.asarray(counts[0 if metric=='Jaccard' else 1]))
        artist=ax.scatter(g.B_limit,g[mean_column],marker='D',s=22,facecolor='white',
                          edgecolor=st.COLORS['ink'],linewidths=.85,zorder=6)
        np.testing.assert_array_equal(artist.get_offsets(),np.column_stack([g.B_limit,g[mean_column]]))
        added[metric]={'column':mean_column,'x':array(g.B_limit),'y':array(g[mean_column]),
                       'counts':g[n_column].astype(int).tolist(),'artist_matches_frozen_summary':True}
    fig.text(.535,.97,st.t('每档 30 组配对；首次养护年 MAE：最低档 n = 28，其余各档 n = 30',
                            '30 pairs per level; first-year MAE: n = 28 at the lowest level, otherwise n = 30'),
             ha='center',va='top',fontsize=7.3)
    handles=[Line2D([0],[0],color=st.COLORS['ink'],lw=1.1,label=st.t('箱内横线：中位数','Box line: median')),
             Line2D([0],[0],color=st.COLORS['ink'],marker='D',ms=4,mfc='white',ls='none',
                    label=st.t('菱形：已有均值','Diamond: saved mean')),
             Line2D([0],[0],color=st.COLORS['ink'],marker='o',ms=3,mfc='white',ls='none',
                    label=st.t('圆点：离群值（1.5×IQR）','Circle: outlier (1.5×IQR)'))]
    fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.52,.055),ncol=3,
               fontsize=7.4,columnspacing=1.5,handletextpad=.5)
    return fig,{'original_series':old_series,'mean_points':added,'counts_per_panel':counts,
                 'whis':1.5,'NA_policy':'dropna; no zero imputation',
                 'new_means_recomputed':False,'new_model_runs':0}


def figure5():
    s=pd.read_csv(st.RESULTS/SOURCE_NAMES[2]);bounds=pd.read_csv(st.RESULTS/SOURCE_NAMES[3])
    assert len(s)==len(bounds)==14
    assert (s.algorithm=='GJO').all() and (s.n_runs==30).all() and (s.n_feasible==30).all()
    assert (s.sample_SD_ddof==1).all()
    assert bounds.included_in_30_run_statistics.astype(str).str.lower().eq('false').all()
    budgets=np.sort(s.B_limit.unique())
    fig,axes=base_figure(5)
    for ax in axes:
        x,y,w,h=ax.get_position().bounds
        ax.set_position([x,.375,w,.490])
    specs=[('J',st.t('长期平均评分 $J$（分）','Long-term mean score $J$ (points)'),
            st.t('绝对状态水平','Absolute condition level')),
           ('Delta_J',st.t('相对本初值无养护增益\n$\\Delta J$（分）','Gain over its own no-maintenance\nbaseline, $\\Delta J$ (points)'),
            st.t('相对养护增益','Relative maintenance gain'))]
    for ax,(metric,ylabel,title),letter in zip(axes,specs,['a','b']):
        for name in ['LOCF','Ridge']:
            g=s[s.initial_condition==name].sort_values('B_limit');color=st.COLORS[name]
            ax.errorbar(g.B_limit,g[metric+'_mean'],yerr=g[metric+'_sd'].fillna(0),
                        color=color,marker='o' if name=='LOCF' else 's',
                        ls='-' if name=='LOCF' else '--',ms=3.5,lw=1.3,capsize=2.4,
                        markeredgecolor='white',markeredgewidth=.4,elinewidth=.8,zorder=4)
            ax.scatter(g.B_limit,g[metric+'_best'],marker='D',s=23,facecolors='white',
                       edgecolors=color,linewidths=.85,zorder=7)
        resource_axis(ax,budgets);ax.set_ylabel(ylabel,labelpad=5);st.panel(ax,letter,title)
    old_series=scientific_artists(fig)
    added={}
    for ax,(metric,_,_) in zip(axes,specs):
        field='verified_feasible_'+metric+'_lower_bound'
        added[metric]={}
        for name in ['LOCF','Ridge']:
            g=bounds[bounds.initial_condition==name].sort_values('B_limit')
            independent=s[s.initial_condition==name].sort_values('B_limit')
            np.testing.assert_array_equal(g.B_limit,independent.B_limit)
            np.testing.assert_array_equal(g.independent_GJO_J_best,independent.J_best)
            line,=ax.plot(g.B_limit,g[field],color=st.COLORS[name],lw=.65,ls=(0,(1,2.4)),
                          marker='_',ms=10,mew=1.15,zorder=5)
            np.testing.assert_array_equal(line.get_xdata(),g.B_limit)
            np.testing.assert_array_equal(line.get_ydata(),g[field])
            added[metric][name]={'column':field,'x':array(g.B_limit),'y':array(g[field]),
                                'artist_matches_frozen_summary':True,
                                'included_in_30_run_statistics':False}
    # The single shortfall is explicitly marked using its saved flag and values.
    flagged=bounds[bounds.search_best_below_known_bound.astype(str).str.lower().eq('true')]
    assert len(flagged)==1 and flagged.iloc[0].initial_condition=='LOCF' and flagged.iloc[0].level_id==5
    row=flagged.iloc[0]
    axes[0].annotate(st.t('LOCF：B = 1.915337\n独立最好 < 既有下界',
                            'LOCF: B = 1.915337\nIndependent best < known bound'),
                     xy=(row.B_limit,row.verified_feasible_J_lower_bound),xycoords='data',
                     xytext=(.73,.43),textcoords='axes fraction',fontsize=7.1,
                     ha='center',va='top',color=st.COLORS['ink'],
                     arrowprops={'arrowstyle':'->','color':st.COLORS['muted'],'lw':.55,
                                 'shrinkA':3,'shrinkB':3},
                     bbox={'boxstyle':'square,pad=.20','facecolor':'white','edgecolor':'none'},zorder=8)
    model_handles=[Line2D([0],[0],color=st.COLORS['LOCF'],lw=1.3,marker='o',ms=3.5,label='LOCF'),
                   Line2D([0],[0],color=st.COLORS['Ridge'],lw=1.3,ls='--',marker='s',ms=3.5,label='Ridge')]
    model_legend=fig.legend(handles=model_handles,loc='upper center',bbox_to_anchor=(.54,1.006),
                            ncol=2,fontsize=8.2,columnspacing=2.4,handletextpad=.6)
    stats_handles=[Line2D([0],[0],color=st.COLORS['ink'],lw=1.0,marker='o',ms=3,
                         label=st.t('可行均值±样本 SD（30 次）','Feasible mean ± sample SD (30 runs)')),
                   Line2D([0],[0],color=st.COLORS['ink'],marker='D',mfc='white',ms=4,ls='none',
                         label=st.t('本档独立最好值','Independent best at this level')),
                   Line2D([0],[0],color=st.COLORS['ink'],marker='_',ms=10,mew=1.1,lw=.65,ls=(0,(1,2.4)),
                         label=st.t('已验证可行下界¹','Verified feasible lower bound¹'))]
    fig.legend(handles=stats_handles,loc='lower center',bbox_to_anchor=(.52,.073),
               ncol=3,fontsize=7.3,columnspacing=1.35,handletextpad=.5)
    fig.text(.52,.023,st.t('¹ 既有可行方案验证结果；独立展示，不计入 30 次运行统计。',
                           '¹ Previously verified feasible schedules; displayed separately, excluded from the 30-run statistics.'),
             ha='center',va='bottom',fontsize=6.9,color=st.COLORS['muted'])
    return fig,{'original_series':old_series,'verified_lower_bound_points':added,
                'mean_SD_best_unchanged':True,'sample_SD_ddof':1,'runs_per_level':30,
                'new_lower_bounds_recomputed':False,'new_model_runs':0,
                'shortfall_annotation':{'initial_condition':'LOCF','level_id':int(row.level_id),
                                        'B_limit':float(row.B_limit),
                                        'independent_best':float(row.independent_GJO_J_best),
                                        'known_feasible_bound':float(row.verified_feasible_J_lower_bound)}}


def build_all(audit_path=None):
    hashes={name:sha(st.RESULTS/name) for name in SOURCE_NAMES}
    audit={'all_passed':True,'model_runs':0,'statistics_recomputed':False,
           'source_hashes_before':hashes,'project':str(st.PROJECT),
           'language':st.LANGUAGE,'figures':{}}
    for current,prior,fn in [(4,6,figure4),(5,4,figure5)]:
        before=original_capture(prior)
        st.configure(st.LANGUAGE,output=st.OUTPUT,project=st.PROJECT)
        fig,notes=fn();original=notes.pop('original_series')
        assert before==original,f'Original numeric series mismatch: Figure {current}'
        layout=st.save(fig,current)
        notes.update(layout)
        notes['original_numeric_artists_exactly_equal']=True
        notes['original_numeric_artist_sha256']=hashlib.sha256(json.dumps(original,sort_keys=True).encode()).hexdigest()
        notes['files']={ext:{'path':str(st.OUTPUT/f'Figure_{current:02d}_redrawn.{ext}'),
                             'sha256':sha(st.OUTPUT/f'Figure_{current:02d}_redrawn.{ext}')}
                        for ext in ['png','svg','pdf']}
        audit['figures'][str(current)]=notes;plt.close(fig)
    audit['source_hashes_after']={name:sha(st.RESULTS/name) for name in SOURCE_NAMES}
    assert audit['source_hashes_before']==audit['source_hashes_after']
    target=Path(audit_path) if audit_path else st.WORK/'f45_redrawn_audit.json'
    target.parent.mkdir(exist_ok=True,parents=True)
    target.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    return audit


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--language',choices=['zh','en'],default='zh')
    parser.add_argument('--project',type=Path,default=st.PROJECT)
    parser.add_argument('--output',type=Path,default=st.OUTPUT)
    parser.add_argument('--audit',type=Path)
    args=parser.parse_args();st.configure(args.language,args.output,args.project)
    result=build_all(args.audit)
    print(json.dumps({'all_passed':result['all_passed'],
                      'clipped_text':{n:d['clipped_text'] for n,d in result['figures'].items()}},ensure_ascii=False))


if __name__=='__main__':main()
