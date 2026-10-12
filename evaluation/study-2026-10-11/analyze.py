"""Descriptive, whole-family analysis of the frozen fictional atomic study.

Run --self-check before --run --cache EXTERNAL_TOKENIZER_CACHE. This script never
loads model weights, calls a reader, changes frozen inputs, or reads a host vault.
It requires every scheduled outcome, retaining infrastructure failures as failures.
Plots and tables describe this authored bank; they do not estimate a population.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.ticker import PercentFormatter

HERE = Path(__file__).resolve().parent
SEED, REPLICATES = 1011, 2000
ENGINES = ('bm25', 'hierarchical_bm25', 'minilm_rerank', 'mixedbread_rerank',
           'hierarchical_mixedbread', 'hierarchical_mixedbread_rescue')
FACTORS = tuple(''.join(map(str, p)) for p in itertools.product((0, 1), repeat=3))
ENGINE_LABELS = ('BM25', 'BM25 branches', 'MiniLM rerank', 'Mixedbread rerank',
                 'Learned branches', 'Learned + rescue')
LABEL = dict(zip(ENGINES, ENGINE_LABELS))
COLORS = dict(zip(ENGINES, ('#50677a', '#96723c', '#5d82b0', '#3c8b77', '#995da6', '#bd654c')))
ARMS = ('bm25_000', 'bm25_111', 'mixedbread_111', 'routing_rescue_111')
ARM_LABEL = {'bm25_000': 'BM25 000', 'bm25_111': 'BM25 111',
             'mixedbread_111': 'Mixedbread 111', 'routing_rescue_111': 'Routing + rescue 111',
             'full_collection': 'Full collection', 'oracle_evidence': 'Sufficient-source oracle',
             'raw_filesystem': 'Raw filesystem', 'retriever_filesystem': 'Filesystem + retriever'}
POLICIES = ((4096, 48), (4096, 144), (8192, 48), (8192, 144))
CONTRASTS = ('A', 'B', 'C', 'AB', 'AC', 'BC', 'ABC')
GATES = ('critical_correct', 'factual_correct', 'citation_sufficient',
         'schema_valid', 'structural_check_pass', 'clean_finish', 'complete_task')
GATE_LABELS = ('Critical/status\nexact match', 'All answer/status\nexact match',
               'Sufficient valid\noriginal citations', 'Accepted answer\nschema',
               'Host structure\ncheck', 'Clean\ncompletion', 'Complete exact\nvalue + source task')


def read(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    temporary.replace(path)


def author(family_id):
    return family_id[0]


def interval(values):
    """Resample complete paired family statistics, never task/cell rows.

    Restarting the same seed makes the interval independent of table iteration
    order; family ordering is always lexical. These are descriptive percentile
    intervals, without multiplicity correction or population-sampling claims.
    """
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError('nonempty_finite_family_statistics_required')
    draws = np.random.default_rng(SEED).integers(0, len(values), size=(REPLICATES, len(values)))
    bounds = np.quantile(values[draws].mean(axis=1), (.025, .975))
    return {'estimate': float(values.mean()), 'lower': float(bounds[0]),
            'upper': float(bounds[1]), 'families': len(values)}


def grouped(rows, fields):
    result = defaultdict(list)
    for row in rows:
        result[tuple(row[k] for k in fields)].append(row)
    return result


def family_means(rows, metric):
    groups = grouped(rows, ('family_id',))
    return {key[0]: float(np.mean([r[metric] for r in group]))
            for key, group in sorted(groups.items())}


def ratio_interval(numerators, denominators):
    """Conditional feasible-query rate; resample numerator/denominator by family."""
    numerator, denominator = np.asarray(numerators, float), np.asarray(denominators, float)
    if not denominator.sum():
        return dict(estimate=None, lower=None, upper=None, families=len(denominator), valid_draws=0)
    draws = np.random.default_rng(SEED).integers(0, len(denominator), size=(REPLICATES, len(denominator)))
    totals = denominator[draws].sum(axis=1)
    valid = totals > 0
    bounds = np.quantile(numerator[draws].sum(axis=1)[valid] / totals[valid], (.025, .975))
    return dict(estimate=float(numerator.sum() / denominator.sum()), lower=float(bounds[0]),
                upper=float(bounds[1]), families=len(denominator), valid_draws=int(valid.sum()))


def effect(cells, contrast):
    """A difference; AB/AC/BC difference-in-differences; ABC third difference.

    Average finite differences over the factors not in the contrast. These are
    on/off rate changes, not effect-coded regression coefficients.
    """
    indexes = ['ABC'.index(factor) for factor in contrast]
    return sum(np.prod([1 if cell[i] == '1' else -1 for i in indexes]) * value
               for cell, value in cells.items()) / 2 ** (3 - len(indexes))


def pareto(points):
    """All non-dominated observed configurations: less context, more recovery."""
    return [i for i, (cost, benefit) in enumerate(points)
            if not any(other_cost <= cost and other_benefit >= benefit and
                       (other_cost < cost or other_benefit > benefit)
                       for other_cost, other_benefit in points)]


def validate_inputs():
    freeze = read('freeze.json')
    for name, digest in freeze['files'].items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('freeze_requires_safe_relative_paths')
        if sha(HERE / path) != digest:
            raise ValueError('frozen_input_changed_' + name)
    result = read('retrieval-results.json')
    if result.get('state') != 'complete' or len(result.get('rows', [])) != 18432:
        raise ValueError('retrieval_results_incomplete')
    rows = result['rows']
    banks = [read(name) for name in ('author-a.json', 'author-b.json')]
    families = [f for bank in banks for f in bank['families']]
    families_by_id = {f['id']: f for f in families}
    tasks = {t['id']: (f['id'], t) for f in families for t in f['tasks']}
    split = read('family-split.json')['families']
    if Counter(split.values()) != {'development': 12, 'held_out': 36}:
        raise ValueError('family_split_counts')
    expected = {(task, engine, factors, size, budget)
                for task in tasks for engine in ENGINES for factors in FACTORS
                for size in (48, 144) for budget in (4096, 8192)}
    observed = {(r['task_id'], r['engine'], r['factors'], r['collection_size'], r['budget']) for r in rows}
    if expected != observed or len(observed) != len(rows) or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('retrieval_schedule_missing_or_duplicate_cells')
    rankings = read('rankings.json')['rows']
    ranking_by_id = {r['id']: r for r in rankings}
    if len(rankings) != len(ranking_by_id) or len(rankings) != 4608:
        raise ValueError('ranking_counts')
    for r in rows:
        if r['family_id'] != tasks[r['task_id']][0] or r['split'] != split[r['family_id']]:
            raise ValueError('family_or_split_mismatch')
        if r['stratum'] != families_by_id[r['family_id']]['stratum']:
            raise ValueError('stratum_mismatch')
        k = ranking_by_id[r['ranking_id']]
        if (k['task_id'], k['engine'], k['collection_size'], str(k['cues']), str(k['gate'])) != (
                r['task_id'], r['engine'], r['collection_size'], r['factors'][0], r['factors'][2]):
            raise ValueError('ranking_link_mismatch')
        if r['bytes'] > r['budget'] or len(set(r['selected_ids'])) != len(r['selected_ids']):
            raise ValueError('packet_budget_or_duplicate_ids')
        # Expansion can recover outside candidates; only B=0 has a candidate ceiling.
        if r['factors'][1] == '0' and r['bundle_complete'] and not r['candidate_bundle_complete']:
            raise ValueError('no_expansion_candidate_ceiling_violated')
    timing = read('timing-results.json')
    if timing.get('state') != 'complete' or len(timing['rows']) != 144 or timing.get('pair_cache_enabled') is not False:
        raise ValueError('uncached_timing_results_incomplete')
    timing_keys = {(r['task_id'], r['engine'], r['repeat']) for r in timing['rows']}
    if len(timing_keys) != 144 or any(split[r['family_id']] != 'development' for r in timing['rows']):
        raise ValueError('timing_schedule_or_split')
    if any(not np.isfinite(r['seconds']) or r['seconds'] < 0 for r in timing['rows']):
        raise ValueError('invalid_timing')
    schedule = read('reader-schedule.json')
    readers = read('reader-results.json')
    if readers.get('planned_trials') != 144 or readers.get('completed_trials') != 144:
        raise ValueError('reader_results_incomplete')
    trials = readers['trials']
    planned = {j['trial_id']: j for j in schedule['jobs']}
    if len(trials) != 144 or set(planned) != {t['trial_id'] for t in trials}:
        raise ValueError('reader_schedule_missing_or_duplicate')
    for trial in trials:
        if not trial.get('completed') or any(trial.get(k) != v for k, v in planned[trial['trial_id']].items()):
            raise ValueError('reader_schedule_mismatch')
        if split[trial['family_id']] != 'held_out':
            raise ValueError('reader_not_held_out')
    if readers.get('reader_schedule_sha256') != sha(HERE / 'reader-schedule.json'):
        raise ValueError('reader_schedule_digest_mismatch')
    if readers.get('freeze_sha256') != sha(HERE / 'freeze.json'):
        raise ValueError('reader_freeze_digest_mismatch')
    return rows, rankings, timing['rows'], trials, families, freeze


def reconstruct_tokens(rows, trials, cache, freeze):
    """Load tokenizer JSON only. Reconstruct exact packets and verify their digests."""
    from tokenizers import Tokenizer
    import benchmark
    cache = cache.resolve()
    repository = HERE.parents[1]
    if cache == repository or repository in cache.parents:
        raise ValueError('tokenizer_cache_must_be_external')
    tokenizers = {}
    tokenizer_manifest = {}
    for name in ('minilm', 'mixedbread'):
        path = cache / name / 'tokenizer.json'
        digest = sha(path)
        pinned = freeze['model_files'][name]['tokenizer.json']['sha256']
        if digest != pinned:
            raise ValueError('tokenizer_digest_mismatch_' + name)
        tokenizer = Tokenizer.from_file(str(path))
        tokenizer.no_padding()
        tokenizer.no_truncation()
        tokenizers[name] = tokenizer
        tokenizer_manifest[name] = {'sha256': digest,
                                    'count': 'packet text only; no special tokens, padding or truncation'}
    docs = benchmark.docs_for(benchmark.load_bank())
    packets, counts = {}, {}
    for row in rows:
        digest = row['packet_sha256']
        if digest not in packets:
            packet = benchmark.packet_for(docs, row['selected_ids'], row['factors'][0] == '1')
            if hashlib.sha256(packet.encode('utf-8')).hexdigest() != digest or len(packet.encode('utf-8')) != row['bytes']:
                raise ValueError('packet_reconstruction_mismatch_' + row['id'])
            packets[digest] = {name: len(t.encode(packet, add_special_tokens=False).ids)
                               for name, t in tokenizers.items()}
        counts[row['id']] = dict(packets[digest])
        row['document_count'] = len(row['selected_ids'])
        row['missing_ref_count'] = len(row['missing_expansion_refs'])
        row['budget_skipped_count'] = len(row['oversized_or_budget_skipped'])
        for name, value in packets[digest].items():
            row[name + '_packet_tokens'] = value
    reader_counts = {}
    for trial in trials:
        if trial['block'] == 'discovery':
            continue
        packet = benchmark.packet_for(docs, trial.get('selected_ids', []), trial['factors'][0] == '1')
        # A harness failure before packet creation does not have fabricated context.
        if 'packet_sha256' not in trial:
            reader_counts[trial['trial_id']] = None
            continue
        if hashlib.sha256(packet.encode('utf-8')).hexdigest() != trial['packet_sha256']:
            raise ValueError('reader_packet_reconstruction_mismatch')
        reader_counts[trial['trial_id']] = {name: len(t.encode(packet, add_special_tokens=False).ids)
                                          for name, t in tokenizers.items()}
    feasibility = []
    feasibility_lookup = {}
    for family in benchmark.load_bank():
        for task in family['tasks']:
            for cues in (False, True):
                bundle_bytes = [len(benchmark.packet_for(docs, ids, cues).encode('utf-8'))
                                for ids in task['evidence_sets']]
                minimum = min(bundle_bytes)
                for budget in (4096, 8192):
                    feasible = minimum <= budget
                    item = dict(task_id=task['id'], family_id=family['id'],
                                split=benchmark.split(family['id']), author=author(family['id']),
                                cues=int(cues), budget=budget, minimum_authored_bundle_bytes=minimum,
                                authored_sufficient_sets=len(bundle_bytes), feasible=feasible)
                    feasibility.append(item)
                    feasibility_lookup[task['id'], int(cues), budget] = item
    for row in rows:
        item = feasibility_lookup[row['task_id'], int(row['factors'][0]), row['budget']]
        row['authored_bundle_feasible'] = item['feasible']
        row['minimum_authored_bundle_bytes'] = item['minimum_authored_bundle_bytes']
        if row['bundle_complete'] and not item['feasible']:
            raise ValueError('recovery_exceeds_authored_bundle_budget_feasibility')
    return counts, reader_counts, tokenizer_manifest, len(packets), feasibility


def retrieval_tables(rows):
    metrics = ('bundle_complete', 'governing_coverage', 'eligible_bundle_complete',
               'candidate_bundle_complete', 'bytes', 'document_count', 'derived_selected',
               'flagged_view_selected', 'missing_ref_count', 'budget_skipped_count',
               'minilm_packet_tokens', 'mixedbread_packet_tokens')
    cells, contrasts, comparison, strata, stage, heterogeneity = [], [], [], [], [], []
    for split in ('development', 'held_out'):
        split_rows = [r for r in rows if r['split'] == split]
        for writer in ('both', 'A', 'B'):
            selected = [r for r in split_rows if writer == 'both' or author(r['family_id']) == writer]
            for key, group in sorted(grouped(selected, ('engine', 'factors', 'budget', 'collection_size')).items()):
                engine, factors, budget, size = key
                summary = dict(split=split, author=writer, engine=engine, factors=factors,
                               budget=budget, collection_size=size, task_rows=len(group))
                family_stats = family_means(group, 'bundle_complete')
                summary.update(interval(list(family_stats.values())))
                summary['complete_task_queries'] = sum(r['bundle_complete'] for r in group)
                summary['authored_bundle_feasible_queries'] = sum(r['authored_bundle_feasible'] for r in group)
                summary['authored_bundle_feasibility_ceiling'] = summary['authored_bundle_feasible_queries'] / len(group)
                feasible_groups = grouped(group, ('family_id',))
                summary['conditional_feasible_query_recovery'] = ratio_interval(
                    [sum(r['bundle_complete'] for r in values) for _, values in sorted(feasible_groups.items())],
                    [sum(r['authored_bundle_feasible'] for r in values) for _, values in sorted(feasible_groups.items())])
                summary['means'] = {m: float(np.mean(list(family_means(group, m).values()))) for m in metrics}
                summary['medians'] = {m: float(np.median([r[m] for r in group])) for m in metrics[4:]}
                cells.append(summary)
            for key, group in sorted(grouped(selected, ('engine', 'budget', 'collection_size')).items()):
                engine, budget, size = key
                by_family = {}
                for (fid,), values in grouped(group, ('family_id',)).items():
                    factor_cells = {factor: np.mean([r['bundle_complete'] for r in values if r['factors'] == factor])
                                    for factor in FACTORS}
                    if any(sum(r['factors'] == factor for r in values) != 2 for factor in FACTORS):
                        raise ValueError('factorial_family_missing_tasks')
                    by_family[fid] = factor_cells
                for contrast in CONTRASTS:
                    estimates = [effect(by_family[fid], contrast) for fid in sorted(by_family)]
                    contrasts.append(dict(split=split, author=writer, engine=engine, budget=budget,
                                          collection_size=size, contrast=contrast, **interval(estimates)))
                joint = [by_family[fid]['111'] - by_family[fid]['000'] for fid in sorted(by_family)]
                heterogeneity.append(dict(split=split, author=writer, engine=engine, budget=budget,
                                          collection_size=size, contrast='111_minus_000', **interval(joint)))
        # All engine comparisons are paired within the same family and policy.
        for factors in ('000', '111'):
            for budget, size in POLICIES:
                values = {e: family_means([r for r in split_rows if r['engine'] == e and
                          r['factors'] == factors and r['budget'] == budget and r['collection_size'] == size],
                          'bundle_complete') for e in ENGINES}
                for baseline, alternative in itertools.combinations(ENGINES, 2):
                    ids = sorted(values[baseline])
                    comparison.append(dict(split=split, factors=factors, budget=budget, collection_size=size,
                                           baseline=baseline, alternative=alternative,
                                           **interval([values[alternative][f] - values[baseline][f] for f in ids])))
    held = [r for r in rows if r['split'] == 'held_out' and r['budget'] == 4096 and r['collection_size'] == 144]
    for key, group in sorted(grouped(held, ('stratum', 'engine')).items()):
        stratum, engine = key
        by_factor = {f: family_means([r for r in group if r['factors'] == f], 'bundle_complete') for f in ('000', '111')}
        ids = sorted(by_factor['000'])
        strata.append(dict(stratum=stratum, engine=engine, budget=4096, collection_size=144,
                           **interval([by_factor['111'][i] - by_factor['000'][i] for i in ids]),
                           baseline=float(np.mean(list(by_factor['000'].values()))),
                           combined=float(np.mean(list(by_factor['111'].values())))))
    for key, group in sorted(grouped(held, ('engine', 'factors')).items()):
        engine, factors = key
        transitions = Counter(('candidate_' + str(int(r['candidate_bundle_complete'])) +
                               '_packed_' + str(int(r['bundle_complete']))) for r in group)
        stage.append(dict(engine=engine, factors=factors, budget=4096, collection_size=144,
                          task_rows=len(group), families=36,
                          eligible=float(np.mean([r['eligible_bundle_complete'] for r in group])),
                          candidate=float(np.mean([r['candidate_bundle_complete'] for r in group])),
                          packed=float(np.mean([r['bundle_complete'] for r in group])),
                          transitions=dict(transitions)))
    return dict(retrieval_cells=cells, factorial_contrasts=contrasts, engine_contrasts=comparison,
                stratum_joint_policy_contrasts=strata, evidence_stages=stage,
                author_split_joint_policy_contrasts=heterogeneity)


def gate(trial, name):
    if name in ('critical_correct', 'factual_correct', 'citation_sufficient', 'schema_valid'):
        return bool((trial.get('score') or {}).get(name, False))
    return bool(trial.get(name, False))


def failure_class(trial):
    if gate(trial, 'complete_task'):
        return 'complete_exact_value_and_source'
    if trial.get('infrastructure_error') or trial.get('termination') in ('infrastructure_failure', 'harness_failure', 'host_write_or_checker_failure'):
        return 'infrastructure_failure'
    if not trial.get('artifact_written'):
        return 'no_accepted_artifact'
    if not gate(trial, 'schema_valid') or not gate(trial, 'structural_check_pass'):
        return 'structure_failure'
    if not gate(trial, 'factual_correct'):
        return 'exact_authored_value_or_status_mismatch'
    if not gate(trial, 'citation_sufficient'):
        return 'source_match_failure'
    return 'unclean_or_forbidden_completion'


def discovery_detail(trial):
    events = trial.get('events', [])
    modes = trial.get('source_modes_supplied_before_final_write', {})
    full_ids = sorted(i for i, values in modes.items() if any(m in ('read', 'retrieve') for m in values))
    partial_only = sorted(i for i, values in modes.items() if 'search' in values and not any(m in ('read', 'retrieve') for m in values))
    delivered = set(trial.get('host_delivered_source_ids', []))
    replayed = set(trial.get('source_id_receipts', []))
    return dict(trial_id=trial['trial_id'], family_id=trial['family_id'], arm=trial['arm'],
                response_turns=len(trial.get('calls', [])), actions=len(events),
                executed_actions=sum(e.get('executed', False) for e in events),
                operations=dict(Counter(e.get('action', {}).get('tool', 'invalid')
                                        if isinstance(e.get('action'), dict) else 'invalid' for e in events)),
                refused_actions=sum(bool((e.get('result') or {}).get('error')) for e in events),
                returned_bytes=trial.get('returned_bytes'),
                delivered_source_ids=len(delivered), replayed_before_final_write_source_ids=len(replayed),
                delivered_without_prewrite_replay=len(delivered - replayed),
                complete_read_or_retrieve_ids=len(full_ids), partial_search_only_ids=len(partial_only),
                reader_saw_final_write_check=bool(trial.get('reader_saw_final_write_check')),
                complete_task=gate(trial, 'complete_task'), source_gate=gate(trial, 'citation_sufficient'),
                artifact_written=bool(trial.get('artifact_written')),
                termination=trial['termination'], failure_class=failure_class(trial))


def reader_tables(trials):
    summaries, paired, discovery_details, field_errors = [], [], [], []
    for key, group in sorted(grouped(trials, ('block', 'arm')).items()):
        block, arm = key
        calls = [c for t in group for c in t.get('calls', [])]
        usage_keys = sorted({k for c in calls for k in (c.get('usage') or {})})
        resources = {}
        for name in ('elapsed_seconds', 'supplied_context_bytes', 'returned_bytes'):
            values = [t[name] for t in group if name in t]
            resources[name] = dict(known_trials=len(values), median=float(np.median(values)) if values else None,
                                   minimum=float(min(values)) if values else None, maximum=float(max(values)) if values else None)
        usage = {}
        for name in usage_keys:
            known = [sum(c['usage'][name] for c in t['calls']) for t in group
                     if t.get('calls') and all(isinstance(c.get('usage'), dict) and name in c['usage'] for c in t['calls'])]
            usage[name] = dict(known_trials=len(known), unknown_trials=len(group) - len(known),
                              median=float(np.median(known)) if known else None,
                              total_known=float(sum(known)))
        summary = dict(block=block, arm=arm, trials=len(group), families=len({t['family_id'] for t in group}),
                       gates={g: dict(passes=sum(gate(t, g) for t in group),
                                      **interval([int(gate(t, g)) for t in sorted(group, key=lambda t: t['family_id'])]))
                              for g in GATES},
                       failure_classes=dict(Counter(failure_class(t) for t in group)),
                       terminations=dict(Counter(t['termination'] for t in group)), resources=resources,
                       usage=usage, reader_calls=len(calls), accepted_calls=sum(c.get('accepted', False) for c in calls),
                       calls_unknown_usage=sum(c.get('usage') is None for c in calls),
                       native_unavailable_calls=sum((c.get('control_receipt') or {}).get('native_failed_unavailable_count', 0) for c in calls),
                       forbidden_virtual_attempts=sum(t.get('forbidden_virtual_attempts', 0) for t in group))
        summaries.append(summary)
        for trial in group:
            for key, values in ((trial.get('score') or {}).get('field_errors') or {}).items():
                field_errors.append(dict(trial_id=trial['trial_id'], block=block, arm=arm,
                                         family_id=trial['family_id'], key=key, **values))
    for block, block_arms in (('main', ARMS), ('diagnostic', ('full_collection', 'oracle_evidence')),
                              ('discovery', ('raw_filesystem', 'retriever_filesystem'))):
        by_arm = {arm: {t['family_id']: t for t in trials if t['block'] == block and t['arm'] == arm}
                  for arm in block_arms}
        for baseline, alternative in itertools.combinations(block_arms, 2):
            ids = sorted(by_arm[baseline])
            if ids != sorted(by_arm[alternative]):
                raise ValueError('reader_pairing_not_complete')
            for metric in GATES:
                paired.append(dict(block=block, baseline=baseline, alternative=alternative, metric=metric,
                                   **interval([int(gate(by_arm[alternative][f], metric)) -
                                               int(gate(by_arm[baseline][f], metric)) for f in ids])))
    # Controls are compared only to the matched diagnostic subset, never 12 versus 24 unpaired trials.
    controls = [t for t in trials if t['block'] == 'diagnostic']
    for control_arm in ('full_collection', 'oracle_evidence'):
        controls_by_id = {t['family_id']: t for t in controls if t['arm'] == control_arm}
        for arm in ARMS:
            main_by_id = {t['family_id']: t for t in trials if t['block'] == 'main' and t['arm'] == arm}
            ids = sorted(controls_by_id)
            paired.append(dict(block='matched_diagnostic', baseline=arm, alternative=control_arm, metric='complete_task',
                               **interval([int(gate(controls_by_id[f], 'complete_task')) - int(gate(main_by_id[f], 'complete_task')) for f in ids])))
    for trial in trials:
        if trial['block'] != 'discovery':
            continue
        discovery_details.append(discovery_detail(trial))
    return dict(reader_arms=summaries, reader_paired_contrasts=paired,
                discovery_trials=discovery_details, exact_field_mismatches=field_errors)


def timing_tables(rows):
    summaries = []
    for engine in ENGINES:
        values = [r for r in rows if r['engine'] == engine]
        means = family_means(values, 'seconds')
        summaries.append(dict(engine=engine, observations=len(values), tasks=len({r['task_id'] for r in values}),
                              **interval(list(means.values())), median_seconds=float(np.median([r['seconds'] for r in values])),
                              minimum_seconds=min(r['seconds'] for r in values), maximum_seconds=max(r['seconds'] for r in values),
                              mean_scored_pairs=float(np.mean([r['scored_pairs'] for r in values])),
                              mean_scorer_input_pair_tokens=float(np.mean([r['scorer_tokens'] for r in values])),
                              truncated_pairs=sum(r['truncated_pairs'] for r in values)))
    return summaries


def style():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.titlesize': 12, 'axes.labelsize': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'savefig.facecolor': 'white', 'figure.facecolor': 'white',
                         'svg.fonttype': 'none', 'axes.axisbelow': True})


def save_figure(fig, name, title, caption, registry):
    fig.suptitle(title, fontsize=16, fontweight='bold', y=.992)
    fig.text(.02, .012, caption, fontsize=8, va='bottom', color='#444444', wrap=True)
    fig.tight_layout(rect=(0, .065, 1, .96))
    directory = HERE / 'figures'
    directory.mkdir(exist_ok=True)
    files = []
    for extension in ('png', 'svg'):
        path = directory / (name + '.' + extension)
        fig.savefig(path, dpi=180, metadata={'Creator': 'Frozen fictional atomic study analysis'})
        files.append(dict(file='figures/' + path.name, sha256=sha(path)))
    plt.close(fig)
    registry.append(dict(number=len(registry) + 1, title=title, caption=caption, files=files))


def heatmap(ax, values, row_labels, column_labels, divergent=False, percent=True):
    matrix = np.asarray(values, dtype=float)
    bound = max(.1, float(np.abs(matrix).max())) if divergent else 1
    im = ax.imshow(matrix, cmap='RdBu_r' if divergent else 'YlGnBu', aspect='auto',
                   norm=TwoSlopeNorm(vmin=-bound, vcenter=0, vmax=bound) if divergent else None,
                   vmin=None if divergent else 0, vmax=None if divergent else 1)
    ax.set_xticks(range(len(column_labels)), column_labels)
    ax.set_yticks(range(len(row_labels)), row_labels)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix[i, j]
            label = ('%+.0f' if divergent else '%.0f') % (value * 100) if percent else '%.1f' % value
            color = 'white' if ((abs(value) > .65 * bound) if divergent else value > .65) else '#152432'
            ax.text(j, i, label, ha='center', va='center', fontsize=9, color=color)
    return im


def forest(ax, records, labels, color='#406f91', limit=None):
    y = np.arange(len(records))
    values = np.array([r['estimate'] for r in records]) * 100
    lower = np.array([r['lower'] for r in records]) * 100
    upper = np.array([r['upper'] for r in records]) * 100
    ax.errorbar(values, y, xerr=np.vstack((values - lower, upper - values)), fmt='o',
                color=color, markersize=4, capsize=2, linewidth=1)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.axvline(0, color='#707070', linewidth=.8)
    ax.grid(axis='x', alpha=.2)
    if limit:
        ax.set_xlim(*limit)
    ax.set_xlabel('Difference in percentage points')


def plot_all(data, rows, timing, trials, execution):
    style()
    figures = []
    cells = data['retrieval_cells']
    primary = [r for r in cells if r['split'] == 'held_out' and r['author'] == 'both']
    lookup = {(r['engine'], r['factors'], r['budget'], r['collection_size']): r for r in primary}
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for ax, (budget, size) in zip(axes.flat, POLICIES):
        heatmap(ax, [[lookup[e, f, budget, size]['estimate'] for f in FACTORS] for e in ENGINES], ENGINE_LABELS, FACTORS)
        ax.set_title(f'{budget:,} UTF-8 bytes; {size} documents')
        ax.set_xlabel('A/B/C factor cell')
    save_figure(fig, '01-heldout-factorial', 'Complete original-evidence bundles across the held-out factorial',
                'Percent of 72 task queries in 36 held-out families. Equal family weight; two queries per family. A=index cues, B=dependency expansion, C=derived-view version gate.', figures)

    contrasts = [r for r in data['factorial_contrasts'] if r['split'] == 'held_out' and r['author'] == 'both']
    for number, wanted, title in ((2, ('A', 'B', 'C'), 'Paired atomic main effects on original-evidence recovery'),
                                  (3, ('AB', 'AC', 'BC', 'ABC'), 'Paired interactions between the atomic interventions')):
        fig, axes = plt.subplots(2, 2, figsize=(15, 12 if number == 2 else 15))
        for ax, (budget, size) in zip(axes.flat, POLICIES):
            records = [next(r for r in contrasts if r['engine'] == e and r['contrast'] == c and
                            r['budget'] == budget and r['collection_size'] == size) for e in ENGINES for c in wanted]
            labels = [LABEL[e] + ' · ' + c for e in ENGINES for c in wanted]
            forest(ax, records, labels)
            ax.set_title(f'{budget:,} bytes; {size} documents')
        caption = ('On/off differences averaged over other factors.' if number == 2 else
                   'AB/AC/BC are difference-in-differences averaged over the remaining factor; ABC is a third difference. Positive values indicate non-additivity on the rate scale.')
        save_figure(fig, f'{number:02d}-' + ('main-effects' if number == 2 else 'interactions'), title,
                    caption + ' 2,000 deterministic whole-family percentile bootstrap intervals; descriptive conditional on this authored bank.', figures)

    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    for ax, (budget, size) in zip(axes.flat, POLICIES):
        records = [next(r for r in data['engine_contrasts'] if r['split'] == 'held_out' and r['factors'] == '111' and
                        r['baseline'] == 'bm25' and r['alternative'] == e and r['budget'] == budget and r['collection_size'] == size)
                   for e in ENGINES[1:]]
        forest(ax, records, ENGINE_LABELS[1:])
        ax.set_title(f'111; {budget:,} bytes; {size} documents')
    save_figure(fig, '04-engine-paired-comparison', 'Engine changes with all three interventions enabled',
                'Recovery difference versus flat BM25, paired by held-out family. Intervals resample 36 whole families; engine scores are relevance scores, not authority probabilities.', figures)

    stage = {(r['engine'], r['factors']): r for r in data['evidence_stages']}
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    categories = ('candidate_1_packed_1', 'candidate_1_packed_0', 'candidate_0_packed_1', 'candidate_0_packed_0')
    stage_colors = ('#3e8875', '#dbac66', '#5f86b3', '#d6dce1')
    stage_labels = ('Candidates and packet complete', 'Candidate complete; packing loss',
                    'Outside candidates; expansion recovery', 'Neither complete')
    for ax, factor in zip(axes, ('101', '111')):
        bottom = np.zeros(len(ENGINES))
        for cat, color, label in zip(categories, stage_colors, stage_labels):
            values = np.array([stage[e, factor]['transitions'].get(cat, 0) / 72 for e in ENGINES])
            ax.barh(np.arange(6), values, left=bottom, color=color, label=label)
            bottom += values
        ax.set_yticks(range(6), ENGINE_LABELS)
        ax.invert_yaxis()
        ax.set_xlim(0, 1)
        ax.xaxis.set_major_formatter(PercentFormatter(1))
        ax.set_title(('Expansion off (101)' if factor == '101' else 'Expansion on (111)') + '; 144 docs; 4,096 bytes')
        ax.set_xlabel('Share of held-out task queries')
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(.5, .045), ncol=2, fontsize=9)
    save_figure(fig, '05-candidate-versus-packing-loss', 'Where complete evidence is lost or recovered',
                'Original evidence is eligible under every gate policy. Candidate availability is a ceiling only with B=0; declared-edge expansion can recover evidence outside routed/reranked seeds.', figures)

    strata = sorted({r['stratum'] for r in data['stratum_joint_policy_contrasts']})
    fig, ax = plt.subplots(figsize=(12, 7))
    strata_lookup = {(r['stratum'], r['engine']): r for r in data['stratum_joint_policy_contrasts']}
    im = heatmap(ax, [[strata_lookup[s, e]['estimate'] for e in ENGINES] for s in strata],
                 [s.replace('_', ' ') + f" (n={strata_lookup[s, ENGINES[0]]['families']})" for s in strata], ENGINE_LABELS, divergent=True)
    fig.colorbar(im, ax=ax, label='111 minus 000 recovery rate', shrink=.8, format=PercentFormatter(1))
    save_figure(fig, '06-authored-strata-effects', 'Joint-policy effects depend on the authored fault stratum',
                'Percentage-point changes at 144 documents / 4,096 bytes. n denotes whole held-out families, not queries; stratum intervals and raw baseline/combined rates are in analysis.json.', figures)

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    for ax, (budget, size) in zip(axes.flat, POLICIES):
        configurations = [lookup[e, '111', budget, size] for e in ENGINES]
        points = [(r['medians']['mixedbread_packet_tokens'], r['estimate']) for r in configurations]
        frontier = pareto(points)
        for e, r in zip(ENGINES, configurations):
            x = r['medians']['mixedbread_packet_tokens']
            ax.errorbar(x, r['estimate'], yerr=[[r['estimate'] - r['lower']], [r['upper'] - r['estimate']]],
                        fmt='o', color=COLORS[e], label=LABEL[e], capsize=3)
            ax.annotate(f"{r['medians']['bytes']:,.0f} B", (x, r['estimate']), xytext=(5, 5), textcoords='offset points', fontsize=8)
        ordered = sorted(frontier, key=lambda i: points[i][0])
        ax.plot([points[i][0] for i in ordered], [points[i][1] for i in ordered], color='#555555', linestyle=':', linewidth=1)
        ax.set_ylim(-.05, 1.06)
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.set_title(f'111; {budget:,} bytes; {size} documents')
        ax.set_xlabel('Median reconstructed Mixedbread packet tokens')
        ax.set_ylabel('Complete original-evidence bundles')
        ax.grid(alpha=.2)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(.5, .047), ncol=3, fontsize=8)
    save_figure(fig, '07-context-recovery-frontier', 'Actual supplied packet context and evidence recovery',
                'Labels show median UTF-8 bytes. Dotted lines connect observed non-dominated configurations using point estimates; no optimality claim. Local tokenizer counts are not Muse billable tokens.', figures)

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    rng = np.random.default_rng(SEED)
    for i, e in enumerate(ENGINES):
        group = [r for r in timing if r['engine'] == e]
        values = [r['seconds'] for r in group]
        axes[0, 0].scatter(i + rng.uniform(-.16, .16, len(values)), values, s=13, alpha=.6, color=COLORS[e])
        axes[0, 0].plot([i - .23, i + .23], [np.median(values)] * 2, color='black', linewidth=2)
        axes[0, 1].bar(i, np.mean([r['scored_pairs'] for r in group]), color=COLORS[e])
        axes[1, 0].scatter([r['scorer_tokens'] for r in group], values, s=16, color=COLORS[e], alpha=.65, label=LABEL[e])
        point = lookup[e, '111', 4096, 144]
        axes[1, 1].scatter(np.median(values), point['estimate'], color=COLORS[e], s=55)
        axes[1, 1].annotate(LABEL[e], (np.median(values), point['estimate']), xytext=(4, 4), textcoords='offset points', fontsize=8)
    for ax in axes[0]:
        ax.set_xticks(range(6), ENGINE_LABELS, rotation=30, ha='right')
    axes[0, 0].set_ylabel('Actual uncached warm rank + pack seconds')
    axes[0, 0].set_title('144 fresh timing measurements; black line = median')
    axes[0, 0].set_yscale('log')
    axes[0, 1].set_ylabel('Mean locally scored query/text pairs')
    axes[0, 1].set_title('Scoring work per uncached ranking')
    axes[1, 0].set_xlabel('Local scorer input-pair tokens (capped at 512/pair)')
    axes[1, 0].set_ylabel('Warm rank + pack seconds')
    axes[1, 0].set_title('Recorded computation, not reconstructed context')
    axes[1, 1].set_xscale('log')
    axes[1, 1].set_xlabel('Median uncached warm seconds (development workload)')
    axes[1, 1].set_ylabel('Held-out original-bundle recovery at 111 / 144 / 4,096')
    axes[1, 1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1, 1].set_ylim(-.05, 1.08)
    for ax in axes.flat:
        ax.grid(alpha=.2)
    save_figure(fig, '08-uncached-computation-frontier', 'Measured local computation and the speed/context trade-off',
                'Timing uses 6 development families × 2 queries × 2 repetitions × 6 engines, without pair caching. Model load/download excluded; index/rank/pack combined. Timing and held-out quality are different workloads.', figures)

    readers = {(r['block'], r['arm']): r for r in data['reader_arms']}
    fig, axes = plt.subplots(2, 1, figsize=(15, 8), gridspec_kw={'height_ratios': [2, 1]})
    for ax, block, arms in ((axes[0], 'main', ARMS), (axes[1], 'diagnostic', ('full_collection', 'oracle_evidence'))):
        values = [[readers[block, arm]['gates'][g]['estimate'] for g in GATES] for arm in arms]
        heatmap(ax, values, [ARM_LABEL[a] + f" (n={readers[block, a]['trials']})" for a in arms], GATE_LABELS)
        ax.set_title('Resource-matched packet arms' if block == 'main' else 'Separate diagnostic controls on 12 matched families')
    save_figure(fig, '09-reader-gates-and-controls', 'Downstream exact-value and source-match gates',
                'Each gate is reported independently. Complete task also requires artifact write, structural check and clean completion. Exact authored answer matching penalizes synonyms and list order; it is not semantic equivalence. Controls are not deployment policies.', figures)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6), gridspec_kw={'width_ratios': [1, 1.3]})
    records = [r for r in data['reader_paired_contrasts'] if r['block'] == 'main' and
               r['baseline'] == 'bm25_000' and r['metric'] == 'complete_task']
    forest(axes[0], records, [ARM_LABEL[r['alternative']] for r in records])
    axes[0].set_title('Paired complete-task difference vs BM25 000')
    categories = ('complete_exact_value_and_source', 'infrastructure_failure', 'no_accepted_artifact',
                  'structure_failure', 'exact_authored_value_or_status_mismatch', 'source_match_failure', 'unclean_or_forbidden_completion')
    error_colors = ('#3e8875', '#676767', '#ad90ac', '#bd825d', '#d6ab59', '#688dac', '#b9c0c6')
    bottom = np.zeros(4)
    for category, color in zip(categories, error_colors):
        values = np.array([readers['main', arm]['failure_classes'].get(category, 0) for arm in ARMS])
        axes[1].barh(range(4), values, left=bottom, label=category.replace('_', ' '), color=color)
        bottom += values
    axes[1].set_yticks(range(4), [ARM_LABEL[a] for a in ARMS])
    axes[1].invert_yaxis()
    axes[1].set_xlim(0, 24)
    axes[1].set_xlabel('Scheduled trials, including infrastructure failures')
    axes[1].set_title('Mutually exclusive outcome classes (precedence documented)')
    axes[1].legend(fontsize=7, loc='upper center', bbox_to_anchor=(.5, -.13), ncol=2)
    save_figure(fig, '10-reader-paired-effects-and-failures', 'Reader differences and observed failure classes',
                'Whole-family bootstrap on 24 paired held-out families. Failure precedence: infrastructure → absent artifact → structure → exact answer/status mismatch → source mismatch → unclean/forbidden finish. No semantic regrading.', figures)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    discovery_arms = ('raw_filesystem', 'retriever_filesystem')
    wanted = ('factual_correct', 'citation_sufficient', 'structural_check_pass', 'clean_finish', 'complete_task')
    x = np.arange(len(wanted))
    for offset, arm in zip((-.18, .18), discovery_arms):
        summary = readers['discovery', arm]
        axes[0].bar(x + offset, [summary['gates'][g]['estimate'] for g in wanted], width=.35,
                    label=ARM_LABEL[arm], color='#50677a' if arm == 'raw_filesystem' else '#3c8b77')
    axes[0].set_xticks(x, ('Exact answer\n+ status', 'Source\nmatch', 'Host\nstructure', 'Clean\nfinish', 'Complete\ntask'))
    axes[0].set_ylim(0, 1.12)
    axes[0].yaxis.set_major_formatter(PercentFormatter(1))
    axes[0].set_title('All 12 scheduled trials per discovery arm')
    axes[0].legend(fontsize=8)
    records = [r for r in data['reader_paired_contrasts'] if r['block'] == 'discovery' and r['metric'] in wanted]
    forest(axes[1], records, [r['metric'].replace('_', ' ') for r in records])
    axes[1].set_title('Filesystem + retriever minus raw filesystem')
    save_figure(fig, '11-discovery-outcomes', 'Fresh virtual-filesystem discovery: outcome and grounding gates',
                '12 matched held-out families; failures and no-write trials remain in the denominator. Source match uses IDs replayed before the final write; same-batch delivery is insufficient. Search excerpts remain distinguishable from complete reads.', figures)

    details = data['discovery_trials']
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for offset, arm in zip((0, 1), discovery_arms):
        group = sorted([r for r in details if r['arm'] == arm], key=lambda r: r['family_id'])
        color = '#50677a' if offset == 0 else '#3c8b77'
        jitter = np.linspace(-.15, .15, len(group))
        axes[0, 0].scatter(np.array([r['response_turns'] for r in group]) + jitter,
                           [r['actions'] for r in group], label=ARM_LABEL[arm], color=color, marker='o' if offset == 0 else '^')
        values = [r['returned_bytes'] for r in group if r['returned_bytes'] is not None]
        axes[0, 1].scatter(np.full(len(values), offset) + jitter[:len(values)], values, color=color)
        metrics = ('delivered_source_ids', 'replayed_before_final_write_source_ids',
                   'complete_read_or_retrieve_ids', 'partial_search_only_ids', 'delivered_without_prewrite_replay')
        axes[1, 0].bar(np.arange(len(metrics)) + (-.18 if offset == 0 else .18),
                       [np.mean([r[m] for r in group]) for m in metrics], width=.35, color=color, label=ARM_LABEL[arm])
        ops = ('list', 'search', 'read', 'retrieve', 'write', 'invalid')
        axes[1, 1].bar(np.arange(len(ops)) + (-.18 if offset == 0 else .18),
                       [sum(r['operations'].get(op, 0) for r in group) for op in ops], width=.35, color=color)
    axes[0, 0].set_xlabel('Reader responses (bounded at four; slight jitter)')
    axes[0, 0].set_ylabel('Requested actions (bounded at sixteen)')
    axes[0, 0].set_title('Each point is one scheduled discovery trial')
    axes[0, 0].set_xticks(range(5))
    axes[0, 0].legend(fontsize=8)
    axes[0, 1].set_xticks((0, 1), [ARM_LABEL[a] for a in discovery_arms])
    axes[0, 1].axhline(16384, color='#b1594f', linestyle=':', label='16,384 returned-byte cap')
    axes[0, 1].set_ylabel('Actually returned UTF-8 bytes')
    axes[0, 1].set_title('Observation budget, including bounded errors')
    axes[1, 0].set_xticks(range(5), ('Host\ndelivered', 'Replayed\nbefore write', 'Complete read\nor retrieve', 'Only partial\nsearch', 'No prewrite\nreplay'))
    axes[1, 0].set_ylabel('Mean distinct source IDs per trial')
    axes[1, 0].set_title('Receipt modes are observable grounding proxies')
    axes[1, 1].set_xticks(range(6), ('list', 'search', 'read', 'retrieve', 'write', 'invalid'))
    axes[1, 1].set_ylabel('Total requested operations')
    axes[1, 1].set_title('Observed navigation and artifact-write workload')
    save_figure(fig, '12-discovery-steps-and-replay', 'Discovery steps, bounded observations and pre-write source replay',
                'Host delivery does not prove model use. Receipt IDs exclude observations first delivered in the final write turn; partial search receipts do not certify full-record comprehension. Per-trial refusal/termination details remain in analysis.json.', figures)

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for ax, (split, writer) in zip(axes.flat, itertools.product(('development', 'held_out'), ('A', 'B'))):
        records = [next(r for r in data['author_split_joint_policy_contrasts'] if r['split'] == split and
                        r['author'] == writer and r['engine'] == e and r['budget'] == 4096 and r['collection_size'] == 144)
                   for e in ENGINES]
        forest(ax, records, ENGINE_LABELS)
        ax.set_title(f"Author {writer}; {split.replace('_', ' ')}; n={records[0]['families']} families")
    save_figure(fig, '13-author-and-split-heterogeneity', 'Joint-policy differences by author and split',
                '111 minus 000 at 144 documents / 4,096 bytes. Development and held-out records remain separate. Authors share framing and templates; author-specific intervals do not create independent author populations.', figures)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    ordered = [('main', a) for a in ARMS] + [('diagnostic', a) for a in ('full_collection', 'oracle_evidence')]
    for i, key in enumerate(ordered):
        summary = readers[key]
        color = '#50677a' if key[0] == 'main' else '#ad8955'
        for ax, metric in zip(axes, ('supplied_context_bytes', 'elapsed_seconds')):
            resource = summary['resources'][metric]
            if resource['median'] is None:
                continue
            ax.plot([resource['minimum'], resource['maximum']], [i, i], color=color, linewidth=1)
            ax.scatter(resource['median'], i, color=color, s=35)
    for ax in axes:
        ax.set_yticks(range(len(ordered)), [ARM_LABEL[a] + (' [control]' if b == 'diagnostic' else '') for b, a in ordered])
        ax.invert_yaxis()
        ax.set_xscale('log')
        ax.grid(axis='x', alpha=.2)
    axes[0].set_xlabel('Supplied packet UTF-8 bytes (median and observed range)')
    axes[1].set_xlabel('Trial elapsed seconds (median and observed range)')
    axes[0].set_title('Controls receive different context resources')
    axes[1].set_title('Actual fresh reader + host-write/check elapsed time')
    save_figure(fig, '14-reader-context-and-time', 'Reader resources: fixed packets and separate diagnostic controls',
                'Full collection is not resource-matched to small packets. Unknown supplied context is omitted, not recorded as zero; scheduled trials still count as failures. Provider-reported usage and missingness are separate from local tokenizer counts in analysis.json.', figures)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    for ax, budget in zip(axes, (4096, 8192)):
        x = np.arange(len(ENGINES))
        for offset, factor, color in ((-.18, '000', '#50677a'), (.18, '111', '#3c8b77')):
            selected = [lookup[e, factor, budget, 144] for e in ENGINES]
            ax.bar(x + offset, [r['estimate'] for r in selected], width=.35, color=color,
                   label='Observed ' + factor)
            ceiling = selected[0]['authored_bundle_feasibility_ceiling']
            ax.axhline(ceiling, color=color, linestyle='--', linewidth=1,
                       label=f'{factor[0]} index cues: authored-bundle byte ceiling {ceiling:.1%}')
        ax.set_xticks(x, ENGINE_LABELS, rotation=25, ha='right')
        ax.set_ylim(0, 1.09)
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.set_title(f'144 documents; {budget:,} UTF-8 bytes')
        ax.set_ylabel('Complete original-evidence recovery')
        ax.legend(fontsize=8, loc='lower right')
    save_figure(fig, '15-whole-record-budget-feasibility', 'The fixed byte budget imposes an authored-bundle recovery ceiling',
                'Ceiling uses the smallest declared sufficient-original set serialized as whole records. Authored sets are non-exhaustive. A changes both index cues and packet byte cost; conditional feasible-query recovery is separately tabulated without changing the frozen primary metric.', figures)
    return figures


def findings(data, execution):
    cells = [r for r in data['retrieval_cells'] if r['split'] == 'held_out' and r['author'] == 'both']
    policy = [r for r in cells if r['factors'] == '111' and r['budget'] == 4096 and r['collection_size'] == 144]
    readers = [r for r in data['reader_arms'] if r['block'] == 'main']
    discovery = [r for r in data['reader_arms'] if r['block'] == 'discovery']
    joint = [r for r in data['author_split_joint_policy_contrasts'] if r['split'] == 'held_out' and r['author'] == 'both' and
             r['budget'] == 4096 and r['collection_size'] == 144]
    return [
        dict(topic='held_out_fixed_policy_recovery', policy='111 / 144 documents / 4096 UTF-8 bytes',
             values={r['engine']: {k: r[k] for k in ('estimate', 'lower', 'upper', 'families', 'complete_task_queries')} for r in policy}),
        dict(topic='joint_policy_difference', comparison='111 minus 000; paired families; 144 / 4096',
             values={r['engine']: {k: r[k] for k in ('estimate', 'lower', 'upper', 'families')} for r in joint}),
        dict(topic='main_reader_exact_value_source_task', denominator=24,
             values={r['arm']: r['gates']['complete_task'] for r in readers}),
        dict(topic='discovery_exact_value_source_task', denominator=12,
             values={r['arm']: r['gates']['complete_task'] for r in discovery}),
        dict(topic='cached_vs_measured_computation', unique_cached_pairs=execution.get('unique_cached_pair_count'),
             timing='Only 144 separately executed uncached development observations support warm rank/pack latency comparisons.'),
        dict(topic='metric_limit', statement='Primary reader metric is exact authored value/status plus valid sufficient original sources and clean completion. Synonyms and list ordering can fail exact match without showing semantic factual disagreement.'),
        dict(topic='fixed_budget_feasibility', statement='Index cues consume packet bytes. A contrasts combine retrieval-cue benefit and serialization cost under a fixed budget; non-exhaustive authored sufficient sets define the scored feasibility ceiling.',
             held_out_ceilings={f'A{a}_budget{budget}': next(r['authored_bundle_feasibility_ceiling'] for r in cells
                                                           if r['engine'] == 'bm25' and r['factors'] == (str(a) + '00') and
                                                           r['budget'] == budget and r['collection_size'] == 144)
                                for a in (0, 1) for budget in (4096, 8192)}),
        dict(topic='scope', statement='Conditional descriptive results for 48 LLM-authored family clusters; 36 held-out. No universal engine winner, representative vault inference, or semantic-reader accuracy claim follows.')]


def selfcheck():
    # Known finite differences: additive A=0.1, B=0.2, C=0.05 plus AB=0.08.
    cells = {f: .1 + .1 * int(f[0]) + .2 * int(f[1]) + .05 * int(f[2]) + .08 * int(f[0]) * int(f[1]) for f in FACTORS}
    assert abs(effect(cells, 'A') - .14) < 1e-12
    assert abs(effect(cells, 'B') - .24) < 1e-12
    assert abs(effect(cells, 'C') - .05) < 1e-12
    assert abs(effect(cells, 'AB') - .08) < 1e-12
    assert abs(effect(cells, 'AC')) < 1e-12 and abs(effect(cells, 'ABC')) < 1e-12
    constant = interval([.25, .25, .25])
    assert constant == dict(estimate=.25, lower=.25, upper=.25, families=3)
    assert interval([0, .5, 1]) == interval([0, .5, 1])
    assert ratio_interval([1, 0], [1, 0])['estimate'] == 1
    assert ratio_interval([0, 0], [0, 0])['estimate'] is None
    rows = [{'family_id': 'A01', 'value': 0}, {'family_id': 'A01', 'value': 1},
            {'family_id': 'B01', 'value': 1}, {'family_id': 'B01', 'value': 1}]
    assert family_means(rows, 'value') == {'A01': .5, 'B01': 1}
    assert interval(list(family_means(rows, 'value').values()))['families'] == 2
    assert pareto([(10, .5), (20, .4), (15, .7), (15, .7)]) == [0, 2, 3]
    assert gate({'score': None}, 'factual_correct') is False
    good = dict(complete_task=True)
    assert failure_class(good) == 'complete_exact_value_and_source'
    assert failure_class(dict(infrastructure_error=True)) == 'infrastructure_failure'
    assert failure_class(dict(artifact_written=True, structural_check_pass=True,
                             score=dict(schema_valid=True, factual_correct=False))) == 'exact_authored_value_or_status_mismatch'
    # Receipt modes distinguish partial search and sources first delivered during the write turn.
    trial = dict(trial_id='R001', family_id='A01', arm='raw_filesystem', block='discovery',
                 score={}, complete_task=False, artifact_written=True, termination='reader_done',
                 source_modes_supplied_before_final_write={'A01R01': ['search'], 'A01R02': ['read']},
                 host_delivered_source_ids=['A01R01', 'A01R02', 'A01R03'],
                 source_id_receipts=['A01R01', 'A01R02'], calls=[], events=[], returned_bytes=42)
    # Exercise only receipt classification; matched schedule validation is performed at --run.
    detail = discovery_detail(trial)
    assert detail['complete_read_or_retrieve_ids'] == 1
    assert detail['partial_search_only_ids'] == 1
    assert detail['delivered_without_prewrite_replay'] == 1
    return dict(state='passed', seed=SEED, bootstrap_replicates=REPLICATES,
                checks=['finite_difference_scaling', 'deterministic_whole_family_bootstrap',
                        'family_aggregation', 'pareto_ties', 'failed_trials_retained',
                        'failure_precedence', 'partial_search_and_prewrite_replay'],
                model_weight_loads=0, reader_calls=0)


def run(cache):
    check = selfcheck()
    rows, rankings, timing, trials, families, freeze = validate_inputs()
    counts, reader_counts, tokenizer_manifest, unique_packets, feasibility = reconstruct_tokens(rows, trials, cache, freeze)
    data = retrieval_tables(rows)
    data.update(reader_tables(trials))
    data['uncached_timing_engines'] = timing_tables(timing)
    execution = read('model-execution.json')
    input_names = ('PLAN.md', 'benchmark.py', 'run_readers.py', 'model_runtime.py', 'check_artifact.py',
                   'author-a.json', 'author-b.json', 'family-split.json', 'reader-schedule.json', 'freeze.json',
                   'retrieval-results.json', 'rankings.json', 'timing-results.json', 'reader-results.json', 'model-execution.json')
    data.update(schema_version=1, study='2026-10-11 prospective atomic fictional retrieval', state='complete',
                input_sha256={name: sha(HERE / name) for name in input_names},
                analysis_code_sha256=sha(Path(__file__)), selfcheck=check,
                methods=dict(seed=SEED, bootstrap_replicates=REPLICATES, interval='descriptive 95% percentile',
                             resampling_unit='whole semantic family; retain both queries and all paired cells',
                             weighting='equal family means; reader uses one selected query per family',
                             contrasts='A=on-off averaged over B/C; AB=(11-10)-(01-00) averaged over C; AC/BC analogously; ABC=AB(C=1)-AB(C=0). Tables retain each budget and collection size separately; differences use family means and percentage-point plotting, not regression coefficients.',
                             scope='conditional on this non-random LLM-authored bank; no multiplicity correction; no population or causal-generalization claim',
                             timing='144 uncached warmed rank/pack observations on six development families; no cached rank receipts used for speed',
                             primary_reader_metric='exact authored answer/status plus sufficient valid original-source citations, artifact write, structural check, clean finish and zero forbidden virtual attempts',
                             exact_match_caveat='Synonyms, freeform paraphrases and list order can fail exact authored matching; scores are not semantic factual equivalence.',
                             controls='Full collection and sufficient-source oracle are distinct diagnostic upper-bound/context controls on twelve families, not deployable policies.',
                             unknown_usage='Missing infrastructure usage is unknown, never a fabricated zero.',
                             provider_usage='Provider usage fields are retained separately. Reasoning tokens are not added to output totals; no derived sum assumes whether provider fields overlap.',
                             fixed_budget_ceiling='Minimum byte size of an authored sufficient-original set bounds the frozen bundle outcome; authored sets are non-exhaustive. A also adds packet serialization bytes. Feasible-query ratios resample whole-family success and feasible counts, without replacing the primary outcome.',
                             discovery_grounding='IDs from complete read, retrieve, or partial-search observations replayed before final write; delivery in the write turn is excluded.',
                             token_counts='Reconstructed local tokenizer text-only counts with no truncation/special tokens; not Muse billable usage.'),
                counts=dict(retrieval_rows=len(rows), rankings=len(rankings), families=len(families),
                            development_families=12, held_out_families=36, tasks=96,
                            uncached_timing_observations=len(timing), readers=len(trials),
                            reader_blocks=dict(Counter(t['block'] for t in trials)), unique_packet_digests=unique_packets),
                tokenizer_manifest=tokenizer_manifest, packet_local_token_counts=counts,
                authored_bundle_feasibility=feasibility,
                reader_packet_local_token_counts=reader_counts,
                local_model_costs={name: {k: model.get(k) for k in ('acquire_or_checksum_seconds', 'load_seconds', 'threads', 'batch_size', 'providers')}
                                   for name, model in execution.get('models', {}).items()},
                first_local_scoring_events={name: next((e for e in execution.get('inference_events', []) if e['model'] == name), None)
                                            for name in ('minilm', 'mixedbread')})
    data['narrative_ready_findings'] = findings(data, execution)
    data['figures'] = plot_all(data, rows, timing, trials, execution)
    atomic_json(HERE / 'analysis.json', data)
    print(json.dumps(dict(state='complete', analysis='analysis.json', figures=len(data['figures']),
                          bootstrap_replicates=REPLICATES, selfcheck=check['state']), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--self-check', action='store_true')
    mode.add_argument('--run', action='store_true')
    parser.add_argument('--cache', type=Path, help='External pinned tokenizer cache; model weights are never loaded')
    args = parser.parse_args()
    if args.self_check:
        print(json.dumps(selfcheck(), sort_keys=True))
    elif args.cache is None:
        parser.error('--run requires --cache EXTERNAL_TOKENIZER_CACHE')
    else:
        run(args.cache)
