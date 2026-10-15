"""Fictional closed-log state experiment; stdlib execution, matplotlib rendering."""
from __future__ import annotations
import argparse, dataclasses, hashlib, itertools, json, random, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WIDTH = 768
SEEDS = list(range(71000, 71096))
ARMS = list(itertools.product((False, True), (False, True), ('real', 'absent', 'shuffled')))

def dump(path, obj):
    path.write_text(json.dumps(obj, separators=(',', ':'), ensure_ascii=True), encoding='utf-8')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def encode(record):
    out = json.dumps(record, separators=(',', ':'), sort_keys=True).encode('utf-8')
    assert len(out) <= WIDTH
    return (out + b' ' * (WIDTH - len(out))).decode('ascii')

def sources(seed):
    rng = random.Random(seed)
    owner, auditor = f'keeper-{rng.randrange(10000)}', f'checker-{rng.randrange(10000)}'
    scope = f'fictional-project-{seed}'
    rows = []
    def add(id, facet, kind, tick=0, actor='', value='', rank=0, links=None, **kw):
        rows.append(dict(id=id, facet=facet, kind=kind, tick=tick, actor=actor,
                         value=value, rank=rank, links=links or [], scope=scope, **kw))
    add('policy', 'governance', 'policy', rank=1000, grant_actor=owner,
        revoke_actors=[owner, auditor], release_actor=owner)
    add('seal', 'governance', 'seal', rank=999,
        closed_ids=['a0', 'a1', 'a2', 'r0', 'r1', 'r2'], cutoff=100,
        note='Closed authority log for this scope through cutoff; other actors cannot amend it.')
    # Half the histories end in an auditor exception/revocation, half in a new grant.
    deny = (seed % 2 == 0)
    for facet, prefix in [('access', 'a'), ('release', 'r')]:
        ticks = sorted(rng.sample(range(10, 90), 3))
        for n in range(3):
            if facet == 'access':
                value = ['grant', 'revoke', 'revoke' if deny else 'grant'][n]
                actor = auditor if value == 'revoke' and (n == 2 or seed % 3 == 0) else owner
            else:
                value, actor = f'edition-{seed}-{n}', owner
            add(f'{prefix}{n}', facet, 'event', ticks[n], actor, value,
                rank=([95, 40, 30] if facet == 'access' else [90, 39, 29])[n],
                links=[f'{prefix}{n+1}'] if n < 2 else [],
                note='Auditor exception' if actor == auditor else 'Scope event')
    for n in range(6):
        facet = 'access' if n < 4 else 'release'
        add(f'u{n}', facet, 'event', 90+n, 'untrusted-clerk',
            'grant' if facet == 'access' else 'unapproved-edition', rank=94-n,
            note='Unauthorised actor; cannot change the authority log.')
    for n in range(10):
        add(f'f{n}', rng.choice(['access', 'release']), 'event', rng.randrange(100),
            owner, 'grant', rank=10-n, note='Different scope', unrelated=True)
        rows[-1]['scope'] = f'other-fictional-project-{seed}-{n}'
    rng.shuffle(rows)
    return [encode(row) for row in rows]

@dataclasses.dataclass(frozen=True)
class SourceView:
    id: str
    facet: str
    kind: str
    rank: int
    links: tuple[str, ...]

def views(raw, mode, seed):
    records = [json.loads(x) for x in raw]
    targets = sorted({x for r in records for x in r['links']})
    shuffled = targets[1:] + targets[:1]  # Derangement for four targets.
    mapping = dict(zip(targets, shuffled))
    return [SourceView(r['id'], r['facet'], r['kind'], r['rank'],
            tuple(r['links'] if mode == 'real' else
                  [mapping[x] for x in r['links']] if mode == 'shuffled' else []))
            for r in records]

def select(candidates, ledger, complement, seen, discovered):
    """Only typed source views cross the selection boundary."""
    assert all(type(x) is SourceView for x in candidates)
    chosen, facets = [], []
    for _ in range(2):
        eligible = [r for r in candidates if r.id not in chosen and (not ledger or r.id not in seen)]
        def score(r):
            penalty = 30 if complement and r.kind == 'event' and r.facet in facets else 0
            return -(r.rank + (200 if r.id in discovered else 0) - penalty), r.id
        item = min(eligible, key=score)
        chosen.append(item.id)
        if item.kind == 'event':
            facets.append(item.facet)
    return chosen

def consume(raw):
    records = {r['id']: r for r in map(json.loads, raw)}
    policy, seal = records.get('policy'), records.get('seal')
    decisions = {'access': None, 'release': None}
    if policy:
        for facet in decisions:
            events = [r for r in records.values() if r['kind'] == 'event'
                      and r['scope'] == policy['scope'] and r['facet'] == facet
                      and r['tick'] <= (seal['cutoff'] if seal else 100)]
            valid = []
            for r in events:
                if facet == 'release':
                    ok = r['actor'] == policy['release_actor']
                elif r['value'] == 'grant':
                    ok = r['actor'] == policy['grant_actor']
                else:
                    ok = r['value'] == 'revoke' and r['actor'] in policy['revoke_actors']
                if ok:
                    valid.append(r)
            if valid:
                decisions[facet] = max(valid, key=lambda r: (r['tick'], r['id']))['value']
    complete = bool(policy and seal and all(x in records for x in seal['closed_ids']))
    naive = bool(policy and all(v is not None for v in decisions.values()))
    return dict(answer=decisions, complete=complete, naive_sufficient=naive,
                safe_authorize=complete and decisions['access'] == 'grant')

def full_truth(raw):
    """Evaluator replay does not invoke the consumer or inspect selector metadata."""
    rows = list(map(json.loads, raw))
    p = next(r for r in rows if r['kind'] == 'policy')
    seal = next(r for r in rows if r['kind'] == 'seal')
    result = {}
    for facet in ('access', 'release'):
        eligible = []
        for row in rows:
            if row['kind'] != 'event' or row['scope'] != p['scope'] or row['facet'] != facet or row['tick'] > seal['cutoff']:
                continue
            allowed = (row['actor'] == p['release_actor']) if facet == 'release' else (
                row['actor'] == p['grant_actor'] if row['value'] == 'grant' else
                row['value'] == 'revoke' and row['actor'] in p['revoke_actors'])
            if allowed:
                eligible.append(row)
        result[facet] = sorted(eligible, key=lambda r: (r['tick'], r['id']))[-1]['value']
    return result

def trial(raw, seed, arm):
    ledger, complement, mode = arm
    candidate = views(raw, mode, seed)
    source_by_id = {json.loads(x)['id']: x for x in raw}
    seen, discovered, packets, cumulative = set(), set(), [], []
    naive_round = None
    for turn in range(1, 5):
        ids = select(candidate, ledger, complement, seen, discovered)
        packets.append(ids)
        cumulative.extend(source_by_id[i] for i in ids)
        seen.update(ids)
        discovered.update(x for r in candidate if r.id in ids for x in r.links)
        state = consume(cumulative)
        if state['naive_sufficient'] and naive_round is None:
            naive_round = turn
            naive_false = not state['complete']
        if state['complete']:
            break
    truth = full_truth(raw)
    return dict(seed=seed, arm=[int(ledger), int(complement), mode], packets=packets,
                packet_sha256=[digest(''.join(source_by_id[i] for i in packet).encode()) for packet in packets],
                output=state, current_decision_correct=state['answer'] == truth,
                complete_proof=state['complete'],
                unsupported_authorization=state['answer']['access'] == 'grant' and not state['complete'],
                false_authorization=state['answer']['access'] == 'grant' and truth['access'] != 'grant',
                safe_false_authorization=state['safe_authorize'] and truth['access'] != 'grant',
                naive_stop_round=naive_round, naive_false_stop=naive_round is not None and naive_false,
                unique_records=len(seen), source_bytes=len(cumulative)*WIDTH)

def check_seal():
    seal = json.loads((HERE/'seal.json').read_text())
    for name, expected in seal['files'].items():
        assert digest((HERE/name).read_bytes()) == expected, f'Seal changed: {name}'
    return seal

def selfcheck():
    raw = sources(SEEDS[0]); byid = {json.loads(x)['id']: x for x in raw}
    stale = consume([byid[x] for x in ('policy','seal','a0','r0')])
    fresh = consume(raw)
    assert stale['answer']['access'] == 'grant' and fresh['answer']['access'] == 'revoke'
    assert not stale['complete'] and stale['naive_sufficient']
    assert fresh['complete'] and not fresh['safe_authorize']
    assert consume([byid[x] for x in ('policy','u0')])['answer']['access'] is None
    assert all(len(x.encode('utf-8')) == WIDTH for x in raw)
    assert b''.join(x.encode() for x in raw) == ''.join(raw).encode()
    fields = {f.name for f in dataclasses.fields(SourceView)}
    assert fields == {'id','facet','kind','rank','links'}
    assert all(not any(k in fields for k in ('gold','answer','support','required','expected')) for _ in [0])
    altered = []
    for text in raw:
        row=json.loads(text); row['hidden_answer']='LEAK_SENTINEL'; altered.append(encode(row))
    assert views(raw, 'real', SEEDS[0]) == views(altered, 'real', SEEDS[0])
    for mode in ('absent','shuffled'):
        assert views(raw, mode, SEEDS[0]) != views(raw, 'real', SEEDS[0])
    real = trial(raw, SEEDS[0], (True,True,'real'))
    assert real['complete_proof'] and real['current_decision_correct'] and real['naive_false_stop']
    assert not trial(raw, SEEDS[0], (True,True,'absent'))['complete_proof']
    assert not trial(raw, SEEDS[0], (True,True,'shuffled'))['complete_proof']
    # Checker can reject an invented authorization even if a selector claims success.
    assert full_truth(raw)['access'] != 'grant'
    assert consume(raw)['answer'] == full_truth(raw)
    return {'checks': ['currentness','unseen-auditor-exception','unauthorized-actor',
            'missing-edge','wrong-edge','false-sufficiency','source-exact-bytes',
            'selector-field-boundary','hidden-answer-invariance','independent-authorization-rejection'], 'passed':10}

def run():
    check_seal()
    assert not (HERE/'results.json').exists(), 'Refuse post-result rerun'
    corpus=json.loads((HERE/'sources.json').read_text())
    rows=[trial(corpus[str(seed)],seed,arm) for seed in SEEDS for arm in ARMS]
    dump(HERE/'results.json', rows)
    return {'histories':len(corpus), 'trials':len(rows), 'results_sha256':digest((HERE/'results.json').read_bytes())}

def audit():
    check_seal()
    corpus=json.loads((HERE/'sources.json').read_text())
    rows=json.loads((HERE/'results.json').read_text())
    assert len(rows)==96*12
    assert len({(r['seed'],tuple(r['arm'])) for r in rows})==96*12
    for row in rows:
        raw=corpus[str(row['seed'])]; byid={json.loads(x)['id']:x for x in raw}
        assert len(raw)==24 and all(len(x.encode())==WIDTH for x in raw)
        assert all(len(p)==2 for p in row['packets']) and len(row['packets'])<=4
        cumulative=[]
        for packet, hash_value in zip(row['packets'],row['packet_sha256']):
            packet_bytes=''.join(byid[i] for i in packet).encode()
            assert len(packet_bytes)==2*WIDTH and digest(packet_bytes)==hash_value
            cumulative.extend(byid[i] for i in packet)
        output=consume(cumulative); truth=full_truth(raw)
        assert output==row['output']
        assert row['current_decision_correct']==(output['answer']==truth)
        p=json.loads(byid['policy']); s=json.loads(byid['seal'])
        observed={json.loads(x)['id'] for x in cumulative}
        independent_complete={'policy','seal',*s['closed_ids']}.issubset(observed)
        assert independent_complete==row['complete_proof']
        assert row['false_authorization']==(output['answer']['access']=='grant' and truth['access']!='grant')
        assert row['unsupported_authorization']==(output['answer']['access']=='grant' and not independent_complete)
        assert row['source_bytes']==len(cumulative)*WIDTH and row['source_bytes']<=6144
        assert row['unique_records']==len(observed)
        assert row==trial(raw,row['seed'],tuple(row['arm']))
    return {'passed':True,'trials':len(rows),'source_records':96*24,'packet_reconstruction':'all',
            'results_sha256':digest((HERE/'results.json').read_bytes()),'selfcheck':selfcheck()}

def render():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=json.loads((HERE/'results.json').read_text())
    metrics=['current_decision_correct','complete_proof','unsupported_authorization',
             'false_authorization','safe_false_authorization','naive_false_stop','unique_records','source_bytes']
    table=[]
    for cohort,seeds in [('all',SEEDS),('development',SEEDS[:24]),('held-out',SEEDS[24:])]:
        for arm in ARMS:
            selected=[r for r in rows if r['seed'] in seeds and r['arm']==[int(arm[0]),int(arm[1]),arm[2]]]
            table.append(dict(cohort=cohort,arm=[int(arm[0]),int(arm[1]),arm[2]],n=len(selected),
                              **{m:sum(r[m] for r in selected) for m in metrics}))
    dump(HERE/'tables.json',table)
    labels=[f'L{int(a[0])} F{int(a[1])} {a[2]}' for a in ARMS]
    allrows=[r for r in table if r['cohort']=='all']
    for number,measures,title in [(1,['current_decision_correct','complete_proof'],'Current decision and closed-log proof'),
                                  (2,['unsupported_authorization','false_authorization','naive_false_stop'],'Authorization and premature sufficiency'),
                                  (3,['unique_records'],'Unique source exposure under matched byte caps')]:
        fig,ax=plt.subplots(figsize=(10,6)); width=.8/len(measures)
        for j,m in enumerate(measures):
            values=[r[m]/r['n'] for r in allrows]
            ax.bar([i+(j-(len(measures)-1)/2)*width for i in range(12)],values,width,label=m.replace('_',' '))
        ax.set_xticks(range(12),labels,rotation=40,ha='right')
        ax.set_ylabel('Mean unique records (maximum 8)' if number==3 else 'Fraction of 96 histories')
        ax.set_title(title); ax.legend(loc='upper left',bbox_to_anchor=(0,1.01),fontsize=8)
        ax.set_ylim(0,8.8 if number==3 else 1.2); ax.grid(axis='y',alpha=.2); ax.set_axisbelow(True)
        fig.text(.01,.01,'L: exact seen ledger; F: complementary facets. Engineered fictional scaffold; paired histories.',fontsize=8)
        fig.tight_layout(rect=(0,.03,1,1))
        for extension in ('png','svg'):
            fig.savefig(HERE/f'figure-{number}.{extension}',dpi=160)
        plt.close(fig)
    # Paired bootstrap uses seed-level deltas, never trial-level pseudo-replication.
    comparisons=[]; rng=random.Random(9173)
    for factor in ('ledger','facet','edges'):
        for metric in metrics[:6]:
            delta=[]
            for seed in SEEDS:
                block=[r for r in rows if r['seed']==seed]
                if factor=='ledger': left=[r[metric] for r in block if r['arm'][0]==1]; right=[r[metric] for r in block if r['arm'][0]==0]
                elif factor=='facet': left=[r[metric] for r in block if r['arm'][1]==1]; right=[r[metric] for r in block if r['arm'][1]==0]
                else: left=[r[metric] for r in block if r['arm'][2]=='real']; right=[r[metric] for r in block if r['arm'][2]=='absent']
                delta.append(sum(left)/len(left)-sum(right)/len(right))
            boot=sorted(sum(rng.choices(delta,k=96))/96 for _ in range(2000))
            comparisons.append(dict(factor=factor,metric=metric,mean=sum(delta)/96,ci95=[boot[49],boot[1949]]))
    dump(HERE/'paired-effects.json',comparisons)
    return {'tables':len(table),'figures':3,'paired_effects':len(comparisons)}

def main():
    stage=argparse.ArgumentParser(); stage.add_argument('stage',choices=['seal','selfcheck','run','audit','render'])
    args=stage.parse_args()
    if args.stage=='seal':
        assert not (HERE/'seal.json').exists()
        dump(HERE/'sources.json',{str(s):sources(s) for s in SEEDS})
        obj={'seeds':SEEDS,'development':SEEDS[:24],'held_out':SEEDS[24:],
             'files':{n:digest((HERE/n).read_bytes()) for n in ('PLAN.md','state_lab.py','sources.json')}}
        dump(HERE/'seal.json',obj); result=obj
    else:
        result=globals()[args.stage]()
    receipt={'stage':args.stage,'result':result}
    if args.stage!='seal': dump(HERE/f'{args.stage}-receipt.json',receipt)
    print(json.dumps(receipt,separators=(',',':')))

if __name__=='__main__': main()
