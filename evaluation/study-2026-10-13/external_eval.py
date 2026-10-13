"""Separate, frozen BEAM publisher-ID retrieval adaptation; no QA or official score.

Corpora, gold, packets, vectors, and row receipts remain private. Public output
contains only provenance, counts, descriptive metrics, and execution receipts.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
from statistics import median
import time

from external_probe import keys, support_ids
from index_lab import PreparedIndex, sha
import packing_lab

HERE = Path(__file__).resolve().parent
RANKERS = ('body_bm25', 'entity_rrf', 'dense_windows', 'dense_window_rrf')
PACKERS = ('whole_record', 'sentence_neighbors')
BUDGETS = (4096, 8192, 16384)
TOP = (8, 16, 32, 64)
PINS = ('EXTERNAL-PLAN.md', 'external-transfer-sources.json', 'external_eval.py',
        'external_probe.py', 'index_lab.py', 'packing_lab.py', 'dense_runtime.py', 'dense-model-spec.json')
METRICS = ('whole_bundle', 'whole_fraction', 'whole_group_fraction', 'selected_bundle',
           'selected_fraction', 'partial_selected_count', 'required_partial_selected_count',
           'bytes_used', 'whole_feasible', 'required_bundle_bytes') + tuple(
           f'candidate_{metric}_{k}' for k in TOP for metric in ('all', 'any', 'fraction'))


def now():
    return datetime.now(timezone.utc).isoformat()


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                               allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    temp.replace(path)


def private_path(path):
    path = path.resolve()
    if path.is_relative_to(HERE.parents[1]):
        raise ValueError('Private corpus/cache/output must be outside the public repository')
    return path


def document_id(value):
    assert type(value) is int and value >= 0, 'Expected nonnegative integer source id'
    return 'M' + str(value).zfill(6)


def project(chat):
    docs = {}
    for batch in chat:
        for group in batch['turns']:
            for turn in group:
                i = document_id(turn['id'])
                assert i not in docs and turn['role'] in ('user', 'assistant')
                assert isinstance(turn['content'], str) and turn['content'].strip()
                anchor = turn.get('time_anchor', batch['time_anchor'])
                assert anchor is None or isinstance(anchor, str)
                docs[i] = {'id': i, 'body': 'time_anchor: ' + json.dumps(anchor, ensure_ascii=False) + '\n' + turn['role'] + ': ' + turn['content'],
                           'kind': 'source', 'revision': 1, 'authored_at': '', 'title': '', 'scope': 'all',
                           'aliases': [], 'links': [], 'supersedes': [], 'incorporates': []}
    allowed = {'id', 'body', 'kind', 'revision', 'authored_at', 'title', 'scope',
               'aliases', 'links', 'supersedes', 'incorporates'}
    assert keys(list(docs.values())) <= allowed
    return docs


def criteria(raw):
    groups = raw if isinstance(raw, dict) else {'listed_ids': raw}
    assert isinstance(groups, dict) and all(isinstance(k, str) for k in groups)
    return {name: {document_id(int(i)) for i in support_ids(value)} for name, value in groups.items()}


def verify_sources(root):
    manifest = json.loads((HERE / 'external-transfer-sources.json').read_bytes())
    source = next(s for s in manifest['sources'] if s['key'] == 'beam')
    sample = source['execution_sample']
    ordered = sorted(sample['candidate_paths'], key=lambda p: (hashlib.sha256((sample['selection_seed']+p).encode()).hexdigest(), p))
    assert len(ordered) == 20 and ordered[:5] == sample['selected_paths']
    for f in manifest['downloaded_files']:
        if not f['local_relative'].startswith('beam-selected/'):
            continue
        data = (root / f['local_relative']).read_bytes()
        blob = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        assert not f['prefix_only'] and len(data) == f['bytes']
        assert hashlib.sha256(data).hexdigest() == f['sha256'] and blob == f['git_blob_sha1']
    return sample


def load_histories(root):
    sample = verify_sources(root)
    output = []
    for n, path in enumerate(sample['selected_paths'], 1):
        folder = root / 'beam-selected' / Path(path).parent
        docs = project(json.loads((folder / 'chat.json').read_bytes()))
        raw = json.loads((folder / 'probing_questions/probing_questions.json').read_bytes())
        queries, absent = [], 0
        for category in sorted(raw):
            for ordinal, row in enumerate(raw[category], 1):
                query = row['question']
                assert isinstance(query, str) and query.strip()
                groups = criteria(row.get('source_chat_ids', []))
                required = set().union(*groups.values())
                assert required <= set(docs)
                if not required:
                    assert category == 'abstention'
                    absent += 1
                    continue
                assert all(groups.values()), 'Empty criterion inside a labeled query'
                queries.append({'qid': f'H{n}:{category}:{ordinal}', 'category': category,
                                'query': query, 'query_sha256': sha(query), 'groups': groups, 'required': required})
        assert len(queries) == 18 and absent == 2
        output.append({'history': f'H{n}', 'upstream_path': path, 'docs': docs, 'queries': queries,
                       'unlabeled_abstentions': absent, 'source_projection_sha256': sha(docs),
                       'query_projection_sha256': sha([q['query'] for q in queries])})
    return output


def merge(intervals):
    result = []
    for start, end in sorted(intervals):
        if result and start <= result[-1][1]:
            result[-1][1] = max(end, result[-1][1])
        else:
            result.append([start, end])
    return result


def whole_cost(doc, verbose=True):
    observation = packing_lab._observation(doc, 0, len(doc['body']))
    return len(packing_lab._piece(doc, observation, verbose=verbose).encode('utf-8'))


def measure(query, docs, order, packet, budget):
    text, observations = packet['packet'], packet['observations']
    verbose = packet['receipt']['method'] == 'whole_record'
    assert text == '\n\n'.join(packing_lab._piece(docs[o['id']], o, verbose) for o in observations)
    actual_bytes = len(text.encode('utf-8'))
    assert actual_bytes == packet['bytes'] and actual_bytes <= budget
    intervals = defaultdict(list)
    for obs in observations:
        body = docs[obs['id']]['body']
        assert type(obs['start']) is int and type(obs['end']) is int
        assert 0 <= obs['start'] < obs['end'] <= len(body)
        assert obs['text'] == body[obs['start']:obs['end']]
        assert obs['source_hash'] == hashlib.sha256(body.encode('utf-8')).hexdigest()
        intervals[obs['id']].append((obs['start'], obs['end']))
    whole = {i for i, values in intervals.items() if merge(values) == [[0, len(docs[i]['body'])]]}
    selected = set(intervals)
    required, groups = query['required'], query['groups']
    assert required and all(groups.values())
    cost = sum(whole_cost(docs[i], verbose) for i in required) + 2 * (len(required)-1)
    result = {'whole_bundle': required <= whole, 'whole_fraction': len(required & whole)/len(required),
              'whole_group_fraction': sum(g <= whole for g in groups.values())/len(groups),
              'selected_bundle': required <= selected, 'selected_fraction': len(required & selected)/len(required),
              'partial_selected_count': len(selected-whole), 'required_partial_selected_count': len((selected-whole)&required),
              'whole_ids_count': len(whole), 'selected_ids_count': len(selected), 'required_ids_count': len(required),
              'bytes_used': actual_bytes, 'required_bundle_bytes': cost, 'whole_feasible': cost <= budget,
              'ranking_sha256': sha(order), 'packet_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()}
    for k in TOP:
        candidates = set(order[:k])
        result.update({f'candidate_all_{k}': required <= candidates,
                       f'candidate_any_{k}': bool(required & candidates),
                       f'candidate_fraction_{k}': len(required & candidates)/len(required)})
    if result['whole_bundle']:
        assert result['whole_feasible'] and result['candidate_all_32']
    return result


def public_audit(histories):
    return [{'history': h['history'], 'upstream_path': h['upstream_path'], 'messages': len(h['docs']),
             'positive_support_queries': len(h['queries']), 'unlabeled_abstentions': h['unlabeled_abstentions'],
             'source_projection_sha256': h['source_projection_sha256'], 'query_projection_sha256': h['query_projection_sha256'],
             'categories': dict(Counter(q['category'] for q in h['queries'])),
             'criterion_groups': sum(len(q['groups']) for q in h['queries']),
             'body_utf8_bytes': sum(len(d['body'].encode('utf-8')) for d in h['docs'].values())}
            for h in histories]


def pinned_hashes():
    return {name: file_digest(HERE/name) for name in PINS}


def freeze(root):
    path = root / 'external-freeze.json'
    assert not path.exists(), 'A freeze already exists; amendments must be explicit'
    histories = load_histories(root)
    receipt = {'schema_version': 1, 'frozen_at_utc': now(), 'implementation_sha256': pinned_hashes(),
               'rankers': list(RANKERS), 'packers': list(PACKERS), 'budgets': list(BUDGETS),
               'candidate_seed_count': 32, 'histories': public_audit(histories), 'scheduled_queries': 90,
               'scheduled_packets': 2160, 'scoring_started': False}
    receipt['freeze_sha256'] = sha(receipt)
    save(path, receipt)
    save(HERE/'external-results.json', {'state': 'prospectively_frozen_no_scored_results', 'freeze': receipt})
    return receipt


def verify_freeze(root):
    receipt = json.loads((root/'external-freeze.json').read_bytes())
    assert receipt['implementation_sha256'] == pinned_hashes(), 'Frozen implementation/protocol changed'
    unsigned = {k: v for k, v in receipt.items() if k != 'freeze_sha256'}
    assert sha(unsigned) == receipt['freeze_sha256']
    assert receipt['rankers'] == list(RANKERS) and receipt['packers'] == list(PACKERS) and receipt['budgets'] == list(BUDGETS)
    return receipt


def stage(root, mode, cache=None):
    frozen = verify_freeze(root)
    histories = load_histories(root)
    assert public_audit(histories) == frozen['histories']
    destination = root / f'external-{mode}-rows.json'
    assert not destination.exists(), 'Completed stage cannot be silently rerun'
    methods = RANKERS[:2] if mode == 'lexical' else RANKERS[2:]
    started, rows, receipts = now(), [], []
    encoder = None
    if mode == 'dense':
        assert cache is not None, 'Existing private dense cache is required'
        from dense_runtime import Encoder, DensePreparedIndex
        encoder = Encoder(private_path(cache), threads=2, batch_size=12)
    for history in histories:
        docs = history['docs']
        if mode == 'lexical':
            index = PreparedIndex(docs)
            build = {'collection_sha256': index.digest, 'encoder_loaded': False}
        else:
            index = DensePreparedIndex(docs, encoder, text_mode='body', windows=True)
            build = {k: v for k, v in index.build_receipt.items() if k != 'mapping'}
            build['model_load'] = encoder.manifest
        query_receipts = []
        for query in history['queries']:
            # The index and packer receive only a string query and observable docs.
            for method in methods:
                if mode == 'lexical':
                    order, ranking = index.rank_with_receipt(query['query'], method)
                else:
                    order, ranking = index.rank_with_receipt(query['query'], 'dense' if method == 'dense_windows' else 'dense_rrf')
                assert len(order) == len(docs) and set(order) == set(docs)
                query_receipts.append({'qid': query['qid'], 'ranker': method, 'ranking_sha256': sha(order),
                                       'query_encode_usage': ranking.get('query_encode_usage'),
                                       'query_and_search_seconds': ranking.get('query_and_search_seconds')})
                for packer in PACKERS:
                    for budget in BUDGETS:
                        clock = time.perf_counter()
                        packet = packing_lab.pack(docs, query['query'], order[:32], budget, packer)
                        metric = measure(query, docs, order, packet, budget)
                        rows.append({'history': history['history'], 'qid': query['qid'], 'category': query['category'],
                                     'ranker': method, 'packer': packer, 'budget': budget,
                                     'packing_seconds': time.perf_counter()-clock, **metric})
        receipts.append({'history': history['history'], 'build': build, 'queries': query_receipts})
        del index
        gc.collect()
    assert len(rows) == 1080 and len({(r['qid'], r['ranker'], r['packer'], r['budget']) for r in rows}) == 1080
    result = {'schema_version': 1, 'stage': mode, 'started_at_utc': started, 'completed_at_utc': now(),
              'freeze_sha256': frozen['freeze_sha256'], 'rows': rows, 'receipts': receipts}
    save(destination, result)
    return {'stage': mode, 'rows': len(rows), 'completed_at_utc': result['completed_at_utc'],
            'private_receipt_sha256': file_digest(destination)}


def averages(rows):
    return {metric: sum(float(r[metric]) for r in rows)/len(rows) for metric in METRICS}


def summarize(root):
    frozen = verify_freeze(root)
    paths = [root/f'external-{m}-rows.json' for m in ('lexical', 'dense')]
    if not all(path.exists() for path in paths):
        return {'state': 'partial_stages_retained_privately', 'complete_stages': [m for m, p in zip(('lexical', 'dense'), paths) if p.exists()]}
    stages = [json.loads(p.read_bytes()) for p in paths]
    assert all(s['freeze_sha256'] == frozen['freeze_sha256'] for s in stages)
    rows = [r for s in stages for r in s['rows']]
    assert len(rows) == 2160 and len({(r['qid'], r['ranker'], r['packer'], r['budget']) for r in rows}) == 2160
    cells, by_history, by_category, paired = [], [], [], []
    for ranker in RANKERS:
        for packer in PACKERS:
            for budget in BUDGETS:
                selected = [r for r in rows if (r['ranker'], r['packer'], r['budget']) == (ranker, packer, budget)]
                per_history = []
                for h in frozen['histories']:
                    group = [r for r in selected if r['history'] == h['history']]
                    assert len(group) == 18
                    mean = averages(group)
                    per_history.append(mean)
                    by_history.append({'history': h['history'], 'ranker': ranker, 'packer': packer, 'budget': budget, 'queries': 18, **mean})
                feasible = [r for r in selected if r['whole_feasible']]
                cells.append({'ranker': ranker, 'packer': packer, 'budget': budget, 'queries': 90,
                              'whole_bundle_count': sum(r['whole_bundle'] for r in selected),
                              'whole_feasible_count': len(feasible),
                              'required_bundle_byte_min': min(r['required_bundle_bytes'] for r in selected),
                              'required_bundle_byte_median': median(r['required_bundle_bytes'] for r in selected),
                              'required_bundle_byte_max': max(r['required_bundle_bytes'] for r in selected),
                              'feasibility_cost_kind': 'exact_whole_wrapper_cost' if packer == 'whole_record' else 'optimistic_single_whole_body_lean_wrapper_lower_bound',
                              'feasible_only_whole_bundle_rate': sum(r['whole_bundle'] for r in feasible)/len(feasible) if feasible else None,
                              **{metric: sum(h[metric] for h in per_history)/5 for metric in METRICS}})
                for category in sorted({r['category'] for r in selected}):
                    group = [r for r in selected if r['category'] == category]
                    assert len(group) == 10
                    by_category.append({'category': category, 'ranker': ranker, 'packer': packer, 'budget': budget,
                                        'queries': len(group), **averages(group)})
                baseline = {r['qid']: r for r in rows if r['ranker'] == 'body_bm25' and r['packer'] == packer and r['budget'] == budget}
                changes = [int(r['whole_bundle'])-int(baseline[r['qid']]['whole_bundle']) for r in selected]
                paired.append({'ranker': ranker, 'packer': packer, 'budget': budget, 'paired_queries': 90,
                               'whole_bundle_rate_delta': sum(changes)/90,
                               'gains': changes.count(1), 'ties': changes.count(0), 'regressions': changes.count(-1)})
    # Full per-query rows and all packet/rank digests remain in private receipts.
    output = {'schema_version': 1, 'state': 'completed_separate_publisher_ID_retrieval_adaptation', 'freeze': frozen,
              'completed_at_utc': now(), 'scheduled_queries': 90, 'scheduled_packets': 2160,
              'executed_packets': len(rows), 'history_clusters': 5, 'aggregation': 'equal history means; no confidence intervals',
              'publisher_support_semantics_validated': False, 'source_span_labels_available': False,
              'official_scores_QA_judges_or_tool_calls_executed': False,
              'cells': cells, 'history_cells': by_history, 'category_cells': by_category, 'paired_vs_matched_body_bm25': paired,
              'execution_receipts': [{'stage': s['stage'], 'started_at_utc': s['started_at_utc'], 'completed_at_utc': s['completed_at_utc'],
                                      'rows': len(s['rows']), 'sha256': file_digest(p),
                                      'builds': [{'history': h['history'], 'build': h['build']} for h in s['receipts']],
                                      'query_encode_texts': sum((q['query_encode_usage'] or {}).get('texts', 0) for h in s['receipts'] for q in h['queries']),
                                      'query_truncated_texts': sum((q['query_encode_usage'] or {}).get('truncated_texts', 0) for h in s['receipts'] for q in h['queries'])}
                                     for s, p in zip(stages, paths)],
              'limitations': ['Five externally authored synthetic histories; no human/representative-corpus inference.',
                              'Original support IDs are publisher-declared proxy labels, not proven semantic/minimal support.',
                              'Partial selected IDs do not establish sufficient evidence exposure.',
                              'No official BEAM QA/nugget/order metric, reader or action evaluation.',
                              'Operational timing under shared CPU activity is not a controlled latency benchmark.']}
    save(HERE/'external-results.json', output)
    return {'state': output['state'], 'packets': len(rows), 'whole_bundle_counts':
            [{'ranker': c['ranker'], 'packer': c['packer'], 'budget': c['budget'], 'count': c['whole_bundle_count']} for c in cells]}


def self_check():
    chat = [{'time_anchor': 'day 1', 'turns': [[{'id': 1, 'role': 'user', 'content': 'α rule. Condition is retained.',
                                               'question_type': 'gold construction marker'},
                                              {'id': 2, 'role': 'assistant', 'content': 'Other rule.'}]]}]
    docs = project(chat)
    assert 'question_type' not in keys(docs) and 'gold construction marker' not in json.dumps(docs)
    groups = criteria({'first_statement': [1], 'second_statement': [2, 2]})
    assert groups == {'first_statement': {'M000001'}, 'second_statement': {'M000002'}}
    query = {'required': {'M000001', 'M000002'}, 'groups': groups}
    order = list(docs)
    for method in RANKERS[:2]:
        assert set(PreparedIndex(docs).rank('rule condition', method)) == set(docs)
    for packer in PACKERS:
        packet = packing_lab.pack(docs, 'rule condition', order, 4096, packer)
        result = measure(query, docs, order, packet, 4096)
        assert result['whole_bundle'] and result['whole_feasible']
    oracle = packing_lab.pack(docs, 'rule', order, 4096, 'whole_record')
    assert sum(whole_cost(d) for d in docs.values()) + 2 == oracle['bytes']
    for budget in (0, oracle['bytes']-1):
        assert not measure(query, docs, order, packing_lab.pack(docs, 'rule', order, budget, 'whole_record'), budget)['whole_bundle']
    d = docs['M000001']; cut = len(d['body'])//2
    observations = [packing_lab._observation(d, 0, cut), packing_lab._observation(d, cut, len(d['body']))]
    # Adjacent partial reads cover a whole message; one partial read does not.
    packet_text = '\n\n'.join(packing_lab._piece(d, o) for o in observations)
    packet = {'packet': packet_text, 'bytes': len(packet_text.encode('utf-8')), 'observations': observations,
              'receipt': {'method': 'sentence_neighbors'}}
    singleton = {'required': {'M000001'}, 'groups': {'listed_ids': {'M000001'}}}
    assert measure(singleton, docs, order, packet, 4096)['whole_bundle']
    packet['observations'] = observations[:1]
    packet['packet'] = packing_lab._piece(d, observations[0])
    packet['bytes'] = len(packet['packet'].encode('utf-8'))
    partial = measure(singleton, docs, order, packet, 4096)
    assert partial['selected_bundle'] and not partial['whole_bundle'] and partial['required_partial_selected_count'] == 1
    return {'self_check': 'passed', 'encoder_loaded': False, 'fixture_only': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--private-root', type=Path)
    parser.add_argument('--cache-root', type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--audit', action='store_true')
    group.add_argument('--freeze', action='store_true')
    group.add_argument('--stage', choices=('lexical', 'dense'))
    group.add_argument('--summarize', action='store_true')
    args = parser.parse_args()
    if args.self_check:
        print(json.dumps(self_check()))
    else:
        assert args.private_root is not None, 'A private download root is required'
        root = private_path(args.private_root)
        if args.audit:
            result = {'histories': public_audit(load_histories(root)), 'scoring_performed': False}
        elif args.freeze:
            self_check()
            result = freeze(root)
        elif args.stage:
            result = stage(root, args.stage, args.cache_root)
        elif args.summarize:
            result = summarize(root)
        else:
            raise ValueError('Select self-check, audit, freeze, stage, or summarize')
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
