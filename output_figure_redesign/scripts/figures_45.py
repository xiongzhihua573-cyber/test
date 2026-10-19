"""Redesign Figures 4/5 from included frozen data, without model execution.

Figure 4 uses exact numeric budget centers and all nonmissing paired runs.
Figure 5 uses verified saved means/sample SD, independent best values and
separate feasible bounds. Jitter is display-only; no smoothing or resampling.
"""
from pathlib import Path
import argparse,hashlib,json,os
os.environ.setdefault('MPLCONFIGDIR','/tmp/figure_redesign_45_mpl')
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.cbook import boxplot_stats
import figure_style as st


SOURCE_NAMES=['paired_schedule_comparison_runs_15y.csv',
              'paired_schedule_comparison_summary_15y.csv',
              'resource_level_summary_15y.csv',
              'resource_lower_bound_summary_15y.csv',
              'resource_level_runs_15y.csv']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def array(value):
    a=np.asarray(value,dtype=float)
    return {'shape':list(a.shape),'values':np.nan_to_num(a,nan=-999999.).tolist()}


def base_figure(number):
    fig=plt.figure(figsize=st.figsize(number))
    axes=[fig.add_axes([.087,.300,.385,.585]),
          fig.add_axes([.592,.300,.385,.585])]
    for ax in axes:st.grid(ax)
    return fig,axes


def resource_axis(ax,budgets):
    gap=np.min(np.diff(budgets))
    ax.set_xticks(budgets,[f'{x:.3f}' for x in budgets],rotation=35,ha='right',rotation_mode='anchor')
    ax.set_xlim(budgets.min()-.23*gap,budgets.max()+.23*gap)
    ax.set_xlabel(st.t('资源上限 $B$（全网络面积当量）',
                       'Resource limit $B$ (network-area equivalent)'),labelpad=3.5)


def figure4():
    """Pairwise schedule distributions with exact-B boxes and every raw run."""
    all_raw=pd.read_csv(st.RESULTS/'paired_schedule_comparison_runs_15y.csv')
    summary=pd.read_csv(st.RESULTS/'paired_schedule_comparison_summary_15y.csv')
    assert len(all_raw)==210 and len(summary)==7
    raw=all_raw[all_raw.both_feasible.astype(str).str.lower().eq('true')].copy()
    assert len(raw)==210 and not raw.duplicated(['level_id','seed']).any()
    raw=raw.sort_values(['level_id','seed'])
    budgets=np.sort(raw.B_limit.unique());gap=np.min(np.diff(budgets))
    assert len(budgets)==7
    g=summary.sort_values('B_limit')
    np.testing.assert_array_equal(g.B_limit.to_numpy(),budgets)
    fig,axes=base_figure(4)
    specs=[('Jaccard',st.COLORS['LOCF'],st.t('Jaccard 相似系数','Jaccard similarity'),
            st.t('排程重合度','Schedule overlap')),
           ('first_year_MAE',st.COLORS['Ridge'],
            st.t('双方均养护单元首次养护年\n平均绝对差（年）','First-maintenance-year MAE\nwithin jointly maintained units (years)'),
            st.t('首次养护年差','First-maintenance-year difference'))]
    records={};counts=[]
    for ax,(metric,color,ylabel,title),letter in zip(axes,specs,['a','b']):
        groups=[raw.loc[np.isclose(raw.B_limit,budget,rtol=0,atol=1e-12)].copy() for budget in budgets]
        values=[group[metric].dropna().to_numpy(float) for group in groups]
        n=[int(len(v)) for v in values];counts.append(n)
        np.testing.assert_array_equal(g[metric+'_n'].to_numpy(),n)
        boxes=ax.boxplot(values,positions=budgets,widths=gap*.46,patch_artist=True,
                          showfliers=True,manage_ticks=False,whis=1.5,
                          medianprops={'color':st.COLORS['ink'],'linewidth':1.05,'zorder':5},
                          boxprops={'edgecolor':color,'linewidth':.8},
                          whiskerprops={'color':color,'linewidth':.75},
                          capprops={'color':color,'linewidth':.75},
                          flierprops={'marker':'o','markersize':2.9,'markerfacecolor':'white',
                                      'markeredgecolor':color,'markeredgewidth':.7,'alpha':1,'zorder':6})
        for box in boxes['boxes']:box.set_facecolor(color);box.set_alpha(.12)
        data=[]
        for k,(budget,v,group) in enumerate(zip(budgets,values,groups)):
            # Display-only deterministic horizontal offsets; every y stays the raw value.
            rng=np.random.default_rng(4100+k)
            offsets=np.linspace(-.14*gap,.14*gap,len(v));rng.shuffle(offsets)
            points=ax.scatter(budget+offsets,v,s=7,color=color,alpha=.48,edgecolors='none',zorder=3)
            actual=np.asarray(points.get_offsets())
            np.testing.assert_array_equal(actual[:,1],v)
            np.testing.assert_array_equal(actual[:,0],budget+offsets)
            stats=boxplot_stats(v,whis=1.5)[0]
            for key,column in [('med',metric+'_median'),('q1',metric+'_Q25'),('q3',metric+'_Q75')]:
                np.testing.assert_allclose(stats[key],g.iloc[k][column],rtol=0,atol=1e-10)
            np.testing.assert_allclose(v.mean(),g.iloc[k][metric+'_mean'],rtol=0,atol=1e-10)
            actual_center=(boxes['boxes'][k].get_path().vertices[:,0].min()+
                           boxes['boxes'][k].get_path().vertices[:,0].max())/2
            np.testing.assert_allclose(actual_center,budget,rtol=0,atol=1e-12)
            np.testing.assert_allclose(boxes['medians'][k].get_ydata(),stats['med'],rtol=0,atol=1e-12)
            np.testing.assert_allclose(boxes['whiskers'][2*k].get_ydata(),[stats['q1'],stats['whislo']],rtol=0,atol=1e-12)
            np.testing.assert_allclose(boxes['whiskers'][2*k+1].get_ydata(),[stats['q3'],stats['whishi']],rtol=0,atol=1e-12)
            np.testing.assert_allclose(np.sort(boxes['fliers'][k].get_ydata()),np.sort(stats['fliers']),rtol=0,atol=1e-12)
            ax.text(budget,.968,f'n={len(v)}',transform=ax.get_xaxis_transform(),ha='center',va='top',
                    fontsize=6.5,color=st.COLORS['muted'])
            data.append({'B_limit':float(budget),'box_center':float(actual_center),
                         'valid_raw_count':len(v),'missing_raw_count':int(group[metric].isna().sum()),
                         'seed_order':group.loc[group[metric].notna(),'seed'].astype(int).tolist(),
                         'raw_y':array(v),'plotted_y_exact':True,'display_offsets':array(offsets),
                         'maximum_absolute_horizontal_display_offset':float(np.max(np.abs(offsets))),
                         'box_statistics':{key:float(stats[key]) for key in ['med','q1','q3','whislo','whishi']},
                         'fliers':array(stats['fliers']),'all_fliers_retained':True,
                         'saved_median_quartiles_mean_match':True})
        mean=ax.scatter(g.B_limit,g[metric+'_mean'],marker='D',s=21,facecolor='white',
                        edgecolor=st.COLORS['ink'],linewidths=.8,zorder=7)
        np.testing.assert_array_equal(mean.get_offsets(),np.column_stack([g.B_limit,g[metric+'_mean']]))
        records[metric]={'groups':data,'raw_points_plotted':sum(n),
                         'missing_excluded':int(raw[metric].isna().sum()),
                         'saved_mean_points':array(np.column_stack([g.B_limit,g[metric+'_mean']]))}
        resource_axis(ax,budgets);ax.set_ylabel(ylabel,labelpad=5);st.panel(ax,letter,title)
    assert counts==[[30]*7,[28,30,30,30,30,30,30]]
    axes[0].set_ylim(-.04,1.12);axes[0].set_yticks([0,.25,.5,.75,1])
    axes[1].set_ylim(-.15,4.0);axes[1].set_yticks([0,1,2,3])
    handles=[Line2D([0],[0],color=st.COLORS['muted'],marker='o',ms=3,ls='none',alpha=.6,
                    label=st.t('运行点','Run')),
             Line2D([0],[0],color=st.COLORS['ink'],marker='D',ms=4,mfc='white',ls='none',
                    label=st.t('均值','Mean')),
             Line2D([0],[0],color=st.COLORS['ink'],lw=1.1,label=st.t('中位数','Median')),
             Line2D([0],[0],color=st.COLORS['ink'],marker='o',ms=3,mfc='white',ls='none',
                    label=st.t('离群值','Outlier'))]
    fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.52,.012),ncol=4,
               fontsize=7.4,columnspacing=1.5,handletextpad=.5)
    return fig,{'paired_run_rows':len(raw),'counts_per_panel':counts,'plotted_scientific_arrays':records,
                 'whis':1.5,'numeric_box_centers':array(budgets),
                 'resource_axis':'actual numeric B, not category indices',
                 'jitter':'display-only deterministic horizontal offsets; every raw y exact',
                 'NA_policy':'dropna only; no zero imputation; 2 missing MAE values excluded at minimum B',
                 'box_statistics_and_saved_means_unchanged':True,'new_model_runs':0,
                 'new_optimization_runs':0,'scientific_numbers_changed':False}


def _resource_response_data():
    """Verify existing 30-run statistics; return saved values, never refit/reoptimize."""
    s=pd.read_csv(st.RESULTS/'resource_level_summary_15y.csv')
    bounds=pd.read_csv(st.RESULTS/'resource_lower_bound_summary_15y.csv')
    raw=pd.read_csv(st.RESULTS/'resource_level_runs_15y.csv')
    assert len(s)==len(bounds)==14 and len(raw)==420
    assert (s.algorithm=='GJO').all() and (s.n_runs==30).all() and (s.n_feasible==30).all()
    assert (s.sample_SD_ddof==1).all()
    assert (raw.planning_horizon==15).all() and (raw.start_year==2025).all() and (raw.end_year==2039).all()
    assert raw.feasible.astype(str).str.lower().eq('true').all()
    assert not raw.duplicated(['initial_condition','level_id','seed']).any()
    assert bounds.included_in_30_run_statistics.astype(str).str.lower().eq('false').all()
    checks=[]
    for row in s.itertuples(index=False):
        g=raw[(raw.initial_condition==row.initial_condition)&(raw.level_id==row.level_id)]
        assert len(g)==30 and g.B_limit.nunique()==1
        np.testing.assert_allclose(g.B_limit,row.B_limit,rtol=0,atol=1e-12)
        metrics={}
        for metric in ['J','Delta_J']:
            v=g[metric].to_numpy(float)
            assert np.isfinite(v).all()
            stats={'mean':float(v.mean()),'sd':float(v.std(ddof=1)),'best':float(v.max())}
            for stat,value in stats.items():
                np.testing.assert_allclose(value,getattr(row,metric+'_'+stat),rtol=0,atol=1e-10)
            metrics[metric]={'raw_mean':stats['mean'],'raw_sample_SD':stats['sd'],
                             'raw_independent_best':stats['best'],
                             'saved_mean':float(getattr(row,metric+'_mean')),
                             'saved_sample_SD':float(getattr(row,metric+'_sd')),
                             'saved_independent_best':float(getattr(row,metric+'_best'))}
        checks.append({'model':row.initial_condition,'level_id':int(row.level_id),
                       'B_limit':float(row.B_limit),'n_feasible_independent_runs':len(g),'metrics':metrics})
    return s,bounds,raw,checks


def figure5():
    """Actual-numeric-B response: saved mean, sample-SD band, best and bound."""
    s,bounds,raw,checks=_resource_response_data()
    budgets=np.sort(s.B_limit.unique())
    assert len(budgets)==7
    fig=plt.figure(figsize=st.figsize(5))
    axes=[fig.add_axes([.087,.300,.385,.565]),
          fig.add_axes([.592,.300,.385,.565])]
    specs=[('J',st.t('长期平均评分 $J$（分）','Long-term mean score $J$ (points)'),
            st.t('长期平均评分','Long-term mean score')),
           ('Delta_J',st.t('相对养护增益 $\\Delta J$（分）','Gain over own no-maintenance\nbaseline, $\\Delta J$ (points)'),
            st.t('相对养护增益','Relative maintenance gain'))]
    display={}
    for ax,(metric,ylabel,title),letter in zip(axes,specs,['a','b']):
        st.grid(ax);display[metric]={}
        for name in ['LOCF','Ridge']:
            g=s[s.initial_condition==name].sort_values('B_limit')
            lb=bounds[bounds.initial_condition==name].sort_values('B_limit')
            x=g.B_limit.to_numpy();y=g[metric+'_mean'].to_numpy();sd=g[metric+'_sd'].to_numpy()
            best=g[metric+'_best'].to_numpy();field='verified_feasible_'+metric+'_lower_bound'
            lower=lb[field].to_numpy();color=st.COLORS[name]
            np.testing.assert_array_equal(lb.B_limit.to_numpy(),x)
            np.testing.assert_array_equal(lb.independent_GJO_J_best.to_numpy(),g.J_best.to_numpy())
            # These are sample-SD bands around existing means, not confidence intervals.
            band=ax.fill_between(x,y-sd,y+sd,color=color,alpha=.20,lw=0,zorder=1)
            line,=ax.plot(x,y,color=color,marker='o' if name=='LOCF' else 's',
                          ls='-',ms=3.5,lw=1.25,markeredgecolor='white',markeredgewidth=.4,zorder=4)
            bound,=ax.plot(x,lower,color=color,lw=.75,ls=(0,(3,2)),zorder=3)
            best_points=ax.scatter(x,best,marker='D',s=21,facecolors='white',
                                    edgecolors=color,linewidths=.8,zorder=6)
            np.testing.assert_array_equal(line.get_xdata(),x);np.testing.assert_array_equal(line.get_ydata(),y)
            np.testing.assert_array_equal(best_points.get_offsets(),np.column_stack([x,best]))
            np.testing.assert_array_equal(bound.get_ydata(),lower)
            # Explicitly verify the plotted polygon contains the real mean±sample SD boundaries.
            vertices=np.concatenate([p.vertices for p in band.get_paths()])
            for k,xvalue in enumerate(x):
                actual=vertices[np.isclose(vertices[:,0],xvalue,rtol=0,atol=1e-12),1]
                assert np.any(np.isclose(actual,y[k]-sd[k],rtol=0,atol=1e-12))
                assert np.any(np.isclose(actual,y[k]+sd[k],rtol=0,atol=1e-12))
            display[metric][name]={'x':array(x),'mean':array(y),'sample_SD':array(sd),
                  'band_lower':array(y-sd),'band_upper':array(y+sd),
                  'independent_best':array(best),'verified_feasible_lower_bound':array(lower),
                  'band_vertices_match_actual_boundaries':True,'bound_in_30_run_statistics':False,
                  'numeric_B_axis':True,'smoothing_or_interpolation':False}
        resource_axis(ax,budgets);ax.set_ylabel(ylabel,labelpad=5);st.panel(ax,letter,title)
    axes[0].set_ylim(85.0,94.15);axes[0].set_yticks([86,88,90,92,94])
    axes[1].set_ylim(0,7.0);axes[1].set_yticks([0,2,4,6])
    model_handles=[Line2D([0],[0],color=st.COLORS['LOCF'],lw=1.25,marker='o',ms=3.5,label='LOCF'),
                   Line2D([0],[0],color=st.COLORS['Ridge'],lw=1.25,marker='s',ms=3.5,label='Ridge')]
    fig.legend(handles=model_handles,loc='upper center',bbox_to_anchor=(.54,1.006),
               ncol=2,fontsize=8.2,columnspacing=2.4,handletextpad=.6)
    stats_handles=[Line2D([0],[0],color=st.COLORS['ink'],lw=1.2,marker='o',ms=3,
                          label=st.t('均值','Mean')),
                   Patch(facecolor=st.COLORS['muted'],alpha=.22,edgecolor='none',
                         label=st.t('均值±样本SD','Mean ± sample SD')),
                   Line2D([0],[0],color=st.COLORS['ink'],marker='D',mfc='white',ms=4,ls='none',
                          label=st.t('本档独立最好','Independent best')),
                   Line2D([0],[0],color=st.COLORS['ink'],lw=.8,ls=(0,(3,2)),
                          label=st.t('已验证可行下界','Verified feasible bound'))]
    fig.legend(handles=stats_handles,loc='lower center',bbox_to_anchor=(.52,.010),
               ncol=4,fontsize=7.15,columnspacing=1.25,handletextpad=.45,handlelength=1.7)
    locf=s[s.initial_condition=='LOCF'].sort_values('B_limit')
    differences=np.diff(locf.J_mean.to_numpy());declines=np.flatnonzero(differences<0)
    assert declines.tolist()==[3]
    flagged=bounds[bounds.search_best_below_known_bound.astype(str).str.lower().eq('true')]
    assert len(flagged)==1 and flagged.iloc[0].initial_condition=='LOCF' and flagged.iloc[0].level_id==5
    row=flagged.iloc[0]
    assert row.independent_GJO_J_best<row.verified_feasible_J_lower_bound
    notes={'verified_raw_run_groups':checks,'plotted_scientific_arrays':display,
           'raw_rows':len(raw),'groups':14,'runs_per_group':30,'all_runs_feasible':True,
           'sample_SD_ddof':1,'uncertainty_semantics':'existing mean ± sample SD; not CI',
           'statistics_read_from_saved_summary':True,'raw_statistics_recomputed_for_validation_only':True,
           'resource_B_axis':'actual numeric, all seven discrete levels displayed; lines only guide the eye',
           'mean_SD_best_unchanged':True,'new_model_runs':0,'new_optimization_runs':0,
           'new_lower_bounds_recomputed':False,'scientific_numbers_changed':False,
           'adverse_results_preserved':{
               'LOCF_local_mean_decline':{'from_B':float(locf.iloc[3].B_limit),'to_B':float(locf.iloc[4].B_limit),
                   'from_J_mean':float(locf.iloc[3].J_mean),'to_J_mean':float(locf.iloc[4].J_mean)},
               'best_below_verified_feasible_lower_bound':{'initial_condition':'LOCF','level_id':int(row.level_id),
                   'B_limit':float(row.B_limit),'independent_best':float(row.independent_GJO_J_best),
                   'known_feasible_bound':float(row.verified_feasible_J_lower_bound)}}}
    return fig,notes


def build_all(audit_path=None,figures=(4,5)):
    """Render requested figures and audit frozen numeric data, not old geometry."""
    hashes={name:sha(st.RESULTS/name) for name in SOURCE_NAMES}
    audit={'all_passed':True,'model_runs':0,'optimization_runs':0,
           'scientific_numbers_changed':False,'source_hashes_before':hashes,
           'project':str(st.PROJECT),'language':st.LANGUAGE,'figures':{},
           'script_sha256':sha(__file__)}
    for current in figures:
        fig,notes=globals()[f'figure{current}']()
        notes.update(st.save(fig,current))
        assert not notes['clipped_text'],notes['clipped_text']
        notes['resource_tick_display_decimals']=3
        notes['files']={ext:{'path':str(st.OUTPUT/f'fig{current}'/f'Figure_{current:02d}_redesigned.{ext}'),
                             'sha256':sha(st.OUTPUT/f'fig{current}'/f'Figure_{current:02d}_redesigned.{ext}')}
                        for ext in ['png','svg','pdf','tiff']}
        audit['figures'][str(current)]=notes;plt.close(fig)
    audit['source_hashes_after']={name:sha(st.RESULTS/name) for name in SOURCE_NAMES}
    assert audit['source_hashes_before']==audit['source_hashes_after']
    target=Path(audit_path) if audit_path else st.OUTPUT/'validation'/'fig45_data_audit.json'
    target.parent.mkdir(exist_ok=True,parents=True)
    target.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    return audit


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--language',choices=['zh','en'],default='zh')
    parser.add_argument('--project',type=Path,default=st.PROJECT)
    parser.add_argument('--output',type=Path,default=st.OUTPUT)
    parser.add_argument('--audit',type=Path)
    parser.add_argument('--figures',type=int,nargs='+',choices=[4,5],default=[4,5])
    args=parser.parse_args();st.configure(args.language,args.output,args.project)
    result=build_all(args.audit,args.figures)
    print(json.dumps({'all_passed':result['all_passed'],
                      'clipped_text':{n:d['clipped_text'] for n,d in result['figures'].items()}},ensure_ascii=False))


if __name__=='__main__':main()
