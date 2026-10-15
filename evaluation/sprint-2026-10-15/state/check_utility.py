"""Derive authorization utility from stored source/outcomes; default read-only."""
import argparse
import json
import sys
sys.dont_write_bytecode = True
from independent_check import ROOT, replay

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    corpus = json.loads((ROOT/'sources.json').read_text())
    rows = json.loads((ROOT/'results.json').read_text())
    truth = {int(seed): replay(list(map(json.loads, texts))) for seed, texts in corpus.items()}
    table = []
    for arm in sorted({tuple(r['arm']) for r in rows}):
        selected = [r for r in rows if tuple(r['arm']) == arm]
        eligible = [r for r in selected if truth[r['seed']]['access'] == 'grant']
        table.append(dict(arm=list(arm), histories=len(selected), true_grant_opportunities=len(eligible),
            correct_provisional_grants=sum(r['output']['answer']['access']=='grant' for r in eligible),
            safe_true_grants=sum(r['output']['safe_authorize'] for r in eligible),
            withheld_true_grants=sum(not r['output']['safe_authorize'] for r in eligible),
            safe_false_grants=sum(r['output']['safe_authorize'] and truth[r['seed']]['access']!='grant' for r in selected)))
    path = ROOT/'utility-table.json'
    if args.write:
        path.write_text(json.dumps(table,separators=(',',':')))
    else:
        assert json.loads(path.read_text()) == table
    print(json.dumps({'passed':True,'arms':len(table),'utility':'source-replayed true and withheld grants'},separators=(',',':')))

if __name__ == '__main__': main()
