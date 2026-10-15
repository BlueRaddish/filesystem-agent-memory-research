"""Postcollection independent replay; does not import generator/selector/consumer."""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def replay(records):
    policy = next((r for r in records if r['kind'] == 'policy'), None)
    out = {'access': None, 'release': None}
    if policy is None:
        return out
    for row in sorted(records, key=lambda r: (r['tick'], r['id'])):
        if row['kind'] != 'event' or row['scope'] != policy['scope'] or row['tick'] > 100:
            continue
        if row['facet'] == 'release' and row['actor'] == policy['release_actor']:
            out['release'] = row['value']
        elif row['facet'] == 'access':
            if row['value'] == 'grant' and row['actor'] == policy['grant_actor']:
                out['access'] = 'grant'
            elif row['value'] == 'revoke' and row['actor'] in policy['revoke_actors']:
                out['access'] = 'revoke'
    return out

def verify(row, texts):
    byid = {json.loads(t)['id']: t for t in texts}
    all_records = [json.loads(t) for t in texts]
    selected = []
    assert len(row['packets']) == len(row['packet_sha256']) == 4
    for packet, expected_hash in zip(row['packets'], row['packet_sha256']):
        assert len(packet) == 2
        data = ''.join(byid[i] for i in packet).encode('utf-8')
        assert len(data) == 1536 and hashlib.sha256(data).hexdigest() == expected_hash
        selected.extend(json.loads(byid[i]) for i in packet)
    selected = list({r['id']: r for r in selected}.values())
    observed = {r['id'] for r in selected}
    log = next(r for r in all_records if r['kind'] == 'seal')
    complete = {'policy', 'seal', *log['closed_ids']} <= observed
    answer, truth = replay(selected), replay(all_records)
    assert row['output']['answer'] == answer
    assert row['output']['complete'] == row['complete_proof'] == complete
    assert row['current_decision_correct'] == (answer == truth)
    assert row['unsupported_authorization'] == (answer['access'] == 'grant' and not complete)
    assert row['false_authorization'] == (answer['access'] == 'grant' and truth['access'] == 'revoke')
    assert row['output']['safe_authorize'] == (complete and answer['access'] == 'grant')
    assert row['safe_false_authorization'] == (complete and answer['access'] == 'grant' and truth['access'] == 'revoke')
    return truth

def verify_census(rows):
    expected = {(seed, ledger, facet, edge)
                for seed in range(71000, 71096)
                for ledger, facet, edge in itertools.product((0, 1), (0, 1), ('real', 'absent', 'shuffled'))}
    keys = {(r['seed'], *r['arm']) for r in rows}
    assert len(rows) == len(keys) == len(expected) and keys == expected

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipt', action='store_true', help='Explicitly write a check receipt; default is read-only')
    args = parser.parse_args()
    corpus = json.loads((ROOT/'sources.json').read_text())
    rows = json.loads((ROOT/'results.json').read_text())
    verify_census(rows)
    for row in rows:
        verify(row, corpus[str(row['seed'])])
    # Mutation controls prove incorrect outputs and source-packet hashes are rejected.
    reference = next(r for r in rows if r['seed'] == 71000 and r['complete_proof'])
    mutations = []
    bad = copy.deepcopy(reference); bad['output']['answer']['access'] = 'grant'; mutations.append(bad)
    bad = copy.deepcopy(reference); bad['complete_proof'] = False; mutations.append(bad)
    bad = copy.deepcopy(reference); bad['packet_sha256'][0] = '0'*64; mutations.append(bad)
    incomplete = next(r for r in rows if r['seed'] == 71000 and not r['complete_proof'])
    bad = copy.deepcopy(incomplete); bad['output']['safe_authorize'] = True; mutations.append(bad)
    rejected = 0
    for bad in mutations:
        try:
            verify(bad, corpus['71000'])
        except AssertionError:
            rejected += 1
    bad_rows = copy.deepcopy(rows)
    bad_rows[0]['arm'][2] = 'invented-edge-mode'
    try:
        verify_census(bad_rows)
    except AssertionError:
        rejected += 1
    assert rejected == 5
    result = {'passed': True, 'trials': len(rows), 'mutation_controls_rejected': rejected,
              'implementation': 'independent source replay; no experiment-module imports'}
    if args.receipt:
        (ROOT/'independent-check-receipt.json').write_text(json.dumps(result,separators=(',',':')))
    print(json.dumps(result,separators=(',',':')))

if __name__ == '__main__':
    main()
