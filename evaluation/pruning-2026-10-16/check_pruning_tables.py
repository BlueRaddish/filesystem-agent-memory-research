"""Read-only independent numeric replay of pruning tables and paired counts.

This checker imports no collection, ranking, reader, analyzer or audit module.
It verifies aggregates from saved source-only trials, gold, snapshots and costs.
The companion audit_pruning.py establishes those inputs' causal correctness.
"""
import argparse
from collections import defaultdict
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
import time


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def accumulate(target, key, values):
    cell = target.setdefault(key, {})
    for metric, value in values.items():
        cell[metric] = cell.get(metric, 0) + value


def derive(directory):
    worlds = {w['id']: w for w in load(directory / 'source-bank.json')}
    gold = load(directory / 'gold.json')
    active = {(s['world'], s['arm'], s['epoch']): set(s['active'])
              for s in rows(directory / 'snapshots.jsonl.gz')}
    groups = {name: {} for name in ('arm', 'epoch', 'scenario', 'task', 'density')}
    total = {}
    completeness = defaultdict(dict)
    trial_count = 0
    for trial, score in zip(rows(directory / 'trials.jsonl.gz'), rows(directory / 'scored.jsonl.gz'), strict=True):
        identity = (trial['world'], trial['arm'], trial['query'], trial['epoch'], trial['task'])
        check(identity == tuple(score[k] for k in ('world', 'arm', 'query', 'epoch', 'task')),
              'trial/score identity mismatch')
        world, arm, query, epoch, task = identity
        calls, answer, selected = trial['calls'], trial['answer'], set(trial['selected'])
        truth = gold[query]
        required = set(truth['required'])
        value_correct = answer['value'] == truth['value']
        complete = bool(value_correct and answer['proof'] and required <= selected)
        check(query not in completeness[arm], 'duplicate arm/query row')
        completeness[arm][query] = complete
        cold = [call for call in calls if call['store'] == 'cold']
        attempted = calls[2]['store'] == 'cold'
        remaining = 8192 - sum(call['returned_bytes'] for call in calls[:2])
        irrecoverable = required - active[world, arm, epoch] if arm.split('|')[1] == 'off' else set()
        values = {'n': 1, 'support_complete': int(complete), 'value_correct': int(value_correct),
                  'stale': int(answer['value'] is not None and not value_correct),
                  'unknown': int(answer['value'] is None),
                  'irrecoverable_any': int(bool(irrecoverable)),
                  'irrecoverable_records': len(irrecoverable),
                  'missing_any': int(not required <= selected),
                  'incomplete_proof': int(not answer['proof']),
                  'candidate_work': sum(call['candidates'] for call in calls),
                  'term_work': sum(call['term_work'] for call in calls),
                  'expansion_probes': sum(call['expansion_probes'] for call in calls),
                  'calls': len(calls), 'returned_bytes': sum(call['returned_bytes'] for call in calls),
                  'archive_calls': len(cold), 'cold_attempt_queries': int(attempted),
                  'cold_first_remaining_bytes': remaining if attempted else 0,
                  'cold_first_under512': int(attempted and remaining < 512),
                  'cold_first_zero': int(attempted and remaining == 0),
                  'cold_calls_no_records': sum(len(call['selected']) == 0 for call in cold),
                  'cold_returned_records': sum(len(call['selected']) for call in cold),
                  'cold_returned_bytes': sum(call['returned_bytes'] for call in cold),
                  'ledger_updates': len(trial['selected'])}
        for label, key in (('arm', arm), ('epoch', (arm, epoch)),
                           ('scenario', (arm, worlds[world]['family'])),
                           ('task', (arm, task)), ('density', (arm, worlds[world]['density']))):
            accumulate(groups[label], key, values)
        for metric, value in values.items():
            total[metric] = total.get(metric, 0) + value
        trial_count += 1
    check(trial_count == 64512 and len(completeness) == 63 and
          all(len(q) == 1024 for q in completeness.values()), 'table input census')
    maintenance, epoch_storage = {}, {}
    maintenance_count = 0
    for row in rows(directory / 'maintenance.jsonl.gz'):
        values = {'n': 1, 'active_bytes': row['active_bytes'], 'retained_bytes': row['retained_bytes'],
                  'operations': row['operations'], 'removed': row['removed'], 'arrivals': row['arrivals'],
                  'promoted': len(row['promoted']), 'cpu_seconds': row['cpu_seconds'],
                  'active_records': row['active_count']}
        accumulate(maintenance, row['arm'], values)
        accumulate(epoch_storage, (row['arm'], row['epoch']), values)
        maintenance_count += 1
    check(maintenance_count == 64512, 'maintenance input census')
    paired = []
    for arm, answers in completeness.items():
        _, archive, method = arm.split('|')
        baseline = 'all|' + archive + '|' + method
        reference = completeness[baseline]
        check(set(answers) == set(reference), 'paired query identity mismatch')
        gains = sum(answers[q] and not reference[q] for q in answers)
        losses = sum(reference[q] and not answers[q] for q in answers)
        same = sum(answers[q] == reference[q] for q in answers)
        paired.append({'arm': arm, 'baseline': baseline, 'gains': gains,
                       'losses': losses, 'same': same, 'net': gains - losses, 'n': len(answers)})
    def exported(data, fields):
        result = []
        for key, values in sorted(data.items()):
            key = (key,) if isinstance(key, str) else key
            result.append(dict(zip(fields, key), **values))
        return result
    return {'state': 'DESCRIPTIVE_NOT_POPULATION_INFERENCE', 'totals': total,
            'arm': exported(groups['arm'], ('arm',)),
            'epoch': exported(groups['epoch'], ('arm', 'epoch')),
            'scenario': exported(groups['scenario'], ('arm', 'scenario')),
            'task': exported(groups['task'], ('arm', 'task')),
            'density': exported(groups['density'], ('arm', 'density')),
            'maintenance': exported(maintenance, ('arm',)),
            'epoch_storage': exported(epoch_storage, ('arm', 'epoch')),
            'paired': paired,
            'input_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in directory.iterdir() if p.is_file()}}


def compare(actual, expected, position='tables'):
    if isinstance(expected, dict):
        check(isinstance(actual, dict) and set(actual) == set(expected), position + ' object keys')
        return sum(compare(actual[key], value, position + '.' + key) for key, value in expected.items())
    if isinstance(expected, list):
        check(isinstance(actual, list) and len(actual) == len(expected), position + ' row census')
        return sum(compare(a, b, f'{position}[{i}]') for i, (a, b) in enumerate(zip(actual, expected)))
    if type(expected) in (int, float):
        check(type(actual) in (int, float) and math.isfinite(actual) and
              math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-9), position + ' numeric value')
        if type(expected) is int:
            check(actual == expected, position + ' exact integral count')
        return 1
    check(type(actual) is type(expected) and actual == expected, position + ' literal value')
    return 0


def verify(directory, path):
    started = time.perf_counter()
    expected, actual = derive(directory), load(path)
    numeric_cells = compare(actual, expected)
    changes = []
    altered = copy.deepcopy(actual)
    altered['arm'][0]['support_complete'] += 1
    changes.append(('wrong aggregate count', altered))
    altered = copy.deepcopy(actual)
    altered['paired'][0]['gains'] += 1
    changes.append(('wrong paired gain', altered))
    altered = copy.deepcopy(actual)
    altered['epoch'].pop()
    changes.append(('missing epoch cell', altered))
    altered = copy.deepcopy(actual)
    altered['input_sha256']['trials.jsonl.gz'] = '0' * 64
    changes.append(('wrong source fingerprint', altered))
    altered = copy.deepcopy(actual)
    altered['maintenance'][0]['cpu_seconds'] = float('inf')
    changes.append(('nonfinite numeric aggregate', altered))
    rejected = []
    for label, mutated in changes:
        try:
            compare(mutated, expected)
        except AssertionError:
            rejected.append(label)
        else:
            raise AssertionError('mutation survived: ' + label)
    return {'state': 'INDEPENDENT_NUMERIC_TABLE_REPLAY_PASSED',
            'numeric_fields_verified': numeric_cells,
            'cells': {k: len(actual[k]) for k in ('arm', 'epoch', 'scenario', 'task', 'density',
                                                'maintenance', 'epoch_storage', 'paired')},
            'mutation_controls_rejected': rejected,
            'tables_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'checker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'wall_seconds': time.perf_counter() - started,
            'scope': 'Independent aggregate and paired-count derivation; no tested modules imported. '
                     'Requires companion trajectory audit for source/causal correctness. '
                     'CPU observations are summed, not independently timed.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--tables', type=Path, required=True)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    if args.receipt:
        check(not args.receipt.exists(), 'receipt already exists')
    receipt = verify(args.run, args.tables)
    if args.receipt:
        with args.receipt.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
