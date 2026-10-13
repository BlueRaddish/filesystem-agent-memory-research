"""Frozen, census-preserving analysis; no model loading or study execution.

Self-checks and optional artificial full-shape plot previews require no outcomes.
Actual analysis refuses incomplete inputs and emits JSON plus scientific PNG/SVG.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

HERE = Path(__file__).resolve().parent
SEED, REPLICATES = 1013, 2000
PRIMARY = 'declared_span_bundle_recovered'
PACKET_METRICS = (PRIMARY, 'declared_whole_bundle_recovered', 'original_id_bundle',
                  'best_declared_span_fraction', 'selected_stale_views',
                  'selected_unverifiable_views', 'budget_skipped_units', 'fault')
GATES = ('artifact_written', 'contract_valid', 'typed_answer_status_match', PRIMARY,
         'declared_original_citation_set', 'complete_task', 'clean_complete_task')
EXTENDED = ('body_bm25', 'entity_rrf', 'dense_window_rrf', 'minilm_passages')
GROUPS = (
    ('Lexical / fields', ('body_bm25', 'search_bm25', 'word_tfidf', 'char_tfidf',
                        'field_bm25', 'rrf_word_char', 'entity_rrf')),
    ('Structure / applicability', ('clause_rrf', 'sentence_maxsim', 'coverage_mmr',
                                  'scope_temporal', 'graph_diffusion', 'pseudo_feedback', 'shallow_tree')),
    ('Dense / pair scoring', ('dense_body', 'dense_search', 'dense_windows', 'dense_window_rrf',
                             'minilm_body', 'mixedbread_body', 'minilm_passages')),
)
METHODS = tuple(m for _, group in GROUPS for m in group)
PACKERS = ('whole_record', 'ranked_body', 'sentence_neighbors', 'closure_passages',
           'original_first', 'diversity_passages', 'coverage_bundles', 'authority_pairs')
COLORS = ('#24648c', '#ba4d35', '#4d805a', '#865699', '#a87825', '#596579')
BOOTSTRAP_INDICES = {}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def value_hash(value):
    return hashlib.sha256(canonical(value).encode('utf8')).hexdigest()


def file_hash(path):
    with Path(path).open('rb') as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                                    allow_nan=False) + '\n', encoding='utf8', newline='\n')
    temporary.replace(path)


def cells(method):
    packers = PACKERS if method in EXTENDED else ('whole_record', 'closure_passages')
    return [(p, b) for p in packers for b in (4096, 8192, 16384)]


def identity(row):
    return row['family_id'], row['task_id']


def cell(row):
    return row['split'], row['ranker'], row['packer'], row['budget'], str(row['size'])


def nested_means(rows, metric):
    """Equal query means inside histories, equal histories inside template groups."""
    families = defaultdict(list)
    for row in rows:
        families[row['template_family'], row['family_id']].append(float(row[metric]))
    groups = defaultdict(list)
    for (group, _), values in families.items():
        groups[group].append(statistics.fmean(values))
    return {g: statistics.fmean(values) for g, values in sorted(groups.items())}


def cluster_interval(group_values):
    require(bool(group_values), 'No template groups for interval')
    values = list(group_values.values())
    import numpy as np
    if len(values) not in BOOTSTRAP_INDICES:
        rng = random.Random(SEED)
        BOOTSTRAP_INDICES[len(values)] = np.asarray([[rng.randrange(len(values)) for _ in values]
                                                    for _ in range(REPLICATES)], dtype=np.int32)
    # One seeded cluster-index matrix is shared by all same-size matched arms.
    # Vectorization keeps the exhaustive grid analysis practical on this host.
    replicates = np.sort(np.asarray(values)[BOOTSTRAP_INDICES[len(values)]].mean(axis=1))
    def percentile(p):
        position = (len(replicates) - 1) * p
        lower = int(position)
        upper = min(lower + 1, len(replicates) - 1)
        return float(replicates[lower] + (replicates[upper] - replicates[lower]) * (position - lower))
    return {'estimate': statistics.fmean(values), 'ci_low': percentile(.025),
            'ci_high': percentile(.975), 'template_groups': len(values), 'group_means': group_values,
            'replicates': REPLICATES, 'seed': SEED, 'interval': 'descriptive cluster percentile'}


def summarize(rows, metric):
    return {**cluster_interval(nested_means(rows, metric)), 'scheduled_rows': len(rows),
            'families': len({r['family_id'] for r in rows})}


def paired(left, right, metric):
    a, b = {identity(r): r for r in left}, {identity(r): r for r in right}
    require(len(a) == len(left) and len(b) == len(right) and a.keys() == b.keys(),
            'Paired comparison has duplicates or unmatched query IDs')
    rows, change = [], Counter()
    regression_ids = []
    for key in sorted(a):
        require(a[key]['template_family'] == b[key]['template_family'], 'Pair group mismatch')
        difference = float(a[key][metric]) - float(b[key][metric])
        label = 'improved' if difference > 0 else 'regressed' if difference < 0 else 'tied'
        change[label] += 1
        if difference < 0:
            regression_ids.append(list(key))
        rows.append({**{k: a[key][k] for k in ('family_id', 'task_id', 'template_family')},
                     'difference': difference})
    return {**summarize(rows, 'difference'), 'improved': change['improved'],
            'regressed': change['regressed'], 'tied': change['tied'],
            'regression_query_ids': regression_ids}


def support(task, observations, docs):
    import study_common
    expanded = []
    for observation in observations:
        require(observation.get('id') in docs, 'Observation names unknown source')
        doc = docs[observation['id']]
        start, end = observation.get('start'), observation.get('end')
        require(type(start) is int and type(end) is int and 0 <= start < end <= len(doc['body']),
                'Invalid source character interval')
        require(observation.get('source_hash') == study_common.digest(doc['body']), 'Source hash mismatch')
        expanded.append({**observation, 'text': doc['body'][start:end]})
    return study_common.support_metrics(task, expanded, docs)


def expected_census(queries):
    packets, rankings = set(), set()
    for family_id, task_id in queries:
        for size in ('144', 'all'):
            for method in METHODS:
                rankings.add((family_id, task_id, method, size))
                for packer, budget in cells(method):
                    packets.add((family_id, task_id, method, packer, budget, size))
    return packets, rankings


def event_costs(row):
    # The core interruption wrapper discards incomplete event traces: unknown is
    # not zero work, even when its conservative evidence score is zero.
    if row['block'] != 'discovery' or row.get('failure') == 'trial_execution_error' or 'events' not in row:
        return {'actions': None, 'rejected_actions': None}
    events = row['events']
    return {'actions': len(events), 'rejected_actions': sum(not e.get('executed', False) for e in events)}


def load_inputs(freeze_sha, preparation_path, maintenance_path, worker_receipts=None):
    import benchmark_runner
    import study_common
    import reader_trials
    import artifact_contract
    freeze = benchmark_runner.verify_freeze(freeze_sha)
    required = {'analyze_results.py', 'ANALYSIS-SPEC.md', 'reader_trials.py', 'reader-schedule.json',
                'artifact_contract.py', 'runtime-public.json', 'maintenance_lab.py'}
    require(required <= set(freeze['file_pins']), 'Freeze omits prospective analysis/reader/maintenance pins')
    require(file_hash(preparation_path) == freeze['prepare_receipt_sha256'], 'Preparation receipt mismatch')
    bank = study_common.bank()
    benchmark_runner.split_families(bank['families'])
    docs = study_common.documents(bank['families'])
    queries = {(f['id'], t['id']): (f, t) for f in bank['families'] for t in f['tasks']}
    collection_ids = {(f['id'], size): set(study_common.collection(docs, f['id'], size))
                      for f in bank['families'] for size in ('144', 'all')}
    require(len(bank['families']) == 96 and len(queries) == 288, 'Frozen bank census changed')
    require(Counter(f['split'] for f in bank['families']) == {'development': 24, 'confirmation': 72},
            'Split census changed')
    manifest = read(HERE / 'grid-manifest.json')
    require(manifest.get('state') == 'complete_grid_collection' and manifest.get('freeze_sha256') == freeze_sha,
            'Incomplete or foreign grid manifest')
    require(manifest.get('bank_sha256') == freeze['bank_sha256'], 'Grid bank identity mismatch')
    require(set(manifest['rankers']) == set(METHODS) and set(manifest['all_packers']) == set(PACKERS),
            'Grid methods changed')
    expected_packets, expected_rankings = expected_census(queries)
    seen_packets, seen_rankings = set(), set()
    packets, rankings, inputs = [], [], []
    failures, omissions = Counter(), Counter()
    for shard in manifest['shards']:
        path = (HERE / shard['file']).resolve()
        require(path.is_relative_to(HERE.resolve()), 'Shard path leaves study directory')
        require(file_hash(path) == shard['sha256'] and path.stat().st_size == shard['bytes'], 'Shard fixity mismatch')
        contents = read(path)
        require(contents.get('state') == 'complete' and contents.get('freeze_sha256') == freeze_sha,
                'Foreign or incomplete shard')
        require(len(contents['rows']) == shard['rows'], 'Shard row count mismatch')
        inputs.append({'file': path.relative_to(HERE).as_posix(), 'sha256': shard['sha256'], 'bytes': shard['bytes']})
        for row in contents['rows']:
            key = identity(row)
            require(key in queries, 'Unknown grid query')
            family, task = queries[key]
            require(row['template_family'] == family['template_family'] == contents['template_family']
                    and row['split'] == family['split'], 'Grid group/split scope mismatch')
            require(row['state'] in ('complete', 'fault'), 'Unknown cell state')
            compact = {k: row[k] for k in ('family_id', 'task_id', 'template_family', 'split', 'ranker', 'size', 'state')}
            compact['size'] = str(compact['size'])
            compact['fault'] = int(row['state'] == 'fault')
            if contents['kind'] == 'packets':
                pkey = (*key, row['ranker'], row['packer'], row['budget'], str(row['size']))
                require(pkey in expected_packets and pkey not in seen_packets, 'Duplicate/unscheduled packet cell')
                seen_packets.add(pkey)
                compact.update(packer=row['packer'], budget=row['budget'])
                if row['state'] == 'complete':
                    require(all(o['id'] in collection_ids[family['id'], str(row['size'])]
                                for o in row['observations']), 'Packet observation outside scheduled collection')
                    metrics = support(task, row['observations'], docs)
                    require(all(metrics[k] == row[k] for k in metrics), 'Exported packet support differs from sources')
                    require(type(row['bytes']) is int and 0 <= row['bytes'] <= row['budget'], 'Packet byte cap invalid')
                    compact.update({k: row[k] for k in PACKET_METRICS if k not in ('original_id_bundle', 'fault')})
                    compact['original_id_bundle'] = any(set(ids) <= set(metrics['observed_original_ids'])
                                                        for ids in task['evidence_sets'])
                    compact['bytes'] = row['bytes']
                    compact['span_count'] = sum(len(x) for x in task['evidence_spans'])
                    omissions.update(row['budget_skip_reasons'])
                else:
                    compact.update({k: 0 for k in PACKET_METRICS if k != 'fault'})
                    compact['bytes'] = None
                    failures['packet:' + row.get('failure_stage', 'packing') + ':' + row['error_type']] += 1
                packets.append(compact)
            elif contents['kind'] == 'rankings':
                rkey = (*key, row['ranker'], str(row['size']))
                require(rkey in expected_rankings and rkey not in seen_rankings, 'Duplicate/unscheduled ranking cell')
                seen_rankings.add(rkey)
                compact['candidates'] = {}
                if row['state'] == 'complete':
                    require(len(row['top64']) == 64 and len(set(row['top64'])) == 64, 'Top-64 IDs invalid')
                    require(set(row['top64']) <= collection_ids[family['id'], str(row['size'])], 'Ranking IDs outside collection')
                    metrics = benchmark_runner.candidate_metrics(task, row['top64'])
                    require(metrics == row['candidate_recovery'], 'Candidate metrics mismatch')
                    compact['candidates'] = {k: int(v['declared_original_bundle_in_candidates']) for k, v in metrics.items()}
                else:
                    compact['candidates'] = {str(k): 0 for k in (8, 16, 32, 64)}
                    failures['ranking:' + row['error_type']] += 1
                rankings.append(compact)
            else:
                raise ValueError('Unknown shard kind')
        # Deliberately retain only compact numeric records, not 114k source arrays.
        # One JSON shard is decoded at a time; larger banks should use streaming JSON.
        del contents
    require(seen_packets == expected_packets and seen_rankings == expected_rankings, 'Incomplete grid cell census')
    require(len(packets) == 114048 and len(rankings) == 12096, 'Grid count differs from frozen plan')
    require(manifest['counts']['packets'] == len(packets) and manifest['counts']['rankings'] == len(rankings)
            and manifest['counts']['packet_faults'] == sum(r['fault'] for r in packets)
            and manifest['counts']['ranking_faults'] == sum(r['fault'] for r in rankings), 'Grid manifest count mismatch')
    planned = reader_trials.schedule(bank)
    require(read(HERE / 'reader-schedule.json') == planned, 'Frozen reader schedule differs from recipe')
    reader_file = read(HERE / 'reader-results.json')
    require(reader_file.get('state') == 'complete' and reader_file.get('freeze_sha256') == freeze_sha
            and reader_file.get('scheduled_trials') == 192, 'Reader collection incomplete/foreign')
    jobs = {job['trial_id']: job for job in planned['jobs']}
    readers, seen = [], set()
    for row in reader_file['results']:
        trial_id = row['trial_id']
        require(trial_id in jobs and trial_id not in seen, 'Reader duplicate/unscheduled trial')
        seen.add(trial_id)
        require(row.get('state') == 'recorded' and all(row.get(k) == v for k, v in jobs[trial_id].items()),
                'Reader schedule scope changed')
        family, task = queries[identity(row)]
        observations = row.get('actual_prewrite_source_observations', [])
        verified = support(task, observations, docs)
        actual = artifact_contract.agreement(row.get('artifact'), task)
        require(all(row['outcome'].get(k) == v for k, v in {**verified, **actual}.items()), 'Reader frozen score mismatch')
        artifact = row.get('artifact')
        returned = row.get('returned_tool_bytes')
        require(returned is None or type(returned) is int and 0 <= returned <= 32768, 'Discovery byte cap invalid')
        compact = {**jobs[trial_id], **{k: bool(row['outcome'][k]) for k in GATES},
            'expected_status': task['expected']['status'],
            'actual_status': artifact.get('status') if isinstance(artifact, dict) else None,
            'returned_tool_bytes': returned, **event_costs(row),
            'elapsed_seconds': row.get('elapsed_seconds'), 'latency_comparable': bool(row.get('latency_comparable', False)),
            'failure': row.get('failure'), 'write_round': None,
            'first_support_round': None, 'first_support_submission_seconds': None,
            'false_hold': bool(task['expected']['status'] == 'ready' and isinstance(artifact, dict) and artifact.get('status') == 'hold'),
            'justified_hold': bool(task['expected']['status'] == 'hold' and row['outcome']['complete_task']),
            'unsupported_ready': bool(task['expected']['status'] == 'hold' and isinstance(artifact, dict) and artifact.get('status') == 'ready'),
            'prompt_input_bytes': None}
        write = row.get('write_receipt')
        recomputed = reader_trials.score(artifact, task, docs, observations, write, row['outcome'].get('clean_protocol', False))
        require(row['outcome'] == recomputed, 'Reader frozen complete/clean gates mismatch')
        if write:
            serialized = (json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf8')
            require(hashlib.sha256(serialized).hexdigest() == write.get('artifact_sha256'), 'Written artifact hash mismatch')
            require('artifact_bytes' not in write or len(serialized) == write['artifact_bytes'], 'Written artifact bytes mismatch')
            if write.get('check', {}).get('schema_valid'):
                require(write['check'] == artifact_contract.validate(artifact, task, docs), 'Artifact/checker citation or contract mismatch')
        require(compact['artifact_written'] == bool(write) and compact['contract_valid'] == bool(write and write.get('check', {}).get('schema_valid')),
                'Artifact/contract receipt gate mismatch')
        cited = set(write.get('check', {}).get('cited_original_ids', [])) if write else set()
        require(compact['declared_original_citation_set'] == any(set(ids) <= cited for ids in task['evidence_sets']),
                'Original citation-set gate mismatch')
        require(compact['complete_task'] == all(compact[g] for g in GATES[:5]), 'Complete task gate conjunction mismatch')
        prompt_sizes = [c.get('input_prompt_bytes') for c in row.get('calls', [])]
        if prompt_sizes and all(type(x) is int and x >= 0 for x in prompt_sizes):
            compact['prompt_input_bytes'] = sum(prompt_sizes)
        write_rounds = [e.get('round') for e in row.get('events', [])
                        if e.get('executed') and isinstance(e.get('action'), dict) and e['action'].get('tool') == 'write']
        compact['write_round'] = write_rounds[-1] if write_rounds else None
        deliveries = []
        for delivery in row.get('source_delivery_history', []):
            if delivery.get('upstream_text_verified') and (compact['write_round'] is None or delivery['round'] <= compact['write_round']):
                deliveries.extend(delivery['sources'])
                if compact['first_support_round'] is None and support(task, deliveries, docs)[PRIMARY]:
                    compact['first_support_round'] = delivery['round']
                    compact['first_support_submission_seconds'] = delivery['host_submission_elapsed_seconds']
        if row.get('failure'):
            failures['reader:' + row['failure']] += 1
        readers.append(compact)
    require(seen == jobs.keys(), 'Reader trial census incomplete')
    timing = read(HERE / 'warm-timing.json')
    require(timing.get('state') == 'complete_warm_timing' and timing.get('freeze_sha256') == freeze_sha,
            'Warm timing collection incomplete/foreign')
    require(timing.get('document_indexes_resident') is True and timing.get('query_embedding_or_pair_cache_enabled') is False
            and timing.get('neural_threads') == 2 and timing.get('serial_repetitions') == 3,
            'Warm timing cache/thread protocol changed')
    timing_keys = set()
    timing_queries = set()
    development = sorted((f for f in bank['families'] if f['split'] == 'development'),
                         key=lambda f: study_common.digest(f['id'] + ':oct13-timing-v1'))
    chosen = []
    for family in development:
        if family['template_family'] not in {f['template_family'] for f in chosen}:
            chosen.append(family)
    for family in development:
        if family not in chosen and len(chosen) < 6:
            chosen.append(family)
    planned_timing_queries = {(f['id'], f['tasks'][0]['id']) for f in chosen[:6]}
    for row in timing['rows']:
        require(identity(row) in queries and queries[identity(row)][0]['split'] == 'development', 'Timing query outside development')
        key = (*identity(row), row['ranker'], row['repetition'])
        require(key not in timing_keys and row['ranker'] in METHODS and row['repetition'] in (1, 2, 3), 'Timing cell invalid')
        require(type(row['seconds']) in (int, float) and math.isfinite(row['seconds']) and row['seconds'] >= 0, 'Timing duration invalid')
        require(not row['pairs_or_vector_usage'].get('query_embedding_cache_hit', False)
                and not row['pairs_or_vector_usage'].get('dense_score_cache_hit', False), 'Warm query cache hit')
        require(str(row['size']) == '144' and row['budget'] == 8192 and row['packer'] == 'closure_passages',
                'Warm timing packing/corpus cell changed')
        timing_keys.add(key)
        timing_queries.add(identity(row))
    require(timing_queries == planned_timing_queries and timing_keys == {(*q, m, r) for q in timing_queries for m in METHODS for r in (1, 2, 3)},
            'Timing census incomplete')
    maintenance_path = Path(maintenance_path).resolve()
    require(maintenance_path.is_relative_to(HERE), 'Public maintenance input must be inside study directory')
    maintenance = read(maintenance_path)
    require(maintenance.get('state') == 'complete_engineered_replay', 'Maintenance replay incomplete')
    require(maintenance.get('seeds') == 64 and maintenance.get('events_per_seed') == 20,
            'Prescribed maintenance seed/event schedule changed')
    policies = ('no_invalidation', 'ttl_5', 'global', 'direct_dependencies', 'transitive_dependencies')
    maintenance_keys = {(r['seed'], r['step'], r['policy'], r['missing_declared_edge']) for r in maintenance['rows']}
    expected = {(s, e, p, missing) for s in range(maintenance['seeds'])
                for e in range(1, maintenance['events_per_seed'] + 1) for p in policies for missing in (False, True)}
    require(len(maintenance_keys) == len(maintenance['rows']) and maintenance_keys == expected, 'Maintenance census incomplete')
    require(isinstance(maintenance.get('commit_checks'), dict) and isinstance(maintenance.get('semantic_ledger_counterexample'), dict),
            'Maintenance local-commit/semantic-boundary checks absent')
    for path in (HERE / 'grid-manifest.json', HERE / 'reader-results.json', HERE / 'warm-timing.json', maintenance_path):
        inputs.append({'file': path.relative_to(HERE).as_posix(), 'sha256': file_hash(path), 'bytes': path.stat().st_size})
    prepared = read(preparation_path)
    preprocessing = {'model_load_seconds': prepared['dense_model'].get('model_load_seconds'),
        'indexes': {k: {field: v.get(field) for field in ('index_cache_hit', 'build_or_cache_load_seconds',
                                                       'vectors', 'vector_storage_bytes')}
                    for k, v in prepared['dense_indexes'].items()}, 'reload_observations': []}
    if worker_receipts:
        for worker in manifest['workers']:
            path = Path(worker_receipts) / f"worker-{worker['worker']}-receipt.json"
            require(file_hash(path) == worker['receipt_sha256'], 'Bound private worker receipt mismatch')
            receipt = read(path)
            require(receipt.get('state') == 'complete_partition' and receipt.get('freeze_sha256') == freeze_sha,
                    'Private worker receipt incomplete/foreign')
            preprocessing['reload_observations'].append({'worker': worker['worker'],
                'receipt_sha256': worker['receipt_sha256'],
                'indexes': {k: {field: v.get(field) for field in ('index_cache_hit', 'build_or_cache_load_seconds',
                    'vectors', 'vector_storage_bytes')} for k, v in receipt['document_indexes'].items()}})
            require(all(v['index_cache_hit'] is True for v in receipt['document_indexes'].values()),
                    'Worker receipt does not verify a cache reload')
    # Missing reload duration remains unavailable, never guessed from first-build values.
    return {'bank': bank, 'queries': queries, 'packets': packets, 'rankings': rankings, 'readers': readers,
            'timing': timing, 'maintenance': maintenance, 'preprocessing': preprocessing,
            'failures': dict(failures), 'omissions': dict(omissions), 'inputs': inputs, 'freeze': freeze}


def tables(data):
    buckets = defaultdict(list)
    for row in data['packets']:
        buckets[cell(row)].append(row)
    packet_stats, rank_contrasts, pack_contrasts, corpus_contrasts = [], [], [], []
    for key, rows in sorted(buckets.items()):
        split, method, packer, budget, size = key
        metrics = {metric: summarize(rows, metric) for metric in PACKET_METRICS}
        byte_rows = [r for r in rows if r['bytes'] is not None]
        # Costs are observed-only with explicit missing counts, unlike success endpoints.
        metrics['bytes'] = {'observed_rows': len(byte_rows), 'missing_rows': len(rows) - len(byte_rows),
                            'mean': statistics.fmean(r['bytes'] for r in byte_rows) if byte_rows else None,
                            'median': statistics.median(r['bytes'] for r in byte_rows) if byte_rows else None}
        packet_stats.append({'split': split, 'ranker': method, 'packer': packer, 'budget': budget,
                             'size': size, 'metrics': metrics})
        if packer in ('whole_record', 'closure_passages'):
            rank_contrasts.append({'split': split, 'ranker': method, 'baseline': 'body_bm25',
                'packer': packer, 'budget': budget, 'size': size,
                **paired(rows, buckets[split, 'body_bm25', packer, budget, size], PRIMARY)})
        if method in EXTENDED:
            pack_contrasts.append({'split': split, 'ranker': method, 'packer': packer,
                'baseline': 'whole_record', 'budget': budget, 'size': size,
                **paired(rows, buckets[split, method, 'whole_record', budget, size], PRIMARY)})
        if size == 'all':
            corpus_contrasts.append({'split': split, 'ranker': method, 'packer': packer, 'budget': budget,
                'contrast': 'all_minus_144', **paired(rows, buckets[split, method, packer, budget, '144'], PRIMARY)})
    candidate_buckets = defaultdict(list)
    for row in data['rankings']:
        for k, value in row['candidates'].items():
            candidate_buckets[row['split'], row['ranker'], row['size'], int(k)].append({**row, 'candidate': value})
    candidate_stats, candidate_contrasts = [], []
    for key, rows in sorted(candidate_buckets.items()):
        split, method, size, k = key
        candidate_stats.append({'split': split, 'ranker': method, 'size': size, 'k': k, **summarize(rows, 'candidate')})
        candidate_contrasts.append({'split': split, 'ranker': method, 'size': size, 'k': k,
            'baseline': 'body_bm25', **paired(rows, candidate_buckets[split, 'body_bm25', size, k], 'candidate')})
    reader_buckets = defaultdict(list)
    for row in data['readers']:
        reader_buckets[row['block'], row['arm']].append(row)
    reader_stats, reader_contrasts = [], []
    for (block, arm), rows in sorted(reader_buckets.items()):
        ready = [r for r in rows if r['expected_status'] == 'ready']
        hold = [r for r in rows if r['expected_status'] == 'hold']
        reader_stats.append({'block': block, 'arm': arm, 'scheduled_trials': len(rows),
            'metrics': {metric: summarize(rows, metric) for metric in GATES},
            'ready_tasks': len(ready), 'hold_tasks': len(hold),
            'false_holds': sum(r['false_hold'] for r in ready), 'justified_holds': sum(r['justified_hold'] for r in hold),
            'unsupported_ready_on_hold': sum(r['unsupported_ready'] for r in hold),
            'absent_or_unresolved_status': sum(r['actual_status'] not in ('ready', 'hold') for r in rows),
            'support_submission_reached': sum(r['first_support_round'] is not None for r in rows),
            'support_submission_not_reached': sum(r['first_support_round'] is None for r in rows),
            'fresh_latency_excluded_support_cases': sum(r['first_support_round'] is not None and not r['latency_comparable'] for r in rows),
            'fresh_support_seconds_observed': sum(r['first_support_submission_seconds'] is not None and r['latency_comparable'] for r in rows),
            'fresh_support_seconds_unavailable': sum(r['first_support_round'] is not None and r['latency_comparable'] and r['first_support_submission_seconds'] is None for r in rows),
            'action_cost_unavailable': sum(r['actions'] is None for r in rows)})
        if block == 'direct':
            reader_contrasts.append({'arm': arm, 'baseline': 'body_whole',
                **paired(rows, reader_buckets['direct', 'body_whole'], 'complete_task')})
    discovery = {arm: {identity(r): r for r in rows} for (block, arm), rows in reader_buckets.items() if block == 'discovery'}
    interaction = []
    for key in sorted(discovery['entry0_helper0']):
        baseline = discovery['entry0_helper0'][key]
        interaction.append({**{k: baseline[k] for k in ('family_id', 'task_id', 'template_family')},
            'difference': (int(discovery['entry1_helper1'][key]['complete_task']) - int(discovery['entry1_helper0'][key]['complete_task']))
                       - (int(discovery['entry0_helper1'][key]['complete_task']) - int(baseline['complete_task']))})
    discovery_contrasts = []
    for first, second, label in [('entry1_helper0', 'entry0_helper0', 'entrypoint_at_helper0'),
                                  ('entry1_helper1', 'entry0_helper1', 'entrypoint_at_helper1'),
                                  ('entry0_helper1', 'entry0_helper0', 'helper_at_entry0'),
                                  ('entry1_helper1', 'entry1_helper0', 'helper_at_entry1')]:
        discovery_contrasts.append({'contrast': label, **paired(list(discovery[first].values()),
                                                               list(discovery[second].values()), 'complete_task')})
    timing_stats = []
    for method in METHODS:
        rows = [r for r in data['timing']['rows'] if r['ranker'] == method]
        seconds = [r['seconds'] for r in rows]
        timing_stats.append({'ranker': method, 'observations': len(rows), 'development_queries': 6,
            'median_seconds': statistics.median(seconds), 'minimum_seconds': min(seconds), 'maximum_seconds': max(seconds),
            'query_medians': [{'family_id': q[0], 'task_id': q[1],
                'median_seconds': statistics.median(r['seconds'] for r in rows if identity(r) == q)} for q in sorted({identity(r) for r in rows})]})
    baseline_times = {(*identity(r), r['repetition']): r['seconds'] for r in data['timing']['rows'] if r['ranker'] == 'body_bm25'}
    timing_contrasts = []
    for method in METHODS:
        changes = [r['seconds'] - baseline_times[(*identity(r), r['repetition'])]
                   for r in data['timing']['rows'] if r['ranker'] == method]
        timing_contrasts.append({'ranker': method, 'baseline': 'body_bm25', 'matched_serial_observations': len(changes),
            'median_difference_seconds': statistics.median(changes), 'minimum_difference_seconds': min(changes),
            'maximum_difference_seconds': max(changes), 'scope': 'Descriptive uncontrolled-host timing; no population uncertainty'})
    maintenance_stats = []
    for policy in ('no_invalidation', 'ttl_5', 'global', 'direct_dependencies', 'transitive_dependencies'):
        for missing in (False, True):
            rows = [r for r in data['maintenance']['rows'] if r['policy'] == policy and r['missing_declared_edge'] == missing]
            maintenance_stats.append({'policy': policy, 'missing_declared_edge': missing, 'events': len(rows),
                'stale_reuses': sum(r['stale_reuse'] for r in rows), 'rebuilds': sum(r['rebuilds'] for r in rows),
                'unnecessary_rebuild_queries': sum(r['unnecessary_rebuild'] for r in rows)})
    return {'packet_cells': packet_stats, 'ranker_contrasts': rank_contrasts, 'packer_contrasts': pack_contrasts,
            'corpus_contrasts': corpus_contrasts, 'candidate_cells': candidate_stats, 'candidate_contrasts': candidate_contrasts,
            'reader_arms': reader_stats, 'reader_contrasts': reader_contrasts,
            'discovery_interaction': summarize(interaction, 'difference'), 'discovery_contrasts': discovery_contrasts,
            'reader_trials': data['readers'], 'timing': timing_stats, 'timing_contrasts': timing_contrasts,
            'timing_observations': data['timing']['rows'],
            'preprocessing': data['preprocessing'], 'maintenance': maintenance_stats,
            'maintenance_checks': {k: data['maintenance'].get(k) for k in ('commit_checks', 'semantic_ledger_counterexample')},
            'pipeline_failures': data['failures'], 'budget_skip_reasons': data['omissions']}


class Figures:
    def __init__(self, output, computational, fixture=False):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        matplotlib.rcParams.update({'font.size': 12, 'axes.titlesize': 15, 'axes.labelsize': 13,
            'xtick.labelsize': 11, 'ytick.labelsize': 11, 'legend.fontsize': 11,
            'figure.titlesize': 18, 'svg.fonttype': 'none', 'savefig.facecolor': 'white'})
        self.plt, self.np = plt, np
        self.output, self.tables, self.fixture = Path(output), computational, fixture
        self.output.mkdir(parents=True, exist_ok=True)
        self.registry = []
        self.date = datetime.now(timezone.utc).isoformat(timespec='seconds')

    def axes(self, title, columns=1, height=7, rows=1):
        fig, axes = self.plt.subplots(rows, columns, figsize=(7 * columns if columns > 1 else 13, height), squeeze=False)
        fig.suptitle(('ARTIFICIAL FIXTURE — NOT STUDY OUTCOMES\n' if self.fixture else '') + title)
        for ax in axes.flat:
            ax.spines[['top', 'right']].set_visible(False)
            ax.grid(axis='x', alpha=.15)
        return fig, axes

    def finish(self, fig, name, purpose, sources, note='Confirmation: equal template means; descriptive 2,000 whole-template bootstrap replicates.'):
        fig.text(.015, .015, note, fontsize=10, va='bottom', wrap=True)
        fig.tight_layout(rect=(0, .065, 1, .90 if self.fixture else .93))
        exports = []
        for extension in ('png', 'svg'):
            path = self.output / (name + '.' + extension)
            metadata = {'Title': purpose, 'Description': note, 'Date': self.date} if extension == 'svg' else {
                'Title': purpose, 'Description': note, 'Creation Time': self.date}
            fig.savefig(path, dpi=160, metadata=metadata)
            exports.append({'file': path.name, 'sha256': file_hash(path), 'bytes': path.stat().st_size})
        self.plt.close(fig)
        self.registry.append({'id': name, 'purpose': purpose, 'source_tables': sources,
            'computational_data_sha256': value_hash({k: self.tables[k] for k in sources}),
            'scope': 'artificial plotting fixture' if self.fixture else note, 'exports': exports})

    def find(self, table, **criteria):
        return [r for r in self.tables[table] if all(r.get(k) == v for k, v in criteria.items())]

    def packet(self, method, packer='closure_passages', budget=8192, size='144', metric=PRIMARY):
        rows = self.find('packet_cells', split='confirmation', ranker=method, packer=packer, budget=budget, size=size)
        return rows[0]['metrics'][metric]

    def forest(self, ax, labels, stats, color=COLORS[0], signed=False):
        y = list(range(len(labels)))
        means = [r['estimate'] for r in stats]
        errors = [[r['estimate'] - r['ci_low'] for r in stats], [r['ci_high'] - r['estimate'] for r in stats]]
        ax.errorbar(means, y, xerr=errors, fmt='o', capsize=3, color=color)
        ax.set_yticks(y, [label.replace('_', ' ') for label in labels])
        ax.invert_yaxis()
        ax.set_xlim((-1, 1) if signed else (-.03, 1.03))
        if signed:
            ax.axvline(0, color='#777', lw=1)

    def render(self):
        p, np = self.plt, self.np
        fig, axs = self.axes('Prospective mechanism grid: which packing cells exist', height=11)
        matrix = [[2 if method in EXTENDED else 1 if packer in ('whole_record', 'closure_passages') else 0
                   for packer in PACKERS] for method in METHODS]
        ax = axs[0, 0]
        ax.imshow(matrix, aspect='auto', cmap='Blues', vmin=0, vmax=2)
        ax.set_yticks(range(21), [m.replace('_', ' ') for m in METHODS])
        ax.set_xticks(range(8), [v.replace('_', '\n') for v in PACKERS], fontsize=10)
        ax.set_xlabel('Every colored cell × 3 byte budgets × 2 corpus sizes × 288 queries')
        self.finish(fig, '01-mechanism-grid', 'Deduplicated 21-ranker × 8-packer schedule', [],
                    'EXPLANATORY SCHEDULE: 198 cells/query/size; 114,048 packets; darker rows are extended packer comparisons.')

        fig, axs = self.axes('Original-span bundle exposure by retrieval mechanism', columns=3, height=7)
        for ax, (label, methods) in zip(axs.flat, GROUPS):
            self.forest(ax, methods, [self.packet(m) for m in methods])
            ax.set_title(label)
            ax.set_xlabel('Complete support-span alternative exposed')
        self.finish(fig, '02-primary-ranker-facets', 'Primary span exposure at 8 KB / 144 records / closure passages', ['packet_cells'])

        fig, axs = self.axes('Candidate IDs are a ceiling, not evidence exposure', columns=2)
        for ax, size in zip(axs.flat, ('144', 'all')):
            for color, method in zip(COLORS, EXTENDED):
                values = sorted(self.find('candidate_cells', split='confirmation', ranker=method, size=size), key=lambda r: r['k'])
                ax.plot([r['k'] for r in values], [r['estimate'] for r in values], 'o-', color=color, label=method.replace('_', ' '))
            ax.set(title=f'Corpus: {size}', xlabel='Candidate cutoff k', ylabel='Sufficient original-ID set in candidates', ylim=(-.02, 1.02))
            ax.set_xticks((8, 16, 32, 64)); ax.legend()
        self.finish(fig, '03-candidate-ceilings', 'Candidate set recovery at four fixed cutoffs', ['candidate_cells'])

        fig, axs = self.axes('Three different evidence endpoints', height=7)
        ax = axs[0, 0]
        endpoints = ((PRIMARY, 'Exact authored spans'), ('original_id_bundle', 'Original IDs exposed'),
                     ('declared_whole_bundle_recovered', 'Whole originals exposed'))
        x = np.arange(4)
        for offset, (metric, label) in enumerate(endpoints):
            ax.bar(x + (offset - 1) * .24, [self.packet(m, metric=metric)['estimate'] for m in EXTENDED], .24, label=label, color=COLORS[offset])
        ax.set_xticks(x, [m.replace('_', '\n') for m in EXTENDED]); ax.set_ylabel('Equal-template recovery fraction'); ax.set_ylim(0, 1.05); ax.legend()
        self.finish(fig, '04-span-id-whole', 'Span, ID and whole-original proxies remain distinct', ['packet_cells'])

        fig, axs = self.axes('Context budget response in two nested corpora', columns=2)
        for ax, size in zip(axs.flat, ('144', 'all')):
            for color, method in zip(COLORS, EXTENDED):
                rows = sorted(self.find('packet_cells', split='confirmation', ranker=method, packer='closure_passages', size=size), key=lambda r: r['budget'])
                ax.plot([r['budget'] / 1024 for r in rows], [r['metrics'][PRIMARY]['estimate'] for r in rows], 'o-', color=color, label=method.replace('_', ' '))
            ax.set(title=f'Corpus: {size}', xlabel='UTF-8 context budget (KiB)', ylabel='Support-span exposure', ylim=(-.02, 1.02)); ax.set_xticks((4, 8, 16)); ax.legend()
        self.finish(fig, '05-budget-corpus-response', 'Bytes and distractor corpus response', ['packet_cells'])

        fig, axs = self.axes('Paired corpus expansion: all records minus 144', height=6)
        rows = [self.find('corpus_contrasts', split='confirmation', ranker=m, packer='closure_passages', budget=8192)[0] for m in EXTENDED]
        self.forest(axs[0, 0], EXTENDED, rows, signed=True); axs[0, 0].set_xlabel('Paired change in original-span exposure')
        self.finish(fig, '06-corpus-expansion-pairs', 'Matched-query corpus expansion contrast', ['corpus_contrasts'])

        fig, axs = self.axes('Matched packer contrasts with ranker and bytes fixed', columns=2, rows=2, height=12)
        for ax, method in zip(axs.flat, EXTENDED):
            rows = [self.find('packer_contrasts', split='confirmation', ranker=method, packer=packer, budget=8192, size='144')[0] for packer in PACKERS]
            self.forest(ax, PACKERS, rows, signed=True); ax.set_title(method.replace('_', ' ')); ax.set_xlabel('Span exposure minus whole-record packer')
        self.finish(fig, '07-atomic-packing-contrasts', 'Eight packing mechanisms compared within four fixed rankers', ['packer_contrasts'])

        fig, axs = self.axes('Heterogeneity across the twelve authored template groups', height=9)
        groups = sorted(self.packet('body_bm25')['group_means'])
        matrix = [[self.packet(m)['group_means'][g] for m in EXTENDED] for g in groups]
        im = axs[0, 0].imshow(matrix, aspect='auto', vmin=0, vmax=1, cmap='viridis')
        axs[0, 0].set_yticks(range(len(groups)), [g.replace('_', ' ') for g in groups]); axs[0, 0].set_xticks(range(4), [m.replace('_', '\n') for m in EXTENDED])
        fig.colorbar(im, ax=axs[0, 0], label='Within-group support-span exposure')
        self.finish(fig, '08-template-heterogeneity', 'Individual cluster means rather than an independent-query illusion', ['packet_cells'])

        fig, axs = self.axes('Matched queries: improvements, ties and regressions', columns=3)
        for ax, (label, methods) in zip(axs.flat, GROUPS):
            rows = [self.find('ranker_contrasts', split='confirmation', ranker=m, packer='closure_passages', budget=8192, size='144')[0] for m in methods]
            left = np.zeros(len(rows))
            for color, field in zip((COLORS[2], '#c7c9cb', COLORS[1]), ('improved', 'tied', 'regressed')):
                counts = [r[field] for r in rows]; ax.barh(range(len(rows)), counts, left=left, label=field, color=color); left += counts
            ax.set_yticks(range(len(rows)), [m.replace('_', ' ') for m in methods]); ax.invert_yaxis(); ax.set_title(label); ax.set_xlabel('Scheduled matched queries vs body BM25'); ax.legend()
        self.finish(fig, '09-paired-regressions', 'All matched ties and regressions remain visible', ['ranker_contrasts'],
                    'Counts describe 216 confirmation queries; clustering applies to estimates, not these raw census counts.')

        fig, axs = self.axes('Pipeline faults remain in scheduled denominators', height=7)
        items = sorted(self.tables['pipeline_failures'].items())
        if items:
            axs[0, 0].barh([k.replace(':', ' / ') for k, _ in items], [v for _, v in items], color=COLORS[1])
        else:
            axs[0, 0].text(.5, .5, 'No recorded infrastructure faults', ha='center', transform=axs[0, 0].transAxes)
        axs[0, 0].set_xlabel('Recorded scheduled-cell / scheduled-trial faults')
        self.finish(fig, '10-pipeline-failure-types', 'Infrastructure faults are outcomes, never discarded rows', ['pipeline_failures'],
                    'Ranking and propagated packet faults are separate census units; no sum is presented as unique incidents.')

        fig, axs = self.axes('Packing cost and partial evidence recovery', height=7)
        for color, method in zip(COLORS, EXTENDED):
            rows = self.find('packet_cells', split='confirmation', ranker=method, packer='closure_passages', size='144')
            axs[0, 0].plot([r['metrics']['bytes']['mean'] for r in rows], [r['metrics']['best_declared_span_fraction']['estimate'] for r in rows], 'o-', color=color, label=method.replace('_', ' '))
        axs[0, 0].set(xlabel='Observed mean packet bytes (fault missingness in table)', ylabel='Best authored span fraction recovered', ylim=(-.02, 1.02)); axs[0, 0].legend()
        self.finish(fig, '11-byte-support-frontier', 'Actual packed bytes versus partial source recovery', ['packet_cells'])

        fig, axs = self.axes('Why whole-body truncation and windows can disagree', height=5)
        ax = axs[0, 0]
        ax.broken_barh([(0, 1100)], (0, .6), facecolors='#ddd')
        ax.broken_barh([(0, 360)], (0, .6), facecolors=COLORS[0], alpha=.65)
        ax.broken_barh([(850, 90)], (0, .6), facecolors=COLORS[1])
        ax.broken_barh([(720, 300)], (1.1, .6), facecolors=COLORS[2], alpha=.65)
        ax.text(850, .75, 'Governing tail qualifier', fontsize=13); ax.text(20, 1.85, 'Source-exact windows can expose it; lexical/semantic selection can still miss it.')
        ax.set(xlim=(0, 1100), ylim=(-.3, 2.2), xlabel='Illustrative source character position'); ax.set_yticks((.3, 1.4), ('Whole-body prefix input', 'Selected local window'))
        self.finish(fig, '12-window-tail-mechanism', 'Explanatory tail-fact and source-window mechanism', [],
                    'EXPLANATORY FICTIONAL DIAGRAM: positions are illustrative, not observed tokenizer boundaries or measured accuracy.')

        fig, axs = self.axes('Budget omission mechanisms', height=6)
        items = sorted(self.tables['budget_skip_reasons'].items())
        if items:
            axs[0, 0].barh([k.replace('_', ' ') for k, _ in items], [v for _, v in items], color=COLORS[4])
        else:
            axs[0, 0].text(.5, .5, 'No recorded budget omissions', ha='center', transform=axs[0, 0].transAxes)
        axs[0, 0].set_xlabel('Skipped units across the complete packet grid')
        self.finish(fig, '13-budget-omissions', 'Oversized windows/bundles and other packing omissions', ['budget_skip_reasons'],
                    'Grid-wide mechanical diagnostic counts; one omitted unit is not necessarily one missing gold span.')

        fig, axs = self.axes('Reader success requires five separately measured gates', height=7)
        reader_arms = [r for r in self.tables['reader_arms'] if r['block'] != 'discovery']
        matrix = [[r['metrics'][g]['estimate'] for g in GATES] for r in reader_arms]
        ax = axs[0, 0]; im = ax.imshow(matrix, vmin=0, vmax=1, cmap='viridis', aspect='auto')
        ax.set_yticks(range(len(reader_arms)), [r['arm'].replace('_', ' ') for r in reader_arms]); ax.set_xticks(range(7), ('Artifact', 'Contract', 'Typed\nanswer/status', 'Support\nspans', 'Original\ncitations', 'Complete\ntask', 'Clean\ncomplete'))
        fig.colorbar(im, ax=ax, label='Equal-template fraction')
        self.finish(fig, '14-reader-gates', 'Artifact, syntax, typed answer, support and citation gates', ['reader_arms'],
                    '24 matched histories, two per template; oracle sufficient originals are outside byte-budget comparisons. Citation IDs do not prove entailment.')

        fig, axs = self.axes('False holds and justified holds have different denominators', columns=2)
        names = [r['arm'].replace('_', ' ') for r in reader_arms]
        axs[0, 0].barh(names, [r['false_holds'] / r['ready_tasks'] if r['ready_tasks'] else 0 for r in reader_arms], color=COLORS[1])
        axs[0, 1].barh(names, [r['justified_holds'] / r['hold_tasks'] if r['hold_tasks'] else 0 for r in reader_arms], color=COLORS[2])
        for ax in axs.flat: ax.set_xlim(0, 1.05)
        axs[0, 0].set_xlabel('False hold / authored-ready tasks (19 per arm)'); axs[0, 1].set_xlabel('Complete justified hold / authored-hold tasks (5 per arm)')
        self.finish(fig, '15-reader-holds', 'Readiness versus evidence insufficiency', ['reader_arms'],
                    'Absent outputs and unsupported ready decisions on hold tasks are separate columns in the computational table.')

        fig, axs = self.axes('Frozen typed conventions: what the exact score checks', height=6)
        ax = axs[0, 0]; ax.axis('off')
        rows = [('Numbers / booleans', 'Exact value and exact JSON type; true is not integer 1'),
                ('Null / hold', 'Conditional null follows contract; null is not a negative decision'),
                ('Lists', 'Declared order, or explicitly declared unordered unique semantics'),
                ('Text', 'Only contract-permitted normalization; no inferred paraphrase grading'),
                ('Citations', 'Original-ID set coverage; cited-span entailment is a separate review'),
                ('Blinded source review', 'Planned supplement; never overwrites the frozen primary endpoint')]
        table = ax.table(cellText=rows, colLabels=('Convention', 'Frozen scoring meaning'), cellLoc='left', loc='center', colWidths=(.25, .75))
        table.auto_set_font_size(False); table.set_fontsize(12); table.scale(1, 2.4)
        self.finish(fig, '16-exact-typed-conventions', 'Exact typed scoring and separately planned source review', [], 'EXPLANATORY PROTOCOL TABLE; not a semantic answer-quality validation result.')

        fig, axs = self.axes('Onboarding: entrypoint × helper interaction', columns=2)
        for ax, gate in zip(axs.flat, ('complete_task', PRIMARY)):
            for color, helper in zip(COLORS, (0, 1)):
                rows = [self.find('reader_arms', block='discovery', arm=f'entry{entry}_helper{helper}')[0]['metrics'][gate] for entry in (0, 1)]
                ax.errorbar((0, 1), [r['estimate'] for r in rows], yerr=[[r['estimate'] - r['ci_low'] for r in rows], [r['ci_high'] - r['estimate'] for r in rows]], fmt='o-', color=color, capsize=4, label=f'Helper {helper}')
            ax.set_xticks((0, 1), ('No entrypoint', 'Entrypoint')); ax.set_ylim(-.05, 1.05); ax.set_ylabel(gate.replace('_', ' ')); ax.legend()
        self.finish(fig, '17-onboarding-factorial', 'Four matched onboarding arms and declared interaction', ['reader_arms', 'discovery_interaction'],
                    '12 matched cases / 12 template groups; interaction is difference-in-differences, not a natural-vault usability claim.')

        fig, axs = self.axes('Navigation resource costs with scheduled-case missingness', columns=2)
        arms = [f'entry{entry}_helper{helper}' for entry in (0, 1) for helper in (0, 1)]
        for ax, metric in zip(axs.flat, ('actions', 'returned_tool_bytes')):
            groups = [[r[metric] for r in self.find('reader_trials', block='discovery', arm=arm) if r[metric] is not None] for arm in arms]
            ax.boxplot([g or [float('nan')] for g in groups], tick_labels=[a.replace('_', '\n') for a in arms]); ax.set_ylabel(metric.replace('_', ' '))
            for x, group in enumerate(groups, 1): ax.text(x, 1.01, f'{len(group)}/12 observed', transform=ax.get_xaxis_transform(), ha='center', fontsize=10)
        self.finish(fig, '18-navigation-costs', 'Actions and exact returned-tool UTF-8 bytes', ['reader_trials'],
                    'Observed costs retain missing counts; 32-action / 32,768-byte caps. Prompt/model usage is a separate receipted table field.')

        fig, axs = self.axes('When verified support first reaches a submitted prompt', columns=2)
        for color, arm in zip(COLORS, arms):
            rows = self.find('reader_trials', block='discovery', arm=arm)
            for ax, metric in zip(axs.flat, ('first_support_round', 'first_support_submission_seconds')):
                observed = sorted(r[metric] for r in rows if r[metric] is not None and (metric == 'first_support_round' or r['latency_comparable']))
                counts = self.find('reader_arms', block='discovery', arm=arm)[0]
                label = arm.replace('_', ' ') + f"\nreached {counts['support_submission_reached']}; not reached {counts['support_submission_not_reached']}"
                if metric == 'first_support_submission_seconds':
                    label += f"; excluded {counts['fresh_latency_excluded_support_cases']}; unavailable {counts['fresh_support_seconds_unavailable']}"
                if observed: ax.step([0] + observed, [0] + [(i + 1) / 12 for i in range(len(observed))], where='post', label=label, color=color)
                else: ax.plot([], [], color=color, label=label)
                ax.set_ylim(0, 1.05); ax.set_ylabel('Fraction of all 12 scheduled cases'); ax.legend(fontsize=9)
        axs[0, 0].set_xlabel('First verified full-support submission round'); axs[0, 1].set_xlabel('Host submission elapsed seconds (fresh only)')
        self.finish(fig, '19-first-support-submission', 'Verified support exposure delivery proxy and non-reached cases', ['reader_trials', 'reader_arms'],
                    'Host submission is not comprehension/provider intake. Reused-call exclusions and unavailable clocks are separate from cases that never reached support.')

        fig, axs = self.axes('Uncached warm queries: resident documents, fresh pair/query work', columns=3)
        for ax, (label, methods) in zip(axs.flat, GROUPS):
            rows = [self.find('timing', ranker=m)[0] for m in methods]
            means = [r['median_seconds'] for r in rows]
            ax.errorbar(means, range(len(rows)), xerr=[[r['median_seconds'] - r['minimum_seconds'] for r in rows], [r['maximum_seconds'] - r['median_seconds'] for r in rows]], fmt='o', color=COLORS[0], capsize=3)
            ax.set_yticks(range(len(rows)), [m.replace('_', ' ') for m in methods]); ax.invert_yaxis(); ax.set_title(label); ax.set_xlabel('Seconds: median and full observed range'); ax.set_xscale('symlog', linthresh=.01)
        self.finish(fig, '20-uncached-warm-timing', '18 serial development timing observations per engine', ['timing'],
                    '6 fixed development queries × 3 repeats; 2 CPU threads; uncontrolled desktop activity; no population interval or isolated hardware claim.')

        fig, axs = self.axes('Preprocessing costs stay separate from warm query latency', columns=3)
        preprocessing = self.tables['preprocessing']; indexes = preprocessing['indexes']
        names = list(indexes)
        axs[0, 0].bar(names, [indexes[k]['build_or_cache_load_seconds'] for k in names], color=COLORS[0]); axs[0, 0].set_ylabel('Receipt build-or-load seconds'); axs[0, 0].set_title('Receipt operation; cache flag in table')
        axs[0, 1].bar(names, [indexes[k]['vector_storage_bytes'] / 1024**2 for k in names], color=COLORS[2]); axs[0, 1].set_ylabel('Vector storage (MiB)'); axs[0, 1].set_title('Persistent vector arrays')
        if preprocessing['reload_observations']:
            reloads = preprocessing['reload_observations'][0]['indexes']
            axs[0, 2].bar(list(reloads), [r['build_or_cache_load_seconds'] for r in reloads.values()], color=COLORS[4])
            axs[0, 2].set_ylabel('Verified cache reload seconds'); axs[0, 2].set_title('First bound worker reload')
        else:
            axs[0, 2].axis('off'); axs[0, 2].text(.03, .75, f"Dense model load: {preprocessing['model_load_seconds']} s\n\nVerified reload duration:\nnot supplied to this analysis\n\nFirst-build and reload\nare never interchangeable.", fontsize=13, va='top')
        self.finish(fig, '21-index-loading-storage', 'Model load, index operation and storage with missing reload explicit', ['preprocessing'],
                    'Bound private preparation receipt, numeric allowlist only; no host paths. These costs are outside warm query timing.')

        fig, axs = self.axes('Shallow development classifier: auditable rule structure', height=8)
        ax = axs[0, 0]; ax.axis('off')
        model = self.tables.get('classifier', {})
        if model.get('nodes'):
            positions = {}
            def walk(n, x, y, width):
                positions[n] = (x, y)
                node = model['nodes'][n]
                if node['left'] != -1:
                    walk(node['left'], x - width, y - 1, width / 2); walk(node['right'], x + width, y - 1, width / 2)
            walk(0, 0, 0, 4)
            for n, (x, y) in positions.items():
                node = model['nodes'][n]
                for child in (node['left'], node['right']):
                    if child != -1: ax.plot((x, positions[child][0]), (y, positions[child][1]), color='#999')
                text = (model['features'][node['feature']].replace('_', '\n') + f" ≤ {node['threshold']:.3g}" if node['left'] != -1 else f"Leaf score {node['positive_score']:.2f}") + f"\nrows: {node['samples']}"
                ax.text(x, y, text, ha='center', va='center', fontsize=10, bbox={'boxstyle': 'round,pad=.4', 'facecolor': 'white', 'edgecolor': COLORS[0]})
            ax.set_ylim(-3.7, .6); ax.set_xlim(-8, 8)
        else: ax.text(.5, .5, 'No classifier structure supplied', ha='center', transform=ax.transAxes)
        self.finish(fig, '22-classifier-structure', 'Frozen depth-three development-only relevance rules', ['classifier'],
                    'DEVELOPMENT TRAINING STRUCTURE: balanced relevance labels; score is uncalibrated and does not detect factual authority.')

        fig, axs = self.axes('Dependency invalidation trades stale reuse for rebuilds', columns=2)
        for ax, missing in zip(axs.flat, (False, True)):
            for color, row in zip(COLORS, self.find('maintenance', missing_declared_edge=missing)):
                ax.scatter(row['rebuilds'], row['stale_reuses'] / row['events'], s=90, color=color)
                ax.annotate(row['policy'].replace('_', '\n'), (row['rebuilds'], row['stale_reuses'] / row['events']), xytext=(5, 5), textcoords='offset points', fontsize=10)
            ax.set_title('Missing declared dependency' if missing else 'Complete prescribed dependency graph'); ax.set_xlabel('Mechanical rebuild count'); ax.set_ylabel('Stale reuse / prescribed events'); ax.margins(.3)
        self.finish(fig, '23-invalidation-tradeoffs', 'Mechanical invalidation with complete and incomplete ledgers', ['maintenance'],
                    'ENGINEERED REPLAY: zero stale reuse here is not LLM-validated semantic maintenance; true dependencies are prescribed by the fixture.')

        fig, axs = self.axes('A matching source ledger can preserve a false projection', height=6)
        ax = axs[0, 0]; ax.axis('off')
        text = 'Original S1: approved interval = 13 days\nOriginal S2: scope = amber lane\n\nDerived prose: approved interval = 99 days\n\nCurrent source hashes match ✓     Retained view checksum matches ✓\nSemantic claim is still false in the prescribed fixture.'
        ax.text(.05, .8, text, fontsize=17, va='top', linespacing=1.7)
        self.finish(fig, '24-ledger-truth-boundary', 'Fixity/dependency ledgers cannot certify semantic correctness', ['maintenance_checks'],
                    'ENGINEERED COUNTEREXAMPLE from maintenance_lab.py; no LLM truth evaluator or general semantic correctness guarantee.')

        fig, axs = self.axes('Fictional authority chronology: effective time differs from author time', height=5)
        ax = axs[0, 0]
        points = [(0, 'Original rule'), (2, 'Scoped correction'), (4, 'Future rule authored'), (7, 'Future rule effective')]
        ax.plot([v[0] for v in points], [0] * 4, '-o', color=COLORS[0]); ax.axvline(5, color=COLORS[1], linestyle='--')
        for x, label in points: ax.annotate(label, (x, 0), xytext=(0, 20 if x % 2 == 0 else -40), textcoords='offset points', ha='center')
        ax.text(5, .45, 'Query date', ha='center', color=COLORS[1]); ax.set_ylim(-.7, .7); ax.set_yticks([]); ax.set_xlabel('Illustrative fictional chronology (arbitrary time units)')
        self.finish(fig, '25-fictional-timeline', 'Explanatory source chronology and applicability', [],
                    'EXPLANATORY FICTIONAL EXAMPLE: the newly authored future rule does not govern the earlier query date.')

        fig, axs = self.axes('Transitive evidence dependencies and missing-edge limits', height=6)
        ax = axs[0, 0]; ax.axis('off')
        nodes = {'S1\noriginal': (0, 1), 'S2\noriginal': (0, -1), 'V1\nderived': (3, 0), 'V2\nderived': (6, 0)}
        for label, (x, y) in nodes.items(): ax.text(x, y, label, ha='center', va='center', bbox={'boxstyle': 'round,pad=.6', 'facecolor': 'white', 'edgecolor': COLORS[0]}, fontsize=15)
        for start, end, dashed in [('S1\noriginal', 'V1\nderived', False), ('S2\noriginal', 'V1\nderived', True), ('V1\nderived', 'V2\nderived', False)]:
            a, b = nodes[start], nodes[end]; ax.annotate('', xy=(b[0] - .4, b[1]), xytext=(a[0] + .4, a[1]), arrowprops={'arrowstyle': '->', 'linestyle': '--' if dashed else '-', 'color': COLORS[1] if dashed else COLORS[0], 'lw': 2})
        ax.text(1.2, -1.5, 'Dashed edge: real requirement absent from declared ledger', color=COLORS[1]); ax.set_xlim(-1, 7); ax.set_ylim(-2, 2)
        self.finish(fig, '26-fictional-dependency-graph', 'Prescribed transitive dependency mechanism and incomplete-ledger limit', [],
                    'EXPLANATORY FICTIONAL GRAPH from the maintenance fixture; edges are prescribed, not learned or automatically recovered.')
        return self.registry


def synthetic_tables():
    """Full 21×8×3 plot shapes with tiny explicitly artificial numeric arrays."""
    packets, ranks = [], []
    for group_index in range(12):
        for family_index in range(2):
            base = {'family_id': f'FIXTURE-F{group_index}-{family_index}', 'task_id': f'FIXTURE-Q{group_index}-{family_index}',
                    'template_family': f'fixture_template_{group_index:02d}', 'split': 'confirmation'}
            for size in ('144', 'all'):
                for method_index, method in enumerate(METHODS):
                    success = int((group_index + family_index + method_index) % 4 != 0)
                    ranks.append({**base, 'ranker': method, 'size': size, 'candidates': {str(k): int(k >= 16) for k in (8, 16, 32, 64)}})
                    for packer, budget in cells(method):
                        packets.append({**base, 'ranker': method, 'packer': packer, 'budget': budget, 'size': size,
                            PRIMARY: success, 'declared_whole_bundle_recovered': success if packer == 'whole_record' else 0,
                            'original_id_bundle': 1, 'best_declared_span_fraction': .5 + success / 2,
                            'selected_stale_views': 0, 'selected_unverifiable_views': 0, 'budget_skipped_units': 1,
                            'fault': 0, 'bytes': budget - 200})
    readers = []
    for group in range(12):
        for number in range(2):
            for block, arm in [('direct', a) for a in ('body_whole', 'search_body', 'entity_closure', 'dense_closure', 'minilm_closure')] + [('oracle', 'oracle_originals')] + ([('discovery', f'entry{e}_helper{h}') for e in (0, 1) for h in (0, 1)] if number == 0 else []):
                success = (group + number + len(arm)) % 3 != 0
                readers.append({'family_id': f'FIXTURE-R{group}-{number}', 'task_id': f'FIXTURE-T{group}-{number}',
                    'template_family': f'fixture_template_{group:02d}', 'block': block, 'arm': arm,
                    **{g: success for g in GATES}, 'expected_status': 'hold' if group < 2 else 'ready',
                    'actual_status': 'hold' if group < 2 else 'ready', 'false_hold': False, 'justified_hold': group < 2 and success,
                    'unsupported_ready': False, 'actions': 6 + group, 'returned_tool_bytes': 4000 + group * 500,
                    'first_support_round': 2 + group % 3 if success else None,
                    'first_support_submission_seconds': 10 + group * 3 if success else None, 'latency_comparable': True,
                    'failure': None, 'elapsed_seconds': 40, 'write_round': 4, 'prompt_input_bytes': None})
    timing = {'rows': [{'ranker': method, 'family_id': f'FIXTURE-D{q}', 'task_id': f'FIXTURE-DQ{q}',
                       'seconds': .01 * (1 + i) * (1 + rep / 10), 'repetition': rep}
                      for i, method in enumerate(METHODS) for q in range(6) for rep in (1, 2, 3)]}
    maintenance = {'rows': [{'policy': policy, 'missing_declared_edge': missing, 'stale_reuse': i % 3 == 0,
                            'rebuilds': p + 1, 'unnecessary_rebuild': i % 7 == 0}
                           for p, policy in enumerate(('no_invalidation', 'ttl_5', 'global', 'direct_dependencies', 'transitive_dependencies'))
                           for missing in (False, True) for i in range(20)]}
    data = {'packets': packets, 'rankings': ranks, 'readers': readers, 'timing': timing, 'maintenance': maintenance,
        'preprocessing': {'model_load_seconds': .3, 'indexes': {name: {'build_or_cache_load_seconds': .4 + i,
            'vector_storage_bytes': 400000 * (i + 1), 'vectors': 1000 * (i + 1), 'index_cache_hit': False}
            for i, name in enumerate(('body', 'search', 'windows'))}, 'reload_observations': []},
        'failures': {'packet:packing:ArtificialFixtureError': 3, 'reader:artificial_fixture': 1},
        'omissions': {'artificial_oversized_bundle': 5}}
    result = tables(data)
    result['classifier'] = {'features': ['fixture_incoming_supersession'], 'nodes': [
        {'feature': 0 if n < 7 else -2, 'threshold': .5, 'left': 2 * n + 1 if n < 7 else -1,
         'right': 2 * n + 2 if n < 7 else -1, 'samples': max(16, 128 // (1 + n)), 'positive_score': .1 + (n % 7) / 10}
        for n in range(15)]}
    return result


def self_check(preview=None):
    require(event_costs({'block': 'discovery', 'failure': 'trial_execution_error', 'events': []}) ==
            {'actions': None, 'rejected_actions': None}, 'Interrupted unknown costs imputed as zero')
    require(event_costs({'block': 'discovery', 'failure': None, 'events': []}) ==
            {'actions': 0, 'rejected_actions': 0}, 'Verified no-action trace lost')
    require(event_costs({'block': 'discovery', 'failure': None, 'events': [{'executed': True}, {'executed': False}]}) ==
            {'actions': 2, 'rejected_actions': 1}, 'Action cost accounting failed')
    rows = [{'family_id': 'A', 'task_id': 'a1', 'template_family': 'T1', 'value': 1},
            {'family_id': 'A', 'task_id': 'a2', 'template_family': 'T1', 'value': 1},
            {'family_id': 'B', 'task_id': 'b1', 'template_family': 'T1', 'value': 0},
            {'family_id': 'C', 'task_id': 'c1', 'template_family': 'T2', 'value': 0}]
    require(nested_means(rows, 'value') == {'T1': .5, 'T2': 0}, 'Nested weighting fixture failed')
    require(summarize(rows, 'value')['estimate'] == .25, 'Equal group weighting failed')
    require(cluster_interval({'T1': 1, 'T2': 0}) == cluster_interval({'T1': 1, 'T2': 0}), 'Bootstrap not reproducible')
    zero = [{**row, 'value': 0} for row in rows]
    contrast = paired(rows, zero, 'value')
    require(contrast['estimate'] == .25 and contrast['improved'] == 2 and contrast['tied'] == 2, 'Pairing fixture failed')
    try:
        paired(rows, zero[:-1], 'value')
    except ValueError:
        pass
    else:
        raise AssertionError('Unmatched pair accepted')
    packet_keys, rank_keys = expected_census([('F', 'Q')])
    require(len(packet_keys) == 396 and len(rank_keys) == 42, 'Deduplicated schedule failed')
    require(len(expected_census([(f'F{i}', f'Q{i}') for i in range(288)])[0]) == 114048, 'Planned census failed')
    failure_fixture = [{'family_id': 'F', 'task_id': 'Q1', 'template_family': 'T', 'success': 1},
                       {'family_id': 'F', 'task_id': 'Q2', 'template_family': 'T', 'success': 0}]
    require(summarize(failure_fixture, 'success')['estimate'] == .5, 'Fault dropped from denominator')
    result = {'state': 'passed', 'checks': ['nested equal group weighting', 'seeded whole-cluster bootstrap',
        'exact matched pairing', 'unmatched rejection', 'deduplicated full census', 'failure denominator retained', 'unknown event costs retained'],
        'study_outcomes_loaded': False}
    if preview:
        computational = synthetic_tables()
        registry = Figures(preview, computational, fixture=True).render()
        require(len(registry) >= 22 and all(len(r['exports']) == 2 for r in registry), 'Figure registry incomplete')
        save(Path(preview) / 'fixture-figure-registry.json', {'state': 'artificial_fixture_only', 'figures': registry})
        result['artificial_preview_figures'] = len(registry)
    print(canonical(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--self-check', action='store_true')
    mode.add_argument('--analyze', action='store_true')
    parser.add_argument('--preview-fixtures', type=Path, help='Private artificial full-shape plotting smoke test')
    parser.add_argument('--freeze-sha256')
    parser.add_argument('--prepare-receipt', type=Path)
    parser.add_argument('--worker-receipts', type=Path, help='Optional private grid work folder; receipts must match manifest digests')
    parser.add_argument('--maintenance', type=Path, default=HERE / 'maintenance-results.json')
    parser.add_argument('--output', type=Path, default=HERE)
    args = parser.parse_args()
    if args.self_check:
        if args.preview_fixtures:
            require(not args.preview_fixtures.resolve().is_relative_to(HERE.parents[1]), 'Artificial previews must stay outside public repository')
        return self_check(args.preview_fixtures)
    require(args.prepare_receipt is not None, '--prepare-receipt bound private receipt is required')
    require(not args.preview_fixtures, 'Artificial fixtures cannot enter actual analysis')
    data = load_inputs(args.freeze_sha256, args.prepare_receipt, args.maintenance, args.worker_receipts)
    computational = tables(data)
    model = read(HERE / 'decision-model.json')
    computational['classifier'] = {k: model[k] for k in ('features', 'nodes', 'training_rows', 'positive_rows',
                                                       'depth_limit', 'minimum_leaf_rows', 'interpretation')}
    output = args.output.resolve()
    figure_folder = output / 'figures'
    registry = Figures(figure_folder, computational).render()
    for row in registry:
        for export in row['exports']:
            export['file'] = 'figures/' + export['file']
    save(output / 'figure-registry.json', {'schema_version': 1, 'generated_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'computational_tables_sha256': value_hash(computational), 'figures': registry})
    analysis = {'schema_version': 1, 'state': 'complete_frozen_census_analysis',
        'generated_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'freeze_sha256': args.freeze_sha256,
        'analysis_spec_sha256': file_hash(HERE / 'ANALYSIS-SPEC.md'), 'analyzer_sha256': file_hash(Path(__file__)),
        'preparation_receipt_sha256': file_hash(args.prepare_receipt), 'inputs': data['inputs'],
        'census': {'families': 96, 'queries': 288, 'development_template_groups': 4, 'confirmation_template_groups': 12,
                   'packet_cells': len(data['packets']), 'ranking_cells': len(data['rankings']), 'reader_trials': len(data['readers']),
                   'warm_timing_observations': len(data['timing']['rows']), 'mechanical_events': len(data['maintenance']['rows'])},
        'primary_endpoint': PRIMARY, 'computational_tables_sha256': value_hash(computational), 'tables': computational,
        'figure_registry': {'file': 'figure-registry.json', 'sha256': file_hash(output / 'figure-registry.json'), 'figures': len(registry)},
        'limitations': ['Authored fictional bank with related scaffolds; not a representative corpus or independent human sample.',
            'Twelve confirmation template clusters; descriptive bootstrap intervals, no population p-values.',
            'Many explored policies; maximum observed score is not a confirmed unique winner.',
            'Source-span and citation-ID endpoints do not establish answer accuracy or citation entailment.',
            'Typed convention/source-entailment blinded review is a separate planned supplement.',
            'Uncontrolled desktop host; warm timing is not an isolated hardware benchmark.',
            'Submission clock is delivery proxy, not measured comprehension or provider intake.',
            'Mechanical maintenance and fixture truth are prescribed; not validated LLM extraction/consolidation.',
            'Public assembly does not expose verified reload duration; missing values are not inferred.']}
    save(output / 'analysis.json', analysis)
    print(canonical({'state': analysis['state'], 'packet_cells': len(data['packets']), 'reader_trials': len(data['readers']),
                     'figures': len(registry), 'analysis_file': 'analysis.json', 'figure_registry': 'figure-registry.json'}))


if __name__ == '__main__':
    main()
