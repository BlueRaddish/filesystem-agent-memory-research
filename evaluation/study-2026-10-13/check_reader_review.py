"""Mechanical validation of audited, opaque supplemental reader judgments.

--self-check reads source pins and fictional temporary fixtures only. --check
requires an explicitly audited PRIVATE-preparation.json SHA256; it never reads
the private condition key, reader results, bank, gold, or primary scores.

Judgment JSON: schema_version, preparation_sha256, plan_sha256, preparer_sha256,
freeze_sha256, cases. Each case has the rubric's exact fields. A review citation
is {fragment_id, start, end}, using source-body Unicode code-point offsets.
This validates provenance/census/coordinates, not the truth of a judgment.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PLAN_SHA = '3c06cf6c3a4ee965743a4f0ca1a515f16fd42eb292f2d3ca5cf63c59091a200a'
PREPARER_SHA = 'ad4fe9cd81b00c2cb04762650fe2f60c062acf1fe3b24ecc9687de7e4504d76c'
FREEZE_SHA = 'fda01f88f50dbb6e66a312ca9ab775c8603643ebe8b7f74b596a7250bc39524c'
LABELS = {'supported', 'contradicted', 'not_established', 'not_auditable'}
CASE_KEYS = {'case_id', 'task', 'artifact', 'artifact_utf8', 'artifact_sha256', 'deliveries', 'extraction_auditability', 'offset_unit'}
JUDGMENT_KEYS = {'case_id', 'input_sha256', 'answer_judgments', 'status_judgment', 'citation_judgment', 'full_query_judgment', 'limitations'}


def require(value, reason):
    if not value:
        raise ValueError(reason)


def file_sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def hash_string(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def helpers():
    for name, expected in [('SEMANTIC-REVIEW-PLAN.md', PLAN_SHA), ('prepare_reader_review.py', PREPARER_SHA), ('freeze.json', FREEZE_SHA)]:
        require(file_sha(HERE / name) == expected, 'prospective_source_pin_changed:' + name)
    spec = importlib.util.spec_from_file_location('pinned_reader_review_json_helpers', HERE / 'prepare_reader_review.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # Definitions only; the preparer's CLI is guarded.
    return module


def input_path(path, private_key, boundary=None):
    require(path.name.casefold() != private_key.name.casefold() and path.resolve() != private_key.resolve()
            and not (path.exists() and private_key.exists() and os.path.samefile(path, private_key)), 'private_condition_key_must_not_be_read')
    require(boundary is None or path.resolve().is_relative_to(boundary.resolve()), 'input_path_escape')


def read(path, h, expected=None, size=None, private_key=None, boundary=None):
    if private_key is not None:
        input_path(path, private_key, boundary)
    raw = path.read_bytes()
    require(expected is None or h.sha(raw) == expected, 'input_sha_mismatch')
    require(size is None or len(raw) == size, 'input_bytes_mismatch')
    return h.strict_json(raw.decode('utf8'))


def packet_records(text, h):
    require(isinstance(text, str), 'delivered_packet_not_text')
    records, cursor = {}, 0
    while cursor < len(text):
        require(text.startswith('SOURCE ', cursor), 'delivered_source_header_missing')
        newline = text.find('\n', cursor)
        require(newline >= 0, 'delivered_source_header_unterminated')
        header = h.strict_json(text[cursor + 7:newline])
        require(isinstance(header, dict) and isinstance(header.get('id'), str) and isinstance(header.get('kind'), str), 'delivered_source_header_shape')
        bounds = header.get('chars')
        require(isinstance(bounds, list) and len(bounds) == 2 and all(type(v) is int for v in bounds)
                and 0 <= bounds[0] < bounds[1], 'delivered_source_bounds')
        start, end = newline + 1, newline + 1 + bounds[1] - bounds[0]
        require(end <= len(text), 'delivered_source_body_short')
        records[(start, end)] = header
        cursor = end
        if cursor < len(text):
            require(text.startswith('\n\nSOURCE ', cursor), 'delivered_source_separator')
            cursor += 2
    return records


def fragments(case, h):
    require(isinstance(case, dict) and set(case) == CASE_KEYS, 'opaque_case_fields')
    task = case['task']
    require(isinstance(task, dict) and set(task) == {'id', 'query', 'answer_keys', 'answer_contract'}
            and isinstance(task['id'], str) and isinstance(task['query'], str) and isinstance(task['answer_contract'], dict), 'opaque_task_fields')
    keys = task['answer_keys']
    require(isinstance(keys, list) and all(isinstance(k, str) and k for k in keys)
            and len(keys) == len(set(keys)), 'requested_answer_keys')
    require(isinstance(case['artifact_utf8'], str) and hash_string(case['artifact_sha256'])
            and h.sha(case['artifact_utf8']) == case['artifact_sha256']
            and h.same(h.strict_json(case['artifact_utf8']), case['artifact']), 'actual_artifact_fixity')
    require(case['offset_unit'] == 'Unicode code points, half-open; source body and actual returned text', 'offset_unit')
    audit = case['extraction_auditability']
    require(isinstance(audit, dict) and set(audit) == {'state', 'reasons'} and audit['state'] in {'auditable', 'not_auditable'}
            and isinstance(audit['reasons'], list) and all(isinstance(v, str) and v.strip() for v in audit['reasons'])
            and (bool(audit['reasons']) == (audit['state'] == 'not_auditable')), 'extraction_auditability')
    require(isinstance(case['deliveries'], list), 'deliveries_type')
    found = {}
    for number, delivery in enumerate(case['deliveries'], 1):
        require(isinstance(delivery, dict) and set(delivery) == {'operation', 'actual_result', 'prompt_sha256', 'source_fragments', 'delivery_id', 'actual_result_canonical_sha256'}
                and delivery['delivery_id'] == f'D{number:03d}' and hash_string(delivery['prompt_sha256'])
                and delivery['actual_result_canonical_sha256'] == h.sha(h.encoded(delivery['actual_result']))
                and isinstance(delivery['source_fragments'], list), 'delivery_fixity')
        operation, actual = delivery['operation'], delivery['actual_result']
        require(operation in {'supplied_packet', 'read', 'retrieve', 'search'} and isinstance(actual, dict), 'delivery_operation')
        field = 'text' if operation == 'read' else 'packet'
        records = packet_records(actual.get(field), h) if operation != 'search' else None
        for fragment in delivery['source_fragments']:
            require(isinstance(fragment, dict) and set(fragment) == {'fragment_id', 'id', 'start', 'end', 'text', 'source_body_sha256', 'result_text_pointer', 'delivered_text_chars'}, 'fragment_fields')
            identifier = fragment['fragment_id']
            require(identifier == f'F{len(found) + 1:04d}' and identifier not in found, 'fragment_census')
            start, end, text = fragment['start'], fragment['end'], fragment['text']
            require(type(start) is int and type(end) is int and 0 <= start < end
                    and isinstance(text, str) and end - start == len(text)
                    and isinstance(fragment['id'], str) and hash_string(fragment['source_body_sha256']), 'fragment_unicode_bounds')
            chars = fragment['delivered_text_chars']
            require(isinstance(chars, list) and len(chars) == 2 and all(type(v) is int for v in chars), 'returned_text_bounds_type')
            if operation == 'search':
                match = re.fullmatch(r'/matches/(0|[1-9][0-9]*)/text', fragment['result_text_pointer']) if isinstance(fragment['result_text_pointer'], str) else None
                require(match is not None and isinstance(actual.get('matches'), list)
                        and int(match[1]) < len(actual['matches']), 'search_fragment_pointer')
                item = actual['matches'][int(match[1])]
                require(isinstance(item, dict) and item.get('id') == fragment['id']
                        and type(item.get('start')) is int and type(item.get('end')) is int
                        and item['start'] == start and item['end'] == end and item.get('text') == text
                        and chars == [0, len(text)], 'search_fragment_crosslink')
                original = True  # Pinned preparer permits search results from originals only.
            else:
                require(fragment['result_text_pointer'] == '/' + field and tuple(chars) in records
                        and 0 <= chars[0] < chars[1] <= len(actual[field])
                        and actual[field][chars[0]:chars[1]] == text, 'packet_fragment_crosslink')
                header = records[tuple(chars)]
                require(header['id'] == fragment['id'] and header['chars'] == [start, end], 'packet_original_interval_crosslink')
                original = header['kind'] == 'source'
            found[identifier] = {'start': start, 'end': end, 'original': original}
    return found


def entry(value, supplied):
    require(isinstance(value, dict) and set(value) == {'label', 'rationale', 'citations'}
            and isinstance(value['label'], str) and value['label'] in LABELS, 'judgment_entry_shape_or_label')
    rationale = value['rationale']
    # This text floor catches blanks/placeholders, not substantive entailment.
    # Reviewer/root review must assess specificity; no semantic heuristic is added.
    require(isinstance(rationale, str) and len(rationale.strip()) >= 12
            and any(c.isalpha() for c in rationale) and rationale.strip() not in LABELS, 'rationale_not_substantive_text')
    require(isinstance(value['citations'], list), 'review_citations_type')
    for citation in value['citations']:
        require(isinstance(citation, dict) and set(citation) == {'fragment_id', 'start', 'end'}
                and isinstance(citation['fragment_id'], str) and citation['fragment_id'] in supplied, 'unknown_review_fragment')
        fragment = supplied[citation['fragment_id']]
        require(fragment['original'], 'derived_fragment_not_original')
        require(type(citation['start']) is int and type(citation['end']) is int
                and fragment['start'] <= citation['start'] < citation['end'] <= fragment['end'], 'review_citation_unicode_bounds')
    # Empty evidence may justify an evidence-bounded hold or unauditable status;
    # citation presence and semantic entailment are not inferred from the label.


def validate(preparation, judgments, audited_sha, h):
    require(hash_string(audited_sha), 'explicit_audited_preparation_sha_required')
    private_key = preparation / 'PRIVATE-key.json'
    input_path(judgments, private_key)
    manifest = read(preparation / 'PRIVATE-preparation.json', h, audited_sha, private_key=private_key, boundary=preparation)
    require(isinstance(manifest, dict) and manifest.get('schema_version') == 'oct13-reader-review-preparation-v1'
            and manifest.get('state') == 'prepared_not_reviewed' and manifest.get('preparer_sha256') == PREPARER_SHA
            and manifest.get('primary_scores_modified') is False, 'audited_preparation_binding')
    for key in ['scheduled_trials', 'written_artifacts', 'no_write_trials', 'not_auditable_artifacts']:
        require(type(manifest.get(key)) is int and manifest[key] >= 0, 'preparation_count_type')
    require(manifest['scheduled_trials'] == 192 and manifest['written_artifacts'] + manifest['no_write_trials'] == 192, 'scheduled_denominator')
    reasons = manifest.get('no_write_reasons')
    require(isinstance(reasons, dict) and all(isinstance(k, str) and k and type(v) is int and v > 0 for k, v in reasons.items())
            and sum(reasons.values()) == manifest['no_write_trials'], 'no_write_reason_census')
    inputs = manifest.get('input_files')
    require(isinstance(inputs, dict) and isinstance(inputs.get('study/freeze.json'), dict)
            and isinstance(inputs.get('study/reader-results.json'), dict)
            and inputs['study/freeze.json'].get('sha256') == FREEZE_SHA
            and hash_string(inputs['study/reader-results.json'].get('sha256')), 'audited_input_bindings')
    partitions = manifest.get('partitions')
    require(isinstance(partitions, list) and len(partitions) == 3, 'partition_census')
    cases, case_hashes, actual_groups, case_sizes = {}, {}, [], {}
    for number, partition in enumerate(partitions, 1):
        require(isinstance(partition, dict) and set(partition) == {'partition', 'cases', 'case_bytes', 'index_sha256'}
                and type(partition['partition']) is int and partition['partition'] == number
                and type(partition['cases']) is int and partition['cases'] >= 0
                and type(partition['case_bytes']) is int and partition['case_bytes'] >= 0
                and hash_string(partition['index_sha256']), 'partition_fields')
        folder = preparation / f'reviewer-{number}'
        require(folder.resolve().is_relative_to(preparation.resolve()), 'reviewer_folder_path_escape')
        index = read(folder / 'index.json', h, partition['index_sha256'], private_key=private_key, boundary=folder)
        require(isinstance(index, dict) and set(index) == {'schema_version', 'cases', 'instructions'}
                and index['schema_version'] == 'oct13-reader-semantic-input-v1' and isinstance(index['instructions'], str)
                and isinstance(index['cases'], list) and len(index['cases']) == partition['cases'], 'partition_index_census')
        group, total = set(), 0
        for item in index['cases']:
            require(isinstance(item, dict) and set(item) == {'case_id', 'file', 'sha256', 'bytes'}
                    and isinstance(item['case_id'], str) and re.fullmatch(r'CASE-[0-9]{3}', item['case_id'])
                    and item['file'] == item['case_id'] + '.json' and hash_string(item['sha256'])
                    and type(item['bytes']) is int and item['bytes'] > 0, 'case_index_fields')
            identifier = item['case_id']
            require(identifier not in cases, 'repeated_case_or_partition_overlap')
            path = folder / item['file']
            require(path.resolve().is_relative_to(folder.resolve()), 'case_path_escape')
            case = read(path, h, item['sha256'], item['bytes'], private_key=private_key, boundary=folder)
            require(isinstance(case, dict) and case.get('case_id') == identifier
                    and h.sha(h.encoded(case, True)) == item['sha256'], 'opaque_case_identity_or_serialization')
            fragments(case, h)
            cases[identifier], case_hashes[identifier], case_sizes[identifier] = case, item['sha256'], item['bytes']
            group.add(identifier); total += item['bytes']
        require({p.name for p in folder.glob('*.json')} == {'index.json'} | {c + '.json' for c in group}, 'extra_or_missing_case_files')
        require(total == partition['case_bytes'], 'partition_byte_census')
        actual_groups.append(group)
    require(set(cases) == {f'CASE-{i:03d}' for i in range(1, manifest['written_artifacts'] + 1)}, 'written_case_census')
    require(sum(c['extraction_auditability']['state'] == 'not_auditable' for c in cases.values()) == manifest['not_auditable_artifacts'], 'not_auditable_census')
    sizes, expected_groups = [0] * 3, [set() for _ in range(3)]
    # The case fixity/serialization checks make these byte sizes exactly the
    # preparer's len(encoded(packet, True)); both tie orders are unchanged.
    for identifier in sorted(cases, key=lambda c: (-case_sizes[c], c)):
        target = min(range(3), key=lambda n: (sizes[n], n))
        expected_groups[target].add(identifier); sizes[target] += case_sizes[identifier]
    require(actual_groups == expected_groups, 'disjoint_size_balanced_partitions')
    review = read(judgments, h, private_key=private_key)
    require(isinstance(review, dict) and set(review) == {'schema_version', 'preparation_sha256', 'plan_sha256', 'preparer_sha256', 'freeze_sha256', 'cases'}
            and review['schema_version'] == 'oct13-reader-semantic-judgments-v1'
            and review['preparation_sha256'] == audited_sha and review['plan_sha256'] == PLAN_SHA
            and review['preparer_sha256'] == PREPARER_SHA and review['freeze_sha256'] == FREEZE_SHA
            and isinstance(review['cases'], list), 'judgment_prospective_bindings')
    seen = set()
    for judgment in review['cases']:
        require(isinstance(judgment, dict) and set(judgment) == JUDGMENT_KEYS, 'case_judgment_fields')
        identifier = judgment['case_id']
        require(isinstance(identifier, str) and identifier in cases and identifier not in seen, 'unknown_or_repeated_judgment_case')
        seen.add(identifier)
        require(judgment['input_sha256'] == case_hashes[identifier], 'judgment_case_sha_mismatch')
        answers = judgment['answer_judgments']
        require(isinstance(answers, dict) and set(answers) == set(cases[identifier]['task']['answer_keys']), 'requested_answer_judgment_census')
        supplied = fragments(cases[identifier], h)
        for value in [*answers.values(), *[judgment[k] for k in ['status_judgment', 'citation_judgment', 'full_query_judgment']]]:
            entry(value, supplied)
        require(isinstance(judgment['limitations'], list) and all(isinstance(v, str) and v.strip() for v in judgment['limitations']), 'limitations_type')
    require(seen == set(cases), 'missing_judgment_cases')
    return {'state': 'PASS_MECHANICAL_REVIEW_VALIDATION', 'scheduled_trials': 192,
            'written_artifacts': len(cases), 'reviewed_cases': len(seen), 'no_write_trials': manifest['no_write_trials'],
            'preparation_sha256': audited_sha, 'primary_scores_modified': 0, 'semantic_judgments_adjudicated': 0,
            'private_condition_key_read': False, 'model_provider_calls': 0}


def self_check(h):
    passed, skipped = 0, []
    def reject(fn, reason=None):
        nonlocal passed
        try: fn()
        except (ValueError, KeyError, TypeError, UnicodeError) as error:
            require(reason is None or str(error) == reason, 'negative_fixture_wrong_rejection')
            passed += 1
        else: raise AssertionError('negative_fixture_accepted')
    for text in ['{"a":1,"a":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e1000}', '{"x":"\\ud800"}', '{"\\udfff":0}']:
        reject(lambda text=text: h.strict_json(text))
    original_text, derived_text = 'A😀e\u0301 = false.', 'Derived summary.'
    blocks, supplied, cursor = [], [], 0
    for n, (identifier, kind, text, start) in enumerate([('S', 'source', original_text, 7), ('V', 'derived', derived_text, 0)], 1):
        header = 'SOURCE ' + h.encoded({'id': identifier, 'kind': kind, 'revision': 1, 'chars': [start, start + len(text)]}).decode() + '\n'
        if blocks: cursor += 2
        body_start = cursor + len(header)
        supplied.append({'fragment_id': f'F{n:04d}', 'id': identifier, 'start': start, 'end': start + len(text), 'text': text,
            'source_body_sha256': h.sha('fictional body ' + text), 'result_text_pointer': '/packet', 'delivered_text_chars': [body_start, body_start + len(text)]})
        blocks.append(header + text); cursor = body_start + len(text)
    actual = {'packet': '\n\n'.join(blocks)}
    artifact = [0]  # Intentionally contract-invalid; the validator must preserve it.
    case = {'case_id': 'CASE-001', 'task': {'id': 'T', 'query': 'Resolve the flag.', 'answer_keys': ['flag'], 'answer_contract': {'flag': 'boolean'}},
        'artifact': artifact, 'artifact_utf8': h.encoded(artifact).decode(), 'artifact_sha256': h.sha(h.encoded(artifact)),
        'deliveries': [{'operation': 'supplied_packet', 'actual_result': actual, 'prompt_sha256': h.sha('fictional prompt'),
            'source_fragments': supplied, 'delivery_id': 'D001', 'actual_result_canonical_sha256': h.sha(h.encoded(actual))}],
        'extraction_auditability': {'state': 'auditable', 'reasons': []},
        'offset_unit': 'Unicode code points, half-open; source body and actual returned text'}
    citation = {'fragment_id': 'F0001', 'start': 7, 'end': 7 + len(original_text)}
    item = {'label': 'not_established', 'rationale': 'The requested field is absent in the retained output.', 'citations': [citation]}
    judgment = {'case_id': 'CASE-001', 'input_sha256': h.sha(h.encoded(case, True)), 'answer_judgments': {'flag': copy.deepcopy(item)},
        'status_judgment': {'label': 'supported', 'rationale': 'An evidence boundary can be described without positive source citations.', 'citations': []},
        'citation_judgment': {'label': 'contradicted', 'rationale': 'The supplied original span is available for reviewer assessment.', 'citations': [copy.deepcopy(citation)]},
        'full_query_judgment': {'label': 'not_auditable', 'rationale': 'Missing proof limits the assessment of the complete request.', 'citations': []}, 'limitations': []}
    with tempfile.TemporaryDirectory(prefix='reader-review-validator-fictional-') as name:
        root = Path(name); groups = []
        for number in range(1, 4):
            folder = root / f'reviewer-{number}'; folder.mkdir()
            entries = []
            if number == 1:
                raw = h.encoded(case, True); (folder / 'CASE-001.json').write_bytes(raw)
                entries = [{'case_id': 'CASE-001', 'file': 'CASE-001.json', 'sha256': h.sha(raw), 'bytes': len(raw)}]
            index_raw = h.encoded({'schema_version': 'oct13-reader-semantic-input-v1', 'cases': entries, 'instructions': 'Fictional fixture only.'}, True)
            (folder / 'index.json').write_bytes(index_raw)
            groups.append({'partition': number, 'cases': len(entries), 'case_bytes': sum(e['bytes'] for e in entries), 'index_sha256': h.sha(index_raw)})
        manifest = {'schema_version': 'oct13-reader-review-preparation-v1', 'state': 'prepared_not_reviewed', 'scheduled_trials': 192,
            'written_artifacts': 1, 'no_write_trials': 191, 'not_auditable_artifacts': 0, 'no_write_reasons': {'fictional_no_write': 191},
            'partitions': groups, 'input_files': {'study/freeze.json': {'sha256': FREEZE_SHA}, 'study/reader-results.json': {'sha256': h.sha('fictional results')}},
            'preparer_sha256': PREPARER_SHA, 'primary_scores_modified': False}
        raw = h.encoded(manifest, True); (root / 'PRIVATE-preparation.json').write_bytes(raw); binding = h.sha(raw)
        review = {'schema_version': 'oct13-reader-semantic-judgments-v1', 'preparation_sha256': binding, 'plan_sha256': PLAN_SHA,
            'preparer_sha256': PREPARER_SHA, 'freeze_sha256': FREEZE_SHA, 'cases': [judgment]}
        path = root / 'judgments.json'; path.write_bytes(h.encoded(review, True))
        require(validate(root, path, binding, h)['reviewed_cases'] == 1, 'normal_fixture_failed'); passed += 1
        reject(lambda: validate(root, path, '0' * 64, h))
        reject(lambda: validate(root, root / 'PRIVATE-key.json', binding, h), 'private_condition_key_must_not_be_read')
        unicode_item = copy.deepcopy(item); unicode_item['citations'][0].update(start=8, end=9)
        entry(unicode_item, fragments(case, h)); passed += 1  # One astral code point.
        variations = []
        for key in ['preparation_sha256', 'plan_sha256', 'preparer_sha256', 'freeze_sha256']:
            bad = copy.deepcopy(review); bad[key] = '0' * 64; variations.append(bad)
        for key, value in [('input_sha256', '0' * 64), ('case_id', 'CASE-999'), ('limitations', 'not a list')]:
            bad = copy.deepcopy(review); bad['cases'][0][key] = value; variations.append(bad)
        for cases in [[], [judgment, judgment]]:
            bad = copy.deepcopy(review); bad['cases'] = copy.deepcopy(cases); variations.append(bad)
        for key in ['missing', 'extra']:
            bad = copy.deepcopy(review)
            if key == 'missing': bad['cases'][0]['answer_judgments'] = {}
            else: bad['cases'][0]['answer_judgments']['extra'] = copy.deepcopy(item)
            variations.append(bad)
        for key, value in [('label', 'unknown'), ('rationale', ' '), ('citations', {}), ('label', True)]:
            bad = copy.deepcopy(review); bad['cases'][0]['answer_judgments']['flag'][key] = value; variations.append(bad)
        for cite in [{'fragment_id': 'unknown', 'start': 7, 'end': 8}, {'fragment_id': 'F0002', 'start': 0, 'end': 1},
                     {'fragment_id': 'F0001', 'start': 6, 'end': 8}, {'fragment_id': 'F0001', 'start': 7, 'end': 999},
                     {'fragment_id': 'F0001', 'start': 7, 'end': 7}, {'fragment_id': 'F0001', 'start': True, 'end': 8},
                     {'fragment_id': 'F0001', 'start': 7, 'end': True}]:
            bad = copy.deepcopy(review); bad['cases'][0]['answer_judgments']['flag']['citations'] = [cite]; variations.append(bad)
        for bad in variations:
            path.write_bytes(h.encoded(bad, True)); reject(lambda: validate(root, path, binding, h))
        path.write_bytes(h.encoded(review, True))
        case_path = root / 'reviewer-1/CASE-001.json'; original = case_path.read_bytes()
        case_path.write_bytes(original + b' '); reject(lambda: validate(root, path, binding, h)); case_path.write_bytes(original)
        manifest_path = root / 'PRIVATE-preparation.json'
        bad_manifest = copy.deepcopy(manifest); bad_manifest['partitions'] = bad_manifest['partitions'][:2]
        bad_raw = h.encoded(bad_manifest, True); manifest_path.write_bytes(bad_raw)
        reject(lambda: validate(root, path, h.sha(bad_raw), h), 'partition_census'); manifest_path.write_bytes(raw)
        index2 = root / 'reviewer-2/index.json'; old_index2 = index2.read_bytes()
        duplicate_index = {'schema_version': 'oct13-reader-semantic-input-v1', 'instructions': 'Fictional duplicate.',
            'cases': [{'case_id': 'CASE-001', 'file': 'CASE-001.json', 'sha256': h.sha(original), 'bytes': len(original)}]}
        duplicate_raw = h.encoded(duplicate_index, True); index2.write_bytes(duplicate_raw)
        bad_manifest = copy.deepcopy(manifest); bad_manifest['partitions'][1].update(cases=1, case_bytes=len(original), index_sha256=h.sha(duplicate_raw))
        bad_raw = h.encoded(bad_manifest, True); manifest_path.write_bytes(bad_raw)
        reject(lambda: validate(root, path, h.sha(bad_raw), h), 'repeated_case_or_partition_overlap')
        index2.write_bytes(old_index2); manifest_path.write_bytes(raw)
        empty_case = copy.deepcopy(case); empty_case['deliveries'] = []
        empty_case['extraction_auditability'] = {'state': 'not_auditable', 'reasons': ['Fictional missing chronology.']}
        empty_raw = h.encoded(empty_case, True); case_path.write_bytes(empty_raw)
        index1 = root / 'reviewer-1/index.json'; old_index1 = index1.read_bytes()
        empty_index = h.strict_json(old_index1.decode()); empty_index['cases'][0].update(sha256=h.sha(empty_raw), bytes=len(empty_raw))
        empty_index_raw = h.encoded(empty_index, True); index1.write_bytes(empty_index_raw)
        empty_manifest = copy.deepcopy(manifest); empty_manifest['not_auditable_artifacts'] = 1
        empty_manifest['partitions'][0].update(case_bytes=len(empty_raw), index_sha256=h.sha(empty_index_raw))
        empty_manifest_raw = h.encoded(empty_manifest, True); manifest_path.write_bytes(empty_manifest_raw)
        empty_review = copy.deepcopy(review); empty_review['preparation_sha256'] = h.sha(empty_manifest_raw)
        empty_judgment = empty_review['cases'][0]; empty_judgment['input_sha256'] = h.sha(empty_raw)
        for value in [*empty_judgment['answer_judgments'].values(), *[empty_judgment[k] for k in ['status_judgment', 'citation_judgment', 'full_query_judgment']]]:
            value['citations'] = []
        path.write_bytes(h.encoded(empty_review, True))
        require(validate(root, path, h.sha(empty_manifest_raw), h)['reviewed_cases'] == 1, 'empty_evidence_fixture_failed'); passed += 1
        case_path.write_bytes(original); index1.write_bytes(old_index1); manifest_path.write_bytes(raw); path.write_bytes(h.encoded(review, True))
        private_key = root / 'PRIVATE-key.json'
        private_key.write_text('{"mapping": [], "no_write_trials": []}', encoding='utf8')
        for guarded in [manifest_path, index1, case_path, path]:
            retained = guarded.read_bytes(); guarded.unlink()
            try:
                os.link(private_key, guarded)
            except OSError:
                guarded.write_bytes(retained)
                skipped.append('Native hard-link alias fixture unavailable: ' + guarded.name)
                continue
            reject(lambda: validate(root, path, binding, h), 'private_condition_key_must_not_be_read')
            guarded.unlink(); guarded.write_bytes(retained)
        with tempfile.TemporaryDirectory(prefix='reader-review-outside-fictional-') as outside_name:
            linked = root / 'linked-preparation'; linked.mkdir()
            (linked / 'PRIVATE-preparation.json').write_bytes(raw)
            outside = Path(outside_name)
            (outside / 'index.json').write_bytes(old_index1)
            try:
                (linked / 'reviewer-1').symlink_to(outside, target_is_directory=True)
            except OSError:
                skipped.append('Native directory-symlink containment fixture unavailable')
            else:
                reject(lambda: validate(linked, path, binding, h), 'reviewer_folder_path_escape')
        (root / 'reviewer-1/CASE-999.json').write_bytes(original); reject(lambda: validate(root, path, binding, h))
    with tempfile.TemporaryDirectory(prefix='reader-review-three-case-fictional-') as name:
        root = Path(name)
        packets = []
        for number in range(1, 4):
            packet = copy.deepcopy(case); packet['case_id'] = f'CASE-{number:03d}'
            packet['task']['id'] = ['T', 'U', 'V'][number - 1]
            if number == 1: packet['task']['query'] += ' More fictional context.' * 4
            packets.append(packet)
        lengths = {p['case_id']: len(h.encoded(p, True)) for p in packets}
        require(lengths['CASE-001'] > lengths['CASE-002'] == lengths['CASE-003'], 'three_case_size_tie_fixture')
        # This independently expected layout exercises both preparer ties:
        # equal case bytes sort by case_id; empty bins choose the lowest index.
        groups, judgments_list = [], []
        for number, packet in enumerate(packets, 1):
            folder = root / f'reviewer-{number}'; folder.mkdir()
            case_raw = h.encoded(packet, True); filename = packet['case_id'] + '.json'
            (folder / filename).write_bytes(case_raw)
            indexed = {'case_id': packet['case_id'], 'file': filename, 'sha256': h.sha(case_raw), 'bytes': len(case_raw)}
            index = {'schema_version': 'oct13-reader-semantic-input-v1', 'cases': [indexed], 'instructions': 'Three-case fictional partition.'}
            index_raw = h.encoded(index, True); (folder / 'index.json').write_bytes(index_raw)
            groups.append({'partition': number, 'cases': 1, 'case_bytes': len(case_raw), 'index_sha256': h.sha(index_raw)})
            judged = copy.deepcopy(judgment); judged.update(case_id=packet['case_id'], input_sha256=h.sha(case_raw)); judgments_list.append(judged)
        multi_manifest = copy.deepcopy(manifest)
        multi_manifest.update(written_artifacts=3, no_write_trials=189, no_write_reasons={'fictional_no_write': 189}, partitions=groups)
        multi_raw = h.encoded(multi_manifest, True); (root / 'PRIVATE-preparation.json').write_bytes(multi_raw)
        multi_review = copy.deepcopy(review); multi_review.update(preparation_sha256=h.sha(multi_raw), cases=judgments_list)
        path = root / 'judgments.json'; path.write_bytes(h.encoded(multi_review, True))
        require(validate(root, path, h.sha(multi_raw), h)['reviewed_cases'] == 3, 'three_disjoint_case_fixture_failed'); passed += 1
        index2 = root / 'reviewer-2/index.json'
        duplicate_index = h.strict_json(index2.read_text(encoding='utf8'))
        case1_raw = (root / 'reviewer-1/CASE-001.json').read_bytes()
        duplicate_index['cases'].append({'case_id': 'CASE-001', 'file': 'CASE-001.json', 'sha256': h.sha(case1_raw), 'bytes': len(case1_raw)})
        (root / 'reviewer-2/CASE-001.json').write_bytes(case1_raw)
        duplicate_raw = h.encoded(duplicate_index, True); index2.write_bytes(duplicate_raw)
        overlap_manifest = copy.deepcopy(multi_manifest)
        overlap_manifest['partitions'][1].update(cases=2, case_bytes=groups[1]['case_bytes'] + len(case1_raw), index_sha256=h.sha(duplicate_raw))
        overlap_raw = h.encoded(overlap_manifest, True); (root / 'PRIVATE-preparation.json').write_bytes(overlap_raw)
        reject(lambda: validate(root, path, h.sha(overlap_raw), h), 'repeated_case_or_partition_overlap')
    print(json.dumps({'state': 'PASS_FICTIONAL_SOURCE_CHECK', 'passed': passed, 'failed': 0, 'skipped': len(skipped), 'skip_reasons': skipped,
        'main_results_cases_bank_gold_read': False, 'private_condition_key_read': False, 'semantic_judgments_created': 0, 'model_provider_calls': 0}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--self-check', action='store_true'); mode.add_argument('--check', action='store_true')
    parser.add_argument('--preparation', type=Path); parser.add_argument('--judgments', type=Path); parser.add_argument('--preparation-sha256')
    args = parser.parse_args(); h = helpers()
    if args.self_check: self_check(h)
    else:
        require(args.preparation is not None and args.judgments is not None and hash_string(args.preparation_sha256), 'explicit_audited_preparation_and_judgments_required')
        print(json.dumps(validate(args.preparation.resolve(), args.judgments.resolve(), args.preparation_sha256, h), sort_keys=True))


if __name__ == '__main__':
    try: main()
    except (ValueError, KeyError, TypeError, UnicodeError, OSError) as error:
        print(json.dumps({'state': 'FAIL_MECHANICAL_REVIEW_VALIDATION', 'error': type(error).__name__,
            'reason': str(error) if isinstance(error, ValueError) else 'Malformed or unavailable review input; inspect private evidence.'}), file=sys.stderr)
        raise SystemExit(1)
