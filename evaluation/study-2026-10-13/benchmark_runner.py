"""Prospectively gated, resumable October 13 ranking and source-packing grid.

Model weights, embeddings and query checkpoints remain in caller-supplied private
directories. Public shards omit repeated source text; exact intervals and hashes
permit deterministic reconstruction with the frozen bank and packer.
"""
import argparse
from collections import Counter, OrderedDict
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

import decision_ranker
import index_lab
import packing_lab
import study_common as common

HERE = Path(__file__).resolve().parent
DENSE_METHODS = ('dense_body', 'dense_search', 'dense_windows', 'dense_window_rrf')
NEURAL_METHODS = ('minilm_body', 'mixedbread_body', 'minilm_passages')
METHODS = (*index_lab.METHODS, *DENSE_METHODS, *NEURAL_METHODS, 'shallow_tree')
EXTENDED = ('body_bm25', 'entity_rrf', 'dense_window_rrf', 'minilm_passages')
BUDGETS = (4096, 8192, 16384)
SIZES = (144, 'all')
BASE_PACKERS = ('whole_record', 'closure_passages')
REQUIRED_PINS = ('challenge-bank.json', 'PLAN.md', 'index_lab.py', 'dense_runtime.py',
    'dense-model-spec.json', 'packing_lab.py', 'study_common.py', 'decision_ranker.py',
    'neural_ranker.py', 'benchmark_runner.py', 'decision-model.json')
MAX_SHARD_BYTES = 40*1024*1024
VERSION = 'oct13-grid-v1'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest_value(value):
    return common.digest(canonical(value))


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def size_name(size):
    if size in (144, '144'): return '144'
    if size == 'all': return 'all'
    raise ValueError('Collection size must be 144 or all')


def cells_for(method):
    if method not in METHODS: raise ValueError('Unknown ranker')
    packers = packing_lab.METHODS if method in EXTENDED else BASE_PACKERS
    return [(packer, budget) for packer in packers for budget in BUDGETS]


def private_path(value):
    path = Path(value).resolve()
    if path.is_relative_to(HERE.parents[1]): raise ValueError('Private work/cache directory is inside public repository')
    return path


def split_families(families):
    groups = sorted({f['template_family'] for f in families},
                    key=lambda t: common.digest(t+':oct13-split-v1'))
    development = set(groups[:4])
    result = {f['id']: 'development' if f['template_family'] in development else 'confirmation' for f in families}
    if any(f.get('split') != result[f['id']] for f in families):
        raise ValueError('Authored split does not match prospective group hash recipe')
    return result


def implementation_pins():
    names = [n for n in REQUIRED_PINS if n != 'decision-model.json']
    return {name: file_sha(HERE/name) for name in names}


def verify_freeze(expected_sha):
    freeze_path = HERE/'freeze.json'
    if not re.fullmatch(r'[a-f0-9]{64}', expected_sha or ''):
        raise ValueError('Explicit exact freeze SHA-256 is required')
    if file_sha(freeze_path) != expected_sha: raise ValueError('Freeze bytes differ from caller-supplied digest')
    freeze = json.loads(freeze_path.read_text(encoding='utf-8'))
    entries = freeze.get('files', freeze.get('file_sha256'))
    if not isinstance(entries, dict): raise ValueError('Freeze requires a files/file_sha256 mapping')
    missing = set(REQUIRED_PINS)-set(entries)
    if missing: raise ValueError('Freeze omits mandatory implementation/bank/model pins: '+','.join(sorted(missing)))
    for name, expected in entries.items():
        if not isinstance(name, str): raise ValueError('Freeze file names must be strings')
        target = (HERE/name).resolve()
        if not target.is_relative_to(HERE.parents[1]): raise ValueError('Freeze path escapes public repository')
        expected = expected.get('sha256') if isinstance(expected, dict) else expected
        if not isinstance(expected, str) or file_sha(target) != expected:
            raise ValueError('Frozen input mismatch: '+name)
    legacy = HERE.parent/'study-2026-10-11/model_runtime.py'
    legacy_key = '../study-2026-10-11/model_runtime.py'
    if legacy_key not in entries:
        raise ValueError('Freeze must pin reused ../study-2026-10-11/model_runtime.py')
    if '../study-2026-10-11/model-execution.json' not in entries:
        raise ValueError('Freeze must pin historical cross-encoder file manifest')
    prepared_sha = freeze.get('prepare_receipt_sha256')
    if not isinstance(prepared_sha, str) or not re.fullmatch(r'[a-f0-9]{64}', prepared_sha):
        raise ValueError('Freeze must bind the exact private preparation receipt')
    return {'freeze_sha256': expected_sha, 'bank_sha256': file_sha(HERE/'challenge-bank.json'),
            'prepare_receipt_sha256': prepared_sha,
            'file_pins': {k: v.get('sha256') if isinstance(v, dict) else v for k, v in entries.items()},
            'legacy_runtime_sha256': file_sha(legacy), 'protocol': VERSION}


def checkpoint_key(family_id, task_id, size):
    return common.digest(family_id+'\n'+task_id+'\n'+size_name(size))


def query_fingerprint(freeze, family_id, task_id, query, size):
    return digest_value({'freeze': freeze, 'family_id': family_id, 'task_id': task_id,
                         'query_sha256': common.digest(query), 'size': size_name(size),
                         'methods': METHODS, 'packers': packing_lab.METHODS, 'budgets': BUDGETS})


def checkpoint_path(work, family_id, task_id, size):
    return Path(work)/'checkpoints'/(checkpoint_key(family_id, task_id, size)+'.json')


def packet_cell_key(ranker, packer, budget):
    return ranker+'|'+packer+'|'+str(budget)


def reader_only_cell(ranker, packer, budget, size):
    return (ranker == 'search_bm25' and packer == 'ranked_body'
            and type(budget) is int and budget == 8192 and size_name(size) == '144')


def identify(families, family_id, task_id):
    found = [f for f in families if f['id'] == family_id]
    if len(found) != 1: raise ValueError('Unknown or duplicate family')
    tasks = [t for t in found[0]['tasks'] if t['id'] == task_id]
    if len(tasks) != 1: raise ValueError('Unknown or duplicate task')
    return found[0], tasks[0]


def runtime_versions():
    return {name: importlib.metadata.version(name) for name in ('numpy', 'onnxruntime', 'tokenizers', 'scikit-learn')}


def compact_observations(observations):
    return [{k: o[k] for k in ('id', 'start', 'end', 'source_hash', 'whole')} for o in observations]


def packet_record(family, task, ranker, packer, budget, size, result, docs, states):
    metrics = common.support_metrics(task, result['observations'], docs)
    selected_states = {i: states[i] for i in result['ids'] if i in states}
    skipped = result['receipt']['budget_skips']
    return {'family_id': family['id'], 'task_id': task['id'], 'template_family': family['template_family'],
            'split': family['split'], 'ranker': ranker, 'packer': packer, 'budget': budget,
            'size': size_name(size), 'collection_documents': len(docs), 'state': 'complete',
            'packet_sha256': result['receipt']['packet_sha256'], 'bytes': result['bytes'],
            'selected_ids': result['ids'], 'observations': compact_observations(result['observations']),
            'packing_receipt_sha256': digest_value(result['receipt']),
            'budget_skipped_units': len(skipped), 'budget_skip_reasons': dict(Counter(s['reason'] for s in skipped)),
            'missing_expansion_refs': result['receipt']['missing_expansion_refs'],
            'traversal_cap_count': len(result['receipt']['traversal_caps']),
            'gated_derived_ids': result['receipt']['gated_derived_ids'],
            'selected_derived_states': selected_states,
            'selected_stale_views': sum(v['state'] == 'stale' for v in selected_states.values()),
            'selected_unverifiable_views': sum(v['state'] == 'unverifiable' for v in selected_states.values()),
            **metrics}


def candidate_metrics(task, order):
    result = {}
    for k in (8, 16, 32, 64):
        candidates = set(order[:k])
        result[str(k)] = {'declared_original_bundle_in_candidates': any(set(s) <= candidates for s in task['evidence_sets']),
                         'best_declared_span_id_fraction': max(sum(s['id'] in candidates for s in spans)/len(spans)
                                                               for spans in task['evidence_spans'])}
    return result


def failure_record(family, task, method, size, error):
    return {'family_id': family['id'], 'task_id': task['id'], 'template_family': family['template_family'],
            'split': family['split'], 'ranker': method, 'size': size_name(size), 'state': 'fault',
            'error_type': type(error).__name__, 'error_message_sha256': common.digest(str(error))}


def prepare(work, cache):
    """Training labels stay inside this preparation step, never ranking/packing."""
    from dense_runtime import Encoder, DensePreparedIndex
    work, cache = private_path(work), private_path(cache)
    families = common.bank()['families']
    split = split_families(families)
    all_docs = common.documents(families)
    development = [f for f in families if split[f['id']] == 'development']
    dev_docs = common.documents(development)
    rows = []
    training_queries = []
    for family in development:
        for task in family['tasks']:
            values = decision_ranker.features(dev_docs, task['query'])
            positive = set.union(*(set(s) for s in task['evidence_sets']))
            if not positive <= set(dev_docs): raise ValueError('Development labels reference nondevelopment record')
            rows.extend((values[i], int(i in positive)) for i in sorted(dev_docs))
            training_queries.append(task['id'])
    identity = {'development_only': True, 'bank_sha256': file_sha(HERE/'challenge-bank.json'),
                'development_family_ids': sorted(f['id'] for f in development),
                'development_template_groups': sorted({f['template_family'] for f in development}),
                'document_ids_sha256': digest_value(sorted(dev_docs)), 'query_ids': training_queries,
                'positive_label': 'Union of authored sufficient ORIGINAL IDs for the development query only',
                'negative_label': 'Every other development-family document',
                'confirmation_records_used_for_training': 0, 'feature_definition': list(decision_ranker.FEATURES)}
    tree = decision_ranker.train(rows, identity)
    common.save(HERE/'decision-model.json', tree)
    encoder = Encoder(cache, threads=2, batch_size=12)
    indexes = {
        'body': DensePreparedIndex(all_docs, encoder, text_mode='body', windows=False),
        'search': DensePreparedIndex(all_docs, encoder, text_mode='search', windows=False),
        'windows': DensePreparedIndex(all_docs, encoder, text_mode='body', windows=True),
    }
    receipt = {'schema_version': 1, 'state': 'complete_preparation', 'bank_sha256': identity['bank_sha256'],
               'implementation_pins': implementation_pins(), 'decision_model_sha256': file_sha(HERE/'decision-model.json'),
               'runtime_versions': runtime_versions(), 'dense_model': encoder.manifest,
               'dense_indexes': {name: index.build_receipt for name, index in indexes.items()},
               'global_documents': len(all_docs), 'development_documents': len(dev_docs),
               'training_rows': len(rows), 'confirmation_endpoints_scored': 0}
    common.save(work/'prepare-receipt.json', receipt)
    print(canonical({'phase': 'prepared', 'global_documents': len(all_docs), 'training_rows': len(rows)}), flush=True)
    return receipt


class Runtime:
    def __init__(self, work, cache, freeze, use_models=True):
        self.work, self.cache, self.freeze = private_path(work), private_path(cache), freeze
        self.families = common.bank()['families']
        split_families(self.families)
        self.docs = common.documents(self.families)
        self.tree = json.loads((HERE/'decision-model.json').read_text(encoding='utf-8'))
        if file_sha(self.work/'prepare-receipt.json') != freeze['prepare_receipt_sha256']:
            raise ValueError('Private preparation receipt differs from the public freeze binding')
        prepared = json.loads((self.work/'prepare-receipt.json').read_text(encoding='utf-8'))
        if prepared['bank_sha256'] != freeze['bank_sha256'] or prepared['decision_model_sha256'] != file_sha(HERE/'decision-model.json'):
            raise ValueError('Preparation does not match frozen bank/tree')
        for name, value in prepared['implementation_pins'].items():
            if file_sha(HERE/name) != value: raise ValueError('Implementation changed after preparation: '+name)
        if prepared['runtime_versions'] != runtime_versions(): raise ValueError('Runtime package versions changed after preparation')
        self.query_vectors, self.dense_scores = {}, {}
        self.events = []
        self.index_cache = OrderedDict()
        # Full character/sentence indexes can be substantial. Keep the global
        # collection and current family resident; do not retain all 96 families.
        self.max_local_indexes = 2
        if use_models:
            from dense_runtime import Encoder, DensePreparedIndex
            from neural_ranker import PairDecisions
            for row in prepared['dense_indexes'].values():
                folder = self.cache/'dense-indexes'/row['index_key']
                if not (folder/'manifest.json').exists() or not (folder/'vectors.npy').exists():
                    raise ValueError('Prepared document-vector cache is missing; no rebuild allowed in frozen run')
            self.encoder = Encoder(cache, threads=2, batch_size=12)
            self.dense = {
                'body': DensePreparedIndex(self.docs, self.encoder, text_mode='body', windows=False),
                'search': DensePreparedIndex(self.docs, self.encoder, text_mode='search', windows=False),
                'windows': DensePreparedIndex(self.docs, self.encoder, text_mode='body', windows=True),
            }
            if any(not value.build_receipt['index_cache_hit'] for value in self.dense.values()):
                raise ValueError('Frozen run unexpectedly rebuilt document vectors; rerun preparation before freeze')
            if any(value.key != prepared['dense_indexes'][name]['index_key'] for name, value in self.dense.items()):
                raise ValueError('Dense representation identity changed after preparation')
            for name, index in self.dense.items():
                for key in ('vector_sha256', 'index_manifest_sha256'):
                    if index.build_receipt[key] != prepared['dense_indexes'][name][key]:
                        raise ValueError('Prepared dense cache bytes changed: ' + name + ':' + key)
            self.pairs = PairDecisions(cache, threads=2)
            historical = json.loads((HERE.parent/'study-2026-10-11/model-execution.json').read_text(encoding='utf-8'))['models']
            for name, scorer in self.pairs.scorers.items():
                if scorer.manifest['files'] != historical[name]['files']:
                    raise ValueError('Cross-encoder configuration/tokenizer/weight bytes differ from historical pin')

    def lexical(self, family_id, size):
        key = (family_id if size_name(size) == '144' else 'global', size_name(size))
        if key not in self.index_cache:
            docs = common.collection(self.docs, family_id, size)
            index = index_lab.PreparedIndex(docs)
            index.prepare_characters()
            self.index_cache[key] = (docs, index)
            while len(self.index_cache) > self.max_local_indexes:
                oldest = next(k for k in self.index_cache if k[0] != 'global')
                self.index_cache.pop(oldest)
        self.index_cache.move_to_end(key)
        return self.index_cache[key]

    def dense_values(self, query, representation, cached=True):
        key = common.digest(query)
        pair = (key, representation)
        embedding_hit = cached and key in self.query_vectors
        score_hit = cached and pair in self.dense_scores
        if score_hit:
            return self.dense_scores[pair], {'query_embedding_cache_hit': embedding_hit, 'dense_score_cache_hit': True,
                'query_input_tokens_computed': 0, 'query_truncated': bool(self.query_vectors[key][1]['truncated_texts']), 'query_encode_seconds': 0.0,
                'dense_search_seconds': 0.0, 'document_vectors_computed_at_query': 0}
        if embedding_hit: vector, original_usage = self.query_vectors[key]
        else:
            matrix, original_usage = self.encoder.encode([query])
            vector = matrix[0]
            if cached: self.query_vectors[key] = (vector, original_usage)
        started = time.perf_counter()
        index = self.dense[representation]
        values = index.vectors @ vector
        scores = {i: -1.0 for i in self.docs}
        for row, value in zip(index.mapping, values): scores[row['id']] = max(scores[row['id']], float(value))
        elapsed = time.perf_counter()-started
        if cached: self.dense_scores[pair] = scores
        usage = {'query_embedding_cache_hit': embedding_hit, 'dense_score_cache_hit': False,
                 'query_input_tokens_computed': 0 if embedding_hit else original_usage['input_tokens'],
                 'query_truncated': bool(original_usage['truncated_texts']),
                 'query_encode_seconds': 0.0 if embedding_hit else original_usage['seconds'],
                 'dense_search_seconds': elapsed, 'document_vectors_computed_at_query': 0,
                 'searched_vectors': len(index.mapping), 'global_index_key': index.key}
        return scores, usage

    def rank(self, family_id, query, size, method, cached=True):
        started = time.perf_counter()
        docs, lexical = self.lexical(family_id, size)
        if method in index_lab.METHODS:
            order, usage = lexical.rank_with_receipt(query, method)
        elif method in DENSE_METHODS:
            representation = {'dense_body': 'body', 'dense_search': 'search',
                              'dense_windows': 'windows', 'dense_window_rrf': 'windows'}[method]
            global_scores, usage = self.dense_values(query, representation, cached=cached)
            scores = {i: global_scores[i] for i in docs}
            dense_order = index_lab.sorted_ids(docs, scores)
            if method == 'dense_window_rrf':
                body_order = lexical.rank(query, 'body_bm25')
                order = index_lab.sorted_ids(docs, index_lab.fuse(docs, [dense_order, body_order]))
            else: order = dense_order
            usage.update(scores=scores, candidate_intersection='Global source vectors intersected with local collection before ranking/fusion',
                         local_lexical_idf=True, query_vectors_cached_for_grid=cached)
        elif method in NEURAL_METHODS:
            order, usage = self.pairs.rank(docs, query, method, lexical=lexical, cached=cached)
        elif method == 'shallow_tree':
            order = decision_ranker.rank(docs, query, self.tree)
            usage = {'decision_model_sha256': file_sha(HERE/'decision-model.json'),
                     'development_only_training': True, 'uncalibrated_score': True}
        else: raise ValueError('Unknown ranker')
        if len(order) != len(docs) or len(set(order)) != len(order) or set(order) != set(docs):
            raise ValueError('Ranker did not return complete collection permutation')
        usage.update(rank_seconds=time.perf_counter()-started, method=method,
                     ranking_sha256=digest_value(order), collection_sha256=lexical.digest)
        self.events.append({'method': method, 'query_sha256': common.digest(query), 'size': size_name(size),
            'rank_seconds': usage['rank_seconds'],
            **{k: v for k, v in usage.items() if k in ('pairs_computed', 'input_pair_tokens', 'truncated_pairs',
                'query_input_tokens_computed', 'query_truncated', 'query_embedding_cache_hit', 'dense_score_cache_hit')}})
        return order, usage, docs


def run_query(runtime, family, task, size):
    path = checkpoint_path(runtime.work, family['id'], task['id'], size)
    fingerprint = query_fingerprint(runtime.freeze, family['id'], task['id'], task['query'], size)
    if path.exists():
        previous = json.loads(path.read_text(encoding='utf-8'))
        if previous.get('fingerprint') != fingerprint or previous.get('state') != 'complete_query':
            raise ValueError('Checkpoint identity/state mismatch')
        return previous, True
    rankings, packets = {}, {}
    for method in METHODS:
        try:
            order, usage, docs = runtime.rank(family['id'], task['query'], size, method)
            states = packing_lab.view_states(docs)
            rank_row = {'family_id': family['id'], 'task_id': task['id'], 'template_family': family['template_family'],
                'split': family['split'], 'ranker': method, 'size': size_name(size), 'state': 'complete',
                'documents': len(docs), 'top64': order[:64], 'full_ranking_sha256': digest_value(order),
                'collection_sha256': usage['collection_sha256'], 'candidate_recovery': candidate_metrics(task, order),
                'execution': {k: v for k, v in usage.items() if k not in ('scores', 'ranked_ids', 'candidate_scores',
                    'channel_rankings', 'greedy_trace', 'applicability_states', 'missing_edges')},
                'full_rank_receipt_sha256': digest_value(usage)}
            rankings[method] = rank_row
            for packer, budget in cells_for(method):
                key = packet_cell_key(method, packer, budget)
                try:
                    result = packing_lab.pack(docs, task['query'], order[:32], budget, packer)
                    packets[key] = packet_record(family, task, method, packer, budget, size, result, docs, states)
                except Exception as error:
                    packets[key] = {**failure_record(family, task, method, size, error), 'packer': packer, 'budget': budget}
                    common.save(runtime.work/'errors'/(fingerprint+'-'+common.digest(key)+'.json'),
                                {'traceback': traceback.format_exc(), 'error': str(error)})
        except Exception as error:
            rankings[method] = failure_record(family, task, method, size, error)
            common.save(runtime.work/'errors'/(fingerprint+'-'+method+'.json'),
                        {'traceback': traceback.format_exc(), 'error': str(error)})
            for packer, budget in cells_for(method):
                packets[packet_cell_key(method, packer, budget)] = {
                    **failure_record(family, task, method, size, error), 'packer': packer, 'budget': budget,
                    'failure_stage': 'ranking'}
    checkpoint = {'schema_version': 1, 'state': 'complete_query', 'fingerprint': fingerprint,
                  'freeze_sha256': runtime.freeze['freeze_sha256'], 'family_id': family['id'],
                  'task_id': task['id'], 'size': size_name(size), 'rankings': rankings, 'packets': packets}
    if len(rankings) != 21 or len(packets) != 198: raise ValueError('Grid deduplication count differs from plan')
    common.save(path, checkpoint)
    return checkpoint, False


def run_partition(work, cache, freeze_sha, worker_index=0, workers=1):
    freeze = verify_freeze(freeze_sha)
    runtime = Runtime(work, cache, freeze)
    groups = sorted({f['template_family'] for f in runtime.families})
    selected = set(groups[worker_index::workers])
    counters = Counter()
    invocation = str(time.time_ns())
    model_receipts = {'dense': runtime.encoder.manifest,
                      'cross_encoders': {name: scorer.manifest for name, scorer in runtime.pairs.scorers.items()}}
    common.save(Path(work)/'worker-history'/f'{worker_index}-{invocation}-models.json',
                {'freeze_sha256': freeze_sha, 'worker': worker_index, 'models': model_receipts})
    for group in groups:
        if group not in selected: continue
        for family in sorted((f for f in runtime.families if f['template_family'] == group), key=lambda f: f['id']):
            for task in family['tasks']:
                for size in SIZES:
                    row, reused = run_query(runtime, family, task, size)
                    counters['reused_queries' if reused else 'executed_queries'] += 1
                    counters['rankings'] += len(row['rankings']); counters['packets'] += len(row['packets'])
        common.save(Path(work)/f'worker-{worker_index}-progress.json',
                    {'state': 'running', 'worker': worker_index, 'last_completed_template': group, 'counts': dict(counters)})
        common.save(Path(work)/'worker-history'/f'{worker_index}-{invocation}-{safe_slug(group)}.json',
                    {'state': 'completed_template_prefix', 'freeze_sha256': freeze_sha, 'worker': worker_index,
                     'last_completed_template': group, 'counts': dict(counters),
                     'events': runtime.events, 'pair_calls': runtime.pairs.calls})
        print(canonical({'worker': worker_index, 'completed_template': group, 'counts': dict(counters)}), flush=True)
    receipt = {'state': 'complete_partition', 'worker': worker_index, 'workers': workers,
               'freeze_sha256': freeze_sha, 'templates': sorted(selected), 'counts': dict(counters),
               'events': runtime.events, 'pair_calls': runtime.pairs.calls,
               'models': model_receipts,
               'document_indexes': {name: value.build_receipt for name, value in runtime.dense.items()}}
    common.save(Path(work)/f'worker-{worker_index}-receipt.json', receipt)
    common.save(Path(work)/'worker-history'/f'{worker_index}-{invocation}-complete.json', receipt)
    return receipt


def safe_slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.casefold()).strip('-') or common.digest(text)[:12]


def write_shards(group, kind, rows, freeze_sha):
    folder = HERE/'results'
    chunks, chunk, estimated = [], [], 0
    for row in rows:
        cost = len((json.dumps(row, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode('utf-8'))+8
        if chunk and estimated+cost > MAX_SHARD_BYTES:
            chunks.append(chunk); chunk, estimated = [], 0
        chunk.append(row); estimated += cost
    if chunk: chunks.append(chunk)
    receipts = []
    for n, chunk in enumerate(chunks, 1):
        path = folder/(safe_slug(group)+'-'+kind+f'-{n:02d}.json')
        common.save(path, {'schema_version': 1, 'state': 'complete', 'freeze_sha256': freeze_sha,
                           'template_family': group, 'kind': kind, 'rows': chunk})
        if path.stat().st_size >= 50*1024*1024: raise ValueError('Public JSON shard exceeds 50 MiB ceiling')
        receipts.append({'file': path.relative_to(HERE).as_posix(), 'sha256': file_sha(path),
                         'bytes': path.stat().st_size, 'rows': len(chunk)})
    return receipts


def assemble(work, freeze_sha):
    freeze = verify_freeze(freeze_sha)
    families = common.bank()['families']
    split_families(families)
    shards, counts = [], Counter()
    for group in sorted({f['template_family'] for f in families}):
        ranks, packets = [], []
        for family in sorted((f for f in families if f['template_family'] == group), key=lambda f: f['id']):
            for task in family['tasks']:
                for size in SIZES:
                    row = json.loads(checkpoint_path(work, family['id'], task['id'], size).read_text(encoding='utf-8'))
                    if (row.get('state') != 'complete_query' or row.get('freeze_sha256') != freeze_sha
                            or row.get('fingerprint') != query_fingerprint(freeze, family['id'], task['id'], task['query'], size)):
                        raise ValueError('Unfrozen/incomplete checkpoint during assembly')
                    ranks.extend(row['rankings'][m] for m in METHODS)
                    packets.extend(row['packets'][packet_cell_key(m,p,b)] for m in METHODS for p,b in cells_for(m))
        shards.extend(write_shards(group, 'rankings', ranks, freeze_sha))
        shards.extend(write_shards(group, 'packets', packets, freeze_sha))
        counts['rankings'] += len(ranks); counts['packets'] += len(packets)
        counts['ranking_faults'] += sum(r['state'] != 'complete' for r in ranks)
        counts['packet_faults'] += sum(r['state'] != 'complete' for r in packets)
    queries = sum(len(f['tasks']) for f in families)
    if counts['rankings'] != queries*2*21 or counts['packets'] != queries*2*198:
        raise ValueError('Assembled census differs from complete prospective grid')
    workers = []
    for path in sorted(Path(work).glob('worker-*-receipt.json')):
        row = json.loads(path.read_text(encoding='utf-8'))
        if row['freeze_sha256'] != freeze_sha: raise ValueError('Worker receipt has different freeze')
        workers.append({'worker': row['worker'], 'templates': row['templates'],
                        'counts': row['counts'], 'receipt_sha256': file_sha(path)})
    manifest = {'schema_version': 1, 'state': 'complete_grid_collection', 'freeze_sha256': freeze_sha,
                'bank_sha256': freeze['bank_sha256'], 'rankers': list(METHODS), 'sizes': list(SIZES),
                'budgets': list(BUDGETS), 'base_packers': list(BASE_PACKERS), 'extended_rankers': list(EXTENDED),
                'all_packers': list(packing_lab.METHODS), 'families': len(families), 'queries': queries,
                'counts': dict(counts), 'shards': shards, 'workers': workers,
                'offset_unit': 'Python Unicode character offsets into unchanged body, half-open',
                'source_hash_definition': 'SHA-256 of unchanged body encoded as UTF-8',
                'packet_hash_definition': 'SHA-256 of exact wrapper/separator/source-slice packet encoded as UTF-8',
                'ranking_hash_definition': 'SHA-256 of full ID list in compact ensure_ascii=False JSON',
                'source_text_omitted': 'Intervals/hash point to unchanged bank bodies; packet reconstruction is deterministic.',
                'candidate_endpoint': 'Source-ID candidate coverage, not source-span exposure or reader success.',
                'selection_statement': 'All scheduled cells retained; no winning policy selected here.'}
    common.save(HERE/'grid-manifest.json', manifest)
    common.save(Path(work)/'grid-completion.json', manifest)
    return manifest


def build_packet(family_id, task_id, ranker, packer, budget, size, privatework):
    """No model required. Reconstruct a verified frozen checkpoint's actual packet."""
    work = private_path(privatework)
    checkpoint = json.loads(checkpoint_path(work, family_id, task_id, size).read_text(encoding='utf-8'))
    freeze = verify_freeze(checkpoint['freeze_sha256'])
    if checkpoint['state'] != 'complete_query': raise ValueError('Incomplete query checkpoint')
    families = common.bank()['families']
    family, task = identify(families, family_id, task_id)
    if checkpoint.get('fingerprint') != query_fingerprint(freeze, family_id, task_id, task['query'], size):
        raise ValueError('Packet checkpoint fingerprint differs from frozen query inputs')
    docs = common.collection(common.documents(families), family_id, size)
    ranking = checkpoint['rankings'][ranker]
    key = packet_cell_key(ranker, packer, budget)
    scheduled = checkpoint['packets'].get(key)
    reader_only = reader_only_cell(ranker, packer, budget, size)
    if scheduled is None and not reader_only:
        raise ValueError('Unknown cell is not a scheduled grid or preregistered reader-only cell')
    if ranking['state'] != 'complete' or scheduled is not None and scheduled['state'] != 'complete':
        raise ValueError('The scheduled cell contains a recorded infrastructure fault')
    result = packing_lab.pack(docs, task['query'], ranking['top64'][:32], int(budget), packer)
    if scheduled is not None and (result['receipt']['packet_sha256'] != scheduled['packet_sha256']
            or digest_value(result['receipt']) != scheduled['packing_receipt_sha256']
            or compact_observations(result['observations']) != scheduled['observations']
            or result['bytes'] != scheduled['bytes']):
        raise ValueError('Packet reconstruction differs from frozen executed cell')
    result.update(ranking_receipt=ranking, freeze_sha256=freeze['freeze_sha256'],
                  family_id=family_id, task_id=task_id, ranker=ranker, packer=packer,
                  reader_only_reconstruction=scheduled is None,
                  grid_packing_receipt_available=scheduled is not None)
    return result


def time_warm(work, cache, freeze_sha):
    runtime = Runtime(work, cache, verify_freeze(freeze_sha))
    development = sorted((f for f in runtime.families if f['split'] == 'development'),
                         key=lambda f: common.digest(f['id']+':oct13-timing-v1'))
    chosen = []
    for family in development:
        if family['template_family'] not in {f['template_family'] for f in chosen}:
            chosen.append(family)
    for family in development:
        if family not in chosen and len(chosen) < 6: chosen.append(family)
    chosen = chosen[:6]
    cases = [(f, f['tasks'][0]) for f in chosen]
    runtime.max_local_indexes = 8
    for family, _ in cases:
        runtime.lexical(family['id'], 144)
    warmup, rows = [], []
    for method in METHODS:
        family, task = cases[0]
        order, usage, docs = runtime.rank(family['id'], task['query'], 144, method, cached=False)
        packing_lab.pack(docs, task['query'], order[:32], 8192, 'closure_passages')
        warmup.append({'method': method, 'rank_usage': usage})
        for family, task in cases:
            for repetition in range(3):
                started = time.perf_counter()
                order, usage, docs = runtime.rank(family['id'], task['query'], 144, method, cached=False)
                packet = packing_lab.pack(docs, task['query'], order[:32], 8192, 'closure_passages')
                rows.append({'ranker': method, 'family_id': family['id'], 'task_id': task['id'],
                    'template_family': family['template_family'], 'repetition': repetition+1, 'size': '144',
                    'budget': 8192, 'packer': 'closure_passages', 'seconds': time.perf_counter()-started,
                    'packet_bytes': packet['bytes'], 'pairs_or_vector_usage': {k: v for k, v in usage.items()
                        if k in ('pairs_computed', 'input_pair_tokens', 'truncated_pairs', 'query_input_tokens_computed',
                                 'query_truncated', 'searched_vectors', 'query_embedding_cache_hit', 'dense_score_cache_hit')}})
    result = {'schema_version': 1, 'state': 'complete_warm_timing', 'freeze_sha256': freeze_sha,
              'document_indexes_resident': True, 'query_embedding_or_pair_cache_enabled': False,
              'neural_threads': 2, 'serial_repetitions': 3, 'development_queries': 6, 'rows': rows,
              'warmup': warmup, 'host_activity': 'Uncontrolled desktop activity; not an isolated hardware benchmark.',
              'loading_and_index_build_excluded': True}
    common.save(HERE/'warm-timing.json', result)
    return result


def self_check():
    assert len(METHODS) == 21 and len(set(METHODS)) == 21
    assert sum(len(cells_for(m)) for m in METHODS) == 198
    assert 288*2*198 == 114048 and 288*2*21 == 12096
    assert all(len(set(cells_for(m))) == len(cells_for(m)) for m in METHODS)
    def doc(i, body, **extra):
        return {'id': i, 'kind': 'source', 'revision': 1, 'authored_at': '2026-10-13',
                'title': i, 'scope': 'all', 'aliases': ['fixture'], 'body': body,
                'links': [], 'supersedes': [], 'incorporates': [], 'branch': 'fixture', **extra}
    docs = {'D1': doc('D1', 'Retention is twelve days.\nThe approval is pending.', links=['D2']),
            'D2': doc('D2', 'Approval remains pending until evidence arrives.'),
            'X': doc('X', 'Apples and cinnamon make a recipe.')}
    task = {'id': 'Q', 'query': 'retention approval', 'evidence_sets': [['D1','D2']],
            'evidence_spans': [[{'id':'D1','start':0,'end':24},{'id':'D2','start':0,'end':len(docs['D2']['body'])}]]}
    family = {'id': 'F', 'template_family': 'synthetic', 'split': 'development'}
    order = index_lab.rank(docs, task['query'], 'body_bm25')
    for packer in packing_lab.METHODS:
        result = packing_lab.pack(docs, task['query'], order, 8192, packer)
        row = packet_record(family, task, 'body_bm25', packer, 8192, 144, result, docs, {})
        reconstructed = packing_lab.pack(docs, task['query'], order, 8192, packer)
        assert row['packet_sha256'] == reconstructed['receipt']['packet_sha256']
        assert compact_observations(reconstructed['observations']) == row['observations']
        assert 'text' not in canonical(row['observations'])
        assert row['bytes'] <= 8192
    assert candidate_metrics(task, ['D1','D2','X'])['8']['declared_original_bundle_in_candidates']
    assert checkpoint_key('F','Q',144) == checkpoint_key('F','Q','144')
    assert reader_only_cell('search_bm25', 'ranked_body', 8192, 144)
    assert not reader_only_cell('search_bm25', 'ranked_body', '8192', 144)
    assert not reader_only_cell('search_bm25', 'ranked_body', 8192, 'all')
    assert not reader_only_cell('entity_rrf', 'ranked_body', 8192, 144)
    try: private_path(HERE)
    except ValueError: pass
    else: raise AssertionError('Private cache accepted inside repository')
    print(canonical({'state': 'passed', 'rankers': len(METHODS), 'cells_per_query_size': 198,
                     'planned_packets': 114048, 'checks': ['deduplicated schedule', 'source-exact packet reconstruction',
                      'text-free interval receipts', 'candidate endpoint boundary', 'private-path boundary']}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--self-check', action='store_true')
    modes.add_argument('--prepare', action='store_true')
    modes.add_argument('--run', action='store_true')
    modes.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    modes.add_argument('--assemble', action='store_true')
    modes.add_argument('--timing', action='store_true')
    parser.add_argument('--work', type=Path)
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--freeze-sha256')
    parser.add_argument('--workers', type=int, choices=(1,2), default=1)
    parser.add_argument('--worker-index', type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.self_check: return self_check()
    if args.work is None: parser.error('--work private directory required')
    work = private_path(args.work); work.mkdir(parents=True, exist_ok=True)
    if args.assemble: return assemble(work, args.freeze_sha256)
    if args.cache is None: parser.error('--cache private directory required')
    cache = private_path(args.cache)
    if args.prepare: return prepare(work, cache)
    if args.worker:
        if not 0 <= args.worker_index < args.workers: parser.error('Invalid worker partition')
        return run_partition(work, cache, args.freeze_sha256, args.worker_index, args.workers)
    if args.timing: return time_warm(work, cache, args.freeze_sha256)
    verify_freeze(args.freeze_sha256)
    if args.workers == 1: run_partition(work, cache, args.freeze_sha256)
    else:
        children, logs = [], []
        try:
            for worker in range(2):
                log = (work/f'worker-{worker}.log').open('ab'); logs.append(log)
                command = [sys.executable, str(Path(__file__).resolve()), '--worker', '--work', str(work),
                           '--cache', str(cache), '--freeze-sha256', args.freeze_sha256,
                           '--workers', '2', '--worker-index', str(worker)]
                options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
                children.append(subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **options))
            while any(child.poll() is None for child in children): time.sleep(1)
            if any(child.returncode for child in children): raise RuntimeError('Owned worker failed; inspect private worker logs')
        except BaseException:
            for child in children:
                if child.poll() is None: child.terminate()
            for child in children: child.wait()
            raise
        finally:
            for log in logs: log.close()
    result = assemble(work, args.freeze_sha256)
    print(canonical({'phase': 'complete_grid', 'counts': result['counts']}), flush=True)
    return result


if __name__ == '__main__': main()
