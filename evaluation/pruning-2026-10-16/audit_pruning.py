"""Independent read-only audit of the pruning study; imports no lab/core code.

Run from any directory with --run OUTPUT_DIRECTORY. A receipt is written only
when --receipt NEW_PATH is supplied. Source/trajectory/output checks are replayed
from public bytes; this is not an independent natural-history replication.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import time


POLICIES = ('all', 'ttl8', 'lru96', 'lfu96', 'latest', 'latest_dependencies', 'random96')
ARCHIVES = ('off', 'unresolved_only', 'scheduled_cold')
METHODS = ('global', 'project', 'linked')
FAMILIES = ('periodic_corrections', 'standing_constraint', 'dormant_reactivation',
            'historical_rollback', 'cross_project', 'lexical_clutter',
            'topic_shift', 'expiring_exception')
ARMS = tuple('|'.join(a) for a in itertools.product(POLICIES, ARCHIVES, METHODS))
EPOCHS = tuple(range(1, 33))
CHECKPOINTS = tuple(range(4, 33, 4))
TASKS = ('current', 'standing', 'historical', 'dependency')
CLAIM_KEYS = ('id', 'created', 'effective', 'expires', 'project', 'key', 'value', 'refs')
ACCEPTED_SEAL = 'b5bddbda9073ad9ef8961c5c6ab3e5d964a3c5e5c7b61a5cc0002320cf70458b'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def digest(obj):
    return hashlib.sha256(canonical(obj).encode('utf-8')).hexdigest()


def unique_object(items):
    result = {}
    for key, value in items:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def decode(text):
    def reject_constant(value):
        raise AssertionError('nonfinite JSON value: ' + value)
    obj = json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
    def walk(value):
        if isinstance(value, float):
            require(math.isfinite(value), 'nonfinite decoded JSON number')
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
    walk(obj)
    return obj


def load(path):
    return decode(path.read_text(encoding='utf-8'))


def lines(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            require(line.strip(), f'blank JSONL row: {path.name}:{number}')
            yield decode(line)


def exact_integer(value, message, minimum=0):
    require(type(value) is int and value >= minimum, message)


def framed(source):
    return ('<SOURCE ' + source['id'] + '>\n' + source['text'] + '\n</SOURCE>\n').encode('utf-8')


def read_packet(query, selected):
    """Derive a decision from first-line assertions, independently of metadata."""
    claims = {}
    for source in selected:
        header, _, _ = source['text'].partition('\n')
        require(header.startswith('ASSERT '), 'missing ASSERT in selected source')
        assertion = decode(header[len('ASSERT '):])
        require(assertion['id'] not in claims, 'duplicate selected source')
        claims[assertion['id']] = assertion
    possible = []
    for claim in claims.values():
        if claim['project'] != query['project'] or claim['key'] != query['key']:
            continue
        if claim['effective'] > query['asof']:
            continue
        if claim['expires'] is not None and query['asof'] >= claim['expires']:
            continue
        possible.append(claim)
    if not possible:
        return {'value': None, 'governing': None, 'missing': [], 'proof': False}
    governing = max(possible, key=lambda c: (c['effective'], c['created'], c['id']))
    missing, visited = set(), set()
    frontier = [governing['id']]
    while frontier:
        ident = frontier.pop()
        if ident in visited:
            continue
        visited.add(ident)
        if ident in claims:
            frontier.extend(claims[ident]['refs'])
        else:
            missing.add(ident)
    return {'value': governing['value'], 'governing': governing['id'],
            'missing': sorted(missing), 'proof': not missing}


def full_truth(query, sources):
    """Evaluate from arrived source bodies, without supplied gold fields."""
    arrived = [s for s in sources.values() if s['created'] <= query['epoch']]
    answer = read_packet(query, arrived)
    require(answer['governing'] is not None and answer['proof'], 'invalid full-history proof')
    byid = {s['id']: s for s in arrived}
    required, queue = set(), [answer['governing']]
    while queue:
        ident = queue.pop()
        if ident not in required:
            require(ident in byid, 'future or absent full-history dependency')
            required.add(ident)
            queue.extend(byid[ident]['refs'])
    return {'value': answer['value'], 'governing': answer['governing'],
            'required': sorted(required)}


def retained(policy, epoch, previous, arrivals, ledger, seed):
    """An independent policy replay; caller supplies any causal promotions."""
    pool = dict(previous)
    pool.update(arrivals)
    operations = len(pool)
    if policy == 'all':
        keep = set(pool)
    elif policy == 'ttl8':
        keep = {ident for ident, source in pool.items() if epoch - source['created'] <= 8}
    elif policy in ('latest', 'latest_dependencies'):
        newest = {}
        for ident, source in pool.items():
            group = (source['project'], source['key'])
            order = (source['effective'], source['created'], ident)
            if group not in newest or order > newest[group][0]:
                newest[group] = (order, ident)
        keep = {pair[1] for pair in newest.values()}
        if policy == 'latest_dependencies':
            pending = list(keep)
            while pending:
                for ident in pool[pending.pop()]['refs']:
                    operations += 1
                    if ident in pool and ident not in keep:
                        keep.add(ident)
                        pending.append(ident)
    else:
        require(policy in ('lru96', 'lfu96', 'random96'), 'unknown pruning policy')
        priorities = {}
        for ident, source in pool.items():
            count, last = ledger.get(ident, (0, -1))
            if policy == 'lru96':
                priorities[ident] = (last, source['created'], ident)
            elif policy == 'lfu96':
                priorities[ident] = (count, last, source['created'], ident)
            else:
                priorities[ident] = hashlib.sha256(f'{seed}:{epoch}:{ident}'.encode()).hexdigest()
        keep = set(sorted(pool, key=priorities.get, reverse=True)[:96])
        operations += len(pool)
    return keep, {'visited': len(pool), 'operations': operations,
                  'removed': len(pool) - len(keep), 'arrivals': len(arrivals)}


class Ranking:
    """Reimplements documented BM25 and source-only paging; no tested imports."""
    def __init__(self, sources):
        self.sources = sources
        self.counts = {i: Counter(re.findall(r'[a-z0-9_]+', s['text'].lower()))
                       for i, s in sources.items()}
        self.lengths = {i: sum(c.values()) for i, c in self.counts.items()}
        self.cache = {}

    def rank(self, query, pool, method, unresolved):
        key = (query['id'], tuple(sorted(pool)), method, tuple(sorted(unresolved)))
        if key in self.cache:
            return self.cache[key]
        candidates = sorted(i for i in pool if method == 'global' or
                            self.sources[i]['project'] == query['project'] or
                            (method == 'linked' and i in unresolved))
        terms = sorted(set(re.findall(r'[a-z0-9_]+', query['cue'].lower())))
        frequencies = {t: sum(t in self.counts[i] for i in candidates) for t in terms}
        mean_length = sum(self.lengths[i] for i in candidates) / max(1, len(candidates))
        scores = []
        for ident in candidates:
            components = []
            for term in terms:
                tf = self.counts[ident].get(term, 0)
                if tf:
                    idf = math.log(1 + (len(candidates) - frequencies[term] + .5) /
                                   (frequencies[term] + .5))
                    components.append(idf * tf * 2.2 /
                                      (tf + 1.2 * (.25 + .75 * self.lengths[ident] / mean_length)))
            score = sum(components) + (1000000.0 if ident in unresolved else 0.0)
            scores.append((ident, score))
        result = (sorted(scores, key=lambda pair: (-pair[1], pair[0])),
                  len(candidates), len(candidates) * len(terms))
        self.cache[key] = result
        return result

    def retrieval(self, query, active, arrived, archive, method):
        selected, seen, calls, total_bytes = [], set(), [], 0
        cold = set(arrived) - set(active)
        cold_mode = False
        for number in range(1, 5):
            before = read_packet(query, selected)
            if number == 3:
                cold_mode = bool(cold) and (archive == 'scheduled_cold' or
                    archive == 'unresolved_only' and (before['value'] is None or before['missing']))
            pool = cold if cold_mode else active
            ranked, candidates, term_work = self.rank(query, pool, method, set(before['missing']))
            queue = [(ident, score, 0) for ident, score in ranked if ident not in seen]
            added, rounded, probes = [], [], 0
            while queue and len(added) < 6:
                ident, score, depth = queue.pop(0)
                if ident in seen:
                    continue
                source = self.sources[ident]
                size = len(framed(source))
                if total_bytes + size > 8192:
                    continue
                selected.append(source)
                seen.add(ident)
                added.append(ident)
                rounded.append([ident, round(score, 8)])
                total_bytes += size
                if method == 'linked' and depth < 2:
                    for dependency in source['refs']:
                        if probes >= 8:
                            break
                        probes += 1
                        if dependency in pool and dependency not in seen:
                            queue.insert(0, (dependency, score, depth + 1))
            calls.append({'call': number, 'store': 'cold' if cold_mode else 'active',
                          'before': before, 'selected': added, 'scores': rounded,
                          'candidates': candidates, 'term_work': term_work,
                          'expansion_probes': probes,
                          'returned_bytes': sum(len(framed(self.sources[i])) for i in added)})
        return selected, calls, total_bytes, read_packet(query, selected)


def same(actual, expected, context):
    # Canonical comparison distinguishes JSON true from the integer 1.
    require(canonical(actual) == canonical(expected), context)


def validate_sources(worlds):
    expected_worlds = [f'{family}-s{seed}-{density}' for family, seed, density in
                       itertools.product(FAMILIES, range(2), ('low', 'high'))]
    same([w['id'] for w in worlds], expected_worlds, 'exact ordered 32-world census')
    total_sources = 0
    all_queries = {}
    for world, (family, seed, density) in zip(worlds, itertools.product(FAMILIES, range(2), ('low', 'high'))):
        same({k: world[k] for k in ('family', 'seed', 'density', 'partition')},
             {'family': family, 'seed': seed, 'density': density,
              'partition': 'prospective_shared_backbone'}, 'world metadata')
        sources = world['sources']
        require(len({s['id'] for s in sources}) == len(sources), 'duplicate source ID')
        same(sources, sorted(sources, key=lambda s: (s['created'], s['id'])), 'source temporal order')
        for source in sources:
            exact_integer(source['created'], 'created time type', 1)
            exact_integer(source['effective'], 'effective time type', 1)
            require(source['created'] <= 32, 'source beyond declared epoch range')
            if source['expires'] is not None:
                exact_integer(source['expires'], 'expiry time type', 1)
                require(source['expires'] > source['effective'], 'expiry precedes applicability')
            exact_integer(source['bytes'], 'source byte count type', 1)
            require(isinstance(source['text'], str) and source['text'].isascii(), 'source text shape')
            raw = source['text'].encode('utf-8')
            require(len(raw) == source['bytes'], 'original source bytes')
            require(hashlib.sha256(raw).hexdigest() == source['sha256'], 'original source SHA256')
            require(source['text'].startswith('ASSERT '), 'source assertion header')
            assertion = decode(source['text'].split('\n', 1)[0][7:])
            same(assertion, {key: source[key] for key in CLAIM_KEYS}, 'source text/metadata equality')
            require(isinstance(source['refs'], list) and
                    len(source['refs']) == len(set(source['refs'])), 'source reference shape')
        byid = {s['id']: s for s in sources}
        for source in sources:
            for dependency in source['refs']:
                require(dependency in byid, 'missing dependency in source bank')
                require(byid[dependency]['created'] <= source['created'], 'future dependency')
        same([(q['epoch'], q['task']) for q in world['queries']],
             list(itertools.product(CHECKPOINTS, TASKS)), 'exact 32-query world census')
        for query in world['queries']:
            require(query['world'] == world['id'], 'query/world mismatch')
            expected_id = f'{world["id"]}-e{query["epoch"]:02d}-{query["task"]}'
            require(query['id'] == expected_id and expected_id not in all_queries, 'query ID census')
            exact_integer(query['asof'], 'query asof type', 1)
            require(query['asof'] <= query['epoch'] and query['project'] == 'orchard', 'query time/scope')
            all_queries[expected_id] = query
        total_sources += len(sources)
    # Both density levels have exactly the same governing sources and queries.
    for low, high in zip(worlds[::2], worlds[1::2]):
        same([s for s in low['sources'] if not s['key'].startswith('noise_')],
             [s for s in high['sources'] if not s['key'].startswith('noise_')], 'density-pair governing bytes')
        low_queries = [{k: v for k, v in q.items() if k not in ('id', 'world')} for q in low['queries']]
        high_queries = [{k: v for k, v in q.items() if k not in ('id', 'world')} for q in high['queries']]
        same(low_queries, high_queries, 'density-pair query schedule')
        low_noise = [s for s in low['sources'] if s['key'].startswith('noise_')]
        high_noise = [s for s in high['sources'] if s['key'].startswith('noise_')]
        require(len(low_noise) == 96 and len(high_noise) == 256, 'density manipulation count')
        high_map = {s['id']: s for s in high_noise}
        require(all(s == high_map[s['id']] for s in low_noise), 'low noise not high subset')
    return total_sources, all_queries


def expected_score(row, truth, active):
    required, selected = set(truth['required']), set(row['selected'])
    return {'world': row['world'], 'arm': row['arm'], 'query': row['query'],
            'epoch': row['epoch'], 'task': row['task'],
            'value_correct': row['answer']['value'] == truth['value'],
            'support_complete': bool(row['answer']['value'] == truth['value'] and
                                     row['answer']['proof'] and required <= selected),
            'stale': row['answer']['value'] is not None and row['answer']['value'] != truth['value'],
            'unknown': row['answer']['value'] is None,
            'missing_required': sorted(required - selected),
            'irrecoverable_required': sorted(required - active) if row['arm'].split('|')[1] == 'off' else [],
            'candidate_work': sum(c['candidates'] for c in row['calls']),
            'term_work': sum(c['term_work'] for c in row['calls']),
            'expansion_probes': sum(c['expansion_probes'] for c in row['calls']),
            'calls': len(row['calls']), 'bytes': row['bytes']}


def validate_trial(row, expected):
    exact_integer(row['bytes'], 'trial byte type')
    require(row['bytes'] <= 8192, 'trial exceeds byte cap')
    require(row['arm'] in ARMS, 'trial arm outside Cartesian census')
    require(type(row['answer']['proof']) is bool, 'proof must be boolean')
    require(len(row['selected']) == len(set(row['selected'])), 'duplicate selected ID')
    for call in row['calls']:
        for key in ('call', 'candidates', 'term_work', 'expansion_probes', 'returned_bytes'):
            exact_integer(call[key], 'call integer type: ' + key)
        require(len(call['selected']) <= 6 and call['expansion_probes'] <= 8, 'call limits')
    same(row, expected, 'trial disagrees with independent causal selection/reader replay: ' +
         '/'.join(str(row.get(k)) for k in ('world', 'arm', 'query')))


def mutation_checks(normal, expected, sources):
    """Exercise the exact validator used for every recorded trial."""
    import copy
    controls = []
    validate_trial(normal, expected)
    cases = []
    changed = copy.deepcopy(normal)
    changed['answer']['value'] = 'invented unsupported answer'
    cases.append(('invented reader value', changed))
    changed = copy.deepcopy(normal)
    changed['bytes'] = 0
    cases.append(('unbilled source bytes', changed))
    changed = copy.deepcopy(normal)
    future = next(s['id'] for s in sources.values() if s['created'] > normal['epoch'])
    changed['selected'].append(future)
    cases.append(('future selected source', changed))
    changed = copy.deepcopy(normal)
    changed['answer']['proof'] = not normal['answer']['proof']
    cases.append(('wrong proof completeness', changed))
    changed = copy.deepcopy(normal)
    changed['arm'] = 'invented|off|global'
    cases.append(('invalid Cartesian arm', changed))
    changed = copy.deepcopy(normal)
    changed['bytes'] = True
    cases.append(('boolean byte charge', changed))
    changed = copy.deepcopy(normal)
    changed['prior_ledger_hash'] = '0' * 64
    cases.append(('wrong causal access ledger', changed))
    for label, corrupted in cases:
        try:
            validate_trial(corrupted, expected)
        except AssertionError:
            controls.append(label)
        else:
            raise AssertionError('mutation survived: ' + label)
    for label, text in (('duplicate JSON keys', '{"x":1,"x":2}'),
                        ('overflow nonfinite JSON', '{"x":1e999}')):
        try:
            decode(text)
        except AssertionError:
            controls.append(label)
        else:
            raise AssertionError('mutation survived: ' + label)
    return controls


def next_row(stream, message):
    row = next(stream, None)
    require(row is not None, 'missing row: ' + message)
    return row


def exhausted(stream, message):
    require(next(stream, None) is None, 'extra row: ' + message)


def audit(directory):
    started = time.perf_counter()
    study = Path(__file__).resolve().parent
    require(hashlib.sha256((study / 'seal.json').read_bytes()).hexdigest() == ACCEPTED_SEAL,
            'seal differs from independently accepted precollection seal')
    seal = load(study / 'seal.json')
    same(sorted(seal['sha256']), ['PLAN.md', 'pruning_core.py', 'pruning_lab.py'], 'sealed file census')
    require(seal['state'] == 'SEALED_BEFORE_COLLECTION' and seal['self_check']['passed'] == 19,
            'precollection seal state/check census')
    for name, expected in seal['sha256'].items():
        require(Path(name).name == name, 'seal path traversal')
        require(hashlib.sha256((study / name).read_bytes()).hexdigest() == expected, 'sealed source changed')
    manifest = load(directory / 'manifest.json')
    names = {'self-check.json', 'source-bank.json', 'gold.json', 'trials.jsonl.gz',
             'snapshots.jsonl.gz', 'maintenance.jsonl.gz', 'execution.json', 'scored.jsonl.gz'}
    same(sorted(manifest['sha256']), sorted(names), 'manifest file census')
    same(sorted(manifest['sizes']), sorted(names), 'manifest size census')
    for name in sorted(names):
        path = directory / name
        require(path.is_file() and not path.is_symlink(), 'missing/nonregular data artifact')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == manifest['sha256'][name], 'artifact hash: ' + name)
        expected_sizes = manifest['sizes'][name]
        unpacked = 0
        if name.endswith('.gz'):
            with path.open('rb') as stream:
                require(stream.read(8) == b'\x1f\x8b\x08\x00\x00\x00\x00\x00', 'gzip filename/time header')
            with gzip.open(path, 'rb') as stream:
                for chunk in iter(lambda: stream.read(1048576), b''):
                    unpacked += len(chunk)
        else:
            unpacked = path.stat().st_size
        same(expected_sizes, {'stored_bytes': path.stat().st_size,
                              'uncompressed_bytes': unpacked}, 'manifest byte sizes: ' + name)
    same(load(directory / 'self-check.json'), seal['self_check'], 'executed self-check/seal agreement')
    worlds = load(directory / 'source-bank.json')
    source_count, queries = validate_sources(worlds)
    gold = load(directory / 'gold.json')
    require(set(gold) == set(queries), 'gold query census')
    truth = {}
    for world in worlds:
        sources = {s['id']: s for s in world['sources']}
        for query in world['queries']:
            truth[query['id']] = full_truth(query, sources)
            same(gold[query['id']], truth[query['id']], 'gold disagrees with full-source replay')
    trials = iter(lines(directory / 'trials.jsonl.gz'))
    scores = iter(lines(directory / 'scored.jsonl.gz'))
    snapshots = iter(lines(directory / 'snapshots.jsonl.gz'))
    maintenance = iter(lines(directory / 'maintenance.jsonl.gz'))
    counts = Counter()
    first_control = None
    summary = Counter()
    cold_budget = {mode: {'switched_trials': 0, 'remaining_bytes_at_switch_total': 0,
                          'minimum_remaining_bytes_at_switch': 8192,
                          'maximum_remaining_bytes_at_switch': 0,
                          'returned_cold_bytes': 0, 'zero_cold_return_trials': 0}
                   for mode in ARCHIVES[1:]}
    for world in worlds:
        sources = {s['id']: s for s in world['sources']}
        ranker = Ranking(sources)
        for arm in ARMS:
            policy, archive, method = arm.split('|')
            active, arrived, pending, ledger, sequence = set(), set(), set(), {}, 0
            for epoch in EPOCHS:
                arrivals = {i: s for i, s in sources.items() if s['created'] == epoch}
                arrived.update(arrivals)
                promotions = pending - active if policy in ('lru96', 'lfu96', 'random96') else set()
                pending = set()
                prior = {i: sources[i] for i in active | promotions}
                active, cost = retained(policy, epoch, prior, arrivals, ledger, world['seed'])
                observed_cost = next_row(maintenance, 'maintenance')
                cpu_seconds = observed_cost.get('cpu_seconds')
                require(type(cpu_seconds) in (int, float) and math.isfinite(cpu_seconds) and
                        cpu_seconds >= 0, 'invalid maintenance CPU observation')
                cost.update(world=world['id'], arm=arm, epoch=epoch, cpu_seconds=cpu_seconds,
                            promoted=sorted(promotions), active_count=len(active),
                            active_bytes=sum(sources[i]['bytes'] for i in active),
                            retained_bytes=sum(sources[i]['bytes'] for i in (arrived if archive != 'off' else active)))
                same(observed_cost, cost, f'causal maintenance replay: {world["id"]}/{arm}/{epoch}')
                counts['maintenance'] += 1
                if epoch not in CHECKPOINTS:
                    continue
                snapshot = {'world': world['id'], 'arm': arm, 'epoch': epoch,
                            'active': sorted(active), 'active_hash': digest(sorted(active)),
                            'ledger_hash': digest(ledger)}
                same(next_row(snapshots, 'snapshot'), snapshot,
                     f'causal prequery snapshot replay: {world["id"]}/{arm}/{epoch}')
                counts['snapshots'] += 1
                for query in (q for q in world['queries'] if q['epoch'] == epoch):
                    selected, calls, used, answer = ranker.retrieval(query, active, arrived, archive, method)
                    expected = {'world': world['id'], 'arm': arm, 'query': query['id'],
                                'epoch': epoch, 'task': query['task'], 'active_hash': snapshot['active_hash'],
                                'prior_ledger_hash': digest(ledger),
                                'selected': [s['id'] for s in selected], 'calls': calls,
                                'bytes': used, 'answer': answer}
                    sequence += 1
                    for source in selected:
                        count, _ = ledger.get(source['id'], (0, -1))
                        ledger[source['id']] = (count + 1, sequence)
                    expected['next_ledger_hash'] = digest(ledger)
                    for call in calls:
                        if call['store'] == 'cold':
                            pending.update(call['selected'])
                    row = next_row(trials, 'trial')
                    validate_trial(row, expected)
                    scored = expected_score(row, truth[query['id']], active)
                    same(next_row(scores, 'score'), scored, 'score rederivation: ' + query['id'] + '/' + arm)
                    if first_control is None:
                        first_control = (row, expected, sources)
                    counts['trials'] += 1
                    counts['calls'] += len(calls)
                    counts['returned_source_observations'] += len(selected)
                    summary['support_complete'] += scored['support_complete']
                    summary['value_correct'] += scored['value_correct']
                    summary['stale'] += scored['stale']
                    summary['unknown'] += scored['unknown']
                    if calls[2]['store'] == 'cold':
                        remaining = 8192 - sum(c['returned_bytes'] for c in calls[:2])
                        returned_cold = sum(c['returned_bytes'] for c in calls[2:])
                        observed = cold_budget[archive]
                        observed['switched_trials'] += 1
                        observed['remaining_bytes_at_switch_total'] += remaining
                        observed['minimum_remaining_bytes_at_switch'] = min(
                            observed['minimum_remaining_bytes_at_switch'], remaining)
                        observed['maximum_remaining_bytes_at_switch'] = max(
                            observed['maximum_remaining_bytes_at_switch'], remaining)
                        observed['returned_cold_bytes'] += returned_cold
                        observed['zero_cold_return_trials'] += returned_cold == 0
        print(canonical({'audited_world': world['id'], 'trials': counts['trials']}), flush=True)
    for stream, label in ((trials, 'trial'), (scores, 'score'),
                          (snapshots, 'snapshot'), (maintenance, 'maintenance')):
        exhausted(stream, label)
    same({k: counts[k] for k in ('trials', 'snapshots', 'maintenance', 'calls')},
         {'trials': 64512, 'snapshots': 16128, 'maintenance': 64512, 'calls': 258048},
         'exact full Cartesian collection census')
    execution = load(directory / 'execution.json')
    same({k: execution[k] for k in ('state', 'trials', 'snapshots', 'worlds', 'queries', 'seal_hash')},
         {'state': 'COLLECTED_NOT_INDEPENDENTLY_AUDITED', 'trials': 64512,
          'snapshots': 16128, 'worlds': 32, 'queries': 1024, 'seal_hash': digest(seal)},
         'execution census/seal')
    for key in ('wall_seconds', 'cpu_seconds'):
        require(type(execution[key]) in (int, float) and math.isfinite(execution[key]) and
                execution[key] >= 0, 'invalid execution time observation')
    controls = mutation_checks(*first_control)
    return {'state': 'INDEPENDENT_REPLAY_PASSED', 'counts': dict(counts),
            'worlds': 32, 'queries': len(queries), 'original_sources': source_count,
            'outcomes': dict(summary), 'mutation_controls_rejected': controls,
            'cold_budget_opportunity': cold_budget,
            'normal_mutation_control': 'passed',
            'seal_sha256': hashlib.sha256((study / 'seal.json').read_bytes()).hexdigest(),
            'manifest_sha256': hashlib.sha256((directory / 'manifest.json').read_bytes()).hexdigest(),
            'audit_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'audit_wall_seconds': time.perf_counter() - started,
            'scope': ['No generator, pruner, retriever, reader or evaluator module imported.',
                      'Independent source-body truth, retention, admission, access ledger, ranking, paging, fallback, byte and endpoint replay.',
                      'Original clock/CPU observations validated only as nonnegative finite values; elapsed performance is not independently reproduced.',
                      'Synthetic supplied-metadata mechanisms; no natural-history or learned-reader generalization.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    if args.receipt:
        require(not args.receipt.exists(), 'receipt destination already exists')
    result = audit(args.run.resolve())
    if args.receipt:
        with args.receipt.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
