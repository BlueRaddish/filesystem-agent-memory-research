"""Render exact summary tables and three PNG/SVG pairs. Existing outputs must match.

python evaluation/sprint-2026-10-15/packing/render.py
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
METHODS = ('two_windows', 'radius3', 'radius8', 'whole_body', 'residual_gaps')
LABELS = ('Two windows', 'Radius 3', 'Radius 8', 'Whole body', 'Residual gaps')
COLORS = ('#555555', '#4477aa', '#228833', '#cc6677', '#aa3377')


def write(path, text):
    if path.exists():
        assert path.read_text(encoding='utf8') == text
    else:
        path.write_text(text, encoding='utf8', newline='\n')


def main():
    data = json.loads((HERE/'run/results.json').read_text(encoding='utf8'))
    out = HERE/'figures'
    out.mkdir(exist_ok=True)
    cells = data['cells']
    for name, table in (('cells', cells), ('templates', data['template_cells'])):
        write(out/(name+'.json'), json.dumps(table, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n')
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                         'svg.hashsalt': 'packing-exploratory-20261015'})
    def export(fig, name):
        fig.savefig(out/(name+'.png'), dpi=170, bbox_inches='tight')
        fig.savefig(out/(name+'.svg'), bbox_inches='tight', metadata={'Date': None})
        plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7), sharey=True)
    for ax, ranker in zip(axes, ('body_bm25', 'entity_rrf')):
        for m, label, color in zip(METHODS, LABELS, COLORS):
            rows = sorted([r for r in cells if r['ranker'] == ranker and r['method'] == m], key=lambda r: r['budget'])
            ax.plot([r['budget']/1024 for r in rows], [r['span_complete'] for r in rows], marker='o', label=label, color=color)
        ax.set(title=ranker, xlabel='Rendered packet budget (KiB)', xticks=[4, 8, 16], ylim=(0, 225))
        ax.grid(axis='y', alpha=.2)
    axes[0].set_ylabel('Complete authored span alternatives / 216')
    axes[1].legend(loc='upper left', bbox_to_anchor=(1.02, 1), fontsize=9)
    fig.suptitle('Broader context recovers governing text on the existing synthetic bank')
    fig.tight_layout()
    export(fig, '01-span-recovery')
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True)
    x = np.arange(5)
    for ax, ranker in zip(axes, ('body_bm25', 'entity_rrf')):
        rows = [next(r for r in cells if r['ranker'] == ranker and r['method'] == m and r['budget'] == 8192) for m in METHODS]
        source = np.array([r['mean_source_bytes']/1024 for r in rows])
        wrapper = np.array([r['mean_wrapper_separator_bytes']/1024 for r in rows])
        unused = np.array([r['mean_unused_bytes']/1024 for r in rows])
        ax.bar(x, source, label='Source text', color='#4477aa')
        ax.bar(x, wrapper, bottom=source, label='Wrappers / separators', color='#ddaa33')
        ax.bar(x, unused, bottom=source+wrapper, label='Unused', color='#dddddd')
        ax.set(title=ranker, xticks=x, xticklabels=LABELS, ylim=(0, 8.6))
        ax.tick_params(axis='x', labelrotation=30)
    axes[0].set_ylabel('Mean KiB per 8 KiB budget')
    axes[1].legend(loc='upper left', bbox_to_anchor=(1.02, 1), fontsize=9)
    fig.suptitle('Equal budgets do not imply equal text exposure')
    fig.tight_layout()
    export(fig, '02-budget-composition')
    templates = sorted({r['template_family'] for r in data['template_cells']})
    fig, axes = plt.subplots(1, 2, figsize=(12, 7), sharey=True)
    for ax, ranker in zip(axes, ('body_bm25', 'entity_rrf')):
        matrix = [[next(r['span_complete'] for r in data['template_cells'] if r['ranker'] == ranker and r['method'] == m and r['budget'] == 8192 and r['template_family'] == t) for m in METHODS] for t in templates]
        image = ax.imshow(matrix, vmin=0, vmax=18, cmap='Blues', aspect='auto')
        for y, row in enumerate(matrix):
            for x, v in enumerate(row):
                ax.text(x, y, str(v), ha='center', va='center', color='white' if v >= 11 else 'black', fontsize=9)
        ax.set(title=ranker, xticks=range(5), xticklabels=LABELS, yticks=range(12), yticklabels=templates)
        ax.tick_params(axis='x', labelrotation=30)
    fig.suptitle('Template dependence at 8 KiB: complete span alternatives / 18 per row')
    fig.tight_layout(rect=(0, 0, .94, .96))
    fig.colorbar(image, ax=axes, location='right', fraction=.025, pad=.02, label='Queries / 18')
    export(fig, '03-template-dependence')
    print('PASS: exact cells/templates JSON and three PNG/SVG pairs rendered')


if __name__ == '__main__':
    main()
