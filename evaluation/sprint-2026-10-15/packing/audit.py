"""Independent offset/render/endpoint audit; no selector or scoring helper calls.

Run from repository root: python evaluation/sprint-2026-10-15/packing/audit.py
"""
import hashlib
import json
from pathlib import Path
import run_experiment as runner

HERE = Path(__file__).resolve().parent


def metrics(task, triples, docs):
    merged, whole, original = {}, set(), set()
    for i, a, b in triples:
        assert type(a) is int and type(b) is int and 0 <= a < b <= len(docs[i]['body'])
        merged.setdefault(i, []).append((a, b))
        if a == 0 and b == len(docs[i]['body']):
            whole.add(i)
        if docs[i]['kind'] == 'source':
            original.add(i)
    for i, intervals in merged.items():
        union = []
        for a, b in sorted(intervals):
            if union and a <= union[-1][1]:
                union[-1][1] = max(b, union[-1][1])
            else:
                union.append([a, b])
        merged[i] = union
    fractions = [sum(any(a <= s['start'] and b >= s['end'] for a, b in merged.get(s['id'], [])) for s in spans) / len(spans) for spans in task['evidence_spans']]
    return {'span_complete': any(x == 1 for x in fractions),
            'best_span_fraction': max(fractions),
            'whole_complete': any(set(ids) <= whole for ids in task['evidence_sets']),
            'original_id_complete': any(set(ids) <= original for ids in task['evidence_sets'])}


def main():
    seal = runner.check_seal()
    assert runner.sha(HERE/'seal.json') == '3205376794d040271ebb0818a25e39c98e76c0989d8cb925d5e2f356dbec6d22'
    rankings = runner.load_rankings(seal)
    saved = json.loads((HERE/'run/ranking-inputs.json').read_text(encoding='utf8'))
    assert saved == [{'family_id': k[0], 'task_id': k[1], 'ranker': k[2], **v} for k, v in sorted(rankings.items())]
    bank = runner.common.bank()
    docs = runner.common.documents(bank['families'])
    families = [f for f in bank['families'] if f['split'] == 'confirmation']
    tasks = {(f['id'], t['id']): t for f in families for t in f['tasks']}
    raw = json.loads((HERE/'run/packets.json').read_text(encoding='utf8'))
    scored = json.loads((HERE/'run/scored.json').read_text(encoding='utf8'))
    results = json.loads((HERE/'run/results.json').read_text(encoding='utf8'))
    expected = {(f, t, r, m, b) for f, t in tasks for r in runner.RANKERS for m in runner.mechanism.METHODS for b in runner.BUDGETS}
    seen = set()
    residual = {}
    reconstructed = []
    for row, score in zip(raw, scored):
        key = tuple(row[k] for k in ('family_id', 'task_id', 'ranker', 'method', 'budget'))
        assert key in expected and key not in seen
        seen.add(key)
        assert all(score[k] == row[k] for k in score if k in row)
        allowed = runner.common.collection(docs, row['family_id'], 144)
        pieces, source_bytes = [], 0
        for i, a, b in row['observations']:
            assert i in allowed
            body = docs[i]['body'][a:b]
            header = {'id': i, 'chars': [a, b], 'kind': docs[i]['kind'], 'revision': docs[i]['revision']}
            pieces.append('SOURCE '+json.dumps(header, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n'+body)
            source_bytes += len(body.encode('utf8'))
        packet = '\n\n'.join(pieces).encode('utf8')
        assert len(packet) == row['bytes'] <= row['budget']
        assert source_bytes == row['source_bytes']
        assert len(packet)-source_bytes == row['wrapper_separator_bytes']
        assert hashlib.sha256(packet).hexdigest() == row['packet_sha256']
        independent = metrics(tasks[key[:2]], row['observations'], docs)
        assert all(score[k] == v for k, v in independent.items())
        reconstructed.append({**score, **independent})
        residual[key[:3]+(key[4], key[3])] = row['observations']
    assert len(raw) == len(scored) == len(seen) == 6480 and seen == expected
    for f, t, r, b, m in residual:
        if m == 'residual_gaps':
            base = residual[(f, t, r, b, 'two_windows')]
            assert residual[(f, t, r, b, m)][:len(base)] == base
    aggregate = runner.aggregate(reconstructed)
    assert aggregate['cells'] == results['cells'] and aggregate['template_cells'] == results['template_cells']
    for name in ('packets', 'scored', 'ranking_inputs'):
        filename = name.replace('_', '-')+'.json'
        assert results[name+'_sha256'] == runner.sha(HERE/'run'/filename)
    receipt = {'state': 'PASS', 'packets': 6480, 'queries': 216, 'histories': 72,
               'rendered_budget_checks': 6480, 'independent_endpoint_checks': 6480,
               'source_and_seal_hashes': 'PASS', 'saved_rankings': 432,
               'residual_baseline_prefixes': 1296,
               'independence': 'Independent render and interval/endpoint implementation; shared bank loader and aggregate formatter.',
               'run_sha256': runner.sha(HERE/'run/results.json')}
    target = HERE/'audit-receipt.json'
    if target.exists():
        assert json.loads(target.read_text(encoding='utf8')) == receipt
    else:
        runner.save(target, receipt)
    print(runner.canon(receipt))


if __name__ == '__main__':
    main()
