"""Source-exact, budgeted evidence packing. No task answers enter this module.

Offsets are Python character offsets into the unchanged body, not UTF-8 byte
offsets. Every wrapper and separator counts toward the UTF-8 packet budget.
These transparent heuristics are experiments, not authority/truth classifiers.
Run `python packing_lab.py --self-check` for executable boundary checks.
"""
import argparse
from collections import deque
import hashlib
import json
import re
import unicodedata

METHODS = (
    'whole_record', 'ranked_body', 'sentence_neighbors', 'closure_passages',
    'original_first', 'diversity_passages', 'coverage_bundles', 'authority_pairs',
)
MAX_DEPTH = 2
MAX_NEW_PER_SEED = 16
MAX_WINDOWS_PER_DOCUMENT = 2


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _tokens(text):
    return set(re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', text).casefold()))


def _validate(docs, query, ranked_ids, budget, method):
    if not isinstance(docs, dict) or not isinstance(query, str):
        raise ValueError('docs must be a dictionary; query must be text')
    try:
        query.encode('utf-8')
    except UnicodeError as exc:
        raise ValueError('query cannot be encoded as UTF-8') from exc
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
        raise ValueError('budget must be a non-negative integer byte count')
    if method not in METHODS:
        raise ValueError('unknown packing method: ' + str(method))
    if not isinstance(ranked_ids, list) or any(not isinstance(i, str) or i not in docs for i in ranked_ids):
        raise ValueError('ranked_ids must be a list of available document IDs')
    for i, doc in docs.items():
        if not isinstance(i, str) or not isinstance(doc, dict) or doc.get('id') != i:
            raise ValueError('each document ID must match its dictionary key')
        if not isinstance(doc.get('body'), str) or doc.get('kind') not in ('source', 'derived'):
            raise ValueError('each document needs a text body and source/derived kind')
        if not isinstance(doc.get('scope'), str) or isinstance(doc.get('revision'), bool) or not isinstance(doc.get('revision'), (str, int)):
            raise ValueError('scope must be text; revision must be an integer or text')
        if 'branch' in doc and not isinstance(doc['branch'], str):
            raise ValueError('branch must be text when supplied')
        for field in ('links', 'supersedes'):
            if not isinstance(doc.get(field), list) or any(not isinstance(v, str) for v in doc[field]):
                raise ValueError(field + ' must contain only text IDs')
        if not isinstance(doc.get('incorporates'), list):
            raise ValueError('incorporates must be a list')
        for ref in doc['incorporates']:
            if not isinstance(ref, dict) or not isinstance(ref.get('id'), str) or isinstance(ref.get('revision'), bool) or not isinstance(ref.get('revision'), (str, int)):
                raise ValueError('each incorporation needs an ID and revision')
        # Encoding is a trust boundary: lone surrogates are not silently replaced.
        try:
            doc['body'].encode('utf-8')
            _json({k: doc.get(k) for k in ('id', 'kind', 'revision', 'title', 'scope', 'aliases', 'authored_at', 'links', 'supersedes', 'incorporates', 'time_scope')}).encode('utf-8')
        except (UnicodeError, TypeError, ValueError) as exc:
            raise ValueError('document metadata/body cannot be serialized') from exc


def _compatible(a, b):
    """Literal scope compatibility only; no semantic/date interval inference."""
    if not (a['scope'] == b['scope'] or 'all' in (a['scope'], b['scope'])):
        return False
    ta, tb = a.get('time_scope'), b.get('time_scope')
    # If either has a declared time scope, both must explicitly match, or both
    # must declare text scopes with an `all` wildcard. Missing is not universal.
    return ta is None and tb is None or ta is not None and tb is not None and (
        ta == tb or isinstance(ta, str) and isinstance(tb, str) and 'all' in (ta, tb))


def _reverse(docs):
    result = {i: [] for i in docs}
    for i in sorted(docs):
        for older in docs[i]['supersedes']:
            if older in result:
                result[older].append(i)
    return result


def view_states(docs):
    """Check incorporation consistency, not whether a summary tells the truth."""
    reverse = _reverse(docs)
    result = {}
    for i, doc in docs.items():
        if doc['kind'] != 'derived':
            continue
        ledger = {r['id']: r['revision'] for r in doc['incorporates']}
        invalid = not ledger or len(ledger) != len(doc['incorporates'])
        stale = False
        missing = []
        for source, revision in ledger.items():
            if source not in docs:
                missing.append(source)
                invalid = True
                continue
            original = docs[source]
            stale |= original['kind'] != 'source' or original['revision'] != revision
            queue, seen = deque(reverse[source]), set()
            while queue:
                newer = queue.popleft()
                if newer in seen:
                    continue
                seen.add(newer)
                correction = docs[newer]
                if correction['kind'] == 'source' and _compatible(doc, correction) and ledger.get(newer) != correction['revision']:
                    stale = True
                queue.extend(reverse[newer])
        result[i] = {'state': 'unverifiable' if invalid else 'stale' if stale else 'declared_current',
                     'missing_declared_sources': sorted(missing)}
    return result


def _closure(docs, seeds, reverse, depth=MAX_DEPTH, cap=MAX_NEW_PER_SEED):
    wanted, missing, capped = [], set(), []
    for seed in seeds:
        if seed not in wanted:
            wanted.append(seed)
        queue, seen, added = deque([(seed, 0)]), set(), 0
        while queue:
            i, level = queue.popleft()
            if i in seen:
                continue
            seen.add(i)
            if level >= depth:
                continue
            doc = docs[i]
            refs = list(dict.fromkeys(doc['links'] + doc['supersedes'] +
                [r['id'] for r in doc['incorporates']] + reverse[i]))
            for ref in refs:
                if ref not in docs:
                    missing.add(ref)
                    continue
                if ref not in wanted:
                    if added >= cap:
                        capped.append({'seed': seed, 'omitted_ref': ref, 'reason': 'per_seed_new_record_cap'})
                        continue
                    wanted.append(ref)
                    added += 1
                queue.append((ref, level + 1))
    return wanted, sorted(missing), capped


def _sentences(body):
    """Exact slices; punctuation/newlines are a heuristic, not an NLP parser."""
    ends = [m.end() for m in re.finditer(r'(?:[.!?](?=\s|$)|\n+)', body)]
    ends.append(len(body))
    spans, start = [], 0
    for end in sorted(set(ends)):
        if end > start:
            spans.append((start, end))
        start = end
    return spans or [(0, len(body))]


def _windows(doc, query_tokens):
    spans = _sentences(doc['body'])
    scores = [len(_tokens(doc['body'][a:b]) & query_tokens) for a, b in spans]
    order = sorted(range(len(spans)), key=lambda n: (-scores[n], n))
    # A no-hit dependency still supplies first and last context rather than an
    # invented summary. Two windows can miss qualifications elsewhere; the
    # upgrade is adaptive expansion after evidence verification, not truncation.
    anchors = order[:MAX_WINDOWS_PER_DOCUMENT] if max(scores, default=0) else list(dict.fromkeys([0, len(spans) - 1]))
    windows = sorted((spans[max(0, n - 1)][0], spans[min(len(spans) - 1, n + 1)][1]) for n in anchors)
    merged = []
    for a, b in windows:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return sorted(merged, key=lambda ab: (-len(_tokens(doc['body'][ab[0]:ab[1]]) & query_tokens), ab))


def _observation(doc, start, end):
    return {'id': doc['id'], 'start': start, 'end': end, 'text': doc['body'][start:end],
            'whole': start == 0 and end == len(doc['body']), 'source_hash': _sha(doc['body'])}


def source_windows(doc, query):
    """Expose the identical frozen lexical windows for independent reranking.

    Return source-exact text and half-open character offsets, with body hashes.
    This is window generation, not inference or an evidence-sufficiency check.
    """
    if not isinstance(doc, dict) or not isinstance(doc.get('id'), str):
        raise ValueError('doc must contain a text ID')
    _validate({doc['id']: doc}, query, [], 0, 'sentence_neighbors')
    return [{k: obs[k] for k in ('start', 'end', 'text', 'source_hash')}
            for obs in (_observation(doc, a, b) for a, b in _windows(doc, _tokens(query)))]


def _piece(doc, obs, verbose=False):
    header = {'id': doc['id'], 'chars': [obs['start'], obs['end']], 'kind': doc['kind'], 'revision': doc['revision']}
    if verbose:
        header.update({k: doc.get(k) for k in ('title', 'scope', 'aliases', 'authored_at', 'links', 'supersedes', 'incorporates')})
        if 'time_scope' in doc:
            header['time_scope'] = doc['time_scope']
    return 'SOURCE ' + _json(header) + '\n' + obs['text']


def pack(docs, query, ranked_ids, budget, method):
    """Return an immutable source-exact evidence projection plus packing receipt.

    Ranking, scope labels, edges and incorporation ledgers are supplied data.
    Source presence is not sufficient evidence coverage: score actual spans.
    This module neither accesses authored answers nor invokes any model.
    """
    _validate(docs, query, ranked_ids, budget, method)
    seeds = list(dict.fromkeys(ranked_ids))
    query_tokens = _tokens(query)
    reverse = _reverse(docs)
    expanded = method in ('closure_passages', 'original_first', 'coverage_bundles', 'authority_pairs')
    order, missing, capped = _closure(docs, seeds, reverse) if expanded else (seeds, [], [])
    states = view_states(docs) if method == 'authority_pairs' else {}
    gated = [i for i in order if i in states and states[i]['state'] != 'declared_current']
    if method == 'authority_pairs':
        order = [i for i in order if i not in gated]
    if method == 'original_first':
        order.sort(key=lambda i: docs[i]['kind'] != 'source')  # stable original rank
    observations, pieces, keys, skipped = [], [], set(), []
    window_cache = {}
    used = 0

    def add(group, verbose=False, reason='budget'):
        nonlocal used
        fresh = [o for o in group if (o['id'], o['start'], o['end']) not in keys]
        texts = [_piece(docs[o['id']], o, verbose) for o in fresh]
        cost = sum(len(s.encode('utf-8')) for s in texts) + 2 * (len(texts) if pieces else max(0, len(texts) - 1))
        if used + cost > budget:
            skipped.append({'spans': [[o['id'], o['start'], o['end']] for o in fresh], 'cost': cost, 'reason': reason})
            return False
        for o, text in zip(fresh, texts):
            observations.append(o)
            pieces.append(text)
            keys.add((o['id'], o['start'], o['end']))
        used += cost
        return True

    def spans_for(i):
        if i not in window_cache:
            window_cache[i] = [_observation(docs[i], a, b) for a, b in _windows(docs[i], query_tokens)]
        return window_cache[i]

    if method in ('whole_record', 'ranked_body'):
        for i in order:
            add([_observation(docs[i], 0, len(docs[i]['body']))], method == 'whole_record')
    elif method in ('sentence_neighbors', 'closure_passages', 'original_first'):
        windows = {i: spans_for(i) for i in order}
        for pass_n in range(MAX_WINDOWS_PER_DOCUMENT):
            for i in order:
                if pass_n < len(windows[i]):
                    add([windows[i][pass_n]])
    elif method in ('diversity_passages', 'coverage_bundles'):
        groups = []
        for n, i in enumerate(order):
            if method == 'diversity_passages':
                groups.extend((n, [o]) for o in spans_for(i))
            else:
                # Atomic seed+immediate-neighbor bundles approximate conjunctive
                # evidence needs. The graph is declared, not learned or gold.
                neighbors, _, _ = _closure(docs, [i], reverse, depth=1, cap=8)
                groups.append((n, [spans_for(j)[0] for j in neighbors]))
        covered, branches, chosen_tokens = set(), set(), []
        # O(U^2) rescoring over candidate units is deliberate for small banks.
        # Larger vaults need cached term sets and a lazy marginal-gain queue;
        # no speed or optimality guarantee is claimed for this prototype.
        while groups:
            scored = []
            for index, (rank_n, group) in enumerate(groups):
                fresh = [o for o in group if (o['id'], o['start'], o['end']) not in keys]
                if not fresh:
                    continue
                cost = sum(len(_piece(docs[o['id']], o).encode('utf-8')) for o in fresh) + 2 * (len(fresh) if pieces else max(0, len(fresh) - 1))
                if used + cost > budget:
                    continue
                terms = set.union(*(_tokens(o['text']) for o in fresh))
                new_query = len((terms & query_tokens) - covered)
                relevance = len(terms & query_tokens)
                rank_prior = 1 / (1 + rank_n)
                if method == 'coverage_bundles':
                    gain = new_query + .15 * relevance + .2 * rank_prior
                else:
                    new_branch = len({docs[o['id']].get('branch', o['id']) for o in fresh} - branches)
                    overlap = max((len(terms & old) / max(1, len(terms | old)) for old in chosen_tokens), default=0)
                    gain = new_query + .2 * relevance + .25 * new_branch + .2 * rank_prior - .3 * overlap
                scored.append((gain / max(1, cost), -rank_n, -index, index, terms))
            if not scored:
                for _, group in groups:
                    add(group, reason='remaining_budget_or_duplicate')
                break
            _, _, _, index, terms = max(scored, key=lambda row: row[:3])
            _, group = groups.pop(index)
            add(group)
            covered |= terms & query_tokens
            branches |= {docs[o['id']].get('branch', o['id']) for o in group}
            chosen_tokens.append(terms)
    else:
        # Keep complete connected supersession components atomic, including
        # mismatched scopes. Only explicit compatible edges affect priority;
        # dates never decide truth. This conservative policy can exhaust budget.
        visited = set()
        for seed in order:
            if seed in visited:
                continue
            component, queue = [], deque([seed])
            while queue:
                i = queue.popleft()
                if i in visited:
                    continue
                visited.add(i)
                component.append(i)
                if docs[i]['kind'] == 'source':
                    refs = docs[i]['supersedes'] + reverse[i]
                    queue.extend(j for j in refs if j in docs and docs[j]['kind'] == 'source' and j not in visited)
            # Pairwise stable ordering avoids treating revision numbers or
            # collection/author dates as a global authority ordering. Cycles
            # leave deterministic ID/rank ordering rather than choosing truth.
            pending = list(component)
            prioritized = []
            while pending:
                frontier = [i for i in pending if not any(i in docs[j]['supersedes'] and _compatible(docs[i], docs[j]) for j in pending if j != i)]
                if not frontier:
                    frontier = pending[:1]
                for i in frontier:
                    prioritized.append(i)
                    pending.remove(i)
            add([_observation(docs[i], 0, len(docs[i]['body'])) for i in prioritized], reason='atomic_supersession_component_budget')
    packet = '\n\n'.join(pieces)
    byte_count = len(packet.encode('utf-8'))
    assert byte_count == used <= budget
    ids = list(dict.fromkeys(o['id'] for o in observations))
    return {'packet': packet, 'observations': observations, 'ids': ids, 'selected_ids': ids, 'bytes': byte_count,
            'receipt': {'schema_version': 1, 'method': method, 'budget': budget,
                        'packet_sha256': _sha(packet), 'offset_unit': 'Python Unicode character, half-open',
                        'source_hash_definition': 'SHA-256 of unchanged body encoded as UTF-8',
                        'ranked_ids': seeds, 'duplicate_rank_ids_removed': len(ranked_ids) - len(seeds),
                        'expanded_order': order if expanded else [], 'missing_expansion_refs': missing,
                        'traversal_caps': capped, 'gated_derived_ids': gated, 'view_states': states,
                        'budget_skips': skipped, 'span_count': len(observations),
                        'ceilings': 'two lexical sentence-neighbor windows/document; depth 2, 16 new refs/seed; coverage groups depth 1, cap 8; greedy objectives have no claimed approximation guarantee'}}


def self_check():
    import copy
    def record(i, body, **kwargs):
        value = {'id': i, 'body': body, 'kind': 'source', 'revision': 1, 'scope': 'all',
                 'title': i, 'aliases': ['fixture'], 'authored_at': '2026-10-13',
                 'links': [], 'supersedes': [], 'incorporates': [], 'branch': 'test'}
        value.update(kwargs)
        return value
    docs = {
        'old': record('old', 'Café 👩🏽‍🔬 starts at 10:00.\nThe approved owner is Zoë.', links=['new', 'missing']),
        'new': record('new', 'Café 👩🏽‍🔬 correction: starts at 11:00.\nOnly for the south room.', scope='south', supersedes=['old']),
        'east': record('east', 'For east only, start at 09:00.', scope='east', supersedes=['old'], time_scope='morning'),
        'view': record('view', 'Old overview says 10:00.', kind='derived', incorporates=[{'id': 'old', 'revision': 1}]),
        'long': record('long', 'irrelevant introduction.\n' * 80 + 'Café closure approved by Zoë.\n' + 'irrelevant ending.\n' * 80),
    }
    docs['old']['supersedes'] = ['new']  # deliberately cyclic explicit metadata
    untouched = copy.deepcopy(docs)
    for method in METHODS:
        for budget in (0, 1, 150, 400, 2000, 20000):
            result = pack(docs, 'Café start approved owner closure', ['view', 'long', 'old', 'old'], budget, method)
            assert result['bytes'] == len(result['packet'].encode('utf-8')) <= budget
            assert result['receipt']['packet_sha256'] == _sha(result['packet'])
            for obs in result['observations']:
                original = docs[obs['id']]['body']
                assert original[obs['start']:obs['end']] == obs['text']
                assert obs['source_hash'] == _sha(original)
                assert obs['whole'] == (obs['start'] == 0 and obs['end'] == len(original))
            if method == 'authority_pairs' and {'old', 'new', 'east'} & set(result['ids']):
                assert {'old', 'new', 'east'}.issubset(result['ids'])
    assert docs == untouched
    assert view_states(docs)['view']['state'] == 'stale'
    docs['view']['incorporates'] = [{'id': 'not-present', 'revision': 1}]
    assert view_states(docs)['view']['state'] == 'unverifiable'
    assert 'view' in pack(docs, 'start', ['view'], 20000, 'authority_pairs')['receipt']['gated_derived_ids']
    docs['view']['incorporates'] = [{'id': 'old', 'revision': 999}]
    assert view_states(docs)['view']['state'] == 'stale'
    assert not _compatible(docs['old'], docs['east'])
    scoped = record('scoped', 'A scoped source.', scope='south', time_scope='morning')
    assert not _compatible(scoped, record('other', '', scope='north', time_scope='morning'))
    assert not _compatible(scoped, record('other', '', scope='south', time_scope='evening'))
    assert _compatible(scoped, record('other', '', scope='south', time_scope='morning'))
    # A consistent declaration cannot certify a truthful summary body.
    clean = {'s': record('s', 'Correct value is eleven.'),
             'v': record('v', 'Incorrect value is seven.', kind='derived', incorporates=[{'id': 's', 'revision': 1}])}
    assert view_states(clean)['v']['state'] == 'declared_current'
    clean['v']['incorporates'].append({'id': 's', 'revision': 1})
    assert view_states(clean)['v']['state'] == 'unverifiable'
    fanout = {str(n): record(str(n), 'Leaf.') for n in range(20)}
    fanout['hub'] = record('hub', 'Hub.', links=list(fanout))
    closed, _, caps = _closure(fanout, ['hub'], _reverse(fanout))
    assert len(closed) == MAX_NEW_PER_SEED + 1 and caps
    # Body/UTF-8 boundaries and wrapper/separator costs are tested one byte below
    # and exactly at the required serialized size, not just with roomy budgets.
    single = {'old': docs['old']}
    exact = pack(single, 'Café', ['old'], 20000, 'ranked_body')['bytes']
    assert pack(single, 'Café', ['old'], exact, 'ranked_body')['ids'] == ['old']
    assert pack(single, 'Café', ['old'], exact - 1, 'ranked_body')['ids'] == []
    result = pack(docs, 'closure approved', ['long'], 500, 'sentence_neighbors')
    assert 'closure approved' in result['packet'] and not result['observations'][0]['whole']
    windows = source_windows(docs['long'], 'closure approved')
    assert [(w['start'], w['end'], w['text']) for w in windows] == [
        (o['start'], o['end'], o['text']) for o in result['observations']]
    assert all(w['source_hash'] == _sha(docs['long']['body']) for w in windows)
    assert pack(docs, 'start', ['old'], 20000, 'closure_passages')['receipt']['missing_expansion_refs'] == ['missing']
    for args in ((docs, '', ['not-present'], 100, 'ranked_body'), (docs, '', [], True, 'ranked_body')):
        try:
            pack(*args)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid boundary accepted')
    invalid = copy.deepcopy(docs)
    invalid['old']['body'] = '\ud800'
    try:
        pack(invalid, '', ['old'], 1000, 'ranked_body')
    except ValueError:
        pass
    else:
        raise AssertionError('invalid UTF-8 accepted')
    for invalid_query in (None, [], '\ud800'):
        try:
            source_windows(docs['old'], invalid_query)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid source-window query accepted')
    print(_json({'state': 'passed', 'methods': list(METHODS), 'checks': 'source offsets, UTF-8 exact budget, wrappers/separators, cycles, missing references, scoped supersession, stale/missing ledgers, immutability, Unicode encoding boundary'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    if args.self_check:
        self_check()
    else:
        parser.error('import pack(...) or run --self-check')
