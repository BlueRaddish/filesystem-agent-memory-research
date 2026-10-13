"""Prospective, development-only fresh retrieval cues; no full-bank access.

All provider text, queries and per-cell receipts stay in an explicit private root.
The public JSON contains only fixed dimensions, hashes and aggregate outcomes.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import sys
import tempfile
import time

from artifact_contract import strict_json
from index_lab import PreparedIndex, clauses_for, fuse, sorted_ids
from packing_lab import pack
import packing_lab
import reader_trials
from study_common import documents, support_metrics

HERE = Path(__file__).resolve().parent
SOURCE_SHA = 'a4b7f77cf2311e1c2cd742df9996ddd5d5b7542b9a0a20f3eb305621f9f9a8fa'
SOURCE_BANK_SHA = '280e6be3f7380ed9c0bc1dbe3ec75dfba136113f230d08751e0f316b67cf9760'
POLICIES = ('original_query', 'deterministic_clause_cues', 'generated_cues')
RETRIEVERS = ('body_bm25', 'entity_rrf')
PACKERS = ('whole_record', 'closure_passages')
BUDGETS = (4096, 8192, 16384)
WORKERS, TOP_K, RRF_K = 2, 32, 60
CUE_CAP, CUE_BYTES, OUTPUT_BYTES = 3, 512, 4096
PINS = ('AGENT-QUERY-PLAN.md', 'agent_query_lab.py', 'index_lab.py',
        'packing_lab.py', 'study_common.py', 'reader_trials.py', 'artifact_contract.py',
        'runtime-public.json')
PROMPT = '''You propose search queries for a fictional read-only evidence collection.
You see only the task text. Do not answer the task or assert any factual result.
Return exactly one JSON object with one key: "queries".
Its value is an array of zero to three alternative retrieval queries or explicit
conditional subquestions that could find evidence needed for this task.
Preserve named workstreams, scope, dates, exceptions and conditions where useful.
Do not invent record IDs, documents, facts, values, decisions or evidence.
Do not repeat the original task query. Each query must be a nonempty string
of at most 512 UTF-8 bytes. If no useful alternative exists, return {"queries":[]}.
No markdown, commentary, answers or extra keys. Use no tools.
Task query (JSON string):
'''
SOURCES = [
    {'name': 'Query2doc', 'url': 'https://aclanthology.org/2023.emnlp-main.585/',
     'relation': 'Adjacent pseudo-document query expansion; full method not reproduced.'},
    {'name': 'HyDE', 'url': 'https://aclanthology.org/2023.acl-long.99/',
     'relation': 'Adjacent hypothetical-document dense retrieval; no dense encoder here.'},
    {'name': 'RQ-RAG', 'url': 'https://arxiv.org/abs/2404.00610',
     'relation': 'Adjacent learned rewriting/decomposition system; no training or full reproduction.'},
]


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode('utf8')).hexdigest()


def object_digest(value):
    return digest(canonical(value))


def file_digest(path):
    return digest(Path(path).read_bytes())


def atomic_json(path, value):
    """Unique per-call/cell paths allow two workers; no shared append log."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                      allow_nan=False) + '\n').encode('utf8')
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('wb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def read_json(path):
    return strict_json(Path(path).read_text(encoding='utf8'))


def private_root(path):
    root = Path(path).resolve()
    assert not root.is_relative_to(HERE.parents[1]), 'Private receipts must stay outside Git'
    return root


def load_development(path):
    """Separate observable/query projections from evaluation-only span gold."""
    path = Path(path)
    assert file_digest(path) == SOURCE_SHA, 'Development excerpt hash mismatch'
    data = read_json(path)
    assert data['source_bank_sha256'] == SOURCE_BANK_SHA
    families = data['families']
    assert len(families) == 24 and all(f['split'] == 'development' for f in families)
    docs = documents(families)
    tasks, gold = [], {}
    for family in families:
        for task in family['tasks']:
            tasks.append({'id': task['id'], 'query': task['query'],
                          'history': family['id'], 'template_group': family['template_family']})
            gold[task['id']] = {k: task[k] for k in ('evidence_sets', 'evidence_spans')}
    tasks.sort(key=lambda t: t['id'])
    assert len(docs) == 276 and len(tasks) == len(gold) == 72
    assert len({t['id'] for t in tasks}) == 72
    for task in tasks:
        assert isinstance(task['query'], str) and task['query'].strip()
        task['query'].encode('utf8')
        assert re.fullmatch(r'[A-Za-z0-9_-]+', task['id'])
        assert set(task) == {'id', 'query', 'history', 'template_group'}
    for value in gold.values():
        assert value['evidence_spans'] and value['evidence_sets']
        for bundle in value['evidence_spans']:
            assert bundle
            for span in bundle:
                assert docs[span['id']]['kind'] == 'source'
                assert type(span['start']) is int and type(span['end']) is int
                assert 0 <= span['start'] < span['end'] <= len(docs[span['id']]['body'])
    return docs, tasks, gold


def prompt_for(query):
    # Only query text crosses this generation boundary; no task ID or source text.
    return PROMPT + json.dumps(query, ensure_ascii=False) + '\n'


def validate_cues(text, original):
    if not isinstance(text, str) or len(text.encode('utf8')) > OUTPUT_BYTES:
        raise ValueError('output_missing_or_over_byte_cap')
    if not text.strip().startswith('{') or not text.strip().endswith('}'):
        raise ValueError('strict_json_object_required')
    value = strict_json(text)
    if not isinstance(value, dict) or set(value) != {'queries'}:
        raise ValueError('exact_queries_key_required')
    cues = value['queries']
    if not isinstance(cues, list) or len(cues) > CUE_CAP:
        raise ValueError('cue_count_or_array_invalid')
    seen, result = {original.strip().casefold()}, []
    original_ids = set(re.findall(r'\bN\d{3}-R\d{3}\b', original))
    for cue in cues:
        if not isinstance(cue, str) or not cue.strip():
            raise ValueError('cue_nonempty_string_required')
        cue = cue.strip()
        if len(cue.encode('utf8')) > CUE_BYTES:
            raise ValueError('cue_byte_cap')
        if cue.casefold() in seen:
            raise ValueError('duplicate_or_original_cue')
        if set(re.findall(r'\bN\d{3}-R\d{3}\b', cue)) - original_ids:
            raise ValueError('invented_source_format_id')
        seen.add(cue.casefold())
        result.append(cue)
    if not result:
        raise ValueError('empty_generation')
    return result


def deterministic_cues(query):
    clauses, _ = clauses_for(query)
    seen, result = {query.strip().casefold()}, []
    for clause in clauses:
        if clause.strip().casefold() not in seen:
            seen.add(clause.strip().casefold())
            result.append(clause.strip())
        if len(result) == CUE_CAP:
            break
    return result


def policy_queries(query, policy, generation):
    if policy == 'original_query':
        cues = []
    elif policy == 'deterministic_clause_cues':
        cues = deterministic_cues(query)
    elif policy == 'generated_cues':
        cues = generation['cues'] if generation['generation_success'] else []
    else:
        raise ValueError('unknown_policy')
    result = [query, *cues]
    assert result[0] == query and len(result) <= 4
    assert len({q.strip().casefold() for q in result}) == len(result)
    return result


def fused_order(ids, orders):
    assert orders and all(len(order) == len(set(order)) == len(ids) and set(order) == set(ids)
                          for order in orders)
    return list(orders[0]) if len(orders) == 1 else sorted_ids(ids, fuse(ids, orders, RRF_K))


def material(dev_path, command_path):
    docs, tasks, _ = load_development(dev_path)
    expected = read_json(HERE / 'runtime-public.json')
    assert expected['model'] == 'muse-spark-1.3-contributor' and expected['reasoning_effort'] == 'high'
    command = read_json(command_path)
    assert isinstance(command, list) and command and all(isinstance(x, str) and x for x in command)
    pins = {name: file_digest(HERE / name) for name in PINS}
    pins['oct11_run_readers.py'] = file_digest(HERE.parent / 'study-2026-10-11' / 'run_readers.py')
    return {'source_sha256': SOURCE_SHA, 'source_bank_sha256': SOURCE_BANK_SHA,
            'documents_projection_sha256': object_digest(docs),
            'query_projection_sha256': object_digest(tasks),
            'prompt_prefix_sha256': digest(PROMPT), 'code_pins': pins,
            'command_sha256': file_digest(command_path), 'expected_runtime': expected,
            'policies': list(POLICIES), 'retrievers': list(RETRIEVERS),
            'packers': list(PACKERS), 'budgets': list(BUDGETS),
            'generation_workers': WORKERS, 'top_k': TOP_K, 'rrf_k': RRF_K,
            'scheduled_calls': 72, 'scheduled_packets': 2592,
            'schedule': [{'task_id': t['id'], 'query_sha256': digest(t['query'])} for t in tasks]}


def prepare(args):
    root = private_root(args.work)
    root.mkdir(parents=True, exist_ok=True)
    assert not (root / 'manifest.json').exists(), 'Existing manifest cannot be overwritten'
    assert not any(root.glob('*-started.json')), 'Existing stage cannot be silently restarted'
    frozen = {'schema_version': 1, 'created_at': now(),
              'material': material(args.development_bank, args.command),
              'environment': {'python': sys.version, 'platform': platform.platform()}}
    atomic_json(root / 'manifest.json', frozen)
    print(canonical({'status': 'prepared_review_pending',
                     'manifest_sha256': file_digest(root / 'manifest.json'),
                     'calls': 72, 'packets': 2592}))


def verified(args):
    root = private_root(args.work)
    frozen = read_json(root / 'manifest.json')
    assert frozen['material'] == material(args.development_bank, args.command), 'Frozen input/code/runtime changed'
    clearance = read_json(root / 'review-clearance.json')
    assert clearance.get('approved') is True, 'Root review clearance required'
    assert clearance.get('manifest_sha256') == file_digest(root / 'manifest.json'), 'Review fingerprint mismatch'
    return root, frozen, read_json(args.command)


def start_stage(root, name, resume):
    marker = root / (name + '-started.json')
    if marker.exists():
        assert resume, 'Existing stage requires explicit --resume'
        assert read_json(marker)['manifest_sha256'] == file_digest(root / 'manifest.json')
    else:
        atomic_json(marker, {'started_at': now(), 'manifest_sha256': file_digest(root / 'manifest.json')})


def derive_generation(text, call, query):
    success, cues, failure = False, [], call.get('failure')
    if call.get('accepted'):
        if call.get('control_receipt', {}).get('native_failed_unavailable_count', 0):
            failure = 'native_tool_attempt_failed_unavailable'
        else:
            try:
                cues = validate_cues(text, query)
                success, failure = True, None
            except (ValueError, TypeError, UnicodeError):
                failure = 'unusable_generation'
    return {'generation_success': success, 'cues': cues, 'fallback_original_query': not success,
            'failure': failure or (None if success else 'unverified_generation')}


def validate_generation_checkpoint(task, row, root, expected):
    prompt = prompt_for(task['query'])
    expected_identity = object_digest({'prompt_sha256': digest(prompt), 'runtime': expected})
    assert row['identity'] == expected_identity and row['task_id'] == task['id']
    call_root = root / 'calls' / task['id']
    receipt_path, pending_path = call_root / 'cue-call.json', call_root / 'cue-pending.json'
    invoke_identity = digest(prompt + json.dumps(expected, sort_keys=True))
    if receipt_path.exists():
        assert row['recorded_call_receipt_sha256'] == file_digest(receipt_path), 'Retained call receipt changed'
        retained = read_json(receipt_path)
        assert retained['identity'] == invoke_identity
        text, call = retained['text'], retained['call']
        assert type(call['accepted']) is bool
        assert call['intended_prompt_sha256'] == digest(prompt)
        assert {k: v for k, v in row['call'].items() if k != 'resume_reused_call'} == {
            k: v for k, v in call.items() if k != 'resume_reused_call'}, 'Stored call fields changed'
        assert type(row['call']['resume_reused_call']) is bool
    else:
        assert row['recorded_call_receipt_sha256'] is None and pending_path.exists()
        pending = read_json(pending_path)
        assert pending['identity'] == invoke_identity and pending['intended_prompt_sha256'] == digest(prompt)
        text, call = None, {'accepted': False, 'usage': None, 'failure': 'interrupted_call_no_receipt',
                            'intended_prompt_sha256': digest(prompt)}
        assert row['call'] == call, 'Unknown-pending call fields changed'
    derived = derive_generation(text, call, task['query'])
    for key, value in derived.items():
        assert type(row[key]) is type(value) and row[key] == value, 'Stored generation result changed'
    return row


def generation_result(task, root, command, expected, transport):
    destination = root / 'generations' / (task['id'] + '.json')
    prompt = prompt_for(task['query'])
    identity = object_digest({'prompt_sha256': digest(prompt), 'runtime': expected})
    if destination.exists():
        result = read_json(destination)
        return validate_generation_checkpoint(task, result, root, expected)
    started = time.perf_counter()
    text, call = reader_trials.invoke_recorded(transport, command, prompt,
        root / 'calls' / task['id'], 'cue', expected)
    receipt_path = root / 'calls' / task['id'] / 'cue-call.json'
    receipt_sha = file_digest(receipt_path) if receipt_path.exists() else None
    assert receipt_sha is not None or call.get('failure') == 'interrupted_call_no_receipt'
    result = {'identity': identity, 'task_id': task['id'], **derive_generation(text, call, task['query']),
              'call': call, 'recorded_call_receipt_sha256': receipt_sha,
              'host_generation_seconds': time.perf_counter() - started}
    validate_generation_checkpoint(task, result, root, expected)
    atomic_json(destination, result)
    return result


def generate(args):
    root, frozen, command = verified(args)
    start_stage(root, 'generation', args.resume)
    assert not (root / 'generation-complete.json').exists(), 'Generation already complete'
    _, tasks, _ = load_development(args.development_bank)
    transport = reader_trials.runtime()
    # Keep the frozen immediate-receipt and unknown-call guard; strengthen only IO durability.
    reader_trials.save = atomic_json
    started = time.perf_counter()
    counts = Counter()
    with ThreadPoolExecutor(max_workers=WORKERS) as workers:
        pending = [workers.submit(generation_result, task, root, command,
                                  frozen['material']['expected_runtime'], transport) for task in tasks]
        for future in as_completed(pending):
            result = future.result()
            counts['completed'] += 1
            counts['usable'] += result['generation_success']
            print(canonical({'generation_completed': counts['completed'],
                             'generation_usable': counts['usable']}), flush=True)
    atomic_json(root / 'generation-complete.json', {'completed_at': now(), 'counts': dict(counts),
        'current_execution_wall_seconds': time.perf_counter() - started,
        'resumed_execution': bool(args.resume), 'manifest_sha256': file_digest(root / 'manifest.json')})


def cached_ranking(index, query, retriever, root):
    identity = object_digest({'index': index.digest, 'query': query, 'retriever': retriever})
    path = root / 'rankings' / retriever / (identity + '.json')
    if path.exists():
        row = read_json(path)
        assert row['identity'] == identity
        return row, True
    started = time.perf_counter()
    order = index.rank(query, retriever)
    elapsed = time.perf_counter() - started
    assert len(order) == len(set(order)) == len(index.ids) and set(order) == set(index.ids)
    row = {'identity': identity, 'ranking': order, 'elapsed_seconds': elapsed,
           'query_sha256': digest(query), 'retriever': retriever}
    atomic_json(path, row)
    return row, False


def fused_ranking(index, queries, retriever, root, task_id, policy):
    identity = object_digest({'index': index.digest, 'queries': queries,
                              'retriever': retriever, 'rrf_k': RRF_K})
    path = root / 'fusion' / (task_id + '-' + policy + '-' + retriever + '.json')
    if path.exists():
        row = read_json(path)
        assert row['identity'] == identity
        assert row['ranking'] == fused_order(index.ids, [row['ranking']])
        return row
    orders, timing, hits = [], [], 0
    for query in queries:
        row, cached = cached_ranking(index, query, retriever, root)
        orders.append(row['ranking'])
        timing.append(row['elapsed_seconds'])
        hits += cached
    started = time.perf_counter()
    order = fused_order(index.ids, orders)
    elapsed = time.perf_counter() - started
    result = {'identity': identity, 'ranking': order, 'cue_count': len(queries) - 1,
              'fusion_seconds': elapsed, 'channel_ranking_seconds': timing,
              'cache_hits_at_creation': hits, 'channel_query_sha256': [digest(q) for q in queries]}
    atomic_json(path, result)
    return result


def validate_packet_row(row, cell, identity, docs, gold, candidates, generation):
    """Recheck durable checkpoints at the same trust boundary as new packets."""
    assert row['identity'] == identity
    assert all(row[key] == value and type(row[key]) is type(value) for key, value in cell.items())
    packet = row['packet']
    text, observations = packet['packet'], packet['observations']
    assert isinstance(text, str) and isinstance(observations, list)
    assert type(packet['bytes']) is int and packet['bytes'] == len(text.encode('utf8')) <= cell['budget']
    score = support_metrics(gold, observations, docs)
    assert all(obs['whole'] is (obs['start'] == 0 and obs['end'] == len(docs[obs['id']]['body']))
               for obs in observations)
    assert text == '\n\n'.join(packing_lab._piece(docs[obs['id']], obs,
                                               cell['packer'] == 'whole_record') for obs in observations)
    selected = list(dict.fromkeys(obs['id'] for obs in observations))
    assert packet['ids'] == packet['selected_ids'] == selected
    receipt = packet['receipt']
    assert receipt['method'] == cell['packer'] and receipt['budget'] == cell['budget']
    assert receipt['packet_sha256'] == digest(text) and receipt['ranked_ids'] == candidates
    assert receipt['span_count'] == len(observations)
    for key, value in score.items():
        assert type(row[key]) is type(value) and row[key] == value, 'Stored support score changed'
    expected = {
        'selected_original_id_bundle_recovered': any(set(bundle) <= set(score['observed_original_ids'])
                                                    for bundle in gold['evidence_sets']),
        'candidate_original_id_bundle_recovered': any(set(bundle) <= set(candidates)
                                                     for bundle in gold['evidence_sets']),
        'generation_success': generation['generation_success'],
        'generation_fallback': generation['fallback_original_query'],
    }
    for key, value in expected.items():
        assert type(row[key]) is type(value) and row[key] == value, 'Stored secondary/generation score changed'
    return row


def evaluate(args):
    root, frozen, _ = verified(args)
    assert read_json(root / 'generation-complete.json')['manifest_sha256'] == file_digest(root / 'manifest.json')
    start_stage(root, 'evaluation', args.resume)
    assert not (root / 'evaluation-complete.json').exists(), 'Evaluation already complete'
    docs, tasks, gold = load_development(args.development_bank)
    started = time.perf_counter()
    index = PreparedIndex(docs)
    index.prepare_characters()
    index_seconds = time.perf_counter() - started
    atomic_json(root / 'index-preparation.json', {'seconds': index_seconds, 'index_digest': index.digest,
        'resumed_execution': bool(args.resume), 'manifest_sha256': file_digest(root / 'manifest.json')})
    started, count = time.perf_counter(), 0
    for task in tasks:
        generation = validate_generation_checkpoint(task,
            read_json(root / 'generations' / (task['id'] + '.json')), root, frozen['material']['expected_runtime'])
        for policy in POLICIES:
            queries = policy_queries(task['query'], policy, generation)
            for retriever in RETRIEVERS:
                ranking = fused_ranking(index, queries, retriever, root, task['id'], policy)
                candidates = ranking['ranking'][:TOP_K]
                candidate_bundle = any(set(bundle) <= set(candidates) for bundle in gold[task['id']]['evidence_sets'])
                for packer in PACKERS:
                    for budget in BUDGETS:
                        cell = {'task_id': task['id'], 'history': task['history'],
                            'template_group': task['template_group'], 'policy': policy,
                            'retriever': retriever, 'packer': packer, 'budget': budget}
                        identity = object_digest({'cell': cell, 'ranking': ranking['identity'],
                                                   'manifest': file_digest(root / 'manifest.json')})
                        path = root / 'packets' / (object_digest(cell) + '.json')
                        if path.exists():
                            validate_packet_row(read_json(path), cell, identity, docs, gold[task['id']],
                                                candidates, generation)
                        else:
                            clock = time.perf_counter()
                            packet = pack(docs, task['query'], candidates, budget, packer)
                            packing_seconds = time.perf_counter() - clock
                            assert packet['bytes'] == len(packet['packet'].encode('utf8')) <= budget
                            # support_metrics checks every unchanged source bound/text/hash.
                            score = support_metrics(gold[task['id']], packet['observations'], docs)
                            selected_bundle = any(set(bundle) <= set(score['observed_original_ids'])
                                                  for bundle in gold[task['id']]['evidence_sets'])
                            row = {'identity': identity, **cell, **score,
                                'selected_original_id_bundle_recovered': selected_bundle,
                                'candidate_original_id_bundle_recovered': candidate_bundle,
                                'generation_success': generation['generation_success'],
                                'generation_fallback': generation['fallback_original_query'],
                                'packing_seconds': packing_seconds, 'packet': packet}
                            validate_packet_row(row, cell, identity, docs, gold[task['id']], candidates, generation)
                            atomic_json(path, row)
                        count += 1
        print(canonical({'evaluated_tasks': count // 36, 'packets': count}), flush=True)
    assert count == 2592
    atomic_json(root / 'evaluation-complete.json', {'completed_at': now(), 'packets': count,
        'current_execution_wall_seconds': time.perf_counter() - started,
        'resumed_execution': bool(args.resume), 'manifest_sha256': file_digest(root / 'manifest.json')})


def numeric_summary(values, total):
    values = [x for x in values if isinstance(x, (float, int)) and not isinstance(x, bool)
              and math.isfinite(x) and x >= 0]
    return {'reported': len(values), 'missing': total - len(values),
            'sum': sum(values) if values else None,
            'median': statistics.median(values) if values else None,
            'minimum': min(values) if values else None, 'maximum': max(values) if values else None}


def usage_summary(calls):
    names = sorted({name for call in calls for name in (call.get('usage') or {})})
    return {name: {'counter_class': 'provider-reported numeric field; semantics and overlap unverified',
                   **numeric_summary([(call.get('usage') or {}).get(name) for call in calls], len(calls))}
            for name in names}


def call_timing_summary(calls):
    return {'transport_call_elapsed_seconds': numeric_summary(
                [call.get('elapsed_seconds') for call in calls], len(calls)),
            'control_receipt_elapsed_seconds': numeric_summary(
                [(call.get('control_receipt') or {}).get('elapsed_seconds') for call in calls], len(calls))}


def receipt_counts(generations):
    returned = sum(r.get('recorded_call_receipt_sha256') is not None for r in generations)
    unknown = sum(r['call'].get('failure') == 'interrupted_call_no_receipt' for r in generations)
    assert returned + unknown == len(generations)
    assert all(r.get('recorded_call_receipt_sha256') is None for r in generations
               if r['call'].get('failure') == 'interrupted_call_no_receipt')
    return {'returned_call_receipts': returned, 'unknown_pending_without_receipt': unknown,
            'generation_failures': sum(not r['generation_success'] for r in generations)}


def outcome_groups(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row['policy'], row['retriever'], row['packer'], row['budget'])].append(row)
    original = {(row['task_id'], row['retriever'], row['packer'], row['budget']): row for row in rows
                if row['policy'] == 'original_query'}
    output = []
    for key, cells in sorted(groups.items()):
        paired = Counter()
        for row in cells:
            baseline = original[(row['task_id'], row['retriever'], row['packer'], row['budget'])]
            delta = int(row['declared_span_bundle_recovered']) - int(baseline['declared_span_bundle_recovered'])
            paired['improved' if delta > 0 else 'regressed' if delta < 0 else 'tied'] += 1
        output.append({'policy': key[0], 'retriever': key[1], 'packer': key[2], 'budget': key[3],
            'packets': len(cells),
            'exact_span_bundle_recovered': sum(r['declared_span_bundle_recovered'] for r in cells),
            'mean_best_span_fraction': sum(r['best_declared_span_fraction'] for r in cells) / len(cells),
            'selected_original_id_bundle_recovered': sum(r['selected_original_id_bundle_recovered'] for r in cells),
            'whole_source_bundle_recovered': sum(r['declared_whole_bundle_recovered'] for r in cells),
            'candidate_top32_original_id_bundle_recovered': sum(r['candidate_original_id_bundle_recovered'] for r in cells),
            'paired_exact_span_vs_original': {k: paired[k] for k in ('improved', 'regressed', 'tied')}})
    return output


def aggregate(args):
    root, frozen, _ = verified(args)
    assert read_json(root / 'evaluation-complete.json')['packets'] == 2592
    generations = [read_json(p) for p in sorted((root / 'generations').glob('*.json'))]
    rows = [read_json(p) for p in sorted((root / 'packets').glob('*.json'))]
    assert len(generations) == 72 and len(rows) == 2592
    docs, tasks, gold = load_development(args.development_bank)
    tasks_by_id = {t['id']: t for t in tasks}
    generation_by_id = {r['task_id']: r for r in generations}
    assert set(generation_by_id) == set(tasks_by_id)
    for task in tasks:
        validate_generation_checkpoint(task, generation_by_id[task['id']], root,
                                        frozen['material']['expected_runtime'])
    cells = set()
    for row in rows:
        task = tasks_by_id[row['task_id']]
        assert row['policy'] in POLICIES and row['retriever'] in RETRIEVERS
        assert row['packer'] in PACKERS and row['budget'] in BUDGETS
        cell = {'task_id': task['id'], 'history': task['history'], 'template_group': task['template_group'],
                **{key: row[key] for key in ('policy', 'retriever', 'packer', 'budget')}}
        cell_key = object_digest(cell)
        assert cell_key not in cells, 'Duplicate aggregate cell'
        cells.add(cell_key)
        ranking = read_json(root / 'fusion' / (task['id'] + '-' + row['policy'] + '-' + row['retriever'] + '.json'))
        assert ranking['ranking'] == fused_order(list(docs), [ranking['ranking']])
        identity = object_digest({'cell': cell, 'ranking': ranking['identity'],
                                  'manifest': file_digest(root / 'manifest.json')})
        validate_packet_row(row, cell, identity, docs, gold[task['id']], ranking['ranking'][:TOP_K],
                            generation_by_id[task['id']])
    success_ids = {r['task_id'] for r in generations if r['generation_success']}
    calls = [r['call'] for r in generations]
    rankings = [read_json(p) for p in sorted((root / 'rankings').glob('*/*.json'))]
    fusions = [read_json(p) for p in sorted((root / 'fusion').glob('*.json'))]
    assert len(fusions) == 432
    safe_material = {k: v for k, v in frozen['material'].items() if k not in ('schedule', 'command_sha256')}
    result = {'schema_version': 1, 'scope': 'development-only query cue supplement',
        'status': 'complete', 'main_experiment_changed': False, 'confirmation_claim': False,
        'manifest_sha256': file_digest(root / 'manifest.json'), 'frozen_material': safe_material,
        'sample': {'histories': 24, 'tasks': 72, 'records': 276, 'packets': 2592},
        'generation': {'scheduled': 72, **receipt_counts(generations),
            'call_accepted': sum(bool(c.get('accepted')) for c in calls),
            'usable': len(success_ids), 'fallback': 72 - len(success_ids),
            'failures_by_kind': dict(Counter(r['failure'] for r in generations if not r['generation_success'])),
            'cue_count_distribution_usable': dict(sorted(Counter(len(r['cues']) for r in generations if r['generation_success']).items())),
            **call_timing_summary(calls),
            'host_generation_seconds': numeric_summary([r.get('host_generation_seconds') for r in generations], 72),
            'stage': read_json(root / 'generation-complete.json'), 'usage_fields': usage_summary(calls),
            'usage_missing_entirely': sum(not isinstance(c.get('usage'), dict) or not c['usage'] for c in calls),
            'usage_note': 'Only transport-retained numeric fields from accepted envelopes are available. Each name is separate; semantics/overlap are unverified. No cross-field total or price estimate.'},
        'retrieval_and_packing': {'index_preparation': read_json(root / 'index-preparation.json'),
            'newly_computed_cached_cue_rankings': len(rankings),
            'cue_ranking_seconds': numeric_summary([r['elapsed_seconds'] for r in rankings], len(rankings)),
            'policy_fusions': len(fusions),
            'fusion_seconds': numeric_summary([r['fusion_seconds'] for r in fusions], len(fusions)),
            'packing_seconds': numeric_summary([r['packing_seconds'] for r in rows], len(rows)),
            'stage': read_json(root / 'evaluation-complete.json'),
            'timing_note': 'Measured under concurrent work and fixed cache order; no causal hardware-speed claim.'},
        'all_scheduled_workflows': outcome_groups(rows),
        'conditional_usable_generation': {'tasks': len(success_ids),
            'groups': outcome_groups([r for r in rows if r['task_id'] in success_ids])},
        'sources': SOURCES,
        'limitations': ['Development only; no confirmation or answer-quality inference.',
            'Structural cue checks do not prove absence of implicit factual assumptions.',
            'One fixed generator/prompt; no full published query-expansion system is reproduced.',
            'Usage field semantics and overlap are not independently established.']}
    atomic_json(HERE / 'agent-query-results.json', result)
    print(canonical({'status': 'aggregated', 'usable': len(success_ids),
                     'public_result_sha256': file_digest(HERE / 'agent-query-results.json')}))


def self_check():
    assert validate_cues('{"queries":["  find conditions  "]}', 'original') == ['find conditions']
    for bad in ('{"queries":[]}', '{"queries":["original"]}',
                '{"queries":["a","A"]}', '{"queries":["a","b","c","d"]}',
                '{"queries":["N001-R001"]}', '{"queries":[],"answer":3}',
                '{"queries":[],"queries":[]}', '```json\n{"queries":["a"]}\n```'):
        try:
            validate_cues(bad, 'original')
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid generation accepted')
    assert validate_cues('{"queries":["'+('é' * 256)+'"]}', 'original')
    try:
        validate_cues('{"queries":["'+('é' * 257)+'"]}', 'original')
    except ValueError:
        pass
    else:
        raise AssertionError('UTF-8 cue bound failed')
    fallback = {'generation_success': False, 'cues': []}
    assert policy_queries('original', 'generated_cues', fallback) == ['original']
    ids = ['a', 'b', 'c']
    assert fused_order(ids, [['b', 'a', 'c']]) == ['b', 'a', 'c']
    assert fused_order(ids, [['b', 'a', 'c'], ['a', 'b', 'c']]) == ['a', 'b', 'c']
    assert usage_summary([{'usage': {'input_tokens': 4}}, {'usage': None}])['input_tokens']['missing'] == 1
    assert numeric_summary([None], 1)['sum'] is None
    clocks = call_timing_summary([{'elapsed_seconds': 4.0, 'control_receipt': {}},
                                 {'elapsed_seconds': 3.0, 'control_receipt': {'elapsed_seconds': 2.0}}])
    assert clocks['transport_call_elapsed_seconds']['sum'] == 7.0
    assert clocks['control_receipt_elapsed_seconds']['sum'] == 2.0
    assert clocks['control_receipt_elapsed_seconds']['missing'] == 1
    assert receipt_counts([
        {'recorded_call_receipt_sha256': 'a' * 64, 'generation_success': False,
         'call': {'accepted': False, 'failure': 'adapter_timeout'}},
        {'recorded_call_receipt_sha256': None, 'generation_success': False,
         'call': {'accepted': False, 'failure': 'interrupted_call_no_receipt'}}]) == {
            'returned_call_receipts': 1, 'unknown_pending_without_receipt': 1,
            'generation_failures': 2}
    transport = reader_trials.runtime()
    controls = {k: True for k in transport.REQUIRED_TRUE}
    controls.update(enabled_skill_count=0, native_filesystem_tools_advertised=False,
        native_session_tools_advertised=False, initial_upstream_user_inputs=1,
        reasoning_effort='high', native_tools_advertised=['muse.write_todos'],
        advertised_tool_audit='actual upstream request', caller_stdin_encoding='utf8',
        caller_stdout_encoding='utf8', measured_upstream_request_text_count=1,
        intended_prompt_utf8_sha256=digest('original'))
    envelope = {'model': 'muse-spark-1.3-contributor', 'text': '{}',
                'native_tools_used': [], 'control_receipt': controls}
    assert not transport.control_errors(envelope, digest('original'))
    assert 'upstream_prompt_digest_mismatch' in transport.control_errors(envelope, digest('changed'))
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        reader_trials.save = atomic_json
        class Fake:
            count = 0
            def invoke(self, command, prompt, timeout, expected):
                self.count += 1
                return '{"queries":["find condition"]}', {'accepted': True, 'usage': None,
                                                          'intended_prompt_sha256': digest(prompt)}
        fake = Fake()
        first = reader_trials.invoke_recorded(fake, [], 'p', root, 'call', {})
        second = reader_trials.invoke_recorded(fake, [], 'p', root, 'call', {})
        assert first[0] == second[0] and fake.count == 1
        atomic_json(root / 'unknown-pending.json', {'identity': digest('p{}')})
        assert reader_trials.invoke_recorded(fake, [], 'p', root, 'unknown', {})[1]['failure'] == 'interrupted_call_no_receipt'
        assert fake.count == 1
        task = {'id': 'T', 'query': 'original'}
        generation = generation_result(task, root, [], {}, fake)
        assert validate_generation_checkpoint(task, generation, root, {})
        assert fake.count == 2
        for mutation in ('cues', 'receipt_hash', 'fallback'):
            changed = copy.deepcopy(generation)
            if mutation == 'cues': changed['cues'] = ['N001-R001']
            elif mutation == 'receipt_hash': changed['recorded_call_receipt_sha256'] = '0' * 64
            else: changed['fallback_original_query'] = True
            try:
                validate_generation_checkpoint(task, changed, root, {})
            except AssertionError:
                pass
            else:
                raise AssertionError('Mutated generation accepted: ' + mutation)
        docs = {'D': {'id': 'D', 'body': 'é: governing rule and exception', 'kind': 'source',
                     'revision': 1, 'scope': 'all', 'links': [], 'supersedes': [], 'incorporates': []}}
        body = docs['D']['body']
        gold = {'evidence_sets': [['D']], 'evidence_spans': [[{'id': 'D', 'start': 0, 'end': 5}]]}
        observation = {'id': 'D', 'start': 0, 'end': 5, 'text': body[:5], 'source_hash': digest(body)}
        assert support_metrics(gold, [observation], docs)['declared_span_bundle_recovered']
        observation['text'] = 'changed'
        try:
            support_metrics(gold, [observation], docs)
        except AssertionError:
            pass
        else:
            raise AssertionError('Exact source-text guard failed')
        cell = {'task_id': 'T', 'history': 'H', 'template_group': 'fictional',
                'policy': 'original_query', 'retriever': 'body_bm25', 'packer': 'whole_record', 'budget': 2000}
        packet = pack(docs, 'governing rule', ['D'], 2000, 'whole_record')
        generation = {'generation_success': False, 'fallback_original_query': True}
        row = {'identity': 'fixture', **cell, **support_metrics(gold, packet['observations'], docs),
               'selected_original_id_bundle_recovered': True, 'candidate_original_id_bundle_recovered': True,
               'generation_success': False, 'generation_fallback': True, 'packet': packet}
        assert validate_packet_row(row, cell, 'fixture', docs, gold, ['D'], generation)
        for mutation in ('observation_text', 'source_hash', 'span_offset', 'packet_text', 'stored_score'):
            changed = copy.deepcopy(row)
            if mutation == 'observation_text': changed['packet']['observations'][0]['text'] = 'changed'
            elif mutation == 'source_hash': changed['packet']['observations'][0]['source_hash'] = '0' * 64
            elif mutation == 'span_offset': changed['packet']['observations'][0]['start'] = 1
            elif mutation == 'packet_text': changed['packet']['packet'] += 'changed'
            else: changed['declared_span_bundle_recovered'] = False
            try:
                validate_packet_row(changed, cell, 'fixture', docs, gold, ['D'], generation)
            except AssertionError:
                pass
            else:
                raise AssertionError('Mutated checkpoint accepted: ' + mutation)
    print('agent_query_lab self-check passed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--stage', choices=('prepare', 'generate', 'evaluate', 'aggregate'))
    parser.add_argument('--development-bank', type=Path)
    parser.add_argument('--command', type=Path)
    parser.add_argument('--work', type=Path)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    assert args.stage and args.development_bank and args.command and args.work
    {'prepare': prepare, 'generate': generate, 'evaluate': evaluate, 'aggregate': aggregate}[args.stage](args)


if __name__ == '__main__':
    main()
