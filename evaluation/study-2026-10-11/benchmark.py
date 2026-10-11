"""Atomic retrieval comparisons over fictional records; no gold reaches engines.

BM25 and declared-edge traversal use the standard library. Local ONNX scoring
uses model_runtime.py. Pair caching saves repeated factorial computation; speed
claims must use the separately executed uncached warmed timing block.
"""
import argparse
from collections import Counter,deque
from functools import lru_cache
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import re
import time
import unicodedata

HERE=Path(__file__).resolve().parent
ENGINES=('bm25','hierarchical_bm25','minilm_rerank','mixedbread_rerank',
         'hierarchical_mixedbread','hierarchical_mixedbread_rescue')
FACTORS=tuple(''.join(map(str,v)) for v in itertools.product((0,1),repeat=3))


def dumps(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)


def sha(text):
    return hashlib.sha256(text.encode('utf8')).hexdigest()


def atomic_json(path,value):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(dumps(value)+'\n',encoding='utf8',newline='\n')
    temp.replace(path)


def load_bank():
    families=[]
    for name in ('author-a.json','author-b.json'):
        bank=json.loads((HERE/name).read_text(encoding='utf8'))
        assert bank['schema_version']==1
        families.extend(bank['families'])
    assert len(families)==48 and len({f['id'] for f in families})==48
    for f in families:
        assert re.fullmatch(r'[AB](?:0[1-9]|1[0-9]|2[0-4])',f['id'])
        assert 10<=len(f['records'])<=14 and len(f['tasks'])==2
        sources={r['id'] for r in f['records'] if r['kind']=='source'}
        ids={r['id'] for r in f['records']}
        assert len(sources)>=8 and len(ids)==len(f['records'])
        for task in f['tasks']:
            assert task['expected']['status'] in ('ready','hold')
            assert set(task['answer_keys'])==set(task['expected']['answer'])
            assert set(task['critical_keys']).issubset(task['answer_keys'])
            assert task['evidence_sets'] and all(set(s).issubset(sources) and s for s in task['evidence_sets'])
    return families


@lru_cache(maxsize=1)
def family_split():
    return json.loads((HERE/'family-split.json').read_text(encoding='utf8'))['families']


def split(family_id):
    return family_split()[family_id]


def write_split(families):
    strata={
        'A':('late_correction','scope_exception','unresolved_conflict','missing_prerequisite','unicode_alias','late_import'),
        'B':('unresolved_conflict','missing_prerequisite','unicode_alias','late_import','missing_edge','wrong_ledger'),
    }
    dev=[]
    for author,selected_strata in strata.items():
        for stratum in selected_strata:
            ids=sorted(f['id'] for f in families if f['id'].startswith(author) and f['stratum']==stratum)
            assert len(ids)>=2, 'Need retained held-out examples for '+author+':'+stratum
            dev.append(ids[0])
    value={f['id']:('development' if f['id'] in dev else 'held_out') for f in families}
    assert Counter(value.values())=={'development':12,'held_out':36}
    atomic_json(HERE/'family-split.json',{'rule':'lowest family ID in six predeclared strata per author; no outcome selection','development_strata':strata,'families':value})


def selected_reader_families(families):
    selected=[]
    for prefix in ('A','B'):
        candidates=[f['id'] for f in families if f['id'].startswith(prefix) and split(f['id'])=='held_out']
        selected.extend(sorted(candidates,key=lambda s:sha(s+':reader-20261011'))[:12])
    return selected


def docs_for(families):
    result={}
    for f in families:
        slug=re.sub(r'[^a-z0-9]+','-',unicodedata.normalize('NFKD',f['name']).encode('ascii','ignore').decode().lower()).strip('-') or 'workstream'
        branch=f['id'].lower()+'-'+slug
        for r in f['records']:
            assert r['id'] not in result
            # Only retained/public record fields cross the retriever boundary.
            doc={k:r[k] for k in ('id','kind','revision','authored_at','title','scope','body','links','supersedes','incorporates')}
            doc.update(family_id=f['id'],branch=branch,aliases=[f['name'],*f['aliases']],
                       path='1-Projects/'+branch+'/records/'+r['id']+'.md')
            result[r['id']]=doc
    return result


def make_collection(all_docs,family_id,size):
    own=[r for r in all_docs.values() if r['family_id']==family_id]
    others=[r for r in all_docs.values() if r['family_id']!=family_id]
    # Nested noise collections expose the same records at both sizes. The hash
    # sample is O(N log N); scale with a persistent indexed sampler for large vaults.
    others.sort(key=lambda d:sha(family_id+':noise-20261011:'+d['id']))
    rows=own+others[:size-len(own)]
    assert len(rows)==size
    return {d['id']:d for d in sorted(rows,key=lambda d:d['id'])}


def render(doc,cues):
    header=f"Record {doc['id']}; kind={doc['kind']}; revision={doc['revision']}; authored={doc['authored_at']}\n"
    if cues:
        header+=f"Index cues: {doc['title']}; scope={doc['scope']}; aliases={'; '.join(doc['aliases'])}\n"
    # Graph/ledger metadata is public in every arm; A changes only index cues.
    metadata={k:doc[k] for k in ('links','supersedes','incorporates')}
    return header+'Declared metadata: '+json.dumps(metadata,ensure_ascii=False,sort_keys=True)+'\n'+doc['body'].strip()+'\n'


def packet_for(docs,ids,cues):
    return '\n'.join(render(docs[i],cues) for i in ids)


def tokens(text):
    return re.findall(r'[^\W_]+',unicodedata.normalize('NFKC',text).casefold(),re.UNICODE)


def bm25(query,texts):
    query=Counter(tokens(query))
    bags=[Counter(tokens(t)) for t in texts]
    lengths=[sum(b.values()) for b in bags]
    mean=sum(lengths)/max(1,len(lengths)) or 1
    df=Counter(w for b in bags for w in b)
    n=len(bags)
    scores=[]
    for bag,length in zip(bags,lengths):
        score=0.0
        for word,qf in query.items():
            count=bag[word]
            if count:
                idf=math.log(1+(n-df[word]+.5)/(df[word]+.5))
                score+=qf*idf*count*2.2/(count+1.2*(.25+.75*length/mean))
        scores.append(score)
    return scores


def ranked(ids,scores):
    return sorted(ids,key=lambda i:(-scores[i],i))


def reverse_edges(docs):
    reverse={i:[] for i in docs}
    for i,d in docs.items():
        for older in d['supersedes']:
            if older in reverse: reverse[older].append(i)
    return reverse


def view_states(docs):
    reverse=reverse_edges(docs)
    states={}
    for i,d in docs.items():
        if d['kind']!='derived': continue
        ledger={p['id']:p['revision'] for p in d['incorporates']}
        invalid=not ledger or len(ledger)!=len(d['incorporates'])
        stale=False
        missing=[]
        for source,revision in ledger.items():
            if source not in docs:
                invalid=True; missing.append(source); continue
            record=docs[source]
            if record['kind']!='source' or record['revision']!=revision: stale=True
            queue=deque(reverse[source]); seen=set()
            while queue:
                newer=queue.popleft()
                if newer in seen: continue
                seen.add(newer)
                correction=docs[newer]
                compatible=d['scope']=='all' or correction['scope']=='all' or d['scope']==correction['scope']
                if compatible and ledger.get(newer)!=correction['revision']: stale=True
                queue.extend(reverse[newer])
        states[i]={'state':'unverifiable' if invalid else 'stale' if stale else 'declared_current',
                   'missing_declared_sources':missing}
    return states


class Scores:
    def __init__(self,scorers,cache=True):
        self.scorers=scorers
        self.cache=cache
        self.values={}
        self.events=[]

    def get(self,name,query,texts):
        keys=[(name,sha(query),sha(t)) for t in texts]
        missing=list(dict.fromkeys(k for k in keys if not self.cache or k not in self.values))
        by_key=dict(zip(keys,texts))
        if missing:
            values,receipt=self.scorers[name].score(query,[by_key[k] for k in missing])
            self.events.append({'model':name,**receipt,'cache_enabled':self.cache})
            self.values.update(zip(missing,values))
        return [self.values[k] for k in keys]


def rank_docs(docs,query,cues,gate,engine,score_source):
    started=time.perf_counter()
    states=view_states(docs)
    eligible=[i for i,d in docs.items() if not gate or i not in states or states[i]['state']=='declared_current']
    texts={i:render(docs[i],cues) for i in eligible}
    lexical=dict(zip(eligible,bm25(query,[texts[i] for i in eligible])))
    order=ranked(eligible,lexical)
    branches=sorted({docs[i]['branch'] for i in eligible})
    branch_docs={b:[i for i in eligible if docs[i]['branch']==b] for b in branches}
    branch_texts=[]
    for b in branches:
        group=branch_docs[b]
        aliases=docs[group[0]]['aliases']
        text='Workstream: '+b+'; aliases: '+'; '.join(aliases)
        if cues: text+='; records: '+'; '.join(docs[i]['title']+' scope='+docs[i]['scope'] for i in group)
        branch_texts.append(text)
    picked_branches=branches
    candidates=order
    branch_scores={}
    if engine=='hierarchical_bm25':
        branch_scores=dict(zip(branches,bm25(query,branch_texts)))
        picked_branches=ranked(branches,branch_scores)[:2]
        candidates=[i for i in order if docs[i]['branch'] in picked_branches]
    elif engine in ('minilm_rerank','mixedbread_rerank'):
        candidates=order[:32]
        model='minilm' if engine=='minilm_rerank' else 'mixedbread'
        scores=dict(zip(candidates,score_source.get(model,query,[texts[i] for i in candidates])))
        candidates=ranked(candidates,scores)
    elif engine in ('hierarchical_mixedbread','hierarchical_mixedbread_rescue'):
        branch_scores=dict(zip(branches,score_source.get('mixedbread',query,branch_texts)))
        picked_branches=ranked(branches,branch_scores)[:2]
        routed=[i for i in order if docs[i]['branch'] in picked_branches]
        if engine.endswith('_rescue'): routed=list(dict.fromkeys(routed+order[:8]))
        candidates=routed
        scores=dict(zip(candidates,score_source.get('mixedbread',query,[texts[i] for i in candidates])))
        candidates=ranked(candidates,scores)
    elif engine!='bm25': raise ValueError(engine)
    return {'ranked_ids':candidates,'eligible_ids':eligible,'routed_branches':picked_branches,
            'candidate_ids':list(candidates),'view_states':states,
            'rank_execution_seconds':time.perf_counter()-started}


def pack(docs,ranking,cues,expand,budget):
    reverse=reverse_edges(docs)
    eligible=set(ranking['eligible_ids'])
    wanted=[]; missing=[]
    for seed in ranking['ranked_ids']:
        if seed not in wanted: wanted.append(seed)
        if not expand: continue
        queue=deque([(seed,0)]); seen=set(); expanded=0
        while queue and expanded<16:
            i,depth=queue.popleft()
            if i in seen: continue
            seen.add(i)
            if depth>=2: continue
            refs=list(dict.fromkeys(docs[i]['links']+docs[i]['supersedes']+
                [p['id'] for p in docs[i]['incorporates']]+reverse.get(i,[])))
            for ref in refs:
                if expanded>=16: break
                if ref not in docs:
                    if ref not in missing: missing.append(ref)
                    continue
                if ref not in eligible: continue
                if ref not in wanted: wanted.append(ref); expanded+=1
                queue.append((ref,depth+1))
    selected=[]; oversized=[]
    for i in wanted:
        trial=packet_for(docs,selected+[i],cues)
        if len(trial.encode('utf8'))<=budget: selected.append(i)
        else: oversized.append(i)
    packet=packet_for(docs,selected,cues)
    return {'selected_ids':selected,'bytes':len(packet.encode('utf8')),'packet_sha256':sha(packet),
            'oversized_or_budget_skipped':oversized,'missing_expansion_refs':missing}


def schema_valid(artifact,keys):
    return (isinstance(artifact,dict) and artifact.get('status') in ('ready','hold')
        and isinstance(artifact.get('answer'),dict) and set(keys).issubset(artifact['answer'])
        and isinstance(artifact.get('evidence'),list) and all(isinstance(v,str) for v in artifact['evidence']))


def equal(a,b):
    if isinstance(a,bool)!=isinstance(b,bool): return False
    return a==b


def score_artifact(task,artifact,docs):
    valid=schema_valid(artifact,task['answer_keys'])
    artifact=artifact if isinstance(artifact,dict) else {}
    answer=artifact.get('answer',{})
    answer=answer if isinstance(answer,dict) else {}
    expected=task['expected']
    errors={k:{'expected':v,'observed':answer.get(k)} for k,v in expected['answer'].items()
            if k not in answer or not equal(v,answer[k])}
    critical=all(k not in errors for k in task['critical_keys']) and artifact.get('status')==expected['status']
    evidence=artifact.get('evidence',[])
    cited=[]; invalid=[]
    for raw in evidence if isinstance(evidence,list) else []:
        m=re.fullmatch(r'([AB]\d{2}R\d+)(?::S\d+)?',raw) if isinstance(raw,str) else None
        if not m or m[1] not in docs or docs[m[1]]['kind']!='source': invalid.append(raw)
        else: cited.append(m[1])
    sufficient=any(set(s).issubset(cited) for s in task['evidence_sets']) and not invalid
    factual=not errors and artifact.get('status')==expected['status']
    return {'schema_valid':valid,'critical_correct':critical,'factual_correct':factual,
            'citation_sufficient':sufficient,'field_errors':errors,'invalid_citations':invalid,
            'success':valid and factual and critical and sufficient}


def retrieval_score(task,result,ranking,docs):
    selected=set(result['selected_ids'])
    sets=[set(s) for s in task['evidence_sets']]
    required=set.union(*sets)
    return {'bundle_complete':any(s.issubset(selected) for s in sets),
        'governing_coverage':max(len(selected&s)/len(s) for s in sets),
        'governing_ids_selected':sorted(selected&required),
        'candidate_bundle_complete':any(s.issubset(ranking['candidate_ids']) for s in sets),
        'eligible_bundle_complete':any(s.issubset(ranking['eligible_ids']) for s in sets),
        'derived_selected':sum(docs[i]['kind']=='derived' for i in selected),
        'flagged_view_selected':sum(i in ranking['view_states'] and ranking['view_states'][i]['state']!='declared_current' for i in selected)}


def verify_freeze():
    freeze=json.loads((HERE/'freeze.json').read_text(encoding='utf8'))
    for rel,digest in freeze['files'].items():
        assert hashlib.sha256((HERE/rel).read_bytes()).hexdigest()==digest, 'Frozen input changed: '+rel
    return freeze


def run(cache):
    from model_runtime import Scorer
    freeze=verify_freeze()
    families=load_bank(); all_docs=docs_for(families)
    scorers={name:Scorer(cache,name) for name in ('minilm','mixedbread')}
    expected_manifest=freeze['model_files']
    for name,model in scorers.items():
        assert model.manifest['files']==expected_manifest[name], 'Frozen model/tokenizer differs'
    score_source=Scores(scorers,cache=True)
    rows=[]; rankings=[]
    jobs=[(f,t,size,a,c) for f in families for t in f['tasks'] for size in (48,144) for a in (0,1) for c in (0,1)]
    random.Random(1011).shuffle(jobs)
    atomic_json(HERE/'retrieval-results.json',{'state':'running','planned_rows':18432,'rows':[]})
    for n,(f,task,size,a,c) in enumerate(jobs,1):
        docs=make_collection(all_docs,f['id'],size)
        for engine in ENGINES:
            ranking=rank_docs(docs,task['query'],bool(a),bool(c),engine,score_source)
            ranking_id=f"K{len(rankings)+1:05}"
            rankings.append({'id':ranking_id,'task_id':task['id'],'family_id':f['id'],'collection_size':size,'cues':a,'gate':c,'engine':engine,**ranking})
            for b,budget in itertools.product((0,1),(4096,8192)):
                result=pack(docs,ranking,bool(a),bool(b),budget)
                rows.append({'id':f'R{len(rows)+1:05}','task_id':task['id'],'family_id':f['id'],
                    'split':split(f['id']),'stratum':f['stratum'],'engine':engine,'factors':f'{a}{b}{c}',
                    'collection_size':size,'budget':budget,'ranking_id':ranking_id,**result,
                    **retrieval_score(task,result,ranking,docs)})
        if n%12==0:
            atomic_json(HERE/'retrieval-results.json',{'state':'running','planned_rows':18432,'rows':rows})
            print(f'Completed {n}/{len(jobs)} query/index/gate groups; {len(rows)} packet comparisons',flush=True)
    assert len(rows)==18432 and len({r['id'] for r in rows})==len(rows)
    atomic_json(HERE/'rankings.json',{'rows':rankings})
    atomic_json(HERE/'retrieval-results.json',{'state':'complete','planned_rows':18432,'rows':rows})
    atomic_json(HERE/'model-execution.json',{'models':{k:v.manifest for k,v in scorers.items()},
        'unique_cached_pair_count':len(score_source.values),'inference_events':score_source.events,
        'timing_limit':'Factorial ranking receipts include score reuse; use timing-results.json for engine latency.'})
    # An outcome-independent development workload measures entire warm rankings
    # with pair caching disabled. Repetitions are timing measurements, not new cases.
    timing=[]
    development=[]
    for author in ('A','B'):
        development.extend(sorted((f for f in families if f['id'].startswith(author) and split(f['id'])=='development'),key=lambda f:f['id'])[:3])
    for f in development:
        docs=make_collection(all_docs,f['id'],144)
        for task in f['tasks']:
            for repeat in range(2):
                engines=list(ENGINES); random.Random(task['id']+str(repeat)).shuffle(engines)
                for engine in engines:
                    uncached=Scores(scorers,cache=False)
                    started=time.perf_counter()
                    ranking=rank_docs(docs,task['query'],True,True,engine,uncached)
                    result=pack(docs,ranking,True,True,4096)
                    timing.append({'task_id':task['id'],'family_id':f['id'],'engine':engine,'repeat':repeat,
                        'seconds':time.perf_counter()-started,'scored_pairs':sum(e['pairs'] for e in uncached.events),
                        'scorer_tokens':sum(e['input_pair_tokens'] for e in uncached.events),
                        'truncated_pairs':sum(e['truncated_pairs'] for e in uncached.events),'packet_bytes':result['bytes']})
    atomic_json(HERE/'timing-results.json',{'state':'complete','rows':timing,'pair_cache_enabled':False,
        'includes_index_construction':True,'excludes_model_load_and_download':True})
    print(f'PASS: {len(rows)} retrieval packets and {len(timing)} uncached warm timing observations.',flush=True)


def selfcheck():
    def doc(i,kind='source',links=(),supersedes=(),ledger=(),scope='all'):
        return dict(id=i,kind=kind,revision=1,authored_at='2026-10-01T00:00:00Z',title=i,
                    scope=scope,body='Blue archive record '+i,links=list(links),supersedes=list(supersedes),
                    incorporates=list(ledger),family_id='A01',branch='a01-blue',aliases=['青灯'],path=i+'.md')
    docs={'A01R01':doc('A01R01'),'A01R02':doc('A01R02',supersedes=['A01R01']),
          'A01R03':doc('A01R03','derived',ledger=[{'id':'A01R01','revision':1}])}
    assert view_states(docs)['A01R03']['state']=='stale'
    ranking=rank_docs(docs,'blue archive',True,True,'bm25',None)
    assert 'A01R03' not in ranking['eligible_ids']
    packed=pack(docs,ranking,True,True,2000)
    assert packed['bytes']<=2000 and set(packed['selected_ids'])=={'A01R01','A01R02'}
    assert packet_for(docs,packed['selected_ids'],True).encode('utf8') and '青灯' in packet_for(docs,packed['selected_ids'],True)
    task={'answer_keys':['value'],'expected':{'status':'hold','answer':{'value':None}},'critical_keys':['value'],'evidence_sets':[['A01R02']]}
    good={'status':'hold','answer':{'value':None,'extra':'allowed'},'evidence':['A01R02:S2','A01R01']}
    assert score_artifact(task,good,docs)['success']
    assert not score_artifact(task,{**good,'status':'ready'},docs)['success']
    assert not score_artifact(task,{**good,'evidence':['A01R03']},docs)['success']
    assert not equal(True,1)
    assert len(FACTORS)==8 and tokens('青灯 λ Café')==['青灯','λ','café']
    assert bm25('archive',['archive retention','banana'])[0]>bm25('archive',['archive retention','banana'])[1]
    # Exact metadata contracts, including deliberately unreliable ledgers.
    for ledger in ([],[{'id':'absent','revision':1}],
                   [{'id':'A01R01','revision':1}]*2):
        broken={**docs,'A01R03':doc('A01R03','derived',ledger=ledger)}
        assert view_states(broken)['A01R03']['state']=='unverifiable'
    wrong={**docs,'A01R03':doc('A01R03','derived',ledger=[{'id':'A01R01','revision':2}])}
    assert view_states(wrong)['A01R03']['state']=='stale'
    scoped={'A01R01':doc('A01R01',scope='manual'),
            'A01R02':doc('A01R02',supersedes=['A01R01'],scope='autonomous'),
            'A01R03':doc('A01R03','derived',ledger=[{'id':'A01R01','revision':1}],scope='manual')}
    assert view_states(scoped)['A01R03']['state']=='declared_current'
    scoped['A01R04']=doc('A01R04',supersedes=['A01R02'],scope='manual')
    scoped['A01R01']['supersedes']=['A01R04']  # cycle terminates
    assert view_states(scoped)['A01R03']['state']=='stale'
    fan={'A01R01':doc('A01R01',links=[f'A01R{i:02}' for i in range(2,22)])}
    fan.update({f'A01R{i:02}':doc(f'A01R{i:02}') for i in range(2,22)})
    seed={'ranked_ids':['A01R01'],'eligible_ids':list(fan)}
    assert len(pack(fan,seed,False,True,100000)['selected_ids'])==17
    assert pack(fan,seed,False,True,1)['selected_ids']==[]
    chain={f'A01R{i:02}':doc(f'A01R{i:02}',links=[f'A01R{i+1:02}'] if i<4 else []) for i in range(1,5)}
    assert pack(chain,{'ranked_ids':['A01R01'],'eligible_ids':list(chain)},False,True,10000)['selected_ids']==['A01R01','A01R02','A01R03']
    assert ranked(['z','a'],{'z':0,'a':0})==['a','z']
    assert not score_artifact(task,good,{'A01R01':docs['A01R01']})['citation_sufficient']
    return {'selfcheck':'passed','model_calls':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selfcheck',action='store_true')
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--make-split',action='store_true')
    parser.add_argument('--cache',type=Path)
    args=parser.parse_args()
    if args.selfcheck: print(dumps(selfcheck()))
    elif args.make_split: write_split(load_bank()); print('PASS: outcome-independent stratified family split written.')
    elif args.run and args.cache: run(args.cache)
    else: parser.error('Use --selfcheck or --run --cache EXTERNAL_DIRECTORY')
