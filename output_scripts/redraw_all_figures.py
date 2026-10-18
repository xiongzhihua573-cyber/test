#!/usr/bin/env python3
"""Generate all seven paper figures from included frozen data; never fits models.

Chinese: python redraw_all_figures.py
English: python redraw_all_figures.py --language en --output-dir ../figures_en
The CSVs are saved scientific results. No training, optimization, or inference runs.
"""
from pathlib import Path
import argparse,importlib,json,hashlib
HERE=Path(__file__).resolve().parent
MODULES={1:'figures16_123',2:'figures16_123',3:'figures16_123',4:'figures16_45',5:'figures16_45',6:'figures16_67',7:'figures16_67'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language',choices=['zh','en'],default='zh')
    parser.add_argument('--project',type=Path,default=HERE/'project_data')
    parser.add_argument('--output-dir',type=Path,default=HERE.parent/'output_figures_redrawn')
    parser.add_argument('--figures',type=int,nargs='+',choices=range(1,8),default=list(range(1,8)))
    args=parser.parse_args()
    import figure16_style as style
    style.configure(args.language,output=args.output_dir,project=args.project)
    frozen={str(p.relative_to(args.project)):hashlib.sha256(p.read_bytes()).hexdigest() for p in args.project.rglob('*.csv')}
    result={}
    import matplotlib.pyplot as plt
    for number in args.figures:
        module=importlib.import_module(MODULES[number])
        function=getattr(module,f'figure{number}')
        value=function()
        if number in (4,5):
            figure, scientific_notes=value
            layout=style.save(figure,number)
        elif isinstance(value,dict):
            layout=value
        else:
            layout=module.REPORTS[number]['export']
        if layout.get('clipped_text'):
            raise RuntimeError(f'Clipped text in figure {number}: {layout["clipped_text"]}')
        for ext in ['png','svg','pdf']:
            p=args.output_dir/f'Figure_{number:02}_redrawn.{ext}'
            if not p.is_file():raise RuntimeError(f'Missing generated figure: {p}')
        result[str(number)]={'formats':['PNG600dpi','SVG','PDF'],'clipped_text':layout.get('clipped_text',[]),'files':{ext:hashlib.sha256((args.output_dir/f'Figure_{number:02}_redrawn.{ext}').read_bytes()).hexdigest() for ext in ['png','svg','pdf']}}
        plt.close('all')
    assert all(hashlib.sha256((args.project/name).read_bytes()).hexdigest()==h for name,h in frozen.items()),'Frozen CSV modified'
    record={'language':args.language,'figures':result,'source_csv_sha256':frozen,'models_fitted':0,'optimizations_run':0,'scientific_statistics_reestimated':False}
    (args.output_dir/'render_manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
    print(json.dumps({'language':args.language,'figures_generated':len(result),'source_csvs_unchanged':True,'output':str(args.output_dir)},ensure_ascii=False))

if __name__=='__main__':main()
