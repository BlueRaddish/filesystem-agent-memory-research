"""Seal and run the bounded exploratory packing census; no external services.

From repository root:
  python evaluation/sprint-2026-10-15/packing/run_experiment.py --self-check
  python evaluation/sprint-2026-10-15/packing/run_experiment.py --seal
  python evaluation/sprint-2026-10-15/packing/run_experiment.py --run
New run directories are exclusive: use --output for an independent reproduction.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import time

import mechanisms as mechanism
import study_common as common

HERE = Path(__file__).resolve().parent
STUDY = mechanism.STUDY
BUDGETS = (4096, 8192, 16384)
RANKERS = ('body_bm25', 'entity_rrf')


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def save(path, value):
    with Path(path).open('x', encoding='utf8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n')


def make_seal():
    fixture = mechanism.self_check()
    manifest = json.loads((STUDY/'grid-manifest.json').read_text(encoding='utf8'))
    ranking_shards = {row['file']: row['sha256'] for row in manifest['shards'] if '-rankings-' in row['file']}
    source = {name: sha(HERE/name) for name in ('mechanisms.py', 'run_experiment.py', 'PLAN.md')}
    inputs = {name: sha(STUDY/name) for name in ('challenge-bank.json', 'packing_lab.py', 'study_common.py', 'grid-manifest.json')}
    assert inputs['challenge-bank.json'] == manifest['bank_sha256']
    save(HERE/'seal.json', {'state': 'SEALED_BEFORE_NEW_PACKETS_AND_GOLD_EVALUATION',
         'created_utc': utc(), 'exploratory_existing_bank': True, 'sources': source,
         'frozen_inputs': inputs, 'ranking_shards': ranking_shards,
         'expected': {'queries': 216, 'histories': 72, 'template_groups': 12,
                      'rankers': list(RANKERS), 'budgets': list(BUDGETS),
                      'methods': list(mechanism.METHODS), 'packets': 6480},
         'fixture_check': fixture})
    print(canon({'state': 'SEALED', 'seal_sha256': sha(HERE/'seal.json')}), flush=True)


def check_seal():
    seal = json.loads((HERE/'seal.json').read_text(encoding='utf8'))
    for name, expected in seal['sources'].items():
        assert sha(HERE/name) == expected, 'Sealed source changed: '+name
    for name, expected in seal['frozen_inputs'].items():
        assert sha(STUDY/name) == expected, 'Frozen input changed: '+name
    return seal


def load_rankings(seal):
    rows = {}
    for name, expected in seal['ranking_shards'].items():
        path = STUDY/name
        assert sha(path) == expected, 'Ranking shard mismatch'
        for row in json.loads(path.read_text(encoding='utf8'))['rows']:
            if row['split'] == 'confirmation' and str(row['size']) == '144' and row['ranker'] in RANKERS:
                key = (row['family_id'], row['task_id'], row['ranker'])
                assert key not in rows and row.get('state', 'complete') == 'complete'
                # Gold candidate-recovery fields never leave this extraction boundary.
                rows[key] = {'ids': row['top64'][:32], 'full_ranking_sha256': row['full_ranking_sha256'],
                             'collection_sha256': row['collection_sha256'], 'shard': name}
    assert len(rows) == 432
    return rows


def evaluate(raw_rows, families, docs):
    tasks = {(f['id'], t['id']): t for f in families for t in f['tasks']}
    result = []
    for row in raw_rows:
        observations = [mechanism.frozen._observation(docs[i], a, b) for i, a, b in row['observations']]
        task = tasks[(row['family_id'], row['task_id'])]
        metrics = common.support_metrics(task, observations, docs)
        original_ids = set(metrics['observed_original_ids'])
        result.append({**{k: row[k] for k in ('family_id', 'task_id', 'template_family', 'ranker', 'method', 'budget', 'bytes', 'source_bytes', 'wrapper_separator_bytes')},
                       'span_complete': metrics['declared_span_bundle_recovered'],
                       'whole_complete': metrics['declared_whole_bundle_recovered'],
                       'original_id_complete': any(set(ids) <= original_ids for ids in task['evidence_sets']),
                       'best_span_fraction': metrics['best_declared_span_fraction']})
    return result


def aggregate(scored):
    groups = defaultdict(list)
    lookup = {}
    for row in scored:
        groups[(row['ranker'], row['method'], row['budget'])].append(row)
        lookup[(row['ranker'], row['method'], row['budget'], row['family_id'], row['task_id'])] = row
    rows = []
    by_template = []
    for (ranker, method, budget), group in sorted(groups.items()):
        assert len(group) == 216
        base = [lookup[(ranker, 'two_windows', budget, r['family_id'], r['task_id'])] for r in group]
        rows.append({'ranker': ranker, 'method': method, 'budget': budget, 'n': len(group),
            'span_complete': sum(r['span_complete'] for r in group),
            'whole_complete': sum(r['whole_complete'] for r in group),
            'original_id_complete': sum(r['original_id_complete'] for r in group),
            'gains_vs_two_windows': sum(r['span_complete'] and not b['span_complete'] for r, b in zip(group, base)),
            'losses_vs_two_windows': sum(b['span_complete'] and not r['span_complete'] for r, b in zip(group, base)),
            'mean_bytes': statistics.mean(r['bytes'] for r in group),
            'mean_source_bytes': statistics.mean(r['source_bytes'] for r in group),
            'mean_wrapper_separator_bytes': statistics.mean(r['wrapper_separator_bytes'] for r in group),
            'mean_unused_bytes': statistics.mean(budget-r['bytes'] for r in group)})
        for template in sorted({r['template_family'] for r in group}):
            subset = [r for r in group if r['template_family'] == template]
            by_template.append({'ranker': ranker, 'method': method, 'budget': budget,
                                'template_family': template, 'n': len(subset),
                                'span_complete': sum(r['span_complete'] for r in subset)})
    return {'cells': rows, 'template_cells': by_template}


def run(output):
    seal = check_seal()
    start = utc()
    started = time.perf_counter()
    output.mkdir(parents=True, exist_ok=False)
    rankings = load_rankings(seal)
    bank = common.bank()
    families = [f for f in bank['families'] if f['split'] == 'confirmation']
    assert len(families) == 72 and len({f['template_family'] for f in families}) == 12
    docs = common.documents(bank['families'])
    save(output/'ranking-inputs.json', [{'family_id': k[0], 'task_id': k[1], 'ranker': k[2], **v} for k, v in sorted(rankings.items())])
    raw = []
    # Gold evaluation starts only after this entire packet file has been closed.
    with (output/'packets.json').open('x', encoding='utf8', newline='\n') as stream:
        stream.write('[\n')
        for family_n, family in enumerate(families, 1):
            collection = common.collection(docs, family['id'], 144)
            for task in family['tasks']:
                query = task['query']
                for ranker in RANKERS:
                    ranked = rankings[(family['id'], task['id'], ranker)]['ids']
                    for budget in BUDGETS:
                        for method in mechanism.METHODS:
                            packet = mechanism.pack(collection, query, ranked, budget, method)
                            source_bytes = sum(len(o['text'].encode('utf8')) for o in packet['observations'])
                            row = {'family_id': family['id'], 'task_id': task['id'],
                                   'template_family': family['template_family'], 'ranker': ranker,
                                   'method': method, 'budget': budget, 'bytes': packet['bytes'],
                                   'source_bytes': source_bytes, 'wrapper_separator_bytes': packet['bytes']-source_bytes,
                                   'packet_sha256': hashlib.sha256(packet['packet'].encode('utf8')).hexdigest(),
                                   'observations': [[o['id'], o['start'], o['end']] for o in packet['observations']]}
                            stream.write((',' if raw else '')+canon(row)+'\n')
                            raw.append(row)
            if family_n % 12 == 0:
                print(canon({'phase': 'packing', 'histories': family_n, 'packets': len(raw)}), flush=True)
        stream.write(']\n')
    assert len(raw) == 6480
    packet_closed = utc()
    packet_sha = sha(output/'packets.json')
    scored = evaluate(raw, families, docs)
    with (output/'scored.json').open('x', encoding='utf8', newline='\n') as stream:
        stream.write(canon(scored)+'\n')
    summary = aggregate(scored)
    summary.update({'state': 'COMPLETED_EXPLORATORY_CENSUS', 'started_utc': start,
        'packets_closed_before_evaluation_utc': packet_closed, 'completed_utc': utc(),
        'elapsed_seconds': time.perf_counter()-started, 'seal_sha256': sha(HERE/'seal.json'),
        'packets_sha256': packet_sha, 'scored_sha256': sha(output/'scored.json'),
        'ranking_inputs_sha256': sha(output/'ranking-inputs.json'),
        'counts': {'histories': 72, 'queries': 216, 'template_groups': 12, 'packets': len(raw), 'failures': 0},
        'endpoint': 'Containment of any complete authored sufficient-span alternative; not answer accuracy.',
        'dependence': 'Repeated packets over the same 216 queries, 72 histories and 12 related templates.'})
    save(output/'results.json', summary)
    print(canon({'state': summary['state'], 'packets': len(raw), 'elapsed_seconds': summary['elapsed_seconds']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--self-check', action='store_true')
    mode.add_argument('--seal', action='store_true')
    mode.add_argument('--run', action='store_true')
    parser.add_argument('--output', type=Path, default=HERE/'run')
    args = parser.parse_args()
    if args.self_check:
        print(canon(mechanism.self_check()))
    elif args.seal:
        make_seal()
    else:
        run(args.output.resolve())
