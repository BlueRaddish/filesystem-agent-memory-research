"""Exploratory, answer-free context expansion over the frozen packing interface.

Only source documents, query, candidate order and byte budget enter selection.
All policies share the original depth-two closure and compact source wrapper.
The residual policy preserves the exact baseline observations before adding gaps.
"""
import hashlib
import json
from pathlib import Path
import sys

STUDY = Path(__file__).resolve().parents[2] / 'study-2026-10-13'
sys.path.insert(0, str(STUDY))
import packing_lab as frozen

METHODS = ('two_windows', 'radius3', 'radius8', 'whole_body', 'residual_gaps')


def windows(doc, query, radius):
    spans = frozen._sentences(doc['body'])
    qt = frozen._tokens(query)
    scores = [len(frozen._tokens(doc['body'][a:b]) & qt) for a, b in spans]
    order = sorted(range(len(spans)), key=lambda n: (-scores[n], n))
    anchors = order[:2] if max(scores, default=0) else list(dict.fromkeys([0, len(spans)-1]))
    candidates = sorted((spans[max(0, n-radius)][0], spans[min(len(spans)-1, n+radius)][1]) for n in anchors)
    merged = []
    for a, b in candidates:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return sorted(merged, key=lambda ab: (-len(frozen._tokens(doc['body'][ab[0]:ab[1]]) & qt), ab))


def gaps(length, intervals):
    """Return the exact complement of a union of half-open source intervals."""
    result, cursor = [], 0
    for a, b in sorted(intervals):
        if cursor < a:
            result.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < length:
        result.append((cursor, length))
    return result


def pack(docs, query, ranked_ids, budget, method):
    if method not in METHODS:
        raise ValueError('Unknown exploratory policy')
    frozen._validate(docs, query, ranked_ids, budget, 'closure_passages')
    seeds = list(dict.fromkeys(ranked_ids))
    order, missing, capped = frozen._closure(docs, seeds, frozen._reverse(docs))
    if method in ('two_windows', 'residual_gaps'):
        result = frozen.pack(docs, query, ranked_ids, budget, 'closure_passages')
        if method == 'two_windows':
            return result
        observations = list(result['observations'])
    else:
        observations = []
    pieces = [frozen._piece(docs[o['id']], o) for o in observations]
    used = len('\n\n'.join(pieces).encode('utf8'))

    def add(i, a, b):
        nonlocal used
        obs = frozen._observation(docs[i], a, b)
        piece = frozen._piece(docs[i], obs)
        cost = len(piece.encode('utf8')) + (2 if pieces else 0)
        if used + cost > budget:
            return False
        observations.append(obs)
        pieces.append(piece)
        used += cost
        return True

    if method == 'whole_body':
        for i in order:
            add(i, 0, len(docs[i]['body']))
    elif method in ('radius3', 'radius8'):
        radius = int(method.removeprefix('radius'))
        candidates = {i: windows(docs[i], query, radius) for i in order}
        for pass_n in range(2):
            for i in order:
                if pass_n < len(candidates[i]):
                    add(i, *candidates[i][pass_n])
    else:
        # One document-order pass over baseline-selected records. Whole missing
        # gaps are indivisible; oversized gaps are skipped. No semantic stopping
        # or optimality claim; sentence fallback is a separately testable policy.
        initial = {}
        for o in observations:
            initial.setdefault(o['id'], []).append((o['start'], o['end']))
        for i in order:
            if i in initial:
                for a, b in gaps(len(docs[i]['body']), initial[i]):
                    add(i, a, b)
    packet = '\n\n'.join(pieces)
    assert used == len(packet.encode('utf8')) <= budget
    return {'packet': packet, 'bytes': used, 'observations': observations,
            'ids': list(dict.fromkeys(o['id'] for o in observations)),
            'receipt': {'packet_sha256': hashlib.sha256(packet.encode('utf8')).hexdigest(),
                        'expanded_order': order, 'missing_expansion_refs': missing,
                        'traversal_caps': capped}}


def self_check():
    import copy
    body = 'Anchor alpha. Anchor beta.\n' + 'Ordinary filler.\n' * 14 + 'Distant qualifier: hold.\n' + 'Ordinary footer.\n' * 9
    doc = {'id': 'S', 'body': body, 'kind': 'source', 'revision': 1, 'scope': 'all',
           'links': [], 'supersedes': [], 'incorporates': [], 'title': 'Synthetic'}
    docs = {'S': doc}
    original = copy.deepcopy(docs)
    assert windows(doc, 'Anchor', 1) == frozen._windows(doc, frozen._tokens('Anchor'))
    baseline = pack(docs, 'Anchor', ['S'], 9000, 'two_windows')
    assert 'Distant qualifier' not in baseline['packet']
    filled = pack(docs, 'Anchor', ['S'], 9000, 'residual_gaps')
    assert 'Distant qualifier' in filled['packet']
    assert filled['observations'][:len(baseline['observations'])] == baseline['observations']
    for method in METHODS:
        for budget in (0, 1, 150, 450, 9000):
            out = pack(docs, 'Anchor', ['S', 'S'], budget, method)
            assert out['bytes'] == len(out['packet'].encode('utf8')) <= budget
            assert all(o['text'] == body[o['start']:o['end']] for o in out['observations'])
    full = pack(docs, 'Anchor', ['S'], 9000, 'whole_body')
    assert pack(docs, 'Anchor', ['S'], full['bytes'], 'whole_body')['observations']
    assert not pack(docs, 'Anchor', ['S'], full['bytes']-1, 'whole_body')['observations']
    assert docs == original
    assert gaps(12, [(1, 5), (3, 9)]) == [(0, 1), (9, 12)]
    rejected = 0
    for args in ((docs, 'Anchor', ['alien'], 1000, 'whole_body'),
                 (docs, 'Anchor', ['S'], True, 'whole_body'),
                 (docs, 'Anchor', ['S'], 1000, 'unknown')):
        try:
            pack(*args)
        except ValueError:
            rejected += 1
        else:
            raise AssertionError('Malformed input accepted')
    assert rejected == 3
    return {'state': 'PASS', 'positive_groups': 7, 'known_bad_rejections': rejected,
            'demonstrated_mechanism': 'Two lexical windows omit a distant qualifier; residual gaps restore it at sufficient budget.'}


if __name__ == '__main__':
    print(json.dumps(self_check(), sort_keys=True))
