"""Check the supplemental semantic comparison using public, relative study files.

This verifies packaging, contracts and agreement; it does not judge prose entailment.
Run: python check_bank_semantics.py
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True

from artifact_contract import agreement, strict_json, typed, validate
from study_common import digest

HERE = Path(__file__).resolve().parent
BANK_SHA256 = '280e6be3f7380ed9c0bc1dbe3ec75dfba136113f230d08751e0f316b67cf9760'
BLIND_INDEX_SHA256 = '937bf53974a31306f78c670325ed72a753b49b7d07aa9d393f3d17b401d9a66d'
METHOD = 'single blind LLM rederivation; not human validation'
RECORD_FIELDS = ('id', 'kind', 'revision', 'authored_at', 'title', 'scope', 'body',
    'links', 'supersedes', 'incorporates', 'path', 'valid_from', 'valid_to', 'time_scope', 'category')
TASK_FIELDS = ('id', 'query', 'answer_contract', 'answer_keys')
BLIND_INDEX_SCOPE = ('All96 authored histories,288 tasks; semantic rederivation supplement only; '
    'original expected answers/rationales/evidence sets/spans/strata/split/template/variants withheld')


def canonical_bytes(value):
    """Deterministic JSON recipe, not a claim of RFC 8785 canonicalization."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf8')


def frozen_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
        allow_nan=False) + '\n').encode('utf8')


def ordered_families(families):
    return sorted(families, key=lambda family: digest('blind-bank-v1:' + family['id']))


def blind_payload(family, case_id):
    # These explicit allowlists are the only fields crossing the review interface.
    # Family metadata, authored keys/rationales/support and experimental arms do not.
    return {'case_id': case_id,
        'records': [{key: record[key] for key in RECORD_FIELDS if key in record}
                    for record in family['records']],
        'tasks': [{key: task[key] for key in TASK_FIELDS} for task in family['tasks']]}


def require_input_digest(payload, expected):
    assert digest(frozen_bytes(payload)) == expected, 'blinded_input_digest_mismatch'


def check_spans(judgment, docs):
    assert isinstance(judgment['support_spans'], list)
    evidence = judgment['predicted']['evidence']
    assert all(isinstance(value, str) and value in docs and docs[value]['kind'] == 'source'
               for value in evidence), 'evidence_must_name_present_originals'
    assert len(evidence) == len(set(evidence)), 'duplicate_evidence_id'
    assert {span['id'] for span in judgment['support_spans']} == set(evidence), 'span_evidence_link'
    for span in judgment['support_spans']:
        assert set(span) == {'id', 'start', 'end'}
        assert span['id'] in docs and docs[span['id']]['kind'] == 'source', 'span_original_kind'
        assert type(span['start']) is int and type(span['end']) is int, 'span_integer_bounds'
        assert 0 <= span['start'] < span['end'] <= len(docs[span['id']]['body']), 'span_codepoint_bounds'


def check_package(package, source_bank):
    assert package['schema_version'] == 'blind-semantic-bank-review-v1'
    assert package['source_bank'] == {'file': 'challenge-bank.json', 'sha256': BANK_SHA256}
    assert package['blinding']['record_field_allowlist'] == list(RECORD_FIELDS)
    assert package['blinding']['task_field_allowlist'] == list(TASK_FIELDS)
    assert package['blinding']['case_order_recipe'] == 'ascending SHA256(UTF8("blind-bank-v1:" + family.id))'
    assert package['method']['reviewer_method'] == METHOD
    families = ordered_families(source_bank['families'])
    assert len(families) == 96 and len({family['id'] for family in families}) == 96
    cases = package['cases']
    assert len(cases) == 96
    manifest_cases, raw_attestations = [], []
    counts = Counter(cases=0, tasks=0, ready=0, hold=0, ambiguous=0, support_spans=0,
        status_agreement=0, typed_answer_status_agreement=0, mismatches=0)
    hold_reasons = Counter()
    seen_tasks = set()
    for position, (case, family) in enumerate(zip(cases, families), 1):
        case_id = f'CASE-{position:03d}'
        assert case['case_id'] == case_id and case['family_id'] == family['id'], 'opaque_case_order'
        payload = blind_payload(family, case_id)
        require_input_digest(payload, case['input_sha256'])
        manifest_cases.append({'case_id': case_id, 'file': case_id + '.json', 'sha256': case['input_sha256']})
        review = case['review']
        assert set(review) == {'case_id', 'input_sha256', 'reviewer_method', 'tasks'}
        assert review['case_id'] == case_id and review['input_sha256'] == case['input_sha256']
        assert review['reviewer_method'] == METHOD
        assert digest(canonical_bytes(review)) == case['canonical_judgment_sha256'], 'canonical_judgment_hash'
        raw_hash = case['raw_judgment_sha256_attested']
        assert re.fullmatch('[0-9a-f]{64}', raw_hash), 'raw_attestation_hash_format'
        raw_attestations.append({'case_id': case_id, 'sha256': raw_hash})
        # The original raw-byte hash is attested by retained private execution proof.
        # Public serialization cannot independently verify those unavailable bytes.
        docs = {record['id']: record for record in family['records']}
        assert len(docs) == len(family['records'])
        assert len(family['tasks']) == len(review['tasks']) == len(case['task_comparisons']) == 3
        counts['cases'] += 1
        for judgment, comparison, task in zip(review['tasks'], case['task_comparisons'], family['tasks']):
            assert set(judgment) == {'task_id', 'predicted', 'rationale', 'ambiguity', 'ambiguity_reason', 'support_spans'}
            assert judgment['task_id'] == comparison['task_id'] == task['id']
            assert task['id'] not in seen_tasks
            seen_tasks.add(task['id'])
            predicted = judgment['predicted']
            assert validate(predicted, task, docs)['schema_valid'], 'strict_answer_contract'
            assert canonical_bytes(comparison['authored_expected']) == canonical_bytes(task['expected']), 'authored_key_link'
            for key in task['answer_keys']:
                assert typed(task['expected']['answer'][key], task['answer_contract']['fields'][key])
            result = agreement(predicted, task)
            assert canonical_bytes(result) == canonical_bytes(comparison['agreement']), 'agreement_recomputation'
            assert isinstance(judgment['rationale'], str) and judgment['rationale'].strip()
            assert type(judgment['ambiguity']) is bool
            assert ((isinstance(judgment['ambiguity_reason'], str) and judgment['ambiguity_reason'].strip())
                    if judgment['ambiguity'] else judgment['ambiguity_reason'] is None)
            check_spans(judgment, docs)
            counts['tasks'] += 1
            counts[predicted['status']] += 1
            counts['ambiguous'] += int(judgment['ambiguity'])
            counts['support_spans'] += len(judgment['support_spans'])
            counts['status_agreement'] += int(result['status_match'])
            counts['typed_answer_status_agreement'] += int(result['typed_answer_status_match'])
            counts['mismatches'] += int(not result['typed_answer_status_match'])
            if predicted['status'] == 'hold': hold_reasons[predicted['answer']['hold_reason']] += 1
    manifest = {'cases': manifest_cases, 'scope': BLIND_INDEX_SCOPE, 'source_bank_sha256': BANK_SHA256}
    assert digest(frozen_bytes(manifest)) == BLIND_INDEX_SHA256, 'rebuilt_blind_index_hash'
    assert package['provenance']['blind_input_manifest_sha256'] == BLIND_INDEX_SHA256
    assert digest(canonical_bytes(raw_attestations)) == package['provenance']['raw_attestation_manifest_canonical_sha256']
    assert dict(counts) == package['comparison']['census'], 'comparison_census'
    assert dict(hold_reasons) == package['comparison']['hold_reasons'], 'hold_reason_census'
    assert len(seen_tasks) == 288
    return dict(counts)


def must_fail(call):
    try:
        call()
    except (AssertionError, ValueError):
        return
    raise AssertionError('negative_self_check_did_not_fail')


def self_check():
    family = {'id': 'F7', 'stratum': 'withheld', 'split': 'withheld', 'variant': 8,
        'records': [{'id': 'S', 'kind': 'source', 'body': 'a😀e\u0301', 'gold_rationale': 'withheld'}],
        'tasks': [{'id': 'Q', 'query': 'Read source.', 'answer_keys': ['flag'],
            'answer_contract': {'fields': {'flag': {'type': 'boolean'}}, 'additional_fields': False},
            'expected': {'status': 'ready', 'answer': {'flag': True}}, 'gold_rationale': 'withheld',
            'evidence_sets': [['S']], 'evidence_spans': [], 'arm_id': 'withheld'}]}
    payload = blind_payload(family, 'CASE-001')
    assert set(payload) == {'case_id', 'records', 'tasks'}
    assert set(payload['records'][0]) == {'id', 'kind', 'body'}
    assert set(payload['tasks'][0]) == set(TASK_FIELDS)
    families = [{'id': 'F7', 'name': 'z'}, {'id': 'F8', 'name': 'a'}]
    assert [family['id'] for family in ordered_families(families)] == [family['id'] for family in ordered_families(list(reversed(families)))]
    assert [family['id'] for family in ordered_families(families)] == [family['id'] for family in sorted(families, key=lambda family: hashlib.sha256(('blind-bank-v1:' + family['id']).encode('utf8')).hexdigest())]
    require_input_digest(payload, digest(frozen_bytes(payload)))
    must_fail(lambda: require_input_digest(payload, '0' * 64))
    docs = {'S': family['records'][0]}
    judgment = {'predicted': {'status': 'ready', 'answer': {'flag': True}, 'evidence': ['S']},
        'support_spans': [{'id': 'S', 'start': 1, 'end': 2}]}
    assert len(docs['S']['body']) == 4 and docs['S']['body'][1:2] == '😀'
    check_spans(judgment, docs)
    bad = copy.deepcopy(judgment); bad['support_spans'][0]['end'] = 5
    must_fail(lambda: check_spans(bad, docs))
    bad_docs = copy.deepcopy(docs); bad_docs['S']['kind'] = 'derived'
    must_fail(lambda: check_spans(judgment, bad_docs))
    bad = copy.deepcopy(judgment); bad['support_spans'][0]['start'] = True
    must_fail(lambda: check_spans(bad, docs))
    task = family['tasks'][0]
    assert validate(judgment['predicted'], task, docs)['schema_valid']
    bad = copy.deepcopy(judgment['predicted']); bad['answer']['flag'] = 1
    assert not validate(bad, task, docs)['schema_valid'] and not agreement(bad, task)['typed_answer_status_match']
    assert not typed(True, {'type': 'integer'})
    must_fail(lambda: strict_json('{"flag":true,"flag":false}'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check-only', action='store_true')
    args = parser.parse_args()
    self_check()
    if args.self_check_only:
        print('check_bank_semantics self-check PASS')
        return
    bank_path = HERE / 'challenge-bank.json'
    assert digest(bank_path.read_bytes()) == BANK_SHA256, 'frozen_source_bank_hash'
    package = strict_json((HERE / 'bank-semantic-review.json').read_text(encoding='utf8'))
    assert set(package['provenance']['helper_sha256']) == {'artifact_contract.py', 'study_common.py'}
    for name, expected in package['provenance']['helper_sha256'].items():
        assert name in {'artifact_contract.py', 'study_common.py'}
        assert digest((HERE / name).read_bytes()) == expected, 'frozen_helper_hash'
    census = check_package(package, strict_json(bank_path.read_text(encoding='utf8')))
    print(json.dumps({'state': 'PASS', 'census': census,
        'scope': 'Public packaging, blinded-input reconstruction, contracts, original span bounds and authored-key agreement; no prose entailment or population accuracy validation.'}, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
