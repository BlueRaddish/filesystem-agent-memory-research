"""Post-collection display amendment; no scoring, models, or statistical reruns.

Run --self-check or --render after the frozen analyzer has completed. Re-running
the original analyzer restores its original layouts; this helper then repairs
only the four documented label/legend layouts. Numeric artists stay unchanged.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import analyze as original

HERE = Path(__file__).resolve().parent
TARGETS = {'05-candidate-versus-packing-loss', '07-context-recovery-frontier',
           '08-uncached-computation-frontier', '15-whole-record-budget-feasibility'}
SOURCE_SHA = '5006cc1cffca9e75c7466d1780c71ef74f5b23e1f34775a31d9af5d85a1c1c87'
COMPUTATIONAL_SHA = '599b5dc1fe01a009c739778d7af383ea1dbe5eb0a82e4bd854ef6b51939ae3ed'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def numeric_artists(fig):
    return [dict(lines=[line.get_xydata().tolist() for line in ax.lines],
                 collections=[dict(offsets=collection.get_offsets().tolist(),
                                   paths=[p.vertices.tolist() for p in collection.get_paths()])
                              for collection in ax.collections],
                 patches=[patch.get_path().vertices.tolist() for patch in ax.patches],
                 limits=[list(ax.get_xlim()), list(ax.get_ylim())]) for ax in fig.axes]


def improve(fig, name):
    if name == '05-candidate-versus-packing-loss':
        fig.legends[0].set_bbox_to_anchor((.5, .055))
        return (0, .19, 1, .96)
    if name == '07-context-recovery-frontier':
        for index, ax in enumerate(fig.axes):
            assert len(ax.texts) == 6
            rows = [[str(i), annotation.get_text()] for i, annotation in enumerate(ax.texts, 1)]
            for annotation in list(ax.texts):
                annotation.remove()
            # Four panels have unused vertical space above the 4K observations
            # or below the 8K observations. Tables remove coincident-point labels.
            table = ax.table(cellText=rows, colLabels=['Engine', 'Median bytes'],
                             bbox=(.03, .55 if index < 2 else .06, .30, .38))
            table.auto_set_font_size(False)
            table.set_fontsize(7)
        handles, labels = fig.axes[0].get_legend_handles_labels()
        fig.legends[0].remove()
        fig.legend(handles, [f'{i}: {label}' for i, label in enumerate(labels, 1)],
                   loc='lower center', bbox_to_anchor=(.5, .055), ncol=3, fontsize=8)
        return (0, .15, 1, .96)
    if name == '08-uncached-computation-frontier':
        ax = fig.axes[3]
        assert len(ax.texts) == 6
        for annotation in list(ax.texts):
            annotation.remove()
        # Engine identity moves to a color key in unused space, leaving measured
        # points and intervals unchanged, including coincident observations.
        ax.legend(ax.collections, original.ENGINE_LABELS, loc='upper left', fontsize=8)
        return (0, .065, 1, .96)
    if name == '15-whole-record-budget-feasibility':
        fig.set_size_inches(15, 7)
        for index, ax in enumerate(fig.axes):
            handles, labels = ax.get_legend_handles_labels()
            ax.get_legend().remove()
            fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(.25 + .5 * index, .055), fontsize=8)
        return (0, .24, 1, .96)
    raise ValueError(name)


def selfcheck():
    fig, ax = original.plt.subplots()
    for i, engine in enumerate(original.ENGINES):
        ax.scatter(i, i, color=original.COLORS[engine], label=original.LABEL[engine])
        ax.annotate('1,000 B', (i, i), xytext=(5, 5), textcoords='offset points')
    fig.legend(*ax.get_legend_handles_labels())
    before = numeric_artists(fig)
    improve(fig, '07-context-recovery-frontier')
    assert before == numeric_artists(fig)
    assert not ax.texts and len(ax.tables) == 1
    original.plt.close(fig)
    return {'state': 'passed', 'checks': ['numeric_artists_unchanged', 'coincident_labels_moved_to_table'],
            'model_loads': 0, 'reader_calls': 0, 'statistical_recomputations': 0}


def render():
    assert original.sha(HERE / 'analyze.py') == SOURCE_SHA
    data = original.read('analysis.json')
    assert data['state'] == 'complete' and len(data['figures']) == 15
    before_sha = original.sha(HERE / 'analysis.json')
    computational = {key: value for key, value in data.items() if key != 'figures'}
    # Original SVG timestamps/IDs can differ on a fresh analyzer run. Bind all
    # computational output instead of requiring byte identity of that registry.
    assert digest(computational) == COMPUTATIONAL_SHA, 'Frozen computational output differs'
    registry = copy.deepcopy(data['figures'])
    old_files = {f['file']: original.sha(HERE / f['file']) for entry in registry for f in entry['files']}
    for entry in registry:
        for item in entry['files']:
            assert item['sha256'] == old_files[item['file']]
    changes = []

    def save(fig, name, title, caption, result):
        index = len(result)
        if name not in TARGETS:
            original.plt.close(fig)
            result.append(registry[index])
            return
        numeric = numeric_artists(fig)
        rect = improve(fig, name)
        assert numeric == numeric_artists(fig), name
        fig.suptitle(title, fontsize=16, fontweight='bold', y=.992)
        fig.text(.02, .012, caption, fontsize=8, va='bottom', color='#444444', wrap=True)
        fig.tight_layout(rect=rect)
        files = []
        for extension in ('png', 'svg'):
            path = HERE / 'figures' / (name + '.' + extension)
            metadata = {'Creator': 'Documented post-collection label amendment'}
            if extension == 'svg':
                metadata['Date'] = None
            fig.savefig(path, dpi=180, metadata=metadata)
            relative = 'figures/' + path.name
            files.append({'file': relative, 'sha256': original.sha(path)})
        original.plt.close(fig)
        result.append(dict(number=index + 1, title=title, caption=caption, files=files))
        changes.append({'figure': name, 'numeric_artists_sha256': digest(numeric),
                        'original_files': [f for f in registry[index]['files']], 'updated_files': files})

    original.plt.rcParams['svg.hashsalt'] = 'fictional-atomic-label-amendment-v1'
    original.save_figure = save
    data['figures'] = original.plot_all(data, original.read('retrieval-results.json')['rows'],
                                      original.read('timing-results.json')['rows'],
                                      original.read('reader-results.json')['trials'],
                                      original.read('model-execution.json'))
    assert computational == {key: value for key, value in data.items() if key != 'figures'}
    for entry in data['figures']:
        for item in entry['files']:
            if Path(item['file']).stem not in TARGETS:
                assert original.sha(HERE / item['file']) == old_files[item['file']]
    assert {change['figure'] for change in changes} == TARGETS
    original.atomic_json(HERE / 'analysis.json', data)
    receipt = dict(state='complete', scope='Display-only post-collection amendment; primary outcomes unchanged',
                   analysis_code_sha256=SOURCE_SHA, renderer_sha256=original.sha(Path(__file__)),
                   original_analysis_sha256=before_sha, updated_analysis_sha256=original.sha(HERE / 'analysis.json'),
                   computational_tables_sha256=digest(computational), untouched_figure_files=22,
                   changes=changes, selfcheck=selfcheck())
    original.atomic_json(HERE / 'visual-amendment.json', receipt)
    print(json.dumps({'state': 'complete', 'figures_amended': len(changes), 'computational_tables_unchanged': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--self-check', action='store_true')
    mode.add_argument('--render', action='store_true')
    args = parser.parse_args()
    print(json.dumps(selfcheck())) if args.self_check else render()
