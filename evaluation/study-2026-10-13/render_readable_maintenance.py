"""Render a postcollection presentation derivative without changing frozen exports."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ANALYSIS_SHA = '4602743218ea56d28c83d1307c9b1e3a6c36118f695018c14dbc0b0badfa10d6'
REGISTRY_SHA = '016d73ee963a6254e7315de5e6225203e2051cc206324c519769bc8b017c8391'
POLICIES = ('no_invalidation', 'ttl_5', 'global', 'direct_dependencies', 'transitive_dependencies')
LABELS = ('No invalidation', 'TTL: five events', 'Global invalidation', 'Direct dependencies', 'Transitive dependencies')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    analysis_path, registry_path = HERE / 'analysis.json', HERE / 'figure-registry.json'
    assert sha(analysis_path) == ANALYSIS_SHA and sha(registry_path) == REGISTRY_SHA
    registry = json.loads(registry_path.read_text(encoding='utf8'))
    original = {item['file']: item['sha256'] for fig in registry['figures'] for item in fig['exports']}
    assert len(original) == 52 and all(sha(HERE / name) == value for name, value in original.items())
    rows = json.loads(analysis_path.read_text(encoding='utf8'))['tables']['maintenance']
    assert len(rows) == 10 and {(r['policy'], r['missing_declared_edge']) for r in rows} == {
        (policy, missing) for policy in POLICIES for missing in (False, True)}
    assert all(r['events'] == 1280 and type(r['stale_reuses']) is int and 0 <= r['stale_reuses'] <= 1280
        and type(r['rebuilds']) is int and r['rebuilds'] >= 0 for r in rows)
    output = HERE / 'presentation'
    output.mkdir(exist_ok=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12, 'svg.fonttype': 'none'})
    fig, axes = plt.subplots(2, 2, figsize=(15, 9.5), layout='constrained')
    colors = ('#6e6199', '#b75537', '#42815d', '#287394', '#a47722')
    for row_number, missing in enumerate((False, True)):
        selected = [next(r for r in rows if r['policy'] == p and r['missing_declared_edge'] is missing) for p in POLICIES]
        group = 'Complete prescribed graph' if not missing else 'One declared dependency missing'
        for column, (field, xlabel) in enumerate((('stale_reuses', 'Stale reuse events (out of 1,280)'),
                ('rebuilds', 'Mechanical rebuild count'))):
            axis = axes[row_number, column]
            values = [r[field] for r in selected]
            axis.barh(range(5), values, color=colors, height=0.6)
            axis.set_yticks(range(5), LABELS)
            axis.invert_yaxis()
            axis.set_xlim(0, 1450 if column == 0 else 2350)
            axis.set_xlabel(xlabel)
            axis.set_title(group + (' — stale reuse' if column == 0 else ' — rebuild work'), fontsize=13, pad=12)
            axis.grid(axis='x', alpha=0.16)
            axis.set_axisbelow(True)
            for i, value in enumerate(values):
                axis.text(value + 22, i, f'{value:,}', va='center', fontsize=11)
            axis.spines[['top', 'right']].set_visible(False)
    fig.suptitle('Dependency maintenance: distinct policies remain visible when outcomes coincide', fontsize=18)
    fig.supxlabel('Same frozen table, new presentation. Engineered replay: 64 seeds × 20 events per policy.\n'
        'Rebuilds can exceed event counts because multiple views can rebuild; this does not test LLM semantic maintenance.', fontsize=10)
    stem = output / '23-invalidation-tradeoffs-readable'
    for extension in ('png', 'svg'):
        fig.savefig(stem.with_suffix('.' + extension), dpi=160, facecolor='white')
    plt.close(fig)
    assert sha(analysis_path) == ANALYSIS_SHA and sha(registry_path) == REGISTRY_SHA
    assert all(sha(HERE / name) == value for name, value in original.items())
    exports = {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(output.iterdir())}
    receipt = {'state': 'presentation_derivative_requires_visual_review', 'source_sha256': sha(Path(__file__)),
        'analysis_sha256': ANALYSIS_SHA, 'frozen_registry_sha256': REGISTRY_SHA,
        'reason': 'Frozen figure23 has coincident policy labels. Separate rows display the same ten table entries.',
        'maintenance_table': rows, 'exports': exports, 'original_52_exports_unchanged': True,
        'scoring_or_statistics_reexecuted': False}
    with (output / 'presentation-receipt.json').open('x', encoding='utf8', newline='\n') as stream:
        stream.write(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps({'state': receipt['state'], 'exports': exports}))


if __name__ == '__main__':
    main()
