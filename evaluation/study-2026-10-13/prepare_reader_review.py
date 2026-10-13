"""Prepare private, blinded semantic-review packets after all 192 reader trials.

Stdlib only. No model, ranker, provider, or study implementation is imported.
Use --self-check before collection; --prepare requires audited result/freeze hashes.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
COUNT, PARTITIONS = 192, 3
TASK_FIELDS = ('id', 'query', 'answer_keys', 'answer_contract')
MINIMAL = {'id', 'chars', 'kind', 'revision'}
VERBOSE = MINIMAL | {'title', 'scope', 'aliases', 'authored_at', 'links', 'supersedes', 'incorporates'}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def strict_json(text):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite_json_number')
    value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    def valid(item):
        if isinstance(item, str):
            try:
                item.encode('utf8')
            except UnicodeError as error:
                raise ValueError('invalid_json_unicode') from error
        elif isinstance(item, float):
            require(math.isfinite(item), 'nonfinite_json_number')
        elif isinstance(item, list):
            for member in item:
                valid(member)
        elif isinstance(item, dict):
            for key, member in item.items():
                valid(key)
                valid(member)
    valid(value)
    return value


def encoded(value, pretty=False):
    options = {'indent': 2} if pretty else {'separators': (',', ':')}
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, **options)
            + ('\n' if pretty else '')).encode('utf8')


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode('utf8')).hexdigest()


def same(left, right):
    # JSON types matter: Python's True == 1 must not equate retained artifacts.
    return encoded(left) == encoded(right)


def read(path, inputs, label):
    raw = path.read_bytes()
    inputs[label] = {'sha256': sha(raw), 'bytes': len(raw)}
    return strict_json(raw.decode('utf8'))


def observational_documents(families):
    """Recreate only the frozen document projection used in delivered headers."""
    docs = {}
    for family in families:
        require(isinstance(family['name'], str) and isinstance(family['aliases'], list)
            and all(isinstance(alias, str) for alias in family['aliases']), 'family_alias_projection')
        for record in family['records']:
            require(record['id'] not in docs, 'duplicate_bank_record')
            docs[record['id']] = {**record, 'aliases': [family['name'], *family['aliases']]}
    return docs


def packet_fragments(packet, docs):
    """Parse by declared character length, not by SOURCE-looking lines in prose."""
    require(isinstance(packet, str), 'packet_not_text')
    fragments, cursor = [], 0
    while cursor < len(packet):
        require(packet.startswith('SOURCE ', cursor), 'source_header_missing')
        newline = packet.find('\n', cursor)
        require(newline >= 0, 'source_header_unterminated')
        header_text = packet[cursor + 7:newline]
        header = strict_json(header_text)
        require(isinstance(header, dict) and isinstance(header.get('id'), str), 'source_header_shape')
        identifier = header['id']
        require(identifier in docs, 'source_id_missing')
        doc = docs[identifier]
        chars = header.get('chars')
        require(isinstance(chars, list) and len(chars) == 2 and all(type(v) is int for v in chars), 'source_bounds_type')
        start, end = chars
        require(0 <= start < end <= len(doc['body']), 'source_bounds_range')
        basic = {'id': identifier, 'chars': chars, 'kind': doc['kind'], 'revision': doc['revision']}
        verbose = {**basic, **{key: doc.get(key) for key in VERBOSE - MINIMAL}}
        if 'time_scope' in doc:
            verbose['time_scope'] = doc['time_scope']
        require(same(header, basic) or same(header, verbose), 'unseen_or_wrong_source_metadata')
        require(header_text == encoded(header).decode('utf8'), 'source_header_serialization')
        body_start, body_end = newline + 1, newline + 1 + end - start
        text = packet[body_start:body_end]
        require(text == doc['body'][start:end], 'source_fragment_text_mismatch')
        fragments.append({'id': identifier, 'start': start, 'end': end, 'text': text,
            'source_body_sha256': sha(doc['body']),
            'delivered_text_chars': [body_start, body_end]})
        cursor = body_end
        if cursor < len(packet):
            require(packet.startswith('\n\nSOURCE ', cursor), 'source_separator_mismatch')
            cursor += 2
    return fragments


def tool_fragments(action, result, docs):
    """Retain a complete actual source-bearing result; add no source metadata."""
    tool = action.get('tool')
    if tool == 'read' and isinstance(result, dict) and 'text' in result:
        require(set(result) == {'path', 'text'} and result['path'] == action.get('path'), 'read_result_shape')
        if result['path'] == 'README.md':
            return []  # navigation prose is not an original/derived source interval
        fragments = packet_fragments(result['text'], docs)
        require(len(fragments) == 1 and docs[fragments[0]['id']]['path'] == result['path'], 'read_path_source_link')
        for fragment in fragments:
            fragment['result_text_pointer'] = '/text'
        return fragments
    if tool == 'retrieve' and isinstance(result, dict) and 'packet' in result:
        require(set(result) == {'packet', 'policy', 'bytes', 'query'}, 'retrieve_result_shape')
        require(result['query'] == action.get('query') and result['policy'] == 'entity_rrf_closure_passages_8192', 'retrieve_identity')
        require(type(result['bytes']) is int and result['bytes'] == len(result['packet'].encode('utf8')), 'retrieve_bytes')
        fragments = packet_fragments(result['packet'], docs)
        for fragment in fragments:
            fragment['result_text_pointer'] = '/packet'
        return fragments
    if tool == 'search' and isinstance(result, dict) and 'matches' in result:
        require(set(result) == {'matches', 'total_matches', 'truncated'}, 'search_result_shape')
        require(type(result['total_matches']) is int and type(result['truncated']) is bool, 'search_census_types')
        require(isinstance(result['matches'], list) and len(result['matches']) <= 40, 'search_matches_shape')
        fragments = []
        for number, match in enumerate(result['matches']):
            require(set(match) == {'path', 'id', 'line', 'start', 'end', 'text'}, 'unseen_search_metadata')
            require(match['id'] in docs, 'search_source_missing')
            doc = docs[match['id']]
            require(doc['kind'] == 'source' and match['path'] == doc['path'], 'search_original_path')
            require(all(type(match[key]) is int for key in ('line', 'start', 'end')), 'search_bounds_type')
            require(0 <= match['start'] < match['end'] <= len(doc['body']), 'search_bounds_range')
            require(doc['body'][match['start']:match['end']] == match['text'], 'search_fragment_text')
            lines, offset, found = doc['body'].splitlines(keepends=True), 0, False
            for line_number, line in enumerate(lines, 1):
                if line_number == match['line']:
                    found = (offset == match['start'] and offset + len(line.rstrip('\r\n')) == match['end'])
                offset += len(line)
            require(found, 'search_line_offsets')
            fragments.append({key: match[key] for key in ('id', 'start', 'end', 'text')})
            fragments[-1].update(source_body_sha256=sha(doc['body']),
                result_text_pointer=f'/matches/{number}/text', delivered_text_chars=[0, len(match['text'])])
        return fragments
    return []


def observation_keys(fragments):
    return [{ 'id': f['id'], 'start': f['start'], 'end': f['end'], 'source_hash': f['source_body_sha256']} for f in fragments]


def prompt_call(root, name, runtime, inputs, label):
    snapshot_name = 'public-prompt.json' if name == 'direct' else name + '-prompt.json'
    snapshot = read(root / snapshot_name, inputs, label + '/' + snapshot_name)
    persisted = read(root / (name + '-call.json'), inputs, label + '/' + name + '-call.json')
    require(set(snapshot) == {'prompt', 'prompt_sha256'} and sha(snapshot['prompt']) == snapshot['prompt_sha256'], 'prompt_fixity')
    identity = sha(snapshot['prompt'] + json.dumps(runtime, sort_keys=True))
    require(persisted.get('identity') == identity, 'call_input_runtime_identity')
    call = persisted.get('call')
    require(isinstance(call, dict) and type(call.get('accepted')) is bool, 'accepted_receipt_missing')
    return snapshot, persisted


def exposure(row, root, task, docs, runtime, inputs, label):
    if row.get('failure') == 'trial_execution_error':
        return [], ['late_fault_missing_final_write_chronology']
    events = row.get('events', [])
    contract_text = json.dumps(task, ensure_ascii=False, sort_keys=True)
    if row['block'] != 'discovery':
        snapshot, persisted = prompt_call(root, 'direct', runtime, inputs, label)
        if not persisted['call']['accepted']:
            return [], ['final_write_upstream_submission_not_verified']
        marker = '\nTASK AND CONTRACT\n' + contract_text + '\nSUPPLIED EVIDENCE\n'
        require(snapshot['prompt'].count(marker) == 1, 'direct_task_contract_boundary')
        packet = snapshot['prompt'].split(marker, 1)[1]
        require(len(events) == 1 and events[0].get('packet_sha256') == sha(packet)
            and events[0].get('packet_bytes') == len(packet.encode('utf8'))
            and events[0].get('response_text') == persisted.get('text'), 'direct_event_prompt_link')
        require(same(strict_json(persisted['text']), row['artifact']), 'direct_artifact_response_link')
        fragments = packet_fragments(packet, docs)
        require(same(observation_keys(fragments), row.get('actual_prewrite_source_observations')), 'direct_observation_link')
        for fragment in fragments:
            fragment['result_text_pointer'] = '/packet'
        return [{'operation': 'supplied_packet', 'actual_result': {'packet': packet},
            'prompt_sha256': snapshot['prompt_sha256'], 'source_fragments': fragments}], []
    writes = [e for e in events if e.get('executed') is True and isinstance(e.get('action'), dict)
        and e['action'].get('tool') == 'write']
    if not writes:
        return [], ['retained_successful_final_write_event_missing']
    final = writes[-1]
    if not same(final.get('result'), row['write_receipt']):
        return [], ['retained_final_write_receipt_not_in_returned_event']
    require(final['action'].get('path') == 'artifacts/result.json' and same(final['action'].get('content'), row['artifact']), 'final_write_artifact_link')
    round_number = final.get('round')
    require(type(round_number) is int and 1 <= round_number <= 8, 'final_write_round')
    snapshot, persisted = prompt_call(root, 'round-' + str(round_number), runtime, inputs, label)
    if not persisted['call']['accepted']:
        return [], ['final_write_upstream_submission_not_verified']
    marker = '\nTASK AND CONTRACT\n' + contract_text + '\nSTATE\n'
    require(snapshot['prompt'].count(marker) == 1, 'discovery_task_contract_boundary')
    history_marker = '\nYOUR REPLAYED TRIAL HISTORY\n'
    require(snapshot['prompt'].count(history_marker) == 1, 'history_boundary')
    history = strict_json(snapshot['prompt'].split(history_marker, 1)[1])
    require(isinstance(history, list) and len(history) == round_number - 1, 'history_round_census')
    reply = strict_json(persisted['text'])
    require(isinstance(reply, dict) and set(reply) == {'actions', 'done'} and type(reply['done']) is bool, 'write_response_shape')
    current_events = [e for e in events if e.get('round') == round_number]
    require(same([e['action'] for e in current_events], reply['actions'][:len(current_events)]), 'write_call_action_link')
    require(any(e.get('seq') == final.get('seq') for e in current_events), 'write_sequence_link')
    deliveries, fragments_all = [], []
    for previous_round, entry in enumerate(history, 1):
        if 'host_results' not in entry:
            require(isinstance(entry.get('host'), dict) and entry['host'].get('error') == 'invalid_action_response', 'invalid_history_entry')
            require(not any(e.get('round') == previous_round for e in events), 'invalid_history_has_actions')
            continue
        prior_events = [e for e in events if e.get('round') == previous_round]
        require(same(entry.get('host_results'), [e['result'] for e in prior_events]), 'returned_result_event_link')
        require(isinstance(entry.get('assistant'), dict) and same(entry['assistant'].get('actions', [])[:len(prior_events)], [e['action'] for e in prior_events]), 'history_action_link')
        for event in prior_events:
            fragments = tool_fragments(event['action'], event['result'], docs)
            require(same(observation_keys(fragments), event.get('delivered_source_observations', [])), 'event_source_observation_link')
            if fragments:
                deliveries.append({'operation': event['action']['tool'], 'actual_result': event['result'],
                    'prompt_sha256': snapshot['prompt_sha256'], 'source_fragments': fragments})
                fragments_all.extend(fragments)
    require(same(observation_keys(fragments_all), row.get('actual_prewrite_source_observations')), 'prewrite_observation_link')
    # The accepted final-write prompt replays only earlier host results. This
    # proves pre-write delivery without treating current-batch reads as exposure.
    return deliveries, []


def artifact_case(row, root, task, docs, runtime, inputs, label):
    path = root / 'artifacts/result.json'
    receipt = row.get('write_receipt')
    if not path.is_file():
        require(receipt is None and row.get('artifact') is None, 'written_artifact_missing')
        return None, row.get('failure') or 'no_write_receipt_or_artifact'
    require(isinstance(receipt, dict), 'on_disk_artifact_write_receipt_missing')
    raw = path.read_bytes()
    require(receipt.get('artifact_sha256') == sha(raw), 'artifact_write_receipt_sha_mismatch')
    if 'artifact_bytes' in receipt:
        require(type(receipt['artifact_bytes']) is int and receipt['artifact_bytes'] == len(raw), 'artifact_write_receipt_bytes')
    inputs[label + '/artifacts/result.json'] = {'sha256': sha(raw), 'bytes': len(raw)}
    artifact_text = raw.decode('utf8')
    artifact = strict_json(artifact_text)
    require(same(artifact, row.get('artifact')), 'artifact_retained_value_mismatch')
    deliveries, reasons = exposure(row, root, task, docs, runtime, inputs, label)
    if not reasons:
        require(receipt.get('written') == 'artifacts/result.json' and 'artifact_bytes' in receipt, 'original_write_receipt_shape')
    number = 0
    for delivery_number, delivery in enumerate(deliveries, 1):
        delivery['delivery_id'] = f'D{delivery_number:03d}'
        delivery['actual_result_canonical_sha256'] = sha(encoded(delivery['actual_result']))
        for fragment in delivery['source_fragments']:
            number += 1
            fragment['fragment_id'] = f'F{number:04d}'
    return {'task': task, 'artifact': artifact, 'artifact_utf8': artifact_text,
        'artifact_sha256': sha(raw), 'deliveries': deliveries,
        'extraction_auditability': {'state': 'not_auditable' if reasons else 'auditable', 'reasons': reasons},
        'offset_unit': 'Unicode code points, half-open; source body and actual returned text'}, None


def prepare(study, work, output, freeze_hash, results_hash):
    require(not output.exists(), 'output_already_exists')
    require(not output.resolve().is_relative_to(study.parent.parent.resolve()), 'output_must_be_private_outside_repository')
    inputs = {}
    freeze = read(study / 'freeze.json', inputs, 'study/freeze.json')
    require(inputs['study/freeze.json']['sha256'] == freeze_hash, 'freeze_sha_mismatch')
    pins = freeze['files']
    required = {'reader_trials.py', 'packing_lab.py', 'reader-schedule.json', 'runtime-public.json', 'challenge-bank.json'}
    require(required <= set(pins), 'required_frozen_inputs_missing')
    for name, expected in pins.items():
        path = (study / name).resolve()
        require(path.is_relative_to(study.parent.resolve()), 'freeze_pin_path_escape')
        raw = path.read_bytes()
        require(sha(raw) == expected, 'frozen_input_sha_mismatch:' + name)
        inputs['study/' + name] = {'sha256': sha(raw), 'bytes': len(raw)}
    planned = read(study / 'reader-schedule.json', inputs, 'study/reader-schedule.json')
    results = read(study / 'reader-results.json', inputs, 'study/reader-results.json')
    require(inputs['study/reader-results.json']['sha256'] == results_hash, 'audited_reader_results_sha_mismatch')
    require(results.get('state') == 'complete' and results.get('scheduled_trials') == COUNT and results.get('freeze_sha256') == freeze_hash, 'reader_collection_not_complete')
    jobs = {job['trial_id']: job for job in planned['jobs']}
    rows = {row['trial_id']: row for row in results['results']}
    require(len(planned['jobs']) == len(results['results']) == len(jobs) == len(rows) == COUNT and set(jobs) == set(rows), 'scheduled_reader_census')
    bank = read(study / 'challenge-bank.json', inputs, 'study/challenge-bank.json')
    runtime = read(study / 'runtime-public.json', inputs, 'study/runtime-public.json')
    docs, tasks = observational_documents(bank['families']), {}
    for family in bank['families']:
        for task in family['tasks']:
            require(task['id'] not in tasks, 'duplicate_bank_task')
            tasks[task['id']] = {key: task[key] for key in TASK_FIELDS}
    packets, key, no_write = [], [], []
    fingerprint = sha(freeze_hash + ':reader-trials-v1')
    ordered = sorted(rows, key=lambda identifier: sha('reader-semantic-v1:' + identifier))
    for trial_id in ordered:
        row, job = rows[trial_id], jobs[trial_id]
        require(all(same(row.get(name), value) for name, value in job.items()), 'schedule_trial_identity')
        checkpoint = read(work / 'reader-checkpoints' / (trial_id + '.json'), inputs, 'private/reader-checkpoints/' + trial_id + '.json')
        require(checkpoint.get('fingerprint') == fingerprint and same(checkpoint.get('result'), row), 'checkpoint_result_fixity')
        root = work / 'reader-artifacts' / trial_id
        # Hash all retained trial outputs, including excluded late-fault prompts
        # and diagnostics. Bytes remain private; no native text enters a case.
        for path in sorted(root.rglob('*')):
            if path.is_file():
                require(path.resolve().is_relative_to(root.resolve()), 'trial_output_path_escape')
                raw = path.read_bytes()
                inputs['private/reader-artifacts/' + trial_id + '/' + path.relative_to(root).as_posix()] = {'sha256': sha(raw), 'bytes': len(raw)}
        packet, reason = artifact_case(row, root, tasks[job['task_id']], docs, runtime, inputs, 'private/reader-artifacts/' + trial_id)
        if packet is None:
            no_write.append({'trial_id': trial_id, 'reason': reason})
            continue
        case_id = f'CASE-{len(packets) + 1:03d}'
        packet = {'case_id': case_id, **packet}
        packets.append(packet)
        key.append({'case_id': case_id, 'trial_id': trial_id, 'block': job['block'], 'arm': job['arm']})
    require(len(packets) + len(no_write) == COUNT, 'review_denominator_loss')
    groups, sizes = [[] for _ in range(PARTITIONS)], [0] * PARTITIONS
    for packet in sorted(packets, key=lambda p: (-len(encoded(p, True)), p['case_id'])):
        partition = min(range(PARTITIONS), key=lambda number: (sizes[number], number))
        groups[partition].append(packet)
        sizes[partition] += len(encoded(packet, True))
    output.mkdir(parents=True)
    manifests = []
    for partition, group in enumerate(groups, 1):
        folder = output / ('reviewer-' + str(partition))
        folder.mkdir()
        cases = []
        for packet in sorted(group, key=lambda p: p['case_id']):
            raw = encoded(packet, True)
            (folder / (packet['case_id'] + '.json')).write_bytes(raw)
            cases.append({'case_id': packet['case_id'], 'file': packet['case_id'] + '.json', 'sha256': sha(raw), 'bytes': len(raw)})
        index = {'schema_version': 'oct13-reader-semantic-input-v1', 'cases': cases,
            'instructions': 'Fresh reviewer context; only these packets and frozen SEMANTIC-REVIEW-PLAN.md rubric. Conditions, authored key, primary scores and private key withheld. Review every actual artifact including invalid output. Source IDs and header/content clues remain visible.'}
        raw = encoded(index, True)
        (folder / 'index.json').write_bytes(raw)
        manifests.append({'partition': partition, 'cases': len(cases), 'case_bytes': sizes[partition - 1], 'index_sha256': sha(raw)})
    (output / 'PRIVATE-key.json').write_bytes(encoded({'mapping': key, 'no_write_trials': no_write}, True))
    manifest = {'schema_version': 'oct13-reader-review-preparation-v1', 'state': 'prepared_not_reviewed',
        'scheduled_trials': COUNT, 'written_artifacts': len(packets), 'no_write_trials': len(no_write),
        'not_auditable_artifacts': sum(p['extraction_auditability']['state'] == 'not_auditable' for p in packets),
        'no_write_reasons': dict(Counter(row['reason'] for row in no_write)), 'partitions': manifests,
        'input_files': inputs, 'preparer_sha256': sha(Path(__file__).read_bytes()),
        'primary_scores_modified': False, 'publication': 'Private preparation only; root must independently verify extraction/fixity/denominator after actual outcome audit before review or public aggregation.'}
    (output / 'PRIVATE-preparation.json').write_bytes(encoded(manifest, True))
    print(json.dumps({key: manifest[key] for key in ('state', 'scheduled_trials', 'written_artifacts', 'no_write_trials', 'not_auditable_artifacts')}, sort_keys=True))


def self_check():
    def must_fail(function):
        try:
            function()
        except (ValueError, FileNotFoundError):
            return
        raise AssertionError('negative_self_check_accepted')
    doc = {'id': 'S', 'kind': 'source', 'revision': 1, 'body': '青灯\nA😀e\u0301 is false.\nUnseen omega scope.',
        'path': 'records/s.md', 'scope': 'omega', 'title': 'Hidden title', 'aliases': ['hidden'],
        'authored_at': '2026-01-01', 'links': [], 'supersedes': [], 'incorporates': []}
    raw_record = {key: value for key, value in doc.items() if key != 'aliases'}
    docs = observational_documents([{'name': 'fixture', 'aliases': ['seen-alias'], 'records': [raw_record]}])
    doc = docs['S']
    assert 'aliases' not in raw_record and doc['aliases'] == ['fixture', 'seen-alias']
    header = {'id': 'S', 'chars': [3, 18], 'kind': 'source', 'revision': 1}
    packet = 'SOURCE ' + encoded(header).decode('utf8') + '\n' + doc['body'][3:18]
    fragments = packet_fragments(packet, docs)
    assert fragments[0]['text'] == doc['body'][3:18] and 'scope' not in fragments[0]
    assert packet[slice(*fragments[0]['delivered_text_chars'])] == fragments[0]['text']
    verbose = {**header, **{key: doc.get(key) for key in VERBOSE - MINIMAL}}
    verbose_packet = 'SOURCE ' + encoded(verbose).decode('utf8') + '\n' + doc['body'][3:18]
    assert packet_fragments(verbose_packet, docs)[0]['text'] == doc['body'][3:18]
    assert 'seen-alias' in verbose_packet and 'scope' not in packet_fragments(verbose_packet, docs)[0]
    bad = {**header, 'scope': 'omega'}
    must_fail(lambda: packet_fragments('SOURCE ' + encoded(bad).decode('utf8') + '\n' + doc['body'][3:18], docs))
    bad = {**header, 'chars': [True, 18]}
    must_fail(lambda: packet_fragments('SOURCE ' + encoded(bad).decode('utf8') + '\n' + doc['body'][3:18], docs))
    search = {'matches': [{'path': doc['path'], 'id': 'S', 'line': 1, 'start': 0, 'end': 2, 'text': '青灯'}], 'total_matches': 1, 'truncated': False}
    assert 'revision' not in tool_fragments({'tool': 'search'}, search, docs)[0]
    bad = copy.deepcopy(search); bad['matches'][0]['revision'] = 1
    must_fail(lambda: tool_fragments({'tool': 'search'}, bad, docs))
    assert not same(True, 1) and not same({'flag': False}, {'flag': 0})
    must_fail(lambda: strict_json('{"flag":true,"flag":false}'))
    must_fail(lambda: strict_json('{"value":1e999}'))
    must_fail(lambda: strict_json('"\\ud800"'))
    task = {'id': 'T', 'query': 'Is the flag set?', 'answer_keys': ['flag'],
        'answer_contract': {'fields': {'flag': {'type': 'boolean'}}, 'additional_fields': False}}
    artifact = {'status': 'ready', 'answer': {'flag': False}, 'evidence': []}
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); (root / 'artifacts').mkdir()
        raw = encoded(artifact, True); (root / 'artifacts/result.json').write_bytes(raw)
        receipt = {'written': 'artifacts/result.json', 'artifact_sha256': sha(raw), 'artifact_bytes': len(raw), 'check': {'schema_valid': True}}
        prompt = 'protocol\nTASK AND CONTRACT\n' + json.dumps(task, ensure_ascii=False, sort_keys=True) + '\nSTATE\n{}\nYOUR REPLAYED TRIAL HISTORY\n[]'
        actions = [{'tool': 'read', 'path': doc['path']}, {'tool': 'write', 'path': 'artifacts/result.json', 'content': artifact}]
        response = {'actions': actions, 'done': True}
        (root / 'round-1-prompt.json').write_bytes(encoded({'prompt': prompt, 'prompt_sha256': sha(prompt)}, True))
        persisted = {'identity': sha(prompt + '{}'), 'text': encoded(response).decode('utf8'), 'call': {'accepted': True}}
        (root / 'round-1-call.json').write_bytes(encoded(persisted, True))
        row = {'block': 'discovery', 'artifact': artifact, 'write_receipt': receipt,
            'events': [{'seq': 1, 'round': 1, 'executed': True, 'action': actions[0], 'result': {'path': doc['path'], 'text': packet}, 'delivered_source_observations': observation_keys(fragments)},
                {'seq': 2, 'round': 1, 'executed': True, 'action': actions[1], 'result': receipt, 'delivered_source_observations': []}],
            'actual_prewrite_source_observations': [], 'failure': None}
        case, reason = artifact_case(row, root, task, docs, {}, {}, 'fixture')
        assert reason is None and not case['deliveries'] and case['extraction_auditability']['state'] == 'auditable'
        # A successful same-batch read still cannot ground that batch's write.
        bad = copy.deepcopy(row); bad['actual_prewrite_source_observations'] = observation_keys(fragments)
        must_fail(lambda: artifact_case(bad, root, task, docs, {}, {}, 'fixture'))
        # A prior-round search result becomes evidence only when a later accepted
        # prompt actually replays it before that later response's write.
        history = [{'assistant': {'actions': [{'tool': 'search', 'query': '青灯'}], 'done': False}, 'host_results': [search]}]
        search_fragments = tool_fragments(history[0]['assistant']['actions'][0], search, docs)
        later_prompt = prompt.rsplit('[]', 1)[0] + json.dumps(history, ensure_ascii=False, sort_keys=True)
        later_reply = {'actions': [actions[1]], 'done': True}
        (root / 'round-2-prompt.json').write_bytes(encoded({'prompt': later_prompt, 'prompt_sha256': sha(later_prompt)}, True))
        (root / 'round-2-call.json').write_bytes(encoded({'identity': sha(later_prompt + '{}'), 'text': encoded(later_reply).decode('utf8'), 'call': {'accepted': True}}, True))
        later = {**row, 'events': [{'seq': 1, 'round': 1, 'executed': True, 'action': history[0]['assistant']['actions'][0], 'result': search, 'delivered_source_observations': observation_keys(search_fragments)},
            {'seq': 2, 'round': 2, 'executed': True, 'action': actions[1], 'result': receipt, 'delivered_source_observations': []}], 'actual_prewrite_source_observations': observation_keys(search_fragments)}
        case, _ = artifact_case(later, root, task, docs, {}, {}, 'fixture')
        assert len(case['deliveries']) == 1 and case['deliveries'][0]['actual_result'] == search
        assert 'revision' not in case['deliveries'][0]['source_fragments'][0]
        direct_prompt = 'protocol\nTASK AND CONTRACT\n' + json.dumps(task, ensure_ascii=False, sort_keys=True) + '\nSUPPLIED EVIDENCE\n' + packet
        (root / 'public-prompt.json').write_bytes(encoded({'prompt': direct_prompt, 'prompt_sha256': sha(direct_prompt)}, True))
        (root / 'direct-call.json').write_bytes(encoded({'identity': sha(direct_prompt + '{}'), 'text': encoded(artifact).decode('utf8'), 'call': {'accepted': True}}, True))
        direct = {**row, 'block': 'direct', 'events': [{'packet_sha256': sha(packet), 'packet_bytes': len(packet.encode('utf8')), 'response_text': encoded(artifact).decode('utf8')}], 'actual_prewrite_source_observations': observation_keys(fragments)}
        case, _ = artifact_case(direct, root, task, docs, {}, {}, 'fixture')
        assert case['deliveries'][0]['source_fragments'][0]['text'] == doc['body'][3:18]
        assert 'Unseen omega scope.' not in case['deliveries'][0]['actual_result']['packet']
        persisted['call']['accepted'] = False
        (root / 'round-1-call.json').write_bytes(encoded(persisted, True))
        case, _ = artifact_case(row, root, task, docs, {}, {}, 'fixture')
        assert not case['deliveries'] and case['extraction_auditability']['state'] == 'not_auditable'
        bad = copy.deepcopy(row); bad['failure'] = 'trial_execution_error'; bad['events'] = []
        case, _ = artifact_case(bad, root, task, docs, {}, {}, 'fixture')
        assert not case['deliveries'] and 'late_fault_missing_final_write_chronology' in case['extraction_auditability']['reasons']
        bad = copy.deepcopy(row); bad['write_receipt']['artifact_sha256'] = '0' * 64
        must_fail(lambda: artifact_case(bad, root, task, docs, {}, {}, 'fixture'))
        bad = copy.deepcopy(row); bad['artifact']['answer']['flag'] = 0
        must_fail(lambda: artifact_case(bad, root, task, docs, {}, {}, 'fixture'))
        (root / 'artifacts/result.json').unlink()
        must_fail(lambda: artifact_case(row, root, task, docs, {}, {}, 'fixture'))
        no_write = {**row, 'artifact': None, 'write_receipt': None, 'failure': 'no_artifact'}
        assert artifact_case(no_write, root, task, docs, {}, {}, 'fixture') == (None, 'no_artifact')
    print(json.dumps({'state': 'PASS', 'checks': ['Unicode fragment offsets', 'observational alias projection and verbose header', 'unseen metadata rejection', 'same-batch pre-write exclusion', 'accepted prior-round search exposure', 'direct partial packet exposure', 'failed upstream exclusion', 'late-fault inclusion without exposure', 'strict boolean identity', 'nonfinite exponent and lone surrogate rejection', 'missing artifact rejection', 'artifact SHA rejection', 'no-write denominator retention'], 'main_outcomes_read': False}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--self-check', action='store_true')
    mode.add_argument('--prepare', action='store_true')
    parser.add_argument('--study', type=Path, default=HERE)
    parser.add_argument('--private-work', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--freeze-sha256')
    parser.add_argument('--results-sha256')
    args = parser.parse_args()
    if args.self_check:
        self_check()
    else:
        require(args.private_work is not None and args.output is not None, 'private_work_and_output_required')
        require(all(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) for value in (args.freeze_sha256, args.results_sha256)), 'explicit_audited_hashes_required')
        prepare(args.study.resolve(), args.private_work.resolve(), args.output.resolve(), args.freeze_sha256, args.results_sha256)


if __name__ == '__main__':
    main()
