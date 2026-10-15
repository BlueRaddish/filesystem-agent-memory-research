"""Four descriptive supplement figures; frozen primary figures are untouched."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

LABELS = ('supported', 'contradicted', 'not_established', 'not_auditable')
COLORS = ('#267b91', '#bd675c', '#ac94b9', '#c5cbd0')
BLOCKS = ('direct', 'oracle', 'discovery')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def projection(rows):
    """Recount raw labels and frozen flags instead of copying summary totals."""
    result = {}
    for block in BLOCKS:
        selected = [r for r in rows if r['block'] == block]
        if not selected:
            continue
        marginals = {}
        for key in ('answer_field', 'status', 'citation', 'full_query'):
            entries = ([v for r in selected for v in r['judgment']['answer_judgments'].values()]
                       if key == 'answer_field' else [r['judgment'][key+'_judgment'] for r in selected])
            counts = Counter(e['label'] for e in entries)
            assert not set(counts)-set(LABELS)
            marginals[key] = {'n': len(entries), 'counts': [counts[label] for label in LABELS]}
            assert len(entries) > 0 and sum(marginals[key]['counts']) == len(entries)
        arms = {}
        matrix = [[0, 0], [0, 0]]
        for row in selected:
            j = row['judgment']
            support = all(e['label'] == 'supported' for e in
                          [*j['answer_judgments'].values(), j['status_judgment']])
            gates = row['frozen_primary_gates']
            assert type(gates['typed_answer_status_match']) is bool
            assert type(gates['complete_task']) is bool
            assert row['descriptive_flags']['all_values_and_status_supported'] is support
            matrix[0 if support else 1][0 if gates['typed_answer_status_match'] else 1] += 1
            arm = arms.setdefault(row['arm'], {'n': 0, 'supported': 0, 'typed': 0, 'complete': 0})
            arm['n'] += 1
            arm['supported'] += support
            arm['typed'] += gates['typed_answer_status_match']
            arm['complete'] += gates['complete_task']
        result[block] = {'n': len(selected), 'marginals': marginals, 'arms': arms, 'matrix': matrix}
    return result


def self_check():
    def row(case_id, labels, support, typed, complete):
        return {'case_id': case_id, 'block': 'direct', 'arm': 'fictional',
            'judgment': {'answer_judgments': {str(i): {'label': v} for i, v in enumerate(labels)},
                'status_judgment': {'label': 'supported'}, 'citation_judgment': {'label': 'not_established'},
                'full_query_judgment': {'label': 'supported'}},
            'frozen_primary_gates': {'typed_answer_status_match': typed, 'complete_task': complete},
            'descriptive_flags': {'all_values_and_status_supported': support}}
    rows = [row('a', ['supported', 'contradicted'], False, True, False),
            row('b', ['supported'], True, False, False)]
    p = projection(rows)['direct']
    assert p['marginals']['answer_field'] == {'n': 3, 'counts': [2, 1, 0, 0]}
    assert p['marginals']['status']['n'] == 2
    assert p['matrix'] == [[0, 1], [1, 0]]
    assert p['arms']['fictional'] == {'n': 2, 'supported': 1, 'typed': 1, 'complete': 0}
    rows[0]['descriptive_flags']['all_values_and_status_supported'] = True
    try:
        projection(rows)
    except AssertionError:
        pass
    else:
        raise AssertionError('inconsistent source flag accepted')
    return {'state': 'PASS', 'fixture_groups': 4, 'expected_rejections': 1}


def render(args):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    raw = args.input.read_bytes()
    assert sha(raw) == args.input_sha256
    data = json.loads(raw)
    rows = data['cases']
    assert len(rows) == len({r['case_id'] for r in rows}) == 192
    p = projection(rows)
    assert {k: v['n'] for k, v in p.items()} == {'direct': 120, 'oracle': 24, 'discovery': 48}
    contexts = data['execution_context_census']
    assert len(contexts) == 11
    assert sum(c['reviewed_cases'] for c in contexts if c['cohort'] == 'initial') == 85
    assert sum(c['reviewed_cases'] for c in contexts if c['cohort'] == 'recovery') == 107
    assert not args.output.exists()
    args.output.mkdir()
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
        'axes.spines.top': False, 'axes.spines.right': False, 'svg.hashsalt': 'oct13-semantic-descriptive'})
    tables = {'input_sha256': sha(raw), 'by_block': p, 'execution_contexts': contexts}
    table_raw = (json.dumps(tables, indent=2, sort_keys=True)+'\n').encode()
    (args.output/'figure-tables.json').write_bytes(table_raw)
    registry = []

    def save(fig, name, description):
        exports = {}
        for suffix in ('png', 'svg'):
            path = args.output/(name+'.'+suffix)
            fig.savefig(path, dpi=160, facecolor='white', metadata={'Creator': 'Filesystem Agent Memory Research'})
            exports[suffix] = {'file': path.name, 'sha256': sha(path.read_bytes()), 'bytes': path.stat().st_size}
        plt.close(fig)
        registry.append({'id': name, 'description': description, 'exports': exports})

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.1))
    keys = ('answer_field', 'status', 'citation', 'full_query')
    names = ('Answer fields', 'Status', 'Citation', 'Full query')
    for ax, block in zip(axes, BLOCKS):
        left = np.zeros(4)
        for i, (label, color) in enumerate(zip(LABELS, COLORS)):
            values = [100*p[block]['marginals'][k]['counts'][i]/p[block]['marginals'][k]['n'] for k in keys]
            ax.barh(range(4), values, left=left, color=color, label=label.replace('_', ' '))
            for y, (x, w) in enumerate(zip(left, values)):
                if w >= 9:
                    ax.text(x+w/2, y, str(p[block]['marginals'][keys[y]]['counts'][i]),
                            ha='center', va='center', color='white' if i == 0 else '#20252b', fontsize=9)
            left += values
        ax.set(yticks=range(4), yticklabels=names, xlim=(0, 118), xticks=[0, 25, 50, 75, 100],
               xlabel='Share of labels (%)', title=block.capitalize()+' (artifacts n='+str(p[block]['n'])+')')
        ax.invert_yaxis()
        for y, k in enumerate(keys):
            ax.text(102, y, 'n='+str(p[block]['marginals'][k]['n']), va='center', fontsize=9)
    fig.suptitle('S1. Evidence-support labels by review dimension', fontsize=17, y=.98)
    fig.legend(*axes[0].get_legend_handles_labels(), loc='upper center', bbox_to_anchor=(.5, .91), ncol=4, frameon=False)
    fig.text(.02, .035, 'One LLM judgment per artifact. Answer fields and artifact-level dimensions have different denominators.\nDescriptive counts; no uncertainty or human-validation claim. Oracle is a separate control block.', fontsize=10)
    fig.subplots_adjust(left=.07, right=.97, top=.74, bottom=.23, wspace=.45)
    save(fig, 'S1-label-marginals', 'Four exclusive labels within each dimension; blocks and units remain separate.')

    fig, axes = plt.subplots(3, 1, figsize=(13, 12), gridspec_kw={'height_ratios': [5, 2, 4]})
    for ax, block in zip(axes, BLOCKS):
        arms = sorted(p[block]['arms'])
        y = np.arange(len(arms))
        for offset, key, color, name in [(-.24, 'supported', COLORS[0], 'All values + status supported'),
                (0, 'typed', '#78838e', 'Frozen typed agreement'),
                (.24, 'complete', '#c89d45', 'Frozen complete task')]:
            vals = [p[block]['arms'][a][key] for a in arms]
            ax.barh(y+offset, vals, height=.21, color=color, label=name)
            for i, v in enumerate(vals):
                ax.text(v+.25, y[i]+offset, str(v)+'/'+str(p[block]['arms'][arms[i]]['n']), va='center', fontsize=9)
        limit = max(p[block]['arms'][a]['n'] for a in arms)
        ax.set(yticks=y, yticklabels=[a.replace('_', ' ') for a in arms], xlim=(0, limit+4),
               xticks=list(range(0, limit+1, 4)), xlabel='Artifacts', title=block.capitalize())
        ax.invert_yaxis()
    fig.suptitle('S2. Support judgments alongside unchanged primary scores', fontsize=17, y=.99)
    fig.legend(*axes[0].get_legend_handles_labels(), loc='upper center', bbox_to_anchor=(.58, .955), ncol=3, frameon=False)
    fig.text(.02, .015, 'Bars overlap as measures; they are not additive. Support judgments do not repair or replace frozen scores.\nSeparate task blocks and bundled arm policies prevent a causal comparison across these panels.', fontsize=10)
    fig.subplots_adjust(left=.21, right=.95, top=.91, bottom=.09, hspace=.65)
    save(fig, 'S2-arm-measures', 'Per-arm support and two unchanged primary gates; direct/oracle/discovery are separate.')

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 5.2))
    for ax, block in zip(axes, BLOCKS):
        matrix = p[block]['matrix']
        ax.imshow(matrix, cmap='Blues', vmin=0, vmax=p[block]['n'])
        for y in range(2):
            for x in range(2):
                ax.text(x, y, str(matrix[y][x]), ha='center', va='center', fontsize=23,
                        color='white' if matrix[y][x] > p[block]['n']*.55 else '#17232b')
        ax.set(xticks=[0, 1], xticklabels=['Typed match', 'Typed mismatch'], yticks=[0, 1],
               yticklabels=['All supported', 'Not all supported'], title=block.capitalize()+' (n='+str(p[block]['n'])+')')
    fig.suptitle('S3. Evidence support and exact typed agreement measure different things', fontsize=16, y=.98)
    fig.text(.025, .035, 'Support means every requested value and status was labelled supported. Counts are descriptive, not corrected accuracy.\nEach panel uses its own n for color scaling. Marginal citation/full-query labels are not included in this intersection.', fontsize=10)
    fig.subplots_adjust(left=.11, right=.98, top=.81, bottom=.24, wspace=.6)
    save(fig, 'S3-support-typed-intersections', 'Disjoint 2x2 case counts within each block; no scores changed.')

    fig, ax = plt.subplots(figsize=(13, 5.7))
    contexts = sorted(contexts, key=lambda c: c['context_id'])
    for c in contexts:
        initial = c['cohort'] == 'initial'
        ax.bar(c['context_id'], c['reviewed_cases'], color='#78838e' if initial else COLORS[0],
               hatch='//' if initial else None, edgecolor='white', linewidth=.5)
        ax.text(c['context_id'], c['reviewed_cases']+.6, str(c['reviewed_cases']), ha='center', fontsize=11)
    ax.set(xticks=list(range(1, 12)), xlabel='Context ID (assignment order, not elapsed time)',
           ylabel='Accepted case judgments', ylim=(0, 45))
    ax.axvline(3.5, color='#a7aeb4', linestyle='--', linewidth=1)
    ax.text(2, 43, 'Original contexts: 85 retained', ha='center')
    ax.text(7.5, 43, 'Eight recovery contexts: 107 new', ha='center')
    fig.suptitle('S4. Review recovery preserved every saved judgment', fontsize=17)
    fig.text(.07, .025, 'Three original contexts stopped before their full assignments: server_overloaded errors or observed compaction boundaries.\nOnly the 107 unjudged cases were redistributed. No rerating; no model override. Contexts are not independent model replications.', fontsize=10)
    fig.subplots_adjust(left=.09, right=.97, top=.85, bottom=.23)
    save(fig, 'S4-review-execution-cohorts', 'Accepted original/recovery case counts; no duration or independence claim.')
    receipt = {'schema_version': 'oct13-semantic-figure-registry-v1', 'input_sha256': sha(raw),
        'renderer_sha256': sha(Path(__file__).read_bytes()), 'figure_tables_sha256': sha(table_raw),
        'figures': registry, 'primary_figures_modified': 0, 'visual_review': 'pending'}
    (args.output/'figure-registry.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf8', newline='\n')
    return {'state': 'FOUR_PAIRS_RENDERED_REQUIRES_VISUAL_QA', 'figures': len(registry), 'input_sha256': sha(raw)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--input-sha256')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.self_check:
        print(json.dumps(self_check()))
    else:
        if not all((args.input, args.input_sha256, args.output)):
            parser.error('--input, --input-sha256 and --output required')
        print(json.dumps(render(args)))
