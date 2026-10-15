"""Independent label-count/primary-join/public-byte checks; no semantic scoring.

Actual --check is held until root supplies the accepted full192 gate and exact
candidate pin. It never opens the condition key or original private outcomes.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ANALYSIS_SHA = '4602743218ea56d28c83d1307c9b1e3a6c36118f695018c14dbc0b0badfa10d6'
VALIDATOR_SHA = '16107e4e83ddb623c404e667024c460605bfda67fcd8133e32e49f94cf8cecf5'
LABELS = ('supported', 'contradicted', 'not_established', 'not_auditable')
GATES = ('artifact_written', 'contract_valid', 'typed_answer_status_match', 'declared_span_bundle_recovered',
         'declared_original_citation_set', 'complete_task', 'clean_complete_task')
EXTRA_PATTERNS = {
    'email': re.compile(r'\b[A-Za-z0-9_.+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
    'windows_machine': re.compile(r'\b(?:DESKTOP|LAPTOP)-[A-Z0-9]{5,}\b', re.I),
    'private_ipv4': re.compile(r'\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'),
    'credential_assignment': re.compile(r'(?i)\b(?:access_token|refresh_token|api_key|client_secret)\b[\s"\x27:=]+[A-Za-z0-9_.-]{16,}')}


def need(test, reason):
    if not test:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def exact(path, pin):
    need('privatekey' not in re.sub('[^a-z0-9]', '', path.name.casefold()), 'condition_key_alias_forbidden')
    raw = path.read_bytes(); need(sha(raw) == pin, 'explicit_input_pin_changed')
    return raw


def modules(study):
    study = study.resolve()
    need(sha((study/'check_reader_review.py').read_bytes()) == VALIDATOR_SHA, 'accepted_validator_changed')
    spec = importlib.util.spec_from_file_location('accepted_citation_validator_only', study/'check_reader_review.py')
    validator = importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)
    h = validator.helpers()
    path = study.parents[1]/'scripts/check_repository.py'
    need(sha(path.read_bytes()) == '31cdc537b24eccf22f9ab8e12f7f508ff6e164632a3c2fa31f873f57a88bf777', 'hygiene_source_changed')
    spec = importlib.util.spec_from_file_location('accepted_hygiene_constants_only', path)
    hygiene = importlib.util.module_from_spec(spec); spec.loader.exec_module(hygiene)
    return validator, h, hygiene


def recount(rows):
    """Use independent label lists/sets and a complete disjoint Boolean census."""
    out = {'cases': len(rows), 'answer_fields': 0, 'answer': Counter(), 'status': Counter(),
           'citation': Counter(), 'query': Counter(), 'presence': Counter(), 'all_values': 0, 'all_value_status': 0,
           'frozen': Counter(), 'intersection': Counter(), 'mismatch_ids': [], 'consistency_ids': []}
    for row in sorted(rows, key=lambda r: r['case_id']):
        answer = row['answer_labels']; status = row['status_label']
        out['answer_fields'] += len(answer); out['answer'].update(answer)
        out['status'][status] += 1; out['citation'][row['citation_label']] += 1; out['query'][row['query_label']] += 1
        out['presence'].update(set(answer+[status]))
        all_values = set(answer) <= {'supported'}
        support = all_values and status == 'supported'
        out['all_values'] += all_values; out['all_value_status'] += support
        for flag, value in row['frozen'].items():
            need(type(value) is bool, 'primary_flag_not_literal_boolean'); out['frozen'][flag] += int(value)
        match = row['frozen']['typed_answer_status_match']
        key = ('all_supported' if support else 'not_all_supported')+'__'+('typed_match' if match else 'typed_mismatch')
        out['intersection'][key] += 1
        if support and not match:
            out['mismatch_ids'].append(row['case_id'])
        if row['query_label'] == 'supported' and not support:
            out['consistency_ids'].append(row['case_id'])
    for key, total in [('answer', out['answer_fields']), ('status', len(rows)), ('citation', len(rows)), ('query', len(rows))]:
        need(set(out[key]) <= set(LABELS) and sum(out[key].values()) == total, 'marginal_unit_census')
    need(sum(out['intersection'].values()) == len(rows), 'disjoint_intersection_census')
    return out


def compare(summary, counts, h):
    def same(left, right, name):
        need(h.same(left, right), 'summary_mismatch:'+name)
    same(summary['reviewed_artifacts'], counts['cases'], 'case_denominator')
    same(summary['answer_fields'], counts['answer_fields'], 'field_denominator')
    for field, metric in [('answer_field_labels', 'answer'), ('status_labels', 'status'),
                          ('citation_labels', 'citation'), ('full_query_labels', 'query')]:
        same(summary[field]['counts'], {label: counts[metric][label] for label in LABELS}, field)
        same(summary[field]['denominator'], counts['answer_fields'] if metric == 'answer' else counts['cases'], field+'_n')
        need(summary[field]['unit'] == ('requested answer field' if metric == 'answer' else 'reviewed artifact'), 'marginal_unit_label')
    same(summary['value_status_case_label_presence']['counts'], {label: counts['presence'][label] for label in LABELS}, 'overlapping_presence')
    same(summary['value_status_case_label_presence']['denominator'], counts['cases'], 'presence_n')
    same(summary['all_values_supported'], counts['all_values'], 'all_values')
    same(summary['all_values_and_status_supported'], counts['all_value_status'], 'all_values_status')
    same(summary['frozen_gate_counts'], {key: counts['frozen'][key] for key in GATES}, 'seven_frozen_gates')
    matrix_keys = ('all_supported__typed_match', 'all_supported__typed_mismatch', 'not_all_supported__typed_match', 'not_all_supported__typed_mismatch')
    same(summary['support_typed_match_intersection']['counts'], {key: counts['intersection'][key] for key in matrix_keys}, '2x2')
    same(summary['support_typed_match_intersection']['denominator'], counts['cases'], '2x2_n')
    same(summary['source_supported_typed_mismatch_case_ids'], counts['mismatch_ids'], 'mismatch_case_IDs')
    same(summary['review_consistency_diagnostic']['case_ids'], counts['consistency_ids'], 'diagnostic_IDs')
    same(summary['review_consistency_diagnostic']['count'], len(counts['consistency_ids']), 'diagnostic_count')


def privacy(text, hygiene):
    patterns = {'existing_'+str(i): p for i, p in enumerate(hygiene.LEAK_PATTERNS)}
    patterns.update(EXTRA_PATTERNS)
    return [{'shape': name, 'match_sha256': sha(match.group().encode('utf8'))} for name, pattern in patterns.items() for match in pattern.finditer(text)]


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key; yield from strings(item)


def actual(args, validator, h, hygiene):
    gate = h.strict_json(exact(args.root_acceptance, args.root_acceptance_sha256).decode('utf8'))
    need(gate['state'] == 'ROOT_ACCEPTED_192_REVIEW_FOR_DESCRIPTIVE_UNBLINDING' and gate['reviewed_cases'] == 192,
         'accepted_full192_gate_required')
    need(all(gate[k] is True for k in ('complete_model_visible_delivery_checked', 'saved_judgment_bytes_checked',
        'mechanical_validation_checked', 'explicit_unblind_authorized')), 'explicit_root_gate_flags_required')
    raw = exact(args.candidate, args.candidate_sha256); data = h.strict_json(raw.decode('utf8'))
    analysis = h.strict_json(exact(args.analysis, ANALYSIS_SHA).decode('utf8'))
    primary = analysis['tables']['reader_trials']; trials = {r['trial_id']: r for r in primary}
    need(len(primary) == len(trials) == len(data['cases']) == 192, 'full192_primary_and_review_census')
    seen, joined_trials, rows, findings, not_auditable, context_cases = set(), set(), [], [], [], Counter()
    for item in data['cases']:
        case_id = item['case_id']; need(case_id not in seen, 'duplicate_case'); seen.add(case_id)
        case_raw, review_raw = item['case_utf8'].encode('utf8'), item['judgment_utf8'].encode('utf8')
        need(len(case_raw) == item['input_bytes'] and sha(case_raw) == item['input_sha256'], 'case_UTF8_fixity')
        need(len(review_raw) == item['judgment_bytes'] and sha(review_raw) == item['judgment_sha256'], 'judgment_UTF8_fixity')
        case, review = h.strict_json(case_raw.decode('utf8')), h.strict_json(review_raw.decode('utf8'))
        need(h.same(review, item['judgment']) and review['case_id'] == case['case_id'] == case_id and
             review['input_sha256'] == item['input_sha256'], 'raw_parsed_and_identity_binding')
        need(set(review) == validator.JUDGMENT_KEYS and set(review['answer_judgments']) == set(case['task']['answer_keys']), 'judgment_fields')
        fragments = validator.fragments(case, h)
        for entry in [*review['answer_judgments'].values(), *[review[k] for k in ('status_judgment', 'citation_judgment', 'full_query_judgment')]]:
            validator.entry(entry, fragments)
        trial_id = item['trial_id']; need(trial_id in trials and trial_id not in joined_trials, 'trial_bijection')
        joined_trials.add(trial_id); trial = trials[trial_id]
        need((item['block'], item['arm'], case['task']['id']) == (trial['block'], trial['arm'], trial['task_id']), 'visible_trial_identity')
        flags = {key: trial[key] for key in GATES}
        need(all(type(v) is bool for v in flags.values()) and h.same(flags, item['frozen_primary_gates']) and
             h.same(trial['failure'], item['frozen_execution_failure']), 'frozen_primary_flags_failure')
        record = {'case_id': case_id, 'block': item['block'], 'arm': item['arm'],
            'answer_labels': [entry['label'] for entry in review['answer_judgments'].values()],
            'status_label': review['status_judgment']['label'], 'citation_label': review['citation_judgment']['label'],
            'query_label': review['full_query_judgment']['label'], 'frozen': flags}
        rows.append(record)
        support = set(record['answer_labels']+[record['status_label']]) == {'supported'}
        need(h.same(item['descriptive_flags'], {'all_values_supported': set(record['answer_labels']) <= {'supported'},
            'all_values_and_status_supported': support, 'full_query_supported': record['query_label'] == 'supported',
            'citation_supported': record['citation_label'] == 'supported',
            'full_query_supported_with_some_value_or_status_not_supported': record['query_label'] == 'supported' and not support}), 'descriptive_flag_reconstruction')
        if case['extraction_auditability']['state'] == 'not_auditable':
            need(case['deliveries'] == [] and fragments == {}, 'unauditable_zero_evidence_retention')
            not_auditable.append(case_id)
        need(item['extraction_auditability'] == case['extraction_auditability']['state'], 'extraction_state_copy')
        context_cases[item['execution_context']['context_id']] += 1
        # Matches are private shape/hash records, not redactions or semantic exclusions.
        for layer, value in [('case', case), ('judgment', review)]:
            for text in strings(value):
                findings += [{'case_id': case_id, 'layer': layer, **m} for m in privacy(text, hygiene)]
    need(seen == {'CASE-'+str(i).zfill(3) for i in range(1, 193)} and joined_trials == set(trials), 'complete_case_trial_sets')
    need(len(not_auditable) == 1, 'accepted_one_zero_evidence_case_census')
    block_tables, arm_tables = [], []
    need(len(data['by_block']) == len({r['block'] for r in data['by_block']}), 'duplicate_block_summary')
    need(len(data['by_block_arm']) == len({(r['block'], r['arm']) for r in data['by_block_arm']}), 'duplicate_arm_summary')
    need({r['block'] for r in data['by_block']} == {r['block'] for r in rows}, 'block_summary_keys')
    need({(r['block'], r['arm']) for r in data['by_block_arm']} == {(r['block'], r['arm']) for r in rows}, 'arm_summary_keys')
    for table, destination, arm in [(data['by_block'], block_tables, False), (data['by_block_arm'], arm_tables, True)]:
        for summary in table:
            selected = [r for r in rows if r['block'] == summary['block'] and (not arm or r['arm'] == summary['arm'])]
            counts = recount(selected); compare(summary, counts, h)
            destination.append({'block': summary['block'], **({'arm': summary['arm']} if arm else {}), 'counts': counts})
    need(h.same(data['census'], {'scheduled_trials': 192, 'written_artifacts': 192, 'no_write_trials': 0, 'reviewed_artifacts': 192,
        'extraction_auditable': 191, 'extraction_not_auditable': 1,
        'recorded_execution_failures': sum(r['failure'] is not None for r in primary),
        'execution_contexts': len(data['execution_context_census']), 'primary_scores_changed': 0}), 'census_reconstruction')
    need({r['context_id']: r['reviewed_cases'] for r in data['execution_context_census']} == dict(context_cases), 'context_case_census')
    need(len(data['execution_context_census']) == len(context_cases), 'duplicate_or_unused_context_summary')
    findings += [{'layer': 'raw_candidate', **m} for m in privacy(raw.decode('utf8'), hygiene)]
    return {'state': 'PASS_INDEPENDENT_COUNTS_BYTES_BOUNDS' if not findings else 'COUNTS_PASS_PRIVACY_REQUIRES_REVIEW',
        'candidate_sha256': sha(raw), 'root_acceptance_sha256': args.root_acceptance_sha256,
        'accepted_validator_sha256': VALIDATOR_SHA, 'independent_checker_sha256': sha(Path(__file__).read_bytes()),
        'analysis_sha256': ANALYSIS_SHA, 'case_count': 192, 'zero_evidence_case_ids': not_auditable,
        'by_block': block_tables, 'by_block_arm': arm_tables, 'privacy_shape_findings': findings,
        'privacy_match_records': len(findings), 'labels_regraded': 0, 'model_calls': 0,
        'limits': ['Private extraction/condition mapping/native delivery remain root-accepted evidence, not independently replayed here.',
            'Bounded sensitive-shape scans do not prove absence of sensitive data; positive shapes require private root review.',
            'Counts/coordinates do not determine entailment; contexts are not independent model replications.']}


def self_check(h, hygiene):
    flags = {key: False for key in GATES}
    rows = [{'case_id': 'CASE-001', 'answer_labels': ['supported', 'not_established'], 'status_label': 'supported',
        'citation_label': 'contradicted', 'query_label': 'supported', 'frozen': flags},
        {'case_id': 'CASE-002', 'answer_labels': ['supported'], 'status_label': 'supported',
        'citation_label': 'supported', 'query_label': 'not_established', 'frozen': flags}]
    counts = recount(rows)
    need(counts['cases'] == 2 and counts['answer_fields'] == 3 and counts['answer']['supported'] == 2 and
         counts['presence']['supported'] == 2 and counts['presence']['not_established'] == 1 and
         counts['all_value_status'] == 1 and counts['intersection']['all_supported__typed_mismatch'] == 1 and
         counts['consistency_ids'] == ['CASE-001'], 'fictional_independent_units_and_intersection')
    need(privacy('fixture@example.invalid', hygiene) and privacy('DESKTOP-ABC1234', hygiene) and
         not privacy('Fictional source S-007; value false and integer zero.', hygiene), 'fictional_privacy_shapes')
    summary = {'reviewed_artifacts': 2, 'answer_fields': 3,
        'answer_field_labels': {'unit': 'requested answer field', 'denominator': 3,
            'counts': {'supported': 2, 'contradicted': 0, 'not_established': 1, 'not_auditable': 0}},
        'status_labels': {'unit': 'reviewed artifact', 'denominator': 2,
            'counts': {'supported': 2, 'contradicted': 0, 'not_established': 0, 'not_auditable': 0}},
        'citation_labels': {'unit': 'reviewed artifact', 'denominator': 2,
            'counts': {'supported': 1, 'contradicted': 1, 'not_established': 0, 'not_auditable': 0}},
        'full_query_labels': {'unit': 'reviewed artifact', 'denominator': 2,
            'counts': {'supported': 1, 'contradicted': 0, 'not_established': 1, 'not_auditable': 0}},
        'value_status_case_label_presence': {'denominator': 2,
            'counts': {'supported': 2, 'contradicted': 0, 'not_established': 1, 'not_auditable': 0}},
        'all_values_supported': 1, 'all_values_and_status_supported': 1,
        'frozen_gate_counts': {key: 0 for key in GATES},
        'support_typed_match_intersection': {'denominator': 2, 'counts': {'all_supported__typed_match': 0,
            'all_supported__typed_mismatch': 1, 'not_all_supported__typed_match': 0, 'not_all_supported__typed_mismatch': 1}},
        'source_supported_typed_mismatch_case_ids': ['CASE-002'],
        'review_consistency_diagnostic': {'case_ids': ['CASE-001'], 'count': 1}}
    compare(summary, counts, h)
    try:
        compare({**summary, 'reviewed_artifacts': 3}, counts, h)
    except ValueError:
        pass
    else:
        raise AssertionError('tampered_case_count_accepted')
    try:
        recount([{**rows[0], 'frozen': {**flags, 'typed_answer_status_match': 0}}])
    except ValueError:
        pass
    else:
        raise AssertionError('integer_boolean_conflation')
    return {'state': 'PASS_FICTIONAL_INDEPENDENT_RECOUNT_AND_PRIVACY', 'normal_groups': 3, 'expected_rejections': 2,
            'actual_cases_judgments_key_read': False, 'actual_check_executed': False, 'model_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--self-check', action='store_true'); modes.add_argument('--check', action='store_true')
    parser.add_argument('--study', type=Path, required=True)
    for name in ('candidate', 'analysis', 'root-acceptance', 'output'):
        parser.add_argument('--'+name, type=Path)
    parser.add_argument('--candidate-sha256'); parser.add_argument('--root-acceptance-sha256')
    args = parser.parse_args()
    if args.check:
        need(all((args.candidate, args.analysis, args.root_acceptance, args.output,
                  args.candidate_sha256, args.root_acceptance_sha256)), 'explicit_root_pinned_actual_inputs_required')
        need(not args.output.exists(), 'evidence_output_already_exists')
    validator, h, hygiene = modules(args.study)
    result = self_check(h, hygiene) if args.self_check else actual(args, validator, h, hygiene)
    raw = h.encoded(result, True)
    if args.check:
        with args.output.open('xb') as stream:
            stream.write(raw)
    sys.stdout.buffer.write(raw)


if __name__ == '__main__':
    main()
