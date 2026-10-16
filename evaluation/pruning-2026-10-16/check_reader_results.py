"""Independent read-only reconstruction and mechanical recount of reader data.

No collector, staging, scoring or reader helper is imported. Common instruction
and schema literals are parsed from the hash-bound helper with ast.literal_eval;
selection, packet construction, assignment, validation and scoring are separately
implemented here. This checker does not grade explanation entailment.
"""
import argparse
import ast
import copy
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import time


HERE = Path(__file__).resolve().parent
FAMILIES = ('periodic_corrections', 'standing_constraint', 'dormant_reactivation',
            'historical_rollback', 'cross_project', 'lexical_clutter',
            'topic_shift', 'expiring_exception')
ARMS = ('all|off|global', 'ttl8|off|global', 'ttl8|scheduled_cold|global',
        'latest_dependencies|off|linked')
ALL_ARMS = {'|'.join(a) for a in itertools.product(
    ('all', 'ttl8', 'lru96', 'lfu96', 'latest', 'latest_dependencies', 'random96'),
    ('off', 'unresolved_only', 'scheduled_cold'), ('global', 'project', 'linked'))}
TASKS = ('current', 'standing')
QUESTION_KEYS = ('project', 'key', 'asof', 'epoch', 'cue')
ANSWER_KEYS = {'case_id', 'value', 'governing', 'citations', 'supported', 'missing_refs', 'explanation'}
METRICS = ('gold_support_in_packet', 'value_agreement', 'governing_agreement',
           'gold_citations_and_value', 'unsupported_citation', 'abstention',
           'reader_reports_supported', 'abstention_when_gold_missing', 'abstention_with_gold_available')
ACCEPTED_SEAL = 'b5bddbda9073ad9ef8961c5c6ab3e5d964a3c5e5c7b61a5cc0002320cf70458b'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + '\n').encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_hash(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            result.update(chunk)
    return result.hexdigest()


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def constant(token):
        raise AssertionError('nonfinite JSON constant')
    def floating(token):
        value = float(token)
        require(math.isfinite(value), 'nonfinite JSON number')
        return value
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant, parse_float=floating)


def load(path, limit=16 * 1024 * 1024):
    require(path.is_file() and not path.is_symlink(), 'missing or symlinked JSON file: ' + path.name)
    require(path.stat().st_size <= limit, 'oversized JSON file: ' + path.name)
    return decode(path.read_text(encoding='utf-8'))


def same(actual, expected, message):
    require(canonical(actual) == canonical(expected), message)


def helper_literals():
    wanted = {'INSTRUCTIONS', 'OUTPUT_SCHEMA'}
    found = {}
    for node in ast.parse((HERE / 'reader_followup.py').read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in wanted:
                    found[target.id] = ast.literal_eval(node.value)
    require(set(found) == wanted, 'missing hash-bound common prompt literals')
    return found['INSTRUCTIONS'], found['OUTPUT_SCHEMA']


def truth_from_sources(query, byid):
    eligible = [s for s in byid.values() if s['created'] <= query['epoch'] and
                s['project'] == query['project'] and s['key'] == query['key'] and
                s['effective'] <= query['asof'] and
                (s['expires'] is None or query['asof'] < s['expires'])]
    require(eligible, 'full-source query has no governing assertion')
    winner = max(eligible, key=lambda s: (s['effective'], s['created'], s['id']))
    required, pending = set(), [winner['id']]
    while pending:
        ident = pending.pop()
        if ident not in required:
            require(ident in byid and byid[ident]['created'] <= query['epoch'], 'unavailable gold dependency')
            required.add(ident)
            pending.extend(byid[ident]['refs'])
    return {'value': winner['value'], 'governing': winner['id'], 'required': sorted(required)}


def reconstruct(directory):
    run = HERE / 'run'
    require(file_hash(HERE / 'seal.json') == ACCEPTED_SEAL, 'changed accepted main seal')
    seal, main_manifest = load(HERE / 'seal.json'), load(run / 'manifest.json')
    bindings = {}
    for name, expected in seal['sha256'].items():
        require(Path(name).name == name and file_hash(HERE / name) == expected, 'changed sealed source')
        bindings[name] = expected
    for name, expected in main_manifest['sha256'].items():
        require(Path(name).name == name and file_hash(run / name) == expected, 'changed main raw artifact')
        bindings['run/' + name] = expected
    for name in ('seal.json', 'READER-PLAN.md', 'reader_followup.py', 'run/manifest.json'):
        bindings[name] = file_hash(HERE / name)
    bank = load(run / 'source-bank.json')
    expected_worlds = {f'{f}-s{s}-{d}' for f, s, d in itertools.product(FAMILIES, range(2), ('low', 'high'))}
    require(len(bank) == 32 and {w['id'] for w in bank} == expected_worlds, 'main world census')
    sources, queries, targets = {}, {}, {}
    for world in bank:
        byid = {s['id']: s for s in world['sources']}
        require(len(byid) == len(world['sources']), 'duplicate main source ID')
        for source in byid.values():
            raw = source['text'].encode('utf-8')
            require(len(raw) == source['bytes'] and sha(raw) == source['sha256'], 'main source hash/bytes')
            require(source['text'].startswith('ASSERT '), 'source ASSERT header')
            claim = decode(source['text'].split('\n', 1)[0][7:])
            same(claim, {k: source[k] for k in ('id', 'created', 'effective', 'expires', 'project', 'key', 'value', 'refs')},
                 'source metadata/body disagreement')
        sources[world['id']] = byid
        for query in world['queries']:
            require(query['id'] not in queries and query['world'] == world['id'], 'duplicate/wrong-world query')
            queries[query['id']] = query
            if (world['family'] in FAMILIES[2:] and world['seed'] == 0 and world['density'] == 'high'
                    and query['epoch'] == 32 and query['task'] in TASKS):
                targets[query['id']] = (FAMILIES[2:].index(world['family']), TASKS.index(query['task']))
    require(len(queries) == 1024 and len(targets) == 12, 'fixed probe census')
    expected_main = {(qid, arm) for qid in queries for arm in ALL_ARMS}
    seen, selected_trials = set(), {}
    with gzip.open(run / 'trials.jsonl.gz', 'rt', encoding='utf-8') as stream:
        for line in stream:
            trial = decode(line)
            key = trial['query'], trial['arm']
            require(key in expected_main and key not in seen, 'main trial Cartesian census')
            require(trial['world'] == queries[trial['query']]['world'], 'trial source world')
            seen.add(key)
            if trial['query'] in targets and trial['arm'] in ARMS:
                selected_trials[key] = trial
    require(seen == expected_main and len(selected_trials) == 48, 'missing main trial or fixed probe')
    main_gold = load(run / 'gold.json')
    instructions, schema = helper_literals()
    inboxes = [{'schema_version': 1, 'instructions': instructions, 'output_schema': copy.deepcopy(schema), 'cases': []}
               for _ in range(8)]
    mapping = {'schema_version': 1, 'cases': {}}
    for qid, (family_index, task_index) in sorted(targets.items(), key=lambda pair: pair[1]):
        query = queries[qid]
        byid = sources[query['world']]
        truth = truth_from_sources(query, byid)
        same(main_gold[qid], truth, 'independently replayed probe gold')
        for arm_index, arm in enumerate(ARMS):
            trial = selected_trials[qid, arm]
            selected = trial['selected']
            require(selected == [i for call in trial['calls'] for i in call['selected']] and
                    len(selected) == len(set(selected)), 'selected source order/uniqueness')
            require(all(i in byid and byid[i]['created'] <= 32 for i in selected), 'unavailable packet source')
            packet = ''.join('<SOURCE ' + i + '>\n' + byid[i]['text'] + '\n</SOURCE>\n' for i in selected)
            raw = packet.encode('utf-8')
            require(len(raw) == trial['bytes'] <= 8192, 'exact reconstructed packet bytes/cap')
            opaque = sha(('pruning-reader-v1:' + qid + arm).encode('utf-8'))[:24]
            require(opaque not in mapping['cases'], 'opaque collision')
            context = (2 * family_index + task_index + 2 * arm_index) % 8
            case = {'case_id': opaque, 'question': {k: query[k] for k in sorted(QUESTION_KEYS)},
                    'packet': packet, 'packet_sha256': sha(raw), 'packet_bytes': len(raw)}
            inboxes[context]['cases'].append(case)
            mapping['cases'][opaque] = {'query': qid, 'world': query['world'], 'family': FAMILIES[2:][family_index],
                'task': TASKS[task_index], 'arm': arm, 'context': context, 'selected': selected,
                'packet_sha256': sha(raw), 'gold': truth,
                'referenced': sorted({r for i in selected for r in byid[i]['refs']})}
    artifacts = {f'inbox-{i:02d}.json': encoded(inbox) for i, inbox in enumerate(inboxes)}
    artifacts['mapping.json'] = encoded(mapping)
    for index, inbox in enumerate(inboxes):
        require(len(inbox['cases']) == 6, 'six cases per fresh context')
        require({mapping['cases'][c['case_id']]['family'] for c in inbox['cases']} == set(FAMILIES[2:]),
                'one scenario per context')
        require({mapping['cases'][c['case_id']]['task'] for c in inbox['cases']} == {TASKS[index % 2]},
                'declared context/task parity')
    manifest = {'state': 'STAGED_FIXED_READER_SAMPLE', 'planned_cases': 48, 'staged_cases': 48,
        'contexts': 8, 'cases_per_context': 6, 'requested_model': 'gpt-6.1-sol',
        'selected_families': list(FAMILIES[2:]), 'seed': 0, 'density': 'high', 'epoch': 32,
        'tasks': list(TASKS), 'arms': list(ARMS), 'source_bindings': bindings,
        'input_hashes': {name: sha(raw) for name, raw in artifacts.items()},
        'prompt_bytes': {f'inbox-{i:02d}.json': {'serialized_input': len(artifacts[f'inbox-{i:02d}.json']),
            'packet_bytes': sum(c['packet_bytes'] for c in inbox['cases']),
            'question_bytes': sum(len(canonical(c['question']).encode('utf-8')) for c in inbox['cases']),
            'common_instruction_bytes': len(instructions.encode('utf-8')),
            'output_schema_bytes': len(canonical(schema).encode('utf-8'))} for i, inbox in enumerate(inboxes)},
        'collection_contract': 'Missing or invalid batches remain in the planned denominator; no output overwrite or retry.'}
    artifacts['sampling-manifest.json'] = encoded(manifest)
    for name, expected in artifacts.items():
        path = directory / name
        require(path.is_file() and not path.is_symlink() and path.read_bytes() == expected,
                'independent staged-byte reconstruction: ' + name)
    return inboxes, mapping, manifest, artifacts


def validate_batch(output, cases, mapping):
    require(isinstance(output, dict) and set(output) == {'answers'} and isinstance(output['answers'], list),
            'invalid top-level output')
    expected = {c['case_id'] for c in cases}
    require(len(output['answers']) == len(expected), 'wrong answer count')
    accepted = {}
    for answer in output['answers']:
        require(isinstance(answer, dict) and set(answer) == ANSWER_KEYS, 'wrong answer fields')
        ident = answer['case_id']
        require(isinstance(ident, str) and ident in expected and ident not in accepted, 'wrong/duplicate case ID')
        require(answer['value'] is None or isinstance(answer['value'], str), 'wrong value type')
        require(answer['governing'] is None or isinstance(answer['governing'], str), 'wrong governing type')
        require(type(answer['supported']) is bool and isinstance(answer['explanation'], str), 'wrong support/explanation type')
        for field in ('citations', 'missing_refs'):
            require(isinstance(answer[field], list) and all(isinstance(i, str) for i in answer[field]) and
                    len(answer[field]) == len(set(answer[field])), 'wrong reference/citation list')
        item = mapping[ident]
        present = set(item['selected'])
        require(set(answer['citations']) <= present, 'citation outside case packet')
        require(answer['governing'] is None or answer['governing'] in present, 'governing outside case packet')
        require(set(answer['missing_refs']) <= set(item['referenced']) - present, 'invented or present missing ref')
        accepted[ident] = answer
    require(set(accepted) == expected, 'missing case ID')
    return accepted


def tally(rows):
    return {'planned': len(rows), 'valid': sum(r['status'] == 'valid' for r in rows),
            'missing': sum(r['status'] == 'missing' for r in rows),
            'invalid': sum(r['status'] == 'invalid' for r in rows),
            **{key: sum(r[key] for r in rows) for key in METRICS}}


def recount(directory, inboxes, mapping, manifest, artifacts):
    answers, statuses, hashes, errors, unsupported = {}, {}, {}, [], set()
    for batch, inbox in enumerate(inboxes):
        name = f'out-{batch:02d}.json'
        path = directory / name
        ids = {c['case_id'] for c in inbox['cases']}
        if not path.exists():
            hashes[name] = None
            statuses.update({i: 'missing' for i in ids})
            continue
        hashes[name] = file_hash(path) if path.is_file() and not path.is_symlink() else None
        try:
            output = load(path, 1024 * 1024)
            if isinstance(output, dict) and isinstance(output.get('answers'), list):
                for answer in output['answers']:
                    if (isinstance(answer, dict) and isinstance(answer.get('case_id'), str) and
                            answer['case_id'] in ids and isinstance(answer.get('citations'), list)):
                        if any(isinstance(i, str) and i not in mapping['cases'][answer['case_id']]['selected']
                               for i in answer['citations']):
                            unsupported.add(answer['case_id'])
            valid = validate_batch(output, inbox['cases'], mapping['cases'])
        except (AssertionError, ValueError, KeyError, TypeError, OSError, UnicodeError) as error:
            errors.append({'batch': batch, 'file': name, 'error_type': type(error).__name__, 'message': str(error)})
            statuses.update({i: 'invalid' for i in ids})
            continue
        answers.update(valid)
        statuses.update({i: 'valid' for i in ids})
    rows = []
    for ident, item in mapping['cases'].items():
        answer = answers.get(ident)
        required = set(item['gold']['required'])
        available = required <= set(item['selected'])
        correct = answer is not None and answer['value'] == item['gold']['value']
        abstained = answer is not None and answer['value'] is None
        rows.append({'case_id': ident, 'query': item['query'], 'arm': item['arm'], 'context': item['context'],
                     'status': statuses[ident], 'gold_support_in_packet': available, 'value_agreement': correct,
                     'governing_agreement': answer is not None and answer['governing'] == item['gold']['governing'],
                     'gold_citations_and_value': correct and required <= set(answer['citations']),
                     'unsupported_citation': ident in unsupported, 'abstention': abstained,
                     'reader_reports_supported': answer is not None and answer['supported'],
                     'abstention_when_gold_missing': abstained and not available,
                     'abstention_with_gold_available': abstained and available})
    total = tally(rows)
    return {'state': 'ALL_OUTPUTS_STRUCTURALLY_ACCEPTED' if total['valid'] == 48 else 'INCOMPLETE_OR_INVALID_COLLECTION',
            'planned_cases': 48, 'staged_cases': 48, 'executed_batches': sum(h is not None for h in hashes.values()),
            'accepted_batches': total['valid'] // 6, 'counts': total,
            'by_arm': {arm: tally([r for r in rows if r['arm'] == arm]) for arm in ARMS},
            'input_hashes': manifest['input_hashes'], 'output_hashes': hashes,
            'sampling_manifest_sha256': sha(artifacts['sampling-manifest.json']), 'errors': errors, 'cases': rows}


def controls(inbox, mapping, directory):
    original = load(directory / 'out-00.json')
    validate_batch(original, inbox['cases'], mapping['cases'])
    cases = []
    changed = copy.deepcopy(original)
    changed['answers'][0]['citations'] = ['invented-source']
    cases.append(('invented citation', changed))
    changed = copy.deepcopy(original)
    changed['answers'][1]['case_id'] = changed['answers'][0]['case_id']
    cases.append(('duplicate case', changed))
    changed = copy.deepcopy(original)
    changed['answers'][0]['supported'] = 1
    cases.append(('integer support flag', changed))
    changed = copy.deepcopy(original)
    changed['answers'][0]['governing'] = 'invented-source'
    cases.append(('invented governing ID', changed))
    changed = copy.deepcopy(original)
    changed['answers'][0]['missing_refs'] = ['invented-reference']
    cases.append(('invented missing reference', changed))
    rejected = []
    for label, changed in cases:
        try:
            validate_batch(changed, inbox['cases'], mapping['cases'])
        except AssertionError:
            rejected.append(label)
        else:
            raise AssertionError('mutation survived: ' + label)
    for label, changed in (('duplicate JSON key', '{"x":1,"x":2}'),
                           ('overflow JSON number', '{"x":1e999}')):
        try:
            decode(changed)
        except AssertionError:
            rejected.append(label)
        else:
            raise AssertionError('mutation survived: ' + label)
    return rejected


def verify(directory, results):
    started = time.perf_counter()
    inboxes, mapping, manifest, artifacts = reconstruct(directory)
    recounted = recount(directory, inboxes, mapping, manifest, artifacts)
    compared = load(results)
    for key, value in recounted.items():
        same(compared[key], value, 'independent mechanical result mismatch: ' + key)
    require(set(compared) == set(recounted) | {'limits'}, 'unexpected result keys')
    require(isinstance(compared['limits'], list) and all(isinstance(s, str) for s in compared['limits']), 'limits shape')
    require(not recounted['errors'], 'actual collection contains invalid batches; details retained')
    mutations = controls(inboxes[0], mapping, directory)
    return {'state': 'INDEPENDENT_READER_RECONSTRUCTION_AND_RECOUNT_PASSED',
            'collection_state': recounted['state'], 'fixed_queries': 12, 'planned_cases': 48,
            'contexts': 8, 'cases_per_context': 6, 'exact_reconstructed_packets': 48,
            'counts': recounted['counts'], 'by_arm': recounted['by_arm'],
            'sampling_manifest_sha256': recounted['sampling_manifest_sha256'],
            'input_hashes': recounted['input_hashes'], 'output_hashes': recounted['output_hashes'],
            'mechanical_results_sha256': file_hash(results),
            'checker_sha256': file_hash(Path(__file__)), 'mutation_controls_rejected': mutations,
            'wall_seconds': time.perf_counter() - started,
            'scope': ['No collection, staging, selector, reader or scoring helper imported.',
                      'Instruction/schema literals parsed from the source-bound helper without execution.',
                      'All fixed probe identities, assignments, original source order/bytes, mapping and prompt accounting reconstructed.',
                      'All outputs schema/citation checked; every existing mechanical case/aggregate metric recounted.',
                      'No semantic explanation judging, new model calls or output repair.',
                      'Collector must separately attest requested model/context/tool identities and no retry.',
                      'Even contexts contain current tasks; odd contexts contain standing tasks.',
                      'Shared-backbone values repeat across scenarios; case-only instructions do not prove absence of cross-case transfer.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    if args.receipt:
        require(not args.receipt.exists(), 'receipt already exists')
    receipt = verify(args.collection, args.results)
    if args.receipt:
        with args.receipt.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
