"""New fictional longitudinal streams, sealed collection and separate scoring."""
import argparse
from contextlib import contextmanager
import gzip
import hashlib
import inspect
import io
import itertools
import json
import math
from pathlib import Path
import time

from pruning_core import (ARCHIVES, BUDGET, METHODS, POLICIES, RetentionSource,
                          Search, canonical, digest, metadata, read_sources,
                          rendered, retain)

HERE = Path(__file__).resolve().parent
FAMILIES = ('periodic_corrections', 'standing_constraint', 'dormant_reactivation',
            'historical_rollback', 'cross_project', 'lexical_clutter',
            'topic_shift', 'expiring_exception')
EPOCHS = 32
CHECKPOINTS = tuple(range(4, 33, 4))


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n', encoding='utf-8')


@contextmanager
def compressed_writer(path):
    with path.open('xb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding='utf-8', newline='\n') as text:
                yield text


def make_world(family, seed, density):
    world = f'{family}-s{seed}-{density}'
    prefix = f'{family[:4]}{seed}'
    records = []
    def add(epoch, key, value, project='orchard', effective=None, expires=None,
            refs=(), narrative='', long=False):
        ident = f'{prefix}-{key}-{epoch:02d}-{sum(s["key"] == key for s in records):02d}'
        claim = {'id': ident, 'created': epoch, 'effective': epoch if effective is None else effective,
                 'expires': expires, 'project': project, 'key': key,
                 'value': value, 'refs': list(refs)}
        text = 'ASSERT ' + canonical(claim) + '\n' + narrative
        # Padding supplies genuine varied-length originals, without answer labels.
        target = 1350 if long else 420
        text += (' Field observations and implementation notes remain attached to this original.' *
                 math.ceil(max(0, target - len(text.encode())) / 80))
        source = dict(claim, text=text)
        source['bytes'] = len(text.encode())
        source['sha256'] = hashlib.sha256(text.encode()).hexdigest()
        records.append(source)
        return ident

    license_id = add(1, 'license', f'permit_{seed}', project='commons',
                     narrative='Shared permit validates dependent delivery bundles.')
    add(1, 'guard', f'no_export_{seed}', narrative='Standing orchard guard constraint. Keep original standing guard rule.')
    add(1, 'guard_new', f'internal_only_{seed}', narrative='Current active topic guard rule.')
    add(1, 'setting', f'initial_{seed}', narrative='Orchard setting current operating configuration.')
    base_bundle = add(1, 'bundle', f'base_bundle_{seed}', refs=(license_id,),
                      narrative='Orchard bundle delivery setting requires shared permit.')
    add(1, 'topic_new', f'new_topic_{seed}', narrative='Orchard topic_new current setting after topic migration.')
    dormant = add(1, 'dormant', f'old_design_{seed}',
                  narrative='Dormant design prerequisite retained for eventual project reactivation.')
    for epoch in range(1, EPOCHS + 1):
        if family in ('periodic_corrections', 'historical_rollback', 'lexical_clutter') and epoch % 4 == 0:
            add(epoch, 'setting', f'revision_{epoch}_{seed}',
                narrative='Orchard setting current operating configuration. Revised operating setting.', long=epoch % 8 == 0)
        if family == 'periodic_corrections' and epoch == 20:
            add(epoch, 'setting', f'corrected_four_{seed}', effective=4,
                narrative='Imported later: correction effective epoch four for historical configuration.')
        if family == 'standing_constraint' and epoch in (8, 16, 24, 32):
            add(epoch, 'setting', f'workstream_{epoch}_{seed}', narrative='Current orchard setting workstream configuration.')
        if family == 'dormant_reactivation' and epoch == 25:
            add(epoch, 'bundle', f'reactivated_{seed}', refs=(dormant,),
                narrative='Reactivated orchard bundle requires dormant original design prerequisite.')
        if family == 'cross_project' and epoch in (8, 16, 24, 32):
            add(epoch, 'bundle', f'linked_bundle_{epoch}_{seed}', refs=(license_id,),
                narrative='Orchard bundle depends on a commons license original.', long=epoch % 16 == 0)
        if family == 'topic_shift' and epoch in (8, 12, 16, 20, 24, 28, 32):
            add(epoch, 'topic_new', f'migrated_{epoch}_{seed}',
                narrative='Orchard topic_new current setting after topic migration.')
        if family == 'expiring_exception' and epoch == 12:
            add(epoch, 'bundle', f'temporary_{seed}', expires=25,
                refs=(license_id,), narrative='Temporary orchard bundle exception expires at epoch twenty five.')
        for n in range(3 if density == 'low' else 8):
            # Noise IDs/keys for first three arrivals match density pairs exactly.
            key = f'noise_{epoch:02d}_{n}'
            near = family == 'lexical_clutter'
            narrative = ('Orchard setting current operating configuration setting current setting. '
                         'This is a separate component discussion, not a governing setting assertion.' if near
                         else 'Orchard daily scratch meeting planning and unrelated component observations.')
            add(epoch, key, f'note_{seed}_{epoch}_{n}', project='orchard' if n % 3 else 'commons',
                narrative=narrative, long=(epoch + n + seed) % 5 == 0)
    records.sort(key=lambda s: (s['created'], s['id']))
    queries = []
    for epoch in CHECKPOINTS:
        current_key = 'topic_new' if family == 'topic_shift' and epoch >= 16 else 'setting'
        standing_key = 'guard_new' if family == 'topic_shift' and 4 < epoch < 32 else 'guard'
        for task, key, asof, cue in (
            ('current', current_key, epoch, f'Orchard {current_key} current operating configuration'),
            ('standing', standing_key, epoch, f'Orchard {standing_key} standing constraint rule'),
            ('historical', 'setting', 4, 'Orchard setting operating configuration epoch four history'),
            ('dependency', 'bundle', epoch, 'Orchard bundle delivery shared permit dependency')):
            queries.append({'id': f'{world}-e{epoch:02d}-{task}', 'world': world,
                            'epoch': epoch, 'task': task, 'project': 'orchard',
                            'key': key, 'asof': asof, 'cue': cue})
    return {'id': world, 'family': family, 'partition': 'prospective_shared_backbone',
            'seed': seed, 'density': density, 'sources': records, 'queries': queries}


def gold_replay(query, sources):
    """Full-source evaluator, deliberately separate from source-only reader."""
    arrived = {s['id']: s for s in sources if s['created'] <= query['epoch']}
    candidates = []
    for s in arrived.values():
        if s['project'] != query['project'] or s['key'] != query['key']:
            continue
        if s['effective'] > query['asof']:
            continue
        if s['expires'] is not None and s['expires'] <= query['asof']:
            continue
        candidates.append(s)
    winner = sorted(candidates, key=lambda s: (s['effective'], s['created'], s['id']))[-1]
    required, pending = set(), [winner['id']]
    while pending:
        ident = pending.pop()
        if ident not in required:
            required.add(ident)
            pending.extend(arrived[ident]['refs'])
    return {'value': winner['value'], 'governing': winner['id'], 'required': sorted(required)}


def self_check():
    checks = []
    def check(name, predicate):
        assert predicate, name
        checks.append(name)
    w = make_world('cross_project', 0, 'high')
    sources, query = w['sources'], w['queries'][-1]
    byid = {s['id']: s for s in sources}
    metas = [metadata(s) for s in sources]
    check('future-query boundary: retention API has no query/gold/future argument',
          list(inspect.signature(retain).parameters) == ['policy', 'epoch', 'previous', 'arrivals', 'ledger', 'seed'])
    check('metadata excludes values/text/query/gold', set(RetentionSource.__dataclass_fields__) ==
          {'id', 'created', 'effective', 'expires', 'project', 'key', 'refs'})
    a = RetentionSource('a', 1, 1, None, 'p', 'k', ())
    b = RetentionSource('b', 2, 2, None, 'p', 'k', ('a',))
    check('TTL inclusive boundary', retain('ttl8', 9, [a], [], {}, 0)[0] == {'a'} and not retain('ttl8', 10, [a], [], {}, 0)[0])
    many = [RetentionSource(f'n{i:03d}', i, i, None, 'p', f'k{i}', ()) for i in range(100)]
    ledger = {'n000': (50, 200), 'n001': (100, 0)}
    check('LRU actual read wins', 'n000' in retain('lru96', 100, many, [], ledger, 0)[0])
    check('LFU actual count wins', 'n001' in retain('lfu96', 100, many, [], ledger, 0)[0])
    check('latest loses superseded; dependencies pin old', retain('latest', 2, [a, b], [], {}, 0)[0] == {'b'} and
          retain('latest_dependencies', 2, [a, b], [], {}, 0)[0] == {'a', 'b'})
    check('evictions do not rehydrate without admission', retain('lru96', 101, [], [], {'n000': (100, 100)}, 0)[0] == set())
    check('buffered cold hit admission uses original age', 'n000' in retain('lru96', 101, [many[0]] + many[4:], [], ledger, 0)[0])
    check('source UTF8 hashes', all(hashlib.sha256(s['text'].encode()).hexdigest() == s['sha256'] and
                                  len(s['text'].encode()) == s['bytes'] for s in sources))
    search = Search(sources)
    allids = set(byid)
    gold = gold_replay(query, sources)
    selected, calls, size, answer = search.retrieve(query, set(), allids, 'scheduled_cold', 'global')
    check('cold archive recovery', answer['value'] == gold['value'] and answer['proof'] and calls[2]['store'] == 'cold')
    check('rendered budget', size == sum(len(rendered(s)) for s in selected) and size <= BUDGET)
    selected, calls, size, answer = search.retrieve(query, allids, allids, 'off', 'global')
    flat = sum((c['selected'] for c in calls), [])
    check('unseen paging', len(flat) == len(set(flat)) and len(calls) == 4 and bool(calls[1]['selected']))
    renamed = Search([dict(s, path='renamed/folders/' + s['id']) for s in sources])
    check('layout-only rename invariance', search.rank(query, allids, 'global', set())[0] == renamed.rank(query, allids, 'global', set())[0])
    early_query = w['queries'][3]
    early_ids = {s['id'] for s in sources if s['created'] <= 4}
    perturbed = [dict(s, text='future changed ' * 900, key='future_only') if s['created'] > 4 else s for s in sources]
    future_search = Search(perturbed)
    check('future source perturbation cannot alter past ranking or packet',
          search.rank(early_query, early_ids, 'global', set()) == future_search.rank(early_query, early_ids, 'global', set()) and
          [s['id'] for s in search.retrieve(early_query, early_ids, early_ids, 'off', 'global')[0]] ==
          [s['id'] for s in future_search.retrieve(early_query, early_ids, early_ids, 'off', 'global')[0]])
    expired = make_world('expiring_exception', 0, 'low')
    eq = expired['queries'][-1]
    check('expired exception restores older base', gold_replay(eq, expired['sources'])['value'] == 'base_bundle_0' and
          read_sources(eq, expired['sources'])['value'] == 'base_bundle_0')
    corrected = make_world('periodic_corrections', 0, 'low')
    hq = corrected['queries'][-2]
    check('imported earlier-effective correction', gold_replay(hq, corrected['sources'])['value'] == 'corrected_four_0')
    old = [s for s in sources if s['key'] == 'bundle' and s['created'] == 1]
    check('wrong stale answer control', read_sources(query, old)['value'] != gold['value'])
    check('unresolved qualifier control', not read_sources(query, old)['proof'])
    low = make_world('cross_project', 0, 'low')
    check('density-pair governing sources equal', [(s['id'], s['text']) for s in low['sources'] if not s['key'].startswith('noise_')] ==
          [(s['id'], s['text']) for s in sources if not s['key'].startswith('noise_')])
    return {'passed': len(checks), 'checks': checks}


def verify_seal():
    seal = json.loads((HERE / 'seal.json').read_text())
    for name, expected in seal['sha256'].items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == expected, name
    return seal


def run(out):
    seal = verify_seal()
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / 'self-check.json', self_check())
    worlds = [make_world(f, s, d) for f, s, d in itertools.product(FAMILIES, range(2), ('low', 'high'))]
    write_json(out / 'source-bank.json', worlds)
    gold = {q['id']: gold_replay(q, w['sources']) for w in worlds for q in w['queries']}
    write_json(out / 'gold.json', gold)
    started = time.perf_counter()
    cpu_start = time.process_time()
    rows, snapshots, maintenance = 0, 0, []
    snapshot_active = {}
    with compressed_writer(out / 'trials.jsonl.gz') as trial_file, \
         compressed_writer(out / 'snapshots.jsonl.gz') as snapshot_file:
        for world in worlds:
            sources = {s['id']: s for s in world['sources']}
            search = Search(world['sources'])
            for policy, archive, method in itertools.product(POLICIES, ARCHIVES, METHODS):
                arm = f'{policy}|{archive}|{method}'
                active, arrived, ledger, sequence, pending = set(), set(), {}, 0, set()
                for epoch in range(1, EPOCHS + 1):
                    new = [s for s in world['sources'] if s['created'] == epoch]
                    arrived.update(s['id'] for s in new)
                    before_cpu = time.process_time()
                    promotions = pending - active if policy in ('lru96', 'lfu96', 'random96') else set()
                    pending = set()
                    active, cost = retain(policy, epoch, [metadata(sources[i]) for i in active | promotions],
                                          [metadata(s) for s in new], ledger, world['seed'])
                    cost.update(world=world['id'], arm=arm, epoch=epoch,
                                cpu_seconds=time.process_time() - before_cpu,
                                promoted=sorted(promotions),
                                active_count=len(active), active_bytes=sum(sources[i]['bytes'] for i in active),
                                retained_bytes=sum(sources[i]['bytes'] for i in (arrived if archive != 'off' else active)))
                    maintenance.append(cost)
                    if epoch not in CHECKPOINTS:
                        continue
                    snapshot = {'world': world['id'], 'arm': arm, 'epoch': epoch,
                                'active': sorted(active), 'active_hash': digest(sorted(active)),
                                'ledger_hash': digest(ledger)}
                    snapshot_active[world['id'], arm, epoch] = active.copy()
                    snapshot_file.write(canonical(snapshot) + '\n')
                    snapshots += 1
                    for query in (q for q in world['queries'] if q['epoch'] == epoch):
                        prior_hash = digest(ledger)
                        selected, calls, used, answer = search.retrieve(query, active, arrived, archive, method)
                        sequence += 1
                        for source in selected:
                            count, last = ledger.get(source['id'], (0, -1))
                            ledger[source['id']] = (count + 1, sequence)
                        for call in calls:
                            if call['store'] == 'cold':
                                pending.update(call['selected'])
                        row = {'world': world['id'], 'arm': arm, 'query': query['id'],
                               'epoch': epoch, 'task': query['task'], 'active_hash': snapshot['active_hash'],
                               'prior_ledger_hash': prior_hash, 'next_ledger_hash': digest(ledger),
                               'selected': [s['id'] for s in selected], 'calls': calls,
                               'bytes': used, 'answer': answer}
                        trial_file.write(canonical(row) + '\n')
                        rows += 1
            print(canonical({'world_done': world['id'], 'trials': rows}), flush=True)
    with compressed_writer(out / 'maintenance.jsonl.gz') as file:
        for row in maintenance:
            file.write(canonical(row) + '\n')
    execution = {'state': 'COLLECTED_NOT_INDEPENDENTLY_AUDITED', 'trials': rows,
                 'snapshots': snapshots, 'worlds': len(worlds), 'queries': len(gold),
                 'wall_seconds': time.perf_counter() - started,
                 'cpu_seconds': time.process_time() - cpu_start,
                 'seal_hash': digest(seal)}
    write_json(out / 'execution.json', execution)
    # File boundary: scores are written only after complete source-only trial file is closed.
    with gzip.open(out / 'trials.jsonl.gz', 'rt', encoding='utf-8') as inp, \
         compressed_writer(out / 'scored.jsonl.gz') as score_file:
        for line in inp:
            row = json.loads(line)
            g = gold[row['query']]
            selected = set(row['selected'])
            required = set(g['required'])
            active = snapshot_active[row['world'], row['arm'], row['epoch']]
            irrecoverable = sorted(required - active) if row['arm'].split('|')[1] == 'off' else []
            score = {'world': row['world'], 'arm': row['arm'], 'query': row['query'],
                     'epoch': row['epoch'], 'task': row['task'],
                     'value_correct': row['answer']['value'] == g['value'],
                     'support_complete': row['answer']['value'] == g['value'] and row['answer']['proof'] and required <= selected,
                     'stale': row['answer']['value'] is not None and row['answer']['value'] != g['value'],
                     'unknown': row['answer']['value'] is None,
                     'missing_required': sorted(required - selected),
                     'irrecoverable_required': irrecoverable,
                     'candidate_work': sum(c['candidates'] for c in row['calls']),
                     'term_work': sum(c['term_work'] for c in row['calls']),
                     'expansion_probes': sum(c['expansion_probes'] for c in row['calls']),
                     'calls': len(row['calls']), 'bytes': row['bytes']}
            score_file.write(canonical(score) + '\n')
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}
    sizes = {}
    for path in out.iterdir():
        if path.is_file():
            uncompressed = 0
            if path.suffix == '.gz':
                with gzip.open(path, 'rb') as file:
                    for chunk in iter(lambda: file.read(1048576), b''):
                        uncompressed += len(chunk)
            else:
                uncompressed = path.stat().st_size
            sizes[path.name] = {'stored_bytes': path.stat().st_size, 'uncompressed_bytes': uncompressed}
    write_json(out / 'manifest.json', {'sha256': hashes, 'sizes': sizes})
    print(canonical(execution), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--seal', action='store_true')
    parser.add_argument('--run', type=Path)
    args = parser.parse_args()
    if args.self_check:
        print(json.dumps(self_check(), indent=2))
    elif args.seal:
        assert not (HERE / 'seal.json').exists(), 'seal already exists'
        result = self_check()
        names = ('PLAN.md', 'pruning_core.py', 'pruning_lab.py')
        write_json(HERE / 'seal.json', {'state': 'SEALED_BEFORE_COLLECTION', 'self_check': result,
                   'sha256': {n: hashlib.sha256((HERE / n).read_bytes()).hexdigest() for n in names}})
    elif args.run:
        run(args.run)
    else:
        parser.error('choose --self-check, --seal or --run NEW_OUTPUT_DIRECTORY')


if __name__ == '__main__':
    main()
