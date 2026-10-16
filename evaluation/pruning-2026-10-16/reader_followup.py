"""Stage fixed source-only reader packets or check retained outputs read-only.

Use --self-check, --stage NEW_PRIVATE_DIRECTORY, or --check PRIVATE_DIRECTORY.
No default action writes files. A check prints hashes/results for its caller to
retain; it never creates missing outputs or repairs an invalid reader batch.
"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('reader_shared_checks', ROOT / 'scripts/check_repository.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)

ARMS = ('all|off|global', 'ttl8|off|global', 'ttl8|scheduled_cold|global',
        'latest_dependencies|off|linked')
TASKS = ('current', 'standing')
QUESTION_KEYS = {'project', 'key', 'asof', 'epoch', 'cue'}
CASE_KEYS = {'case_id', 'question', 'packet', 'packet_sha256', 'packet_bytes'}
ANSWER_KEYS = {'case_id', 'value', 'governing', 'citations', 'supported',
               'missing_refs', 'explanation'}
OUTPUT_SCHEMA = {'answers': [{'case_id': 'string', 'value': 'string or null',
    'governing': 'source ID or null', 'citations': ['source ID'], 'supported': 'boolean',
    'missing_refs': ['referenced source ID absent from packet'], 'explanation': 'string'}]}
INSTRUCTIONS = """Answer each case using only that case's supplied packet. Cases are independent.
Use tools only to read this inbox and write the assigned output file. Use no outside
knowledge, project navigation or other cases as evidence.
Each original source begins with ASSERT followed by JSON. Treat that assertion as
the source's declared claim. For the requested project/key, eligible assertions
have effective <= asof and either no expiry or asof < expires. Select the greatest
(effective, created, id) among eligible assertions. Explicit refs are prerequisites;
check their transitive availability in the same packet. Narrative is supplementary.
Return a value and governing source ID when the packet justifies them, or null if
you cannot determine them. You may report a visible provisional value while setting
supported false if prerequisites are missing. Cite only IDs present in that packet.
List missing referenced IDs you find, and briefly explain the answer or abstention.
Return exactly one JSON object with the sole key answers, containing one answer
for every supplied case. Use exactly the fields/types in output_schema, no extra
fields, no Markdown fences and no text outside the JSON. Preserve each case_id.
Do not infer missing information from identifiers or fabricate source content.
"""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def constant(token):
        raise ValueError('Nonfinite JSON constant')
    def floating(token):
        value = float(token)
        require(math.isfinite(value), 'Nonfinite JSON number')
        return value
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant, parse_float=floating)


def load(path, max_bytes=16 * 1024 * 1024):
    require(path.is_file() and not path.is_symlink(), 'Missing or linked input: ' + path.name)
    require(path.stat().st_size <= max_bytes, 'Oversized input: ' + path.name)
    return strict_json(path.read_bytes().decode('utf-8'))


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + '\n').encode('utf-8')


def literal(name, filename):
    tree = ast.parse((HERE / filename).read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('Missing sealed constant: ' + name)


def framed(source):
    return ('<SOURCE ' + source['id'] + '>\n' + source['text'] + '\n</SOURCE>\n').encode('utf-8')


def case_id(query, arm):
    return sha(('pruning-reader-v1:' + query + arm).encode('utf-8'))[:24]


def validate_inbox(inbox):
    require(isinstance(inbox, dict) and set(inbox) == {'schema_version', 'instructions', 'output_schema', 'cases'},
            'Unexpected inbox fields')
    require(inbox['schema_version'] == 1 and type(inbox['schema_version']) is int, 'Invalid inbox version')
    require(inbox['instructions'] == INSTRUCTIONS and inbox['output_schema'] == OUTPUT_SCHEMA,
            'Changed common instructions/schema')
    require(isinstance(inbox['cases'], list) and len(inbox['cases']) == 6, 'Inbox must contain six cases')
    ids = set()
    for case in inbox['cases']:
        require(isinstance(case, dict) and set(case) == CASE_KEYS, 'Unexpected reader case fields')
        require(isinstance(case['case_id'], str) and case['case_id'] not in ids, 'Duplicate/invalid inbox case ID')
        ids.add(case['case_id'])
        q = case['question']
        require(isinstance(q, dict) and set(q) == QUESTION_KEYS, 'Unexpected question fields')
        require(all(isinstance(q[k], str) for k in ('project', 'key', 'cue')) and
                all(type(q[k]) is int for k in ('asof', 'epoch')), 'Invalid question types')
        require(isinstance(case['packet'], str), 'Packet must be text')
        raw = case['packet'].encode('utf-8')
        require(type(case['packet_bytes']) is int and 0 <= case['packet_bytes'] <= 8192 and
                len(raw) == case['packet_bytes'], 'Packet byte count/budget mismatch')
        require(case['packet_sha256'] == sha(raw), 'Changed packet digest')


def build_inputs():
    """Reconstruct the complete fixed sampling without inspecting scored outcomes."""
    run = HERE / 'run'
    manifest = load(run / 'manifest.json')
    seal = load(HERE / 'seal.json')
    require(seal['state'] == 'SEALED_BEFORE_COLLECTION', 'Unrecognized source seal')
    bindings = {}
    for name, expected in seal['sha256'].items():
        require(Path(name).name == name and file_hash(HERE / name) == expected, 'Changed sealed input')
        bindings[name] = expected
    for name, expected in manifest['sha256'].items():
        require(Path(name).name == name and (run / name).is_file() and not (run / name).is_symlink(),
                'Invalid main-run file binding')
        require(file_hash(run / name) == expected, 'Changed main-run file: ' + name)
        bindings['run/' + name] = expected
    require({'trials.jsonl.gz', 'scored.jsonl.gz', 'snapshots.jsonl.gz', 'maintenance.jsonl.gz',
             'source-bank.json', 'gold.json', 'execution.json', 'self-check.json'} <= set(manifest['sha256']),
            'Incomplete main manifest')
    for name in ('seal.json', 'READER-PLAN.md', 'reader_followup.py', 'run/manifest.json'):
        bindings[name] = file_hash(HERE / name)
    families = literal('FAMILIES', 'pruning_lab.py')
    selected_families = families[-6:]
    all_arms = {'|'.join(a) for a in itertools.product(literal('POLICIES', 'pruning_core.py'),
                literal('ARCHIVES', 'pruning_core.py'), literal('METHODS', 'pruning_core.py'))}
    bank = load(run / 'source-bank.json')
    require(len(bank) == 32 and len(families) == 8, 'Wrong source-bank world census')
    expected_worlds = {f'{f}-s{s}-{d}' for f, s, d in itertools.product(families, range(2), ('low', 'high'))}
    require({w['id'] for w in bank} == expected_worlds and len({w['id'] for w in bank}) == len(bank),
            'Wrong/duplicate worlds')
    sources, queries, query_world = {}, {}, {}
    targets = {}
    for world in bank:
        by_id = {s['id']: s for s in world['sources']}
        require(len(by_id) == len(world['sources']), 'Duplicate original ID within world')
        for source in by_id.values():
            raw = source['text'].encode('utf-8')
            require(source['sha256'] == sha(raw) and source['bytes'] == len(raw), 'Original source hash/size mismatch')
        sources[world['id']] = by_id
        require(len(world['queries']) == 32, 'Wrong per-world query census')
        for q in world['queries']:
            require(q['id'] not in queries and q['world'] == world['id'], 'Duplicate/wrong-world query')
            queries[q['id']] = q
            query_world[q['id']] = world['id']
            if world['family'] in selected_families and world['seed'] == 0 and world['density'] == 'high' and q['epoch'] == 32 and q['task'] in TASKS:
                targets[q['id']] = (selected_families.index(world['family']), TASKS.index(q['task']))
    require(len(queries) == 1024 and len(targets) == 12, 'Wrong query/reader-sample census')
    expected = {(q, arm) for q in queries for arm in all_arms}
    seen, chosen = set(), {}
    for _, row in shared.compressed_jsonl_lines(run / 'trials.jsonl.gz'):
        key = row['query'], row['arm']
        require(key in expected and key not in seen and row['world'] == query_world[row['query']],
                'Unexpected/duplicate trial row')
        seen.add(key)
        if row['query'] in targets and row['arm'] in ARMS:
            chosen[key] = row
    require(seen == expected and len(seen) == 64512 and len(chosen) == 48, 'Incomplete trial/sample census')
    gold = load(run / 'gold.json')
    inboxes = [{'schema_version': 1, 'instructions': INSTRUCTIONS,
                'output_schema': copy.deepcopy(OUTPUT_SCHEMA), 'cases': []} for _ in range(8)]
    mapping = {'schema_version': 1, 'cases': {}}
    for qid, (f, t) in sorted(targets.items(), key=lambda item: item[1]):
        q = queries[qid]
        by_id = sources[q['world']]
        for a, arm in enumerate(ARMS):
            row = chosen[qid, arm]
            selected = row['selected']
            require(len(selected) == len(set(selected)) and selected ==
                    [i for call in row['calls'] for i in call['selected']], 'Changed selected order')
            require(all(i in by_id and by_id[i]['created'] <= q['epoch'] for i in selected), 'Unavailable selected source')
            packet = b''.join(framed(by_id[i]) for i in selected)
            require(len(packet) == row['bytes'] and len(packet) <= 8192, 'Trial packet size mismatch')
            opaque = case_id(qid, arm)
            require(opaque not in mapping['cases'], 'Opaque ID collision')
            batch = (2 * f + t + 2 * a) % 8
            case = {'case_id': opaque, 'question': {k: q[k] for k in sorted(QUESTION_KEYS)},
                    'packet': packet.decode('utf-8'), 'packet_sha256': sha(packet), 'packet_bytes': len(packet)}
            inboxes[batch]['cases'].append(case)
            require(set(gold[qid]['required']) <= set(by_id), 'Unknown complete-source gold ID')
            mapping['cases'][opaque] = {'query': qid, 'world': q['world'], 'family': selected_families[f],
                'task': TASKS[t], 'arm': arm, 'context': batch, 'selected': selected,
                'packet_sha256': sha(packet), 'gold': gold[qid],
                'referenced': sorted({r for i in selected for r in by_id[i]['refs']})}
    for batch, inbox in enumerate(inboxes):
        validate_inbox(inbox)
        require({mapping['cases'][c['case_id']]['family'] for c in inbox['cases']} == set(selected_families),
                'A context must receive exactly one case per family')
    artifacts = {f'inbox-{i:02d}.json': encoded(inbox) for i, inbox in enumerate(inboxes)}
    artifacts['mapping.json'] = encoded(mapping)
    sample = {'state': 'STAGED_FIXED_READER_SAMPLE', 'planned_cases': 48, 'staged_cases': 48,
        'contexts': 8, 'cases_per_context': 6, 'requested_model': 'gpt-6.1-sol',
        'selected_families': list(selected_families), 'seed': 0, 'density': 'high', 'epoch': 32,
        'tasks': list(TASKS), 'arms': list(ARMS), 'source_bindings': bindings,
        'input_hashes': {name: sha(raw) for name, raw in artifacts.items()},
        'prompt_bytes': {f'inbox-{i:02d}.json': {'serialized_input': len(artifacts[f'inbox-{i:02d}.json']),
            'packet_bytes': sum(c['packet_bytes'] for c in inbox['cases']),
            'question_bytes': sum(len(canonical(c['question']).encode('utf-8')) for c in inbox['cases']),
            'common_instruction_bytes': len(INSTRUCTIONS.encode('utf-8')),
            'output_schema_bytes': len(canonical(OUTPUT_SCHEMA).encode('utf-8'))}
            for i, inbox in enumerate(inboxes)},
        'collection_contract': 'Missing or invalid batches remain in the planned denominator; no output overwrite or retry.'}
    artifacts['sampling-manifest.json'] = encoded(sample)
    return artifacts, inboxes, mapping, sample


def stage(directory):
    require(not directory.exists(), 'Staging target already exists; refusing overwrite')
    artifacts, _, _, sample = build_inputs()
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in artifacts.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
    require(all((directory / name).read_bytes() == raw for name, raw in artifacts.items()), 'Staging readback mismatch')
    return {'state': sample['state'], 'planned_cases': 48, 'staged_cases': 48, 'contexts': 8,
            'input_hashes': sample['input_hashes'], 'sampling_manifest_sha256': sha(artifacts['sampling-manifest.json'])}


def validate_batch(output, cases, mapping):
    require(isinstance(output, dict) and set(output) == {'answers'} and isinstance(output['answers'], list),
            'Output must be an object containing only an answers list')
    answers = output['answers']
    expected = {c['case_id'] for c in cases}
    require(len(answers) == len(expected), 'Wrong answer count')
    seen = set()
    for answer in answers:
        require(isinstance(answer, dict) and set(answer) == ANSWER_KEYS, 'Unexpected answer fields')
        ident = answer['case_id']
        require(isinstance(ident, str) and ident in expected and ident not in seen, 'Unexpected/duplicate case ID')
        seen.add(ident)
        require(answer['value'] is None or isinstance(answer['value'], str), 'Invalid value type')
        require(answer['governing'] is None or isinstance(answer['governing'], str), 'Invalid governing type')
        require(type(answer['supported']) is bool and isinstance(answer['explanation'], str), 'Invalid support/explanation type')
        for field in ('citations', 'missing_refs'):
            require(isinstance(answer[field], list) and all(isinstance(i, str) for i in answer[field]) and
                    len(answer[field]) == len(set(answer[field])), 'Invalid/duplicate ' + field)
        item = mapping[ident]
        present = set(item['selected'])
        require(set(answer['citations']) <= present, 'Citation absent from supplied packet')
        require(answer['governing'] is None or answer['governing'] in present, 'Governing ID absent from packet')
        require(set(answer['missing_refs']) <= set(item['referenced']) - present, 'Invented or present missing-reference ID')
    require(seen == expected, 'Missing expected case')
    return {answer['case_id']: answer for answer in answers}


def check(directory):
    artifacts, inboxes, mapping, sample = build_inputs()
    require(directory.is_dir(), 'Reader collection directory is absent')
    for name, expected in artifacts.items():
        require((directory / name).is_file() and not (directory / name).is_symlink() and
                (directory / name).read_bytes() == expected, 'Changed staged input: ' + name)
    outputs, errors, answers, statuses = {}, [], {}, {}
    unsupported_cases = set()
    for batch, inbox in enumerate(inboxes):
        name = f'out-{batch:02d}.json'
        path = directory / name
        ids = [c['case_id'] for c in inbox['cases']]
        if not path.exists():
            outputs[name] = None
            statuses.update({i: 'missing' for i in ids})
            continue
        outputs[name] = file_hash(path) if path.is_file() and not path.is_symlink() else None
        try:
            output = load(path, max_bytes=1024 * 1024)
            if isinstance(output, dict) and isinstance(output.get('answers'), list):
                for answer in output['answers']:
                    if isinstance(answer, dict) and isinstance(answer.get('case_id'), str) and answer['case_id'] in ids and isinstance(answer.get('citations'), list):
                        if any(isinstance(i, str) and i not in mapping['cases'][answer['case_id']]['selected'] for i in answer['citations']):
                            unsupported_cases.add(answer['case_id'])
            accepted = validate_batch(output, inbox['cases'], mapping['cases'])
        except (ValueError, TypeError, KeyError, OSError, UnicodeError) as error:
            errors.append({'batch': batch, 'file': name, 'error_type': type(error).__name__, 'message': str(error)})
            statuses.update({i: 'invalid' for i in ids})
            continue
        answers.update(accepted)
        statuses.update({i: 'valid' for i in ids})
    rows = []
    for ident, item in mapping['cases'].items():
        answer = answers.get(ident)
        required = set(item['gold']['required'])
        packet_complete = required <= set(item['selected'])
        correct = answer is not None and answer['value'] == item['gold']['value']
        abstained = answer is not None and answer['value'] is None
        rows.append({'case_id': ident, 'query': item['query'], 'arm': item['arm'], 'context': item['context'],
            'status': statuses[ident], 'gold_support_in_packet': packet_complete,
            'value_agreement': correct,
            'governing_agreement': answer is not None and answer['governing'] == item['gold']['governing'],
            'gold_citations_and_value': correct and required <= set(answer['citations']),
            'unsupported_citation': ident in unsupported_cases, 'abstention': abstained,
            'reader_reports_supported': answer is not None and answer['supported'],
            'abstention_when_gold_missing': abstained and not packet_complete,
            'abstention_with_gold_available': abstained and packet_complete})
    def counts(selected):
        return {'planned': len(selected), 'valid': sum(r['status'] == 'valid' for r in selected),
                'missing': sum(r['status'] == 'missing' for r in selected),
                'invalid': sum(r['status'] == 'invalid' for r in selected),
                **{key: sum(r[key] for r in selected) for key in ('gold_support_in_packet', 'value_agreement',
                    'governing_agreement', 'gold_citations_and_value', 'unsupported_citation', 'abstention',
                    'reader_reports_supported', 'abstention_when_gold_missing', 'abstention_with_gold_available')}}
    total = counts(rows)
    return {'state': 'ALL_OUTPUTS_STRUCTURALLY_ACCEPTED' if total['valid'] == 48 else 'INCOMPLETE_OR_INVALID_COLLECTION',
        'planned_cases': 48, 'staged_cases': 48, 'executed_batches': sum(v is not None for v in outputs.values()),
        'accepted_batches': total['valid'] // 6, 'counts': total,
        'by_arm': {arm: counts([r for r in rows if r['arm'] == arm]) for arm in ARMS},
        'input_hashes': sample['input_hashes'], 'output_hashes': outputs,
        'sampling_manifest_sha256': sha(artifacts['sampling-manifest.json']), 'errors': errors, 'cases': rows,
        'limits': ['Mechanical gold/citation matching is not semantic entailment or human truth.',
                   'Abstention labels describe source availability and the returned null; no judge regrades explanations.',
                   'A batch with any schema/case/citation error is invalid as a whole; bytes are preserved.',
                   'Actual model/context identities must be recorded by the collector separately.',
                   'Twelve fixed probes and eight shared contexts are exploratory repeated observations.']}


def self_check():
    cases, mapping, valid = [], {}, []
    for i in range(6):
        ident, source = f'opaque-{i}', f'fictional-source-{i}'
        packet = '<SOURCE ' + source + '>\nfictional evidence\n</SOURCE>\n'
        cases.append({'case_id': ident, 'question': {'project': 'orchard', 'key': 'setting', 'asof': 32,
            'epoch': 32, 'cue': 'current setting'}, 'packet': packet, 'packet_sha256': sha(packet.encode()),
            'packet_bytes': len(packet.encode())})
        mapping[ident] = {'selected': [source], 'referenced': ['fictional-missing']}
        valid.append({'case_id': ident, 'value': 'declared', 'governing': source,
            'citations': [source], 'supported': True, 'missing_refs': [], 'explanation': 'Supplied source.'})
    inbox = {'schema_version': 1, 'instructions': INSTRUCTIONS, 'output_schema': OUTPUT_SCHEMA, 'cases': cases}
    validate_inbox(inbox)
    validate_batch({'answers': valid}, cases, mapping)
    passed = ['valid six-case inbox and batch']
    def rejects(name, operation):
        try:
            operation()
        except (ValueError, TypeError):
            passed.append(name)
        else:
            raise AssertionError('Failed to reject ' + name)
    duplicate = copy.deepcopy(valid)
    duplicate[1] = copy.deepcopy(duplicate[0])
    rejects('duplicate cases', lambda: validate_batch({'answers': duplicate}, cases, mapping))
    invented = copy.deepcopy(valid)
    invented[0]['citations'] = ['invented-source']
    rejects('invented citation', lambda: validate_batch({'answers': invented}, cases, mapping))
    digest_changed = copy.deepcopy(inbox)
    digest_changed['cases'][0]['packet_sha256'] = '0' * 64
    rejects('changed packet digest', lambda: validate_inbox(digest_changed))
    bytes_changed = copy.deepcopy(inbox)
    bytes_changed['cases'][0]['packet'] += 'changed'
    rejects('changed packet bytes', lambda: validate_inbox(bytes_changed))
    unknown = copy.deepcopy(valid)
    unknown[0]['extra'] = True
    rejects('unknown answer field', lambda: validate_batch({'answers': unknown}, cases, mapping))
    boolean = copy.deepcopy(valid)
    boolean[0]['supported'] = 1
    rejects('integer pretending to be boolean', lambda: validate_batch({'answers': boolean}, cases, mapping))
    governing = copy.deepcopy(valid)
    governing[0]['governing'] = 'invented-source'
    rejects('invented governing source', lambda: validate_batch({'answers': governing}, cases, mapping))
    missing = copy.deepcopy(valid)
    missing[0]['missing_refs'] = ['invented-reference']
    rejects('invented missing reference', lambda: validate_batch({'answers': missing}, cases, mapping))
    for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}'):
        rejects('strict JSON rejection ' + text, lambda text=text: strict_json(text))
    for f in range(6):
        require({(2*f+t+2*a) % 8 for t in range(2) for a in range(4)} == set(range(8)),
                'Assignment formula must give one case per family/context')
    require(len({case_id(f'q-{f}-{t}', arm) for f in range(6) for t in range(2) for arm in ARMS}) == 48,
            'Opaque IDs must be distinct')
    passed.extend(['all 48 assignment positions', 'all 48 opaque IDs distinct'])
    return {'state': 'READER_HELPER_SELF_CHECK_PASSED', 'passed': len(passed), 'checks': passed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--self-check', action='store_true')
    modes.add_argument('--stage', type=Path)
    modes.add_argument('--check', type=Path)
    args = parser.parse_args()
    if args.self_check:
        result = self_check()
    elif args.stage is not None:
        result = stage(args.stage)
    elif args.check is not None:
        result = check(args.check)
    else:
        parser.print_help()
        return 0
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2 if args.check is not None and result['state'] != 'ALL_OUTPUTS_STRUCTURALLY_ACCEPTED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
