"""Source-only pruning/retrieval/reading. No generator or gold imports."""
import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass

POLICIES = ('all', 'ttl8', 'lru96', 'lfu96', 'latest', 'latest_dependencies', 'random96')
ARCHIVES = ('off', 'unresolved_only', 'scheduled_cold')
METHODS = ('global', 'project', 'linked')
BUDGET = 8192
CALLS = 4
SLOTS = 6


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def digest(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def tokens(text):
    return re.findall(r'[a-z0-9_]+', text.lower())


@dataclass(frozen=True)
class RetentionSource:
    id: str
    created: int
    effective: int
    expires: int | None
    project: str
    key: str
    refs: tuple


def metadata(source):
    return RetentionSource(**{k: tuple(source[k]) if k == 'refs' else source[k]
                              for k in RetentionSource.__dataclass_fields__})


def retain(policy, epoch, previous, arrivals, ledger, seed):
    """Prune from prior active plus new arrivals only; no query/gold capability."""
    pool = {s.id: s for s in previous + arrivals}
    ops = len(pool)
    if policy == 'all':
        keep = set(pool)
    elif policy == 'ttl8':
        keep = {i for i, s in pool.items() if epoch - s.created <= 8}
    elif policy in ('latest', 'latest_dependencies'):
        latest = {}
        for i, s in pool.items():
            k = (s.project, s.key)
            if k not in latest or (s.effective, s.created, i) > (
                    pool[latest[k]].effective, pool[latest[k]].created, latest[k]):
                latest[k] = i
        keep = set(latest.values())
        if policy == 'latest_dependencies':
            todo = list(keep)
            while todo:
                for dep in pool[todo.pop()].refs:
                    ops += 1
                    if dep in pool and dep not in keep:
                        keep.add(dep)
                        todo.append(dep)
    elif policy in ('lru96', 'lfu96', 'random96'):
        def priority(i):
            s = pool[i]
            count, last = ledger.get(i, (0, -1))
            if policy == 'lru96':
                return last, s.created, i
            if policy == 'lfu96':
                return count, last, s.created, i
            return hashlib.sha256(f'{seed}:{epoch}:{i}'.encode()).hexdigest()
        keep = set(sorted(pool, key=priority, reverse=True)[:96])
        ops += len(pool)  # Priority evaluations; comparisons are not counted.
    else:
        raise ValueError(policy)
    return keep, {'visited': len(pool), 'operations': ops,
                  'removed': len(pool) - len(keep), 'arrivals': len(arrivals)}


def parse_source(source):
    line = source['text'].split('\n', 1)[0]
    if not line.startswith('ASSERT '):
        raise ValueError('missing assertion')
    claim = json.loads(line[7:])
    for key in ('id', 'project', 'key', 'value', 'effective', 'expires', 'refs', 'created'):
        if claim[key] != source[key]:
            raise ValueError('text/metadata disagreement')
    return claim


def read_sources(query, selected):
    claims = {s['id']: parse_source(s) for s in selected}
    matches = [s for s in claims.values() if s['project'] == query['project']
               and s['key'] == query['key'] and s['effective'] <= query['asof']
               and (s['expires'] is None or query['asof'] < s['expires'])]
    if not matches:
        return {'value': None, 'governing': None, 'missing': [], 'proof': False}
    source = max(matches, key=lambda s: (s['effective'], s['created'], s['id']))
    seen, missing, todo = set(), set(), [source['id']]
    while todo:
        i = todo.pop()
        if i in seen:
            continue
        seen.add(i)
        if i not in claims:
            missing.add(i)
        else:
            todo.extend(claims[i]['refs'])
    return {'value': source['value'], 'governing': source['id'],
            'missing': sorted(missing), 'proof': not missing}


def rendered(source):
    return ('<SOURCE ' + source['id'] + '>\n' + source['text'] + '\n</SOURCE>\n').encode('utf-8')


class Search:
    """Small exhaustive BM25; O(records) per call, not a speed benchmark."""
    def __init__(self, sources):
        self.sources = {s['id']: s for s in sources}
        self.counts = {i: Counter(tokens(s['text'])) for i, s in self.sources.items()}
        self.lengths = {i: sum(c.values()) for i, c in self.counts.items()}

    def rank(self, query, pool, method, unresolved):
        ids = sorted(i for i in pool if method == 'global' or
                     self.sources[i]['project'] == query['project'] or
                     (method == 'linked' and i in unresolved))
        terms = sorted(set(tokens(query['cue'])))
        dfs = {t: sum(t in self.counts[i] for i in ids) for t in terms}
        avg = sum(self.lengths[i] for i in ids) / max(1, len(ids))
        scores = []
        for i in ids:
            score = 0.0
            for t in terms:
                tf = self.counts[i].get(t, 0)
                if tf:
                    idf = math.log(1 + (len(ids) - dfs[t] + .5) / (dfs[t] + .5))
                    score += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * self.lengths[i] / avg))
            if i in unresolved:
                score += 1000000.0
            scores.append((i, score))
        scores.sort(key=lambda x: (-x[1], x[0]))
        return scores, len(ids), len(ids) * len(terms)

    def retrieve(self, query, active, arrived, archive, method):
        selected, selected_ids, calls, used = [], set(), [], 0
        cold = set(arrived) - set(active)
        cold_mode = False
        for call in range(1, CALLS + 1):
            before = read_sources(query, selected)
            if call == 3:
                cold_mode = bool(cold) and (archive == 'scheduled_cold' or
                    archive == 'unresolved_only' and (before['value'] is None or before['missing']))
            store = 'cold' if cold_mode else 'active'
            pool = cold if cold_mode else active
            ranking, candidates, terms = self.rank(query, pool, method, set(before['missing']))
            added, scored, expansion_probes = [], [], 0
            queue = [(i, score, 0) for i, score in ranking if i not in selected_ids]
            while queue and len(added) < SLOTS:
                i, score, depth = queue.pop(0)
                if i in selected_ids:
                    continue
                source = self.sources[i]
                size = len(rendered(source))
                if used + size > BUDGET:
                    continue
                selected.append(source)
                selected_ids.add(i)
                added.append(i)
                scored.append([i, round(score, 8)])
                used += size
                if method == 'linked' and depth < 2:
                    for dep in source['refs']:
                        if expansion_probes >= 8:
                            break
                        expansion_probes += 1
                        if dep in pool and dep not in selected_ids:
                            queue.insert(0, (dep, score, depth + 1))
            calls.append({'call': call, 'store': store, 'before': before,
                          'selected': added, 'scores': scored, 'candidates': candidates,
                          'term_work': terms, 'expansion_probes': expansion_probes,
                          'returned_bytes': sum(len(rendered(self.sources[i])) for i in added)})
        return selected, calls, used, read_sources(query, selected)
