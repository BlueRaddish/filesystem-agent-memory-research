"""Render three scientific figures from the safe native-transfer aggregates only.

Run --self-check after rendering to validate the source census, exact tables and
export hashes, including known bad count/private-key cases. No retrieval/model IO.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import struct
import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ENGINES = ('fts_body_or', 'fts_search_or', 'body_bm25', 'search_bm25')
NAMES = ('FTS body OR', 'FTS search OR', 'Custom body BM25', 'Custom search BM25')
PACKERS, BUDGETS = ('whole_record', 'sentence_neighbors'), (4096, 8192, 16384)
COLORS = ('#27679c', '#bc6733', '#408267', '#80599b')
IDS = ('native-transfer-recovery', 'native-transfer-exposure', 'native-transfer-paired')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def table_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf8')).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def find(data, engine, packer, budget):
    return next(row for row in data['cells'] if (row['engine'], row['packer'], row['budget']) == (engine, packer, budget))


def validate(data):
    assert set(data) == {'schema_version', 'state', 'scope', 'provenance', 'counts', 'history_audit',
        'category_census', 'execution', 'cells', 'conditional_categories', 'paired_measured_only', 'limitations'}
    def hygiene(value):
        if isinstance(value, dict):
            assert not set(value) & {'question', 'answer', 'packet', 'body', 'content', 'text', 'private_message', 'native_path'}
            for item in value.values(): hygiene(item)
        elif isinstance(value, list):
            for item in value: hygiene(item)
        elif isinstance(value, str):
            assert not PureWindowsPath(value).is_absolute() and not PurePosixPath(value).is_absolute()
    hygiene(data)
    counts = data['counts']
    assert counts['questions_available'] == 300 and counts['nominal_queries'] == 270
    assert counts['valid_positive_queries'] == 264 and counts['ranking_jobs'] == 1080 and counts['packet_rows'] == 6480
    assert counts['label_unscorable_ranking_jobs'] == 24 and counts['label_unscorable_packet_rows'] == 144
    assert counts['label_availability'] == {'valid_positive': 264, 'unlabeled_abstention': 30,
        'missing_non_abstention_support': 5, 'malformed_criterion_group': 1}
    assert len(data['history_audit']) == 15
    assert Counter(row['label_availability']['valid_positive'] for row in data['history_audit']) == {18: 11, 17: 2, 16: 2}
    expected = {(engine, packer, budget) for engine in ENGINES for packer in PACKERS for budget in BUDGETS}
    assert len(data['cells']) == 24 and {(row['engine'], row['packer'], row['budget']) for row in data['cells']} == expected
    for row in data['cells']:
        assert (row['nominal_queries'], row['valid_queries'], row['label_unscorable'], row['measured_queries'], row['algorithm_faults']) == (270, 264, 6, 264, 0)
        assert 0 <= row['whole_bundle_verified_count'] <= 264
        assert math.isclose(row['whole_bundle_verified_count']/264, row['whole_bundle_query_weighted_verified_rate'])
        assert len(row['per_history']) == 15 and sum(history['valid_queries'] for history in row['per_history']) == 264
        assert math.isclose(sum(history['whole_bundle_verified_rate'] for history in row['per_history'])/15,
            row['whole_bundle_macro_history_verified_rate'])
        assert math.isclose(sum(round(history['whole_bundle_verified_rate']*history['valid_queries']) for history in row['per_history']),
            row['whole_bundle_verified_count'])
        m = row['fault_free_metric_means']
        assert math.isclose(m['whole_bundle'], row['whole_bundle_query_weighted_verified_rate'])
        assert 0 <= m['whole_bundle'] <= m['selected_bundle'] <= 1
        assert math.isclose(m['whole_feasible']*264, row['feasible_only_conditional']['valid_scheduled_queries'])
    assert len(data['conditional_categories']) == 216
    categories = {row['category'] for row in data['category_census']}
    assert len(categories) == 9 and {(row['engine'], row['packer'], row['budget'], row['category'])
        for row in data['conditional_categories']} == {(engine, packer, budget, category)
        for engine, packer, budget in expected for category in categories}
    for row in data['conditional_categories']:
        assert row['nominal_queries'] == 30 and row['algorithm_faults'] == 0
        assert math.isclose(row['whole_bundle_verified_count']/row['valid_queries'], row['whole_bundle_query_weighted_verified_rate'], abs_tol=1e-12)
        if row['category'] == 'summarization':
            assert row['valid_queries'] == 26 and row['whole_bundle_macro_history_verified_rate'] is None
            assert row['whole_bundle_macro_history_fault_bounds'] is None and row['fault_free_macro_history_count'] == 13
        else: assert row['fault_free_macro_history_count'] == 15
    assert len(data['paired_measured_only']) == 24
    assert {(row['engine'], row['packer'], row['budget']) for row in data['paired_measured_only']} == expected
    for row in data['paired_measured_only']:
        assert row['nominal_pairs'] == 270 and row['valid_label_pairs'] == row['measured_pairs'] == 264
        assert row['gains'] + row['ties'] + row['regressions'] == 264
        baseline = find(data, 'body_bm25', row['packer'], row['budget'])
        cell = find(data, row['engine'], row['packer'], row['budget'])
        assert row['gains'] - row['regressions'] == cell['whole_bundle_verified_count'] - baseline['whole_bundle_verified_count']
        assert math.isclose((row['gains'] - row['regressions'])/264, row['pair_query_weighted_mean_whole_bundle_difference'], abs_tol=1e-12)
    execution = data['execution']
    assert execution['ranking_state_counts'] == {'ok': 1056, 'label_unscorable': 24}
    assert execution['packet_state_counts'] == {'ok': 6336, 'label_unscorable': 144}
    assert len(execution['preparation_states']) == 61 and all(row['status'] in ('ok', 'complete') for row in execution['preparation_states'])
    assert execution['provider_calls'] == execution['model_calls'] == execution['retry_count'] == execution['resume_count'] == 0


def tables(data):
    recovery, exposure = [], []
    for packer in PACKERS:
        for engine in ENGINES:
            for budget in BUDGETS:
                row = find(data, engine, packer, budget)
                recovery.append({key: row[key] for key in ('engine', 'packer', 'budget', 'whole_bundle_verified_count',
                    'valid_queries', 'whole_bundle_query_weighted_verified_rate', 'whole_bundle_macro_history_verified_rate')})
            row = find(data, engine, packer, 8192); metrics = row['fault_free_metric_means']
            exposure.append({'engine': engine, 'packer': packer, 'budget': 8192, 'valid_queries': 264,
                'candidate_all_32_rate': metrics['candidate_all_32'], 'candidate_all_32_count': round(metrics['candidate_all_32']*264),
                'selected_bundle_rate': metrics['selected_bundle'], 'selected_bundle_count': round(metrics['selected_bundle']*264),
                'whole_bundle_rate': row['whole_bundle_query_weighted_verified_rate'], 'whole_bundle_count': row['whole_bundle_verified_count'],
                'necessary_feasible_rate': metrics['whole_feasible'], 'necessary_feasible_count': row['feasible_only_conditional']['valid_scheduled_queries']})
    paired = [{key: row[key] for key in ('engine', 'packer', 'budget', 'measured_pairs', 'gains', 'ties', 'regressions',
        'pair_query_weighted_mean_whole_bundle_difference', 'pair_macro_history_mean_whole_bundle_difference')}
        for row in data['paired_measured_only']]
    return recovery, exposure, paired


def finish(fig, name, title, caption, table, registry, bottom=.15):
    caption = '\n'.join(line for original in caption.split('\n')
        for line in textwrap.wrap(original, width=int(fig.get_size_inches()[0]*13)))
    fig.suptitle(title, x=.045, y=.98, ha='left', fontsize=15, fontweight='bold')
    fig.text(.045, .025, caption, va='bottom', fontsize=9, color='#46515b', linespacing=1.45)
    fig.tight_layout(rect=[.025, bottom, .99, .92])
    assets = []
    for suffix in ('png', 'svg'):
        path = HERE / (name + '.' + suffix)
        metadata = {'Software': 'Matplotlib native transfer supplement'} if suffix == 'png' else {'Date': None, 'Creator': 'Matplotlib native transfer supplement'}
        fig.savefig(path, dpi=165, metadata=metadata)
        asset = {'file': path.name, 'sha256': digest(path), 'bytes': path.stat().st_size}
        if suffix == 'png': asset['width_pixels'], asset['height_pixels'] = struct.unpack('>II', path.read_bytes()[16:24])
        assets.append(asset)
    plt.close(fig)
    registry.append({'id': name, 'title': title, 'caption': caption, 'input_table': table,
        'input_table_sha256': table_hash(table), 'assets': assets})


def render(data):
    validate(data)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
        'axes.spines.right': False, 'svg.hashsalt': 'native-transfer-figures-v1', 'svg.fonttype': 'none', 'savefig.facecolor': 'white'})
    recovery, exposure, paired = tables(data); registry = []
    status = 'Interpretation provisional pending root audit acceptance.' if data['state'].startswith('PROVISIONAL') else 'Independent actual execution audit accepted.'
    fig, axes = plt.subplots(1, 2, figsize=(13.7, 7.6), sharex=True)
    for ax, packer, title in zip(axes, PACKERS, ('Whole original messages', 'Sentence neighbors')):
        rows = [row for row in recovery if row['packer'] == packer]
        for index, row in enumerate(rows):
            color = COLORS[ENGINES.index(row['engine'])]
            query, macro = row['whole_bundle_query_weighted_verified_rate']*100, row['whole_bundle_macro_history_verified_rate']*100
            ax.plot([query, macro], [index, index], color='#707982', linewidth=1)
            ax.scatter(query, index, color=color, s=28, zorder=3)
            ax.scatter(macro, index, facecolor='none', edgecolor='#1c2f3e', marker='D', s=60, linewidth=1, zorder=4)
            ax.text(40.8, index, f"{row['whole_bundle_verified_count']}/264 | {macro:.2f}%", va='center', fontsize=9)
        ax.set_yticks(range(12), [f"{NAMES[ENGINES.index(row['engine'])]} · {row['budget']//1024} KiB" for row in rows], fontsize=9)
        ax.set_ylim(11.7, -.8); ax.set_xlim(0, 56); ax.set_xticks([0, 10, 20, 30, 40])
        ax.set_xlabel('Complete original-message bundle recovery (%)'); ax.set_title(title)
        ax.grid(axis='x', color='#e0e5e9', linewidth=.7); ax.set_axisbelow(True)
        ax.text(40.8, -.7, 'query count | macro %', fontsize=8.5, color='#46515b')
    axes[0].scatter([], [], color='#46515b', s=28, label='Query-weighted (264 valid questions)')
    axes[0].scatter([], [], facecolor='none', edgecolor='#1c2f3e', marker='D', s=60, label='Equal-history (15 history fractions)')
    fig.legend(*axes[0].get_legend_handles_labels(), loc='upper center', bbox_to_anchor=(.53, .92), ncol=2, frameon=False, fontsize=9)
    finish(fig, IDS[0], 'BEAM transfer: all 24 fixed recovery cells',
        'Full-message publisher-ID bundle exposure, not answer correctness. Right labels show exact query counts and equal-history percentages.\n'
        '270 nominal / 264 valid tasks per cell; six label-unscorable tasks remain null. Valid history denominators: eleven × 18, two × 17, two × 16.\n'
        'The same questions recur across cells; no independent-packet N, population winner or confidence interval. ' + status,
        recovery, registry, .17)

    fig, axes = plt.subplots(1, 2, figsize=(12.1, 6.1), sharey=True)
    labels = ('All IDs in top 32', 'All IDs selected (partials count)', 'All original bodies exposed')
    keys = ('candidate_all_32', 'selected_bundle', 'whole_bundle')
    for ax, packer, title in zip(axes, PACKERS, ('Whole original messages', 'Sentence neighbors')):
        rows = [row for row in exposure if row['packer'] == packer]
        for offset, key, label, color in zip((-.25, 0, .25), keys, labels, ('#b4bec8', '#63a59d', '#2d618b')):
            bars = ax.bar([index+offset for index in range(4)], [row[key+'_rate']*100 for row in rows], .24, color=color, label=label)
            for bar, row in zip(bars, rows):
                ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1.8, str(row[key+'_count']), ha='center', fontsize=8.5)
        bound = rows[0]['necessary_feasible_rate']*100
        ax.axhline(bound, color='#785e38', linestyle='--', linewidth=1.2)
        ax.text(1.5, bound+2, 'Necessary byte bound: 233/264 (88.26%)', ha='center', fontsize=9, color='#785e38')
        ax.set_xticks(range(4), ['FTS body\nOR', 'FTS search\nOR', 'Custom body\nBM25', 'Custom search\nBM25'], fontsize=9)
        ax.set_ylim(0, 100); ax.set_yticks([0, 25, 50, 75, 100]); ax.set_title(title)
        ax.grid(axis='y', color='#e0e5e9', linewidth=.7); ax.set_axisbelow(True)
    axes[0].set_ylabel('Valid questions (%)')
    fig.legend(*axes[0].get_legend_handles_labels(), loc='upper center', bbox_to_anchor=(.53, .91), ncol=3, frameon=False, fontsize=9)
    finish(fig, IDS[1], 'BEAM at 8 KiB: candidate presence, partial selection and complete exposure',
        'All eight fixed engine/packer cells. Bar labels are counts out of 264 valid questions; candidate presence is a separate ranking diagnostic.\n'
        'The dashed line is necessary only: exact whole-wrapper cost on the left; optimistic single-body/lean-wrapper lower bound on the right.\n'
        'No labeled minimal answer spans or QA evaluation; feasibility does not establish attainable or semantically sufficient recovery. ' + status,
        exposure, registry, .20)

    fig, axes = plt.subplots(2, 3, figsize=(13.6, 7.5), sharex=True)
    for row_index, packer in enumerate(PACKERS):
        for column, budget in enumerate(BUDGETS):
            ax = axes[row_index][column]
            rows = [next(row for row in paired if (row['engine'], row['packer'], row['budget']) == (engine, packer, budget)) for engine in ENGINES]
            ax.barh(range(4), [-row['regressions'] for row in rows], color='#b95651', height=.55, label='Lost full-message bundles')
            ax.barh(range(4), [row['gains'] for row in rows], color='#3e8369', height=.55, label='Gained full-message bundles')
            for index, row in enumerate(rows):
                if row['regressions']: ax.text(-row['regressions']-.4, index, str(row['regressions']), ha='right', va='center', fontsize=8.5)
                if row['gains']: ax.text(row['gains']+.4, index, str(row['gains']), ha='left', va='center', fontsize=8.5)
                ax.text(17.8, index, f"{row['ties']} ties", ha='right', va='center', fontsize=8.5, color='#46515b')
            ax.axvline(0, color='#717b85', linewidth=.8); ax.set_xlim(-12, 18); ax.set_ylim(3.7, -.7)
            ax.set_xticks([-10, -5, 0, 5, 10]); ax.set_yticks(range(4), NAMES, fontsize=8.5)
            ax.grid(axis='x', color='#e0e5e9', linewidth=.7); ax.set_axisbelow(True)
            ax.set_title(('Whole messages' if packer == 'whole_record' else 'Sentence neighbors') + f' · {budget//1024} KiB')
            if row_index == 1: ax.set_xlabel('Lost ← paired query count → gained', fontsize=9)
    fig.legend(*axes[0][0].get_legend_handles_labels(), loc='upper center', bbox_to_anchor=(.53, .92), ncol=2, frameon=False, fontsize=9)
    finish(fig, IDS[2], 'BEAM transfer: all matched engine gains, ties and regressions',
        'Reference: custom body BM25 at the same question, packer and budget. Each cell has 264 measured valid pairs; 270 nominal pairs include six unscorable labels.\n'
        'Ties combine joint full-message recoveries and joint nonrecoveries. The body reference is shown as 264 structural ties.\n'
        'Repeated synthetic histories/questions; descriptive changes only, no population winner, significance test or confidence interval. ' + status,
        paired, registry, .18)
    value = {'schema_version': 1, 'scope': data['scope'], 'source_public_results_sha256': digest(HERE/'native-transfer-results.json'),
        'source_private_aggregate_sha256': data['provenance']['private_aggregate_sha256'],
        'renderer_sha256': digest(__file__), 'matplotlib_version': matplotlib.__version__, 'figures': registry}
    destination = HERE / 'native-transfer-figures.json'
    destination.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({'state': 'RENDERED_THREE_FIGURE_PAIRS', 'registry_sha256': digest(destination), 'figure_count': 3}))


def self_check(data):
    validate(data)
    for mutation in ('bad_count', 'private_key'):
        bad = copy.deepcopy(data)
        if mutation == 'bad_count': bad['cells'][0]['whole_bundle_verified_count'] += 1
        else: bad['packet'] = 'KNOWN_BAD_PRIVATE_FIELD'
        try: validate(bad)
        except AssertionError: pass
        else: raise AssertionError('known_bad_source_accepted')
    registry = read(HERE / 'native-transfer-figures.json')
    assert registry['renderer_sha256'] == digest(__file__) and registry['source_public_results_sha256'] == digest(HERE/'native-transfer-results.json')
    assert [row['id'] for row in registry['figures']] == list(IDS)
    for figure, expected in zip(registry['figures'], tables(data)):
        assert figure['input_table'] == expected and figure['input_table_sha256'] == table_hash(expected)
        assert len(figure['assets']) == 2
        assert {asset['file'] for asset in figure['assets']} == {figure['id']+'.png', figure['id']+'.svg'}
        for asset in figure['assets']:
            path = HERE / asset['file']
            assert path.parent == HERE and digest(path) == asset['sha256'] and path.stat().st_size == asset['bytes']
    print(json.dumps({'state': 'PASS_PUBLIC_DATA_TABLE_EXPORT_CHECKS', 'cells': 24, 'category_cells': 216,
        'paired_cells': 24, 'figure_pairs': 3, 'known_bad_cases_rejected': 2, 'raw_corpus_or_retrieval_used': False,
        'visual_layout_inspection': 'SEPARATE_REQUIRED_CHECK'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    data = read(HERE / 'native-transfer-results.json')
    if args.self_check: self_check(data)
    else: render(data)
