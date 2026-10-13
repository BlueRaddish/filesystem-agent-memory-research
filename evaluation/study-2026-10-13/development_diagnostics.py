"""Development-only, stdlib robustness and nested-budget diagnostics.

Never opens the full bank or confirmation outcomes. Per-cell receipts are flushed
and synced; an interrupted run cannot silently restart over its existing marker.
"""
import argparse
from collections import Counter, defaultdict
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import time

from index_lab import PreparedIndex, sha, tokens
import packing_lab as packing
from study_common import documents, support_metrics

HERE = Path(__file__).resolve().parent
SOURCE_SHA = 'a4b7f77cf2311e1c2cd742df9996ddd5d5b7542b9a0a20f3eb305621f9f9a8fa'
SOURCE_BANK_SHA = '280e6be3f7380ed9c0bc1dbe3ec75dfba136113f230d08751e0f316b67cf9760'
GROUPS = ('dependency-closure', 'map-page-chain', 'queue-limits', 'service-alias')
CONDITIONS = ('baseline', 'iteration_shuffle', 'opaque_ids', 'path_permutation',
              'padding_before', 'padding_after', 'padding_balanced', 'near_alias_cues',
              'near_identifier_records', 'combined_shuffle_opaque_paths')
RANKERS = ('body_bm25', 'entity_rrf', 'graph_diffusion')
PACKERS = ('whole_record', 'sentence_neighbors', 'nested_whole')
BUDGETS = (4096, 8192, 16384)
SEED = 101310
PAD_UNIT = 'devpadzx devpadzx devpadzx.    \n'
PINS = ('DEV-PLAN.md', 'development_diagnostics.py', 'index_lab.py', 'packing_lab.py', 'study_common.py')


def now():
    return datetime.now(timezone.utc).isoformat()


def fdigest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    tmp = path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
    tmp.replace(path)


def private_root(path):
    path = path.resolve()
    assert not path.is_relative_to(HERE.parents[1]), 'Private excerpt/receipts must be outside Git'
    return path


def load(root):
    path = root/'dev-bank.json'
    assert fdigest(path) == SOURCE_SHA
    data = json.loads(path.read_bytes())
    assert data['source_bank_sha256'] == SOURCE_BANK_SHA
    families = data['families']
    assert len(families) == 24 and all(f['split'] == 'development' for f in families)
    assert Counter(f['template_family'] for f in families) == Counter({g: 6 for g in GROUPS})
    docs = documents(families)
    tasks = []
    for family in families:
        for task in family['tasks']:
            tasks.append({k: copy.deepcopy(task[k]) for k in ('id', 'query', 'evidence_sets', 'evidence_spans')} |
                         {'template_group': family['template_family'], 'history': family['id']})
    assert len(tasks) == 72 and len({t['id'] for t in tasks}) == 72
    assert 'devpadzx' not in set(tokens(' '.join(t['query'] for t in tasks)))
    for task in tasks:
        for alternative in task['evidence_spans']:
            for span in alternative:
                assert span['id'] in docs and docs[span['id']]['kind'] == 'source'
                assert 0 <= span['start'] < span['end'] <= len(docs[span['id']]['body'])
    return docs, tasks


def id_pattern(ids):
    return re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(i) for i in sorted(ids, key=lambda i: (-len(i), i)))+r')(?!\w)')


def opaque_map(ids):
    result, used = {}, set()
    for old in sorted(ids):
        assert old.isascii()
        nonce = 0
        while True:
            raw = hashlib.sha256(f'dev-opaque:{SEED}:{old}:{nonce}'.encode()).digest()
            value = ''.join('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'[raw[n % len(raw)] % 36] for n in range(len(old)))
            if value not in used and value not in ids:
                break
            nonce += 1
        used.add(value); result[old] = value
    assert len(set(result.values())) == len(ids)
    return result


def near_map(ids):
    used, result = set(ids), {}
    for old in sorted(ids):
        for position in reversed(range(len(old))):
            for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789':
                value = old[:position]+letter+old[position+1:]
                if value not in used and letter != old[position]:
                    used.add(value); result[old] = value
                    break
            if old in result:
                break
        assert old in result
    return result


def transformed(docs, tasks, condition):
    out, queries = copy.deepcopy(docs), copy.deepcopy(tasks)
    pattern = id_pattern(docs)
    positions = [{'query_id': t['id'], 'positions': [[m.start(), m.end()] for m in pattern.finditer(t['query'])]}
                 for t in tasks if pattern.search(t['query'])]
    receipt = {'condition': condition, 'literal_id_queries': len(positions),
               'query_literal_id_positions_sha256': sha(positions), 'record_count': len(out)}
    if condition in ('opaque_ids', 'combined_shuffle_opaque_paths'):
        mapping = opaque_map(docs)
        replace = lambda text: pattern.sub(lambda m: mapping[m.group()], text)
        renamed = {}
        body_occurrences, alias_occurrences = 0, 0
        for old, doc in out.items():
            body_occurrences += len(pattern.findall(doc['body']))
            alias_occurrences += sum(len(pattern.findall(a)) for a in doc.get('aliases', []))
            doc['id'] = mapping[old]
            for field in ('body', 'title', 'scope', 'path', 'branch'):
                if field in doc:
                    doc[field] = replace(doc[field])
            doc['aliases'] = [replace(a) for a in doc.get('aliases', [])]
            for field in ('links', 'supersedes'):
                doc[field] = [mapping.get(i, i) for i in doc.get(field, [])]
            for ref in doc.get('incorporates', []):
                ref['id'] = mapping.get(ref['id'], ref['id'])
            assert len(doc['body']) == len(docs[old]['body'])
            renamed[doc['id']] = doc
        out = renamed
        for task in queries:
            task['query'] = replace(task['query'])
            task['evidence_sets'] = [[mapping[i] for i in alternative] for alternative in task['evidence_sets']]
            for alternative in task['evidence_spans']:
                for span in alternative:
                    old = span['id']; span['id'] = mapping[old]
                    assert out[span['id']]['body'][span['start']:span['end']] == replace(docs[old]['body'][span['start']:span['end']])
        receipt.update(mapping_sha256=sha(mapping), body_literal_ID_occurrences=body_occurrences, alias_literal_ID_occurrences=alias_occurrences)
    if condition in ('path_permutation', 'combined_shuffle_opaque_paths'):
        ids = sorted(out)
        paths = sorted((d.get('path', '') for d in out.values()), key=lambda p: hashlib.sha256(f'dev-path:{SEED}:{p}'.encode()).hexdigest())
        for n, i in enumerate(ids):
            out[i]['path'] = f'permuted/{n%7}/depth/{n%11}/'+paths[n].replace('/', '_')
    if condition in ('iteration_shuffle', 'combined_shuffle_opaque_paths'):
        items = list(out.items()); random.Random(SEED).shuffle(items); out = dict(items)
    if condition.startswith('padding_'):
        assert len(PAD_UNIT.encode('ascii')) == 32
        before_units = {'padding_before': 128, 'padding_after': 0, 'padding_balanced': 64}[condition]
        before, after = PAD_UNIT*before_units, PAD_UNIT*(128-before_units)
        for doc in out.values():
            doc['body'] = before+'\n'+doc['body']+'\n'+after
        shift = len(before)+1
        for task in queries:
            for alternative in task['evidence_spans']:
                for span in alternative:
                    old_text = docs[span['id']]['body'][span['start']:span['end']]
                    span['start'] += shift; span['end'] += shift
                    assert out[span['id']]['body'][span['start']:span['end']] == old_text
        receipt.update(added_ascii_bytes_per_body=4098, prefix_chars=shift, padding_token_multiset_sha256=sha(Counter(tokens(before+after))))
    if condition in ('near_alias_cues', 'near_identifier_records'):
        near = near_map(out)
        # Query-aware adversarial cues use observable identifiers, never labels.
        cue_pattern = re.compile(r'(?<!\w)[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*(?!\w)')
        cues = sorted({v for t in tasks for v in cue_pattern.findall(t['query']) if any(c.isdigit() for c in v)})
        assert cues
        cue_near = near_map(cues)
        cue_values = [cue_near[v] for v in cues]
        if condition == 'near_alias_cues':
            ids = sorted(out)
            for n, i in enumerate(ids):
                out[i]['aliases'].append(cue_values[n%len(cue_values)])
        else:
            for n, (old, i) in enumerate(near.items()):
                cue = cue_values[n%len(cue_values)]
                out[i] = {'id': i, 'kind': 'source', 'revision': 1, 'authored_at': '', 'title': 'Reference marker', 'scope': 'all',
                          'body': f'Reference marker {cue}. No governing claim is recorded here.',
                          'aliases': [cue], 'links': [], 'supersedes': [], 'incorporates': [], 'path': 'markers/'+i+'.md'}
        receipt.update(near_identifier_mapping_sha256=sha(near), added_records=len(out)-len(docs),
                       near_query_cue_mapping_sha256=sha(cue_near), observable_query_identifier_cues=len(cues),
                       near_query_cue_queries=sum(any(v in cue_near for v in cue_pattern.findall(t['query'])) for t in tasks))
    receipt.update(record_count=len(out), documents_sha256=sha(out), query_projection_sha256=sha([t['query'] for t in queries]))
    return out, queries, receipt


def nested_packets(docs, query, candidates):
    first = packing.pack(docs, query, candidates, BUDGETS[0], 'whole_record')
    output = {BUDGETS[0]: first}
    observations, pieces = list(first['observations']), [packing._piece(docs[o['id']], o, True) for o in first['observations']]
    selected = {o['id'] for o in observations}
    for budget in BUDGETS[1:]:
        for i in candidates:
            if i in selected:
                continue
            obs = packing._observation(docs[i], 0, len(docs[i]['body']))
            piece = packing._piece(docs[i], obs, True)
            prospective = '\n\n'.join(pieces+[piece])
            if len(prospective.encode('utf-8')) <= budget:
                pieces.append(piece); observations.append(obs); selected.add(i)
        text = '\n\n'.join(pieces)
        output[budget] = {'packet': text, 'bytes': len(text.encode('utf-8')), 'observations': list(observations), 'ids': list(selected)}
    for low, high in zip(BUDGETS, BUDGETS[1:]):
        assert output[high]['packet'].encode('utf-8').startswith(output[low]['packet'].encode('utf-8'))
        assert {o['id'] for o in output[low]['observations']} <= {o['id'] for o in output[high]['observations']}
    return output


def evaluate(task, docs, ranked, candidates, packet, budget, packer):
    assert packet['bytes'] == len(packet['packet'].encode('utf-8')) <= budget
    verbose = packer in ('whole_record', 'nested_whole')
    assert packet['packet'] == '\n\n'.join(packing._piece(docs[o['id']], o, verbose) for o in packet['observations'])
    metrics = support_metrics(task, packet['observations'], docs)
    result = {'span_bundle': metrics['declared_span_bundle_recovered'],
              'whole_bundle': metrics['declared_whole_bundle_recovered'], 'span_fraction': metrics['best_declared_span_fraction'],
              'bytes_used': packet['bytes'], 'fault': False, 'packet_sha256': sha(packet['packet']), 'ranking_sha256': sha(ranked),
              'source_intervals_sha256': sha([(o['id'], o['start'], o['end']) for o in packet['observations']]),
              'observed_source_ids': sorted({o['id'] for o in packet['observations']}),
              'observed_source_intervals': [[o['id'], o['start'], o['end']] for o in packet['observations']]}
    alternatives = task['evidence_sets']
    for k in (8, 16, 32):
        result[f'candidate_bundle_{k}'] = any(set(ids) <= set(ranked[:k]) for ids in alternatives)
        result[f'candidate_any_{k}'] = any(set(ids) & set(ranked[:k]) for ids in alternatives)
    result['filtered_candidate_bundle_32'] = any(set(ids) <= set(candidates) for ids in alternatives)
    costs = [sum(len(packing._piece(docs[i], packing._observation(docs[i], 0, len(docs[i]['body'])), verbose).encode('utf-8')) for i in ids)+2*max(0,len(ids)-1) for ids in alternatives]
    result['whole_byte_bound_possible'] = min(costs) <= budget
    return result


def pins():
    return {name: fdigest(HERE/name) for name in PINS}


def freeze(root):
    assert not (root/'development-freeze.json').exists()
    docs, tasks = load(root)
    receipt = {'schema_version': 1, 'frozen_at_utc': now(), 'source_excerpt_sha256': SOURCE_SHA, 'source_bank_sha256': SOURCE_BANK_SHA,
               'implementation_sha256': pins(), 'conditions': list(CONDITIONS), 'rankers': list(RANKERS), 'packers': list(PACKERS),
               'budgets': list(BUDGETS), 'seed': SEED, 'development_histories': 24, 'development_queries': 72,
               'development_template_groups': list(GROUPS), 'base_records': len(docs), 'scheduled_packets': 19440}
    receipt['freeze_sha256'] = sha(receipt)
    save(root/'development-freeze.json', receipt)
    save(HERE/'development-results.json', {'state': 'prospectively_frozen_no_scored_results', 'freeze': receipt})
    return receipt


def verify(root):
    receipt = json.loads((root/'development-freeze.json').read_bytes())
    assert receipt['implementation_sha256'] == pins()
    assert receipt['freeze_sha256'] == sha({k:v for k,v in receipt.items() if k != 'freeze_sha256'})
    return receipt


def execute(root):
    frozen = verify(root)
    marker, destination = root/'development-started.json', root/'development-packets.jsonl'
    assert not marker.exists() and not destination.exists(), 'Existing run/partial receipts require an explicit amendment; no silent restart'
    save(marker, {'started_at_utc': now(), 'freeze_sha256': frozen['freeze_sha256'], 'scheduled_packets': 19440})
    base_docs, base_tasks = load(root)
    transforms, timing, fault_counts = [], [], Counter()
    with destination.open('x', encoding='utf-8', newline='\n') as stream:
        for condition in CONDITIONS:
            docs, tasks, transform = transformed(base_docs, base_tasks, condition)
            transforms.append(transform)
            clock = time.perf_counter(); index = PreparedIndex(docs)
            timing.append({'condition': condition, 'index_build_seconds': time.perf_counter()-clock})
            for task in tasks:
                for ranker in RANKERS:
                    try:
                        ranked = index.rank(task['query'], ranker)
                        assert len(ranked) == len(docs) and set(ranked) == set(docs)
                        candidates = [i for i in ranked if docs[i]['kind'] == 'source'][:32]
                        ranking_error = None
                    except Exception as exc:
                        ranking_error = exc
                    for packer in PACKERS:
                        nested, nested_error = None, None
                        if packer == 'nested_whole' and ranking_error is None:
                            try:
                                nested = nested_packets(docs, task['query'], candidates)
                            except Exception as exc:
                                nested_error = exc
                        for budget in BUDGETS:
                            row = {'condition': condition, 'qid': task['id'], 'history': task['history'], 'template_group': task['template_group'],
                                   'literal_ID_query': bool(id_pattern(docs).search(task['query'])), 'ranker': ranker, 'packer': packer, 'budget': budget}
                            try:
                                if ranking_error:
                                    raise ranking_error
                                if nested_error:
                                    raise nested_error
                                packet = nested[budget] if packer == 'nested_whole' else packing.pack(docs, task['query'], candidates, budget, packer)
                                row.update(evaluate(task, docs, ranked, candidates, packet, budget, packer))
                            except Exception as exc:
                                fault_counts[type(exc).__name__] += 1
                                row.update(fault=True, error_type=type(exc).__name__, error_sha256=sha(str(exc)),
                                           span_bundle=False, whole_bundle=False, span_fraction=0.0, bytes_used=None,
                                           candidate_bundle_8=None, candidate_bundle_16=None, candidate_bundle_32=None,
                                           candidate_any_8=None, candidate_any_16=None, candidate_any_32=None,
                                           filtered_candidate_bundle_32=None, whole_byte_bound_possible=None,
                                           observed_source_ids=[], observed_source_intervals=[])
                            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False)+'\n')
                            stream.flush(); os.fsync(stream.fileno())
            del index
    completion = {'completed_at_utc': now(), 'freeze_sha256': frozen['freeze_sha256'], 'rows_sha256': fdigest(destination),
                  'fault_counts': dict(fault_counts), 'transformations': transforms, 'index_operational_timing': timing}
    save(root/'development-completed.json', completion)
    return completion


def metric_summary(rows, metrics):
    observed = {k: [float(r[k]) for r in rows if r[k] is not None] for k in metrics}
    return ({k: sum(v)/len(v) if v else None for k,v in observed.items()},
            {k: len(v) for k,v in observed.items()})


def transition_summary(pairs, packer):
    assessed = [(a,b) for a,b in pairs if not a['fault'] and not b['fault']]
    loses = sum(a['span_bundle'] and not b['span_bundle'] for a,b in assessed)
    lost_ids = sum(not set(a['observed_source_ids']) <= set(b['observed_source_ids']) for a,b in assessed)
    lost_intervals = sum(not set(map(tuple,a['observed_source_intervals'])) <= set(map(tuple,b['observed_source_intervals'])) for a,b in assessed)
    if packer == 'nested_whole':
        assert loses == lost_ids == lost_intervals == 0
    return {'span_success_losses': loses, 'source_ID_exposure_losses': lost_ids,
            'source_interval_exposure_losses': lost_intervals,
            'assessed_successful_pairs': len(assessed), 'unassessed_fault_pairs': len(pairs)-len(assessed), 'queries': len(pairs)}


def equivalent_pair(row, baseline):
    if row['fault'] or baseline['fault']:
        return None
    assert row['ranking_sha256'] == baseline['ranking_sha256'] and row['packet_sha256'] == baseline['packet_sha256']
    return True


def byte_deltas(pairs):
    observed = [(a,b) for a,b in pairs if a['bytes_used'] is not None and b['bytes_used'] is not None]
    groups = defaultdict(list)
    for a,b in observed:
        groups[a.get('template_group', 'fixture')].append(a['bytes_used']-b['bytes_used'])
    expected = {a.get('template_group', 'fixture') for a,b in pairs}
    mean = (sum(sum(v)/len(v) for v in groups.values())/len(expected)) if groups and set(groups)==expected else None
    return {'mean_byte_delta': mean, 'observed_byte_pairs': len(observed), 'unobserved_byte_pairs': len(pairs)-len(observed),
            'observed_byte_template_groups': len(groups)}


def summarize(root):
    frozen = verify(root)
    completion = json.loads((root/'development-completed.json').read_bytes())
    assert completion['freeze_sha256'] == frozen['freeze_sha256'] and completion['rows_sha256'] == fdigest(root/'development-packets.jsonl')
    rows = [json.loads(line) for line in (root/'development-packets.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows) == 19440 and len({(r['condition'],r['qid'],r['ranker'],r['packer'],r['budget']) for r in rows}) == 19440
    baseline = {(r['qid'],r['ranker'],r['packer'],r['budget']):r for r in rows if r['condition']=='baseline'}
    cells, profiles, paired, budget_transitions = [], [], [], []
    bykey = {(r['condition'],r['qid'],r['ranker'],r['packer'],r['budget']):r for r in rows}
    numeric = ('span_bundle','whole_bundle','span_fraction','bytes_used','fault','candidate_bundle_8','candidate_bundle_16','candidate_bundle_32',
               'candidate_any_8','candidate_any_16','candidate_any_32','filtered_candidate_bundle_32','whole_byte_bound_possible')
    for condition in CONDITIONS:
        for ranker in RANKERS:
            for packer in PACKERS:
                for budget in BUDGETS:
                    group = [r for r in rows if (r['condition'],r['ranker'],r['packer'],r['budget'])==(condition,ranker,packer,budget)]
                    assert len(group)==72
                    means, counts = [], []
                    for template in GROUPS:
                        selected=[r for r in group if r['template_group']==template]; assert len(selected)==18
                        mean,count=metric_summary(selected,numeric); means.append(mean); counts.append(count)
                        profiles.append({'condition':condition,'ranker':ranker,'packer':packer,'budget':budget,'template_group':template,'queries':18,
                                         'metric_observed_cells':count,**mean})
                    cells.append({'condition':condition,'ranker':ranker,'packer':packer,'budget':budget,'queries':72,
                                  'span_bundle_count':sum(r['span_bundle'] for r in group),
                                  'metric_observed_cells':{k:sum(c[k] for c in counts) for k in numeric},
                                  **{k:sum(m[k] for m in means)/4 if all(m[k] is not None for m in means) else None for k in numeric}})
                    deltas=[int(r['span_bundle'])-int(baseline[(r['qid'],ranker,packer,budget)]['span_bundle']) for r in group]
                    paired.append({'condition':condition,'ranker':ranker,'packer':packer,'budget':budget,'gains':deltas.count(1),'ties':deltas.count(0),'regressions':deltas.count(-1),
                                   'paired_scheduled_queries':72,
                                   'fault_pairs':sum(r['fault'] or baseline[(r['qid'],ranker,packer,budget)]['fault'] for r in group),
                                   **byte_deltas([(r,baseline[(r['qid'],ranker,packer,budget)]) for r in group])})
                for low,high in zip(BUDGETS,BUDGETS[1:]):
                    pairs=[(bykey[(condition,t['qid'],ranker,packer,low)],bykey[(condition,t['qid'],ranker,packer,high)]) for t in rows if t['condition']=='baseline' and t['ranker']==ranker and t['packer']==packer and t['budget']==low]
                    assert len(pairs)==72
                    budget_transitions.append({'condition':condition,'ranker':ranker,'packer':packer,'from_budget':low,'to_budget':high,
                                               **transition_summary(pairs,packer)})
    equivalence_counts=[]
    for condition in ('iteration_shuffle','path_permutation'):
        assessed=unassessed=0
        for row in rows:
            if row['condition']==condition:
                original=baseline[(row['qid'],row['ranker'],row['packer'],row['budget'])]
                if equivalent_pair(row,original): assessed+=1
                else: unassessed+=1
        equivalence_counts.append({'condition':condition,'assessed_successful_pairs':assessed,'unassessed_fault_pairs':unassessed})
    # Per-query receipts retain intervals privately. Public output is aggregate.
    output={'schema_version':1,'state':'completed_development_only_exploratory_diagnostics','freeze':frozen,'completion':completion,
            'scheduled_packets':19440,'executed_packets':len(rows),'failed_cells':sum(r['fault'] for r in rows),'cells':cells,
            'template_group_cells':profiles,'paired_vs_baseline':paired,'budget_transitions':budget_transitions,'feature_equivalence_checks':equivalence_counts,
            'confirmation_gold_or_main_results_read':False,'models_or_provider_calls_used':False,
            'limitations':['Four authored development groups, not confirmation or human data.',
                           'Source-kind filtering and nested packing are separate exploratory adaptations.',
                           'Layout/iteration equivalence is an implemented-feature boundary, not navigation robustness.',
                           'Padding changes byte ceilings and length normalization; near-marker insertion changes corpus statistics.']}
    save(HERE/'development-results.json',output)
    return {'state':output['state'],'packets':len(rows),'failed_cells':output['failed_cells'],'public_result_sha256':fdigest(HERE/'development-results.json')}


def self_check():
    docs={'A1':{'id':'A1','kind':'source','revision':1,'scope':'all','body':'α A1 threshold. qualifier applies.',
                'title':'A1','aliases':['A1'],'links':['B1'],'supersedes':[],'incorporates':[],'path':'x/A1.md'},
          'B1':{'id':'B1','kind':'source','revision':1,'scope':'all','body':'β B1 threshold.',
                'title':'B1','aliases':['B1'],'links':[],'supersedes':['A1'],'incorporates':[{'id':'A1','revision':1}],'path':'x/B1.md'}}
    tasks=[{'id':'q','query':'What is A1 threshold?','history':'f','template_group':GROUPS[0],
            'evidence_sets':[['A1']],'evidence_spans':[[{'id':'A1','start':0,'end':len(docs['A1']['body'])}]]}]
    for condition in CONDITIONS:
        changed,queries,_=transformed(docs,tasks,condition)
        assert len(queries)==1
        span=queries[0]['evidence_spans'][0][0]
        assert span['end']-span['start']==len(docs['A1']['body'])
        if condition=='opaque_ids':
            assert 'A1' not in changed and 'A1' not in queries[0]['query']
            mapping=opaque_map(docs)
            assert changed[mapping['A1']]['links']==[mapping['B1']]
            assert changed[mapping['B1']]['incorporates'][0]['id']==mapping['A1']
    chain=nested_packets(docs,tasks[0]['query'],list(docs))
    for budget,packet in chain.items():
        assert evaluate(tasks[0],docs,list(docs),list(docs),packet,budget,'nested_whole')['span_bundle']
    # A high-ranked 5KB original is skipped at 4KB but fits at 8KB; a later
    # required original fits only in the nested packet once early choices persist.
    large=copy.deepcopy(docs)
    large['A1']['body']='x '*2450
    large['B1']['body']='required '*400
    greedy={b:packing.pack(large,'required',['A1','B1'],b,'whole_record') for b in BUDGETS}
    nested=nested_packets(large,'required',['A1','B1'])
    assert 'B1' in greedy[4096]['ids'] and 'B1' not in greedy[8192]['ids']
    assert 'B1' in nested[8192]['ids']
    # A failed cell has no cost observation, no hash-equality assessment and no
    # successful-pair monotonicity claim. It remains a failure in primary recovery.
    success={'fault':False,'span_bundle':True,'bytes_used':100,'observed_source_ids':['A1'],
             'observed_source_intervals':[['A1',0,3]],'ranking_sha256':'rank','packet_sha256':'packet'}
    failure={'fault':True,'span_bundle':False,'bytes_used':None,'observed_source_ids':[],'observed_source_intervals':[]}
    means,counts=metric_summary([success,failure],('bytes_used','span_bundle'))
    assert means['bytes_used']==100 and counts['bytes_used']==1 and means['span_bundle']==.5
    assert equivalent_pair(failure,success) is None
    diagnostic=transition_summary([(success,success),(success,failure)],'nested_whole')
    assert diagnostic['assessed_successful_pairs']==1 and diagnostic['unassessed_fault_pairs']==1 and diagnostic['span_success_losses']==0
    assert byte_deltas([(success,failure)])['mean_byte_delta'] is None
    assert byte_deltas([(success,success),(success,failure)])['observed_byte_pairs']==1
    return {'self_check':'passed','models_loaded':False,'fixture_only':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-root',type=Path)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--self-check',action='store_true');group.add_argument('--freeze',action='store_true')
    group.add_argument('--execute',action='store_true');group.add_argument('--summarize',action='store_true')
    args=parser.parse_args()
    if args.self_check: result=self_check()
    else:
        assert args.private_root is not None
        root=private_root(args.private_root)
        if args.freeze: self_check();result=freeze(root)
        elif args.execute: result=execute(root)
        else: result=summarize(root)
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
