"""Postcollection descriptive tables; never changes frozen raw outcomes."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path


def lines(path):
    with gzip.open(path, 'rt', encoding='utf-8') as file:
        for line in file:
            yield json.loads(line)


def summarize(run, output):
    source_bank = json.loads((run / 'source-bank.json').read_text(encoding='utf-8'))
    worlds = {w['id']: w for w in source_bank}
    tables = {name: defaultdict(lambda: defaultdict(float)) for name in
              ('arm', 'epoch', 'scenario', 'task', 'density')}
    rows = {}
    totals = defaultdict(float)
    for score, trial in zip(lines(run / 'scored.jsonl.gz'), lines(run / 'trials.jsonl.gz'), strict=True):
        assert (score['world'], score['arm'], score['query']) == (trial['world'], trial['arm'], trial['query'])
        world = worlds[score['world']]
        arm = score['arm']
        rows[arm, score['query']] = score
        cold_attempt = trial['calls'][2]['store'] == 'cold'
        cold_remaining = 8192 - sum(c['returned_bytes'] for c in trial['calls'][:2])
        cold_calls = [c for c in trial['calls'] if c['store'] == 'cold']
        metrics = {'n': 1, 'support_complete': score['support_complete'],
                   'value_correct': score['value_correct'], 'stale': score['stale'],
                   'unknown': score['unknown'], 'irrecoverable_any': bool(score['irrecoverable_required']),
                   'irrecoverable_records': len(score['irrecoverable_required']),
                   'missing_any': bool(score['missing_required']),
                   'incomplete_proof': not trial['answer']['proof'],
                   'candidate_work': score['candidate_work'], 'term_work': score['term_work'],
                   'expansion_probes': score['expansion_probes'], 'calls': score['calls'],
                   'returned_bytes': score['bytes'],
                   'archive_calls': sum(c['store'] == 'cold' for c in trial['calls']),
                   'cold_attempt_queries': cold_attempt,
                   'cold_first_remaining_bytes': cold_remaining if cold_attempt else 0,
                   'cold_first_under512': cold_attempt and cold_remaining < 512,
                   'cold_first_zero': cold_attempt and cold_remaining == 0,
                   'cold_calls_no_records': sum(not c['selected'] for c in cold_calls),
                   'cold_returned_records': sum(len(c['selected']) for c in cold_calls),
                   'cold_returned_bytes': sum(c['returned_bytes'] for c in cold_calls),
                   'ledger_updates': len(trial['selected'])}
        for name, key in (('arm', arm), ('epoch', (arm, score['epoch'])),
                          ('scenario', (arm, world['family'])), ('task', (arm, score['task'])),
                          ('density', (arm, world['density']))):
            for metric, value in metrics.items():
                tables[name][key][metric] += value
        for metric, value in metrics.items():
            totals[metric] += value
    maintenance = defaultdict(lambda: defaultdict(float))
    epoch_storage = defaultdict(lambda: defaultdict(float))
    for row in lines(run / 'maintenance.jsonl.gz'):
        arm = row['arm']
        values = {'n': 1, 'active_bytes': row['active_bytes'], 'retained_bytes': row['retained_bytes'],
                  'operations': row['operations'], 'removed': row['removed'], 'arrivals': row['arrivals'],
                  'promoted': len(row['promoted']), 'cpu_seconds': row['cpu_seconds'],
                  'active_records': row['active_count']}
        for key in (arm,):
            for metric, value in values.items():
                maintenance[key][metric] += value
        for metric, value in values.items():
            epoch_storage[arm, row['epoch']][metric] += value
    paired = []
    for arm, stats in tables['arm'].items():
        policy, archive, method = arm.split('|')
        baseline = '|'.join(('all', archive, method))
        gains, losses, same = 0, 0, 0
        for q in (q for a, q in rows if a == arm):
            a = rows[arm, q]['support_complete']
            b = rows[baseline, q]['support_complete']
            gains += a and not b
            losses += b and not a
            same += a == b
        paired.append({'arm': arm, 'baseline': baseline, 'gains': gains, 'losses': losses,
                       'same': same, 'net': gains - losses, 'n': gains + losses + same})
    def exported(data, fields):
        result = []
        for key, stats in sorted(data.items()):
            key = (key,) if isinstance(key, str) else key
            result.append(dict(zip(fields, key), **dict(stats)))
        return result
    result = {'state': 'DESCRIPTIVE_NOT_POPULATION_INFERENCE', 'totals': dict(totals),
              'arm': exported(tables['arm'], ('arm',)),
              'epoch': exported(tables['epoch'], ('arm', 'epoch')),
              'scenario': exported(tables['scenario'], ('arm', 'scenario')),
              'task': exported(tables['task'], ('arm', 'task')),
              'density': exported(tables['density'], ('arm', 'density')),
              'maintenance': exported(maintenance, ('arm',)),
              'epoch_storage': exported(epoch_storage, ('arm', 'epoch')), 'paired': paired,
              'input_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in run.iterdir() if p.is_file()}}
    assert totals['n'] == 64512
    assert len(result['arm']) == 63 and len(result['paired']) == 63
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return {'rows': int(totals['n']), 'cells': {k: len(result[k]) for k in tables},
            'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    assert not args.output.exists(), 'output exists; use a new path'
    print(json.dumps(summarize(args.run, args.output), indent=2))
