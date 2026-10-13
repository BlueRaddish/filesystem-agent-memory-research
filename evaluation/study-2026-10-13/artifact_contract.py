"""Typed artifact agreement is separate from actual supplied-source coverage."""
import argparse
import json
import math
from pathlib import Path
import re
import unicodedata


def strict_json(text):
    text = text.strip()
    if text.startswith('```json\n') and text.endswith('\n```'):
        text = text[8:-4]
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate_json_key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('non_finite_json_constant')
    result = json.loads(text, object_pairs_hook=object_pairs, parse_constant=constant)
    def utf8(value):
        if isinstance(value, str):
            value.encode('utf8', errors='strict')
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError('non_finite_json_number')
        elif isinstance(value, list):
            for item in value:
                utf8(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                utf8(key)
                utf8(item)
    utf8(result)
    return result


def typed(value, contract):
    kinds = contract['type'] if isinstance(contract['type'], list) else [contract['type']]
    good = any((kind == 'null' and value is None) or
               (kind == 'boolean' and type(value) is bool) or
               (kind == 'integer' and type(value) is int) or
               (kind == 'string' and isinstance(value, str)) or
               (kind == 'array' and isinstance(value, list)) for kind in kinds)
    if not good:
        return False
    if 'enum' in contract and not any(type(value) is type(v) and value == v for v in contract['enum']):
        return False
    if value is None:
        return True
    if isinstance(value, list):
        if not all(typed(item, contract['items']) for item in value):
            return False
        if contract.get('comparison') == 'unordered_unique':
            serialized = [json.dumps(v, ensure_ascii=False, sort_keys=True) for v in value]
            if len(set(serialized)) != len(serialized):
                return False
    return True


def canonical(value, contract):
    if isinstance(value, list):
        values = [canonical(v, contract['items']) for v in value]
        return sorted(values, key=lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True)) if contract.get('comparison') == 'unordered_unique' else values
    if isinstance(value, str):
        normalization = contract.get('normalization', 'none')
        if normalization in ('NFC', 'NFKC'):
            return unicodedata.normalize(normalization, value)
        if normalization != 'none':
            raise ValueError('unrecognized_prospective_normalization')
    return value


def validate(value, task, docs):
    errors = []
    if not isinstance(value, dict):
        return {'schema_valid': False, 'errors': ['artifact_not_object']}
    if set(value) != {'status', 'answer', 'evidence'}:
        errors.append('top_level_fields')
    status, answer, evidence = value.get('status'), value.get('answer'), value.get('evidence')
    if status not in ('ready', 'hold'):
        errors.append('status')
    if not isinstance(answer, dict):
        errors.append('answer_not_object')
        answer = {}
    contract = task['answer_contract']
    unresolved = contract.get('unresolved_policy', {})
    reason = unresolved.get('reason_field', 'hold_reason')
    sidecar = {reason} if status == 'hold' and unresolved.get('reason_required') else set()
    if set(task['answer_keys']) - set(answer):
        errors.append('requested_keys_missing')
    if not contract.get('additional_fields', False) and set(answer) - set(task['answer_keys']) - sidecar:
        errors.append('unexpected_answer_keys')
    if status == 'hold' and unresolved.get('reason_required'):
        if not isinstance(answer.get(reason), str) or not answer[reason].strip():
            errors.append('hold_reason_missing')
        elif answer[reason] not in ('required_source_missing', 'scope_not_established', 'conflicting_authority'):
            errors.append('hold_reason_code')
    for key, rule in contract['fields'].items():
        if key not in answer:
            continue
        if answer[key] is None and key != reason and status != 'hold':
            errors.append('unresolved_null_requires_hold:' + key)
        conditional_null = status == 'hold' and answer[key] is None and key != reason and unresolved.get('allow_null_when_status_hold')
        if not conditional_null and not typed(answer[key], rule):
            errors.append('field_contract:' + key)
    cited = set()
    if not isinstance(evidence, list) or any(not isinstance(v, str) for v in evidence):
        errors.append('evidence_not_string_list')
    else:
        for citation in evidence:
            match = re.fullmatch(r'([A-Za-z0-9_-]+)(?:@(\d+):(\d+))?', citation)
            if not match or match[1] not in docs or docs[match[1]]['kind'] != 'source':
                errors.append('invalid_original_citation')
                continue
            document = docs[match[1]]
            length = len(document['body']) if 'body' in document else document['body_length']
            if match[2] is not None and not 0 <= int(match[2]) < int(match[3]) <= length:
                errors.append('invalid_citation_offsets')
                continue
            cited.add(match[1])
    return {'schema_valid': not errors, 'errors': sorted(set(errors)), 'cited_original_ids': sorted(cited)}


def agreement(value, task):
    if not isinstance(value, dict) or not isinstance(value.get('answer'), dict):
        return {'typed_answer_status_match': False, 'matching_fields': [], 'mismatching_fields': list(task['answer_keys'])}
    matched, missed = [], []
    for key in task['answer_keys']:
        expected = task['expected']['answer'][key]
        actual = value['answer'].get(key)
        rule = task['answer_contract']['fields'][key]
        policy = task['answer_contract'].get('unresolved_policy', {})
        conditional_null = actual is None and value.get('status') == 'hold' and key != policy.get('reason_field', 'hold_reason') and policy.get('allow_null_when_status_hold')
        serialized = lambda item: json.dumps(canonical(item, rule), ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        good = key in value['answer'] and (typed(actual, rule) or conditional_null) and type(actual) is type(expected) and serialized(actual) == serialized(expected)
        (matched if good else missed).append(key)
    return {'typed_answer_status_match': not missed and value.get('status') == task['expected']['status'],
            'status_match': value.get('status') == task['expected']['status'],
            'matching_fields': matched, 'mismatching_fields': missed}


def self_check():
    task = {'answer_keys': ['values'], 'answer_contract': {'fields': {'values': {'type': 'array', 'items': {'type': 'string'}, 'comparison': 'unordered_unique'}}, 'additional_fields': False,
        'unresolved_policy': {'allow_null_when_status_hold': True, 'reason_field': 'hold_reason', 'reason_required': True}},
        'expected': {'status': 'ready', 'answer': {'values': ['青灯', 'amber']}}}
    docs = {'S': {'kind': 'source', 'body': 'evidence'}}
    value = {'status': 'ready', 'answer': {'values': ['amber', '青灯']}, 'evidence': ['S@0:8']}
    assert validate(value, task, docs)['schema_valid'] and agreement(value, task)['typed_answer_status_match']
    value['answer']['values'] = ['amber', 'amber', '青灯']
    assert not validate(value, task, docs)['schema_valid']
    value = {'status': 'hold', 'answer': {'values': None, 'hold_reason': 'required_source_missing'}, 'evidence': []}
    assert validate(value, task, docs)['schema_valid'] and not agreement(value, task)['typed_answer_status_match']
    assert not typed(True, {'type': 'integer'})
    assert not typed(None, {'type': ['string', 'null'], 'enum': ['missing']})
    nullable = {'answer_keys': ['value'], 'answer_contract': {'fields': {'value': {'type': ['boolean', 'null']}}, 'additional_fields': False,
        'unresolved_policy': {'allow_null_when_status_hold': True, 'reason_required': True, 'reason_field': 'hold_reason'}}}
    assert not validate({'status': 'ready', 'answer': {'value': None}, 'evidence': ['S']}, nullable, docs)['schema_valid']
    hold = {'answer_keys': ['value'], 'answer_contract': {'fields': {'value': {'type': 'integer'}},
        'unresolved_policy': {'allow_null_when_status_hold': True}}, 'expected': {'status': 'hold', 'answer': {'value': None}}}
    assert agreement({'status': 'hold', 'answer': {'value': None}}, hold)['typed_answer_status_match']
    mixed = {'answer_keys': ['values'], 'answer_contract': {'fields': {'values': {'type': 'array', 'items': {'type': ['boolean', 'integer']}, 'comparison': 'ordered_exact'}}},
             'expected': {'status': 'ready', 'answer': {'values': [False]}}}
    assert not agreement({'status': 'ready', 'answer': {'values': [0]}}, mixed)['typed_answer_status_match']
    for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":1e309}', '{"x":"\\ud800"}'):
        try:
            strict_json(text)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid JSON accepted')
    print('artifact_contract self-check passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', type=Path)
    parser.add_argument('--task-contract', type=Path)
    parser.add_argument('--source-bounds', type=Path)
    args = parser.parse_args()
    if args.check and args.task_contract and args.source_bounds:
        try:
            result = validate(strict_json(args.check.read_text(encoding='utf8')),
                strict_json(args.task_contract.read_text(encoding='utf8')),
                strict_json(args.source_bounds.read_text(encoding='utf8')))
        except (ValueError, TypeError, KeyError, UnicodeError):
            result = {'schema_valid': False, 'errors': ['invalid_artifact_or_checker_input']}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
        raise SystemExit(0 if result['schema_valid'] else 1)
    elif any((args.check, args.task_contract, args.source_bounds)):
        parser.error('All three checker paths are required')
    else:
        self_check()
