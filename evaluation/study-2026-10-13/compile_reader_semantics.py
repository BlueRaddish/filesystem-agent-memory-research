"""Private-candidate descriptive compiler; no semantic judge or primary regrading.

Only --self-check is authorized while this source is prospective. --compile
requires a separately sealed root acceptance/unblind receipt and writes a NEW
private candidate. Publication requires a separate privacy/link/content gate.
--check reproduces a candidate against pinned public analysis, without private
preparation/key/native inputs; it does not attest the original private audit.
"""
import argparse
from collections import Counter
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import stat
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
CHECKER_SHA = '16107e4e83ddb623c404e667024c460605bfda67fcd8133e32e49f94cf8cecf5'
PREPARER_SHA = 'ad4fe9cd81b00c2cb04762650fe2f60c062acf1fe3b24ecc9687de7e4504d76c'
PLAN_SHA = '3c06cf6c3a4ee965743a4f0ca1a515f16fd42eb292f2d3ca5cf63c59091a200a'
FREEZE_SHA = 'fda01f88f50dbb6e66a312ca9ab775c8603643ebe8b7f74b596a7250bc39524c'
ANALYSIS_SHA = '4602743218ea56d28c83d1307c9b1e3a6c36118f695018c14dbc0b0badfa10d6'
PREPARATION_SHA = '46d910d5a96046d333de5760d63a637ee3268ac3c365ec3e0a07131612cb861c'
LABELS = ('supported', 'contradicted', 'not_established', 'not_auditable')
GATES = ('artifact_written', 'contract_valid', 'typed_answer_status_match',
         'declared_span_bundle_recovered', 'declared_original_citation_set',
         'complete_task', 'clean_complete_task')


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def no_links(path):
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400
                    and (not stat.S_ISREG(info.st_mode) or info.st_nlink == 1), 'linked_input_or_output')


def exact(path, pin, size=None):
    no_links(path)
    raw = path.read_bytes()
    require(sha(raw) == pin and (size is None or len(raw) == size), 'input_hash_or_bytes_changed')
    return raw


def load_helpers(study):
    exact(study/'check_reader_review.py', CHECKER_SHA)
    spec = importlib.util.spec_from_file_location('accepted_semantic_validator', study/'check_reader_review.py')
    checker = importlib.util.module_from_spec(spec); spec.loader.exec_module(checker)
    helper = checker.helpers()  # Pinned plan/preparer/freeze; definitions only.
    return checker, helper


def preserved(raw, pin, h):
    require(sha(raw) == pin, 'raw_UTF8_hash_changed')
    text = raw.decode('utf8', errors='strict')
    value = h.strict_json(text)
    require(text.encode('utf8') == raw, 'raw_UTF8_roundtrip_changed')
    return text, value


def summarize(rows):
    count = len(rows)
    answers = [entry for row in rows for entry in row['judgment']['answer_judgments'].values()]
    def marginal(entries, unit):
        counts = Counter(entry['label'] for entry in entries)
        return {'unit': unit, 'denominator': len(entries), 'counts': {label: counts[label] for label in LABELS}}
    answer_labels = marginal(answers, 'requested answer field')
    case_marginals = {name: marginal([row['judgment'][name+'_judgment'] for row in rows], 'reviewed artifact')
                      for name in ('status', 'citation', 'full_query')}
    presence = {label: sum(any(entry['label'] == label for entry in
        [*row['judgment']['answer_judgments'].values(), row['judgment']['status_judgment']]) for row in rows)
        for label in LABELS}
    intersection = Counter()
    for row in rows:
        supported = row['descriptive_flags']['all_values_and_status_supported']
        match = row['frozen_primary_gates']['typed_answer_status_match']
        intersection[('all_supported' if supported else 'not_all_supported')+'__'+('typed_match' if match else 'typed_mismatch')] += 1
    return {'reviewed_artifacts': count, 'answer_fields': len(answers), 'answer_field_labels': answer_labels,
        'status_labels': case_marginals['status'], 'citation_labels': case_marginals['citation'],
        'full_query_labels': case_marginals['full_query'],
        'value_status_case_label_presence': {'unit': 'reviewed artifact with any requested answer/status entry bearing this label',
            'denominator': count, 'counts': presence, 'overlap': 'Independent marginals; a mixed-label artifact may count in several labels.'},
        'all_values_supported': sum(row['descriptive_flags']['all_values_supported'] for row in rows),
        'all_values_and_status_supported': sum(row['descriptive_flags']['all_values_and_status_supported'] for row in rows),
        'frozen_gate_counts': {gate: sum(row['frozen_primary_gates'][gate] for row in rows) for gate in GATES},
        'support_typed_match_intersection': {'unit': 'reviewed artifact', 'denominator': count,
            'counts': {key: intersection[key] for key in ('all_supported__typed_match', 'all_supported__typed_mismatch',
                'not_all_supported__typed_match', 'not_all_supported__typed_mismatch')}},
        'source_supported_typed_mismatch_case_ids': [row['case_id'] for row in rows
            if row['descriptive_flags']['all_values_and_status_supported'] and not row['frozen_primary_gates']['typed_answer_status_match']],
        'review_consistency_diagnostic': {'meaning': 'Full query labelled supported while at least one requested answer/status entry is not supported; descriptive flag, not rejection or regrading.',
            'case_ids': [row['case_id'] for row in rows if row['descriptive_flags']['full_query_supported_with_some_value_or_status_not_supported']],
            'count': sum(row['descriptive_flags']['full_query_supported_with_some_value_or_status_not_supported'] for row in rows)}}


def joined(case_inputs, judgment_inputs, mapping, primary, contexts, h):
    require(len({r['case_id'] for r in mapping}) == len(mapping), 'duplicate_mapping_case')
    require(len({r['trial_id'] for r in mapping}) == len(mapping), 'duplicate_mapping_trial')
    require(len({r['trial_id'] for r in primary}) == len(primary), 'duplicate_primary_trial')
    by_trial = {row['trial_id']: row for row in primary}
    require(set(case_inputs) == set(judgment_inputs) == {row['case_id'] for row in mapping}, 'case_judgment_mapping_census')
    result = []
    for item in sorted(mapping, key=lambda row: row['case_id']):
        require(set(item) == {'case_id', 'trial_id', 'block', 'arm'} and item['trial_id'] in by_trial, 'mapping_shape_or_unknown_trial')
        case_id = item['case_id']
        trial = by_trial[item['trial_id']]
        require(trial['block'] == item['block'] and trial['arm'] == item['arm'], 'mapping_primary_condition_mismatch')
        require(all(type(trial[gate]) is bool for gate in GATES), 'frozen_gate_not_boolean')
        require(trial['failure'] is None or type(trial['failure']) is str, 'frozen_failure_shape')
        raw_case, case_pin = case_inputs[case_id]
        raw_judgment, judgment_pin, context_id = judgment_inputs[case_id]
        case_text, case = preserved(raw_case, case_pin, h)
        judgment_text, judgment = preserved(raw_judgment, judgment_pin, h)
        require(case['case_id'] == judgment['case_id'] == case_id and judgment['input_sha256'] == case_pin,
                'case_judgment_identity_or_hash')
        require(case['task']['id'] == trial['task_id'], 'case_primary_task_ID_mismatch')
        require(set(judgment['answer_judgments']) == set(case['task']['answer_keys']), 'answer_field_census')
        require(context_id in contexts, 'unknown_execution_context')
        values = list(judgment['answer_judgments'].values())
        value_status = values+[judgment['status_judgment']]
        all_supported = all(entry['label'] == 'supported' for entry in value_status)
        result.append({'case_id': case_id, 'trial_id': item['trial_id'], 'block': item['block'], 'arm': item['arm'],
            'execution_context': contexts[context_id], 'input_sha256': case_pin, 'input_bytes': len(raw_case),
            'case_utf8': case_text, 'judgment_sha256': judgment_pin, 'judgment_bytes': len(raw_judgment),
            'judgment_utf8': judgment_text, 'judgment': judgment,
            'extraction_auditability': case['extraction_auditability']['state'],
            'frozen_execution_failure': trial['failure'],
            'frozen_primary_gates': {gate: trial[gate] for gate in GATES},
            'descriptive_flags': {'all_values_supported': all(entry['label'] == 'supported' for entry in values),
                'all_values_and_status_supported': all_supported,
                'full_query_supported': judgment['full_query_judgment']['label'] == 'supported',
                'citation_supported': judgment['citation_judgment']['label'] == 'supported',
                'full_query_supported_with_some_value_or_status_not_supported':
                    judgment['full_query_judgment']['label'] == 'supported' and not all_supported}})
    return result


def candidate_payload(rows, contexts, provenance):
    blocks = sorted({r['block'] for r in rows})
    arms = sorted({(r['block'], r['arm']) for r in rows})
    return {'schema_version': 'oct13-descriptive-semantic-supplement-v1', 'state': 'PRIVATE_CANDIDATE_REQUIRES_PUBLICATION_PRIVACY_REVIEW',
        'provenance': provenance,
        'census': {'scheduled_trials': 192, 'written_artifacts': len(rows), 'no_write_trials': 0, 'reviewed_artifacts': len(rows),
            'extraction_auditable': sum(r['extraction_auditability'] == 'auditable' for r in rows),
            'extraction_not_auditable': sum(r['extraction_auditability'] == 'not_auditable' for r in rows),
            'recorded_execution_failures': sum(r['frozen_execution_failure'] is not None for r in rows),
            'execution_contexts': len(contexts), 'primary_scores_changed': 0},
        'by_block': [{'block': block, **summarize([r for r in rows if r['block'] == block])} for block in blocks],
        'by_block_arm': [{'block': block, 'arm': arm, **summarize([r for r in rows if r['block'] == block and r['arm'] == arm])}
                         for block, arm in arms],
        'execution_context_census': [{**context, 'reviewed_cases': sum(r['execution_context']['context_id'] == number for r in rows)}
                                     for number, context in sorted(contexts.items())],
        'cases': rows,
        'limitations': ['Descriptive one-LLM-judgment supplement; no human adjudication or reliability estimate.',
            'Block/arm summaries remain separate; oracle controls are not pooled into reader effectiveness.',
            'Related authored scaffolds, shared within-context exposure and inherited model biases limit generalization.',
            'Support/strict-match intersections do not change or repair primary scores.',
            'Citation/full-query labels are separate marginal judgments, not a forced support hierarchy.',
            'Any-label case counts overlap; answer-field and case denominators differ.',
            'Complete raw fictional cases/judgments still require a separate privacy/content/link review before publication.']}


def check_payload(candidate, analysis, checker, h):
    """Reproduce public fixity/joins/tables, not private extraction or entailment."""
    require(type(candidate) is dict and type(candidate.get('cases')) is list and
            type(candidate.get('execution_context_census')) is list, 'public_candidate_shape')
    require(analysis['state'] == 'complete_frozen_census_analysis' and analysis['freeze_sha256'] == FREEZE_SHA,
            'public_analysis_binding')
    primary = analysis['tables']['reader_trials']
    require(len(primary) == 192 and len(candidate['cases']) == 192, 'public_192_census')
    provenance = candidate['provenance']
    pinned = {'compiler_sha256': sha(Path(__file__).read_bytes()), 'preparation_sha256': PREPARATION_SHA,
        'analysis_sha256': ANALYSIS_SHA, 'freeze_sha256': FREEZE_SHA, 'review_plan_sha256': PLAN_SHA,
        'validator_sha256': CHECKER_SHA, 'preparer_sha256': PREPARER_SHA}
    require(set(provenance) == set(pinned) | {'root_unblind_acceptance_sha256', 'judgment_index_sha256', 'condition_mapping_sha256'}
            and all(type(v) is str and re.fullmatch('[0-9a-f]{64}', v) for v in provenance.values())
            and all(provenance[k] == v for k, v in pinned.items()), 'public_provenance_binding')
    contexts = {}
    for row in candidate['execution_context_census']:
        require(set(row) == {'context_id', 'cohort', 'original_partition', 'reviewed_cases'} and
                type(row['context_id']) is int and row['context_id'] > 0 and row['context_id'] not in contexts and
                row['cohort'] in {'initial', 'recovery'} and type(row['original_partition']) is int and
                1 <= row['original_partition'] <= 3 and type(row['reviewed_cases']) is int and row['reviewed_cases'] >= 0,
                'public_context_schema')
        contexts[row['context_id']] = {k: row[k] for k in ('context_id', 'cohort', 'original_partition')}
    cases, judgments, mapping = {}, {}, []
    for row in candidate['cases']:
        identifier = row['case_id']
        require(type(identifier) is str and re.fullmatch('CASE-[0-9]{3}', identifier) and identifier not in cases,
                'public_case_identity')
        require(type(row['case_utf8']) is str and type(row['judgment_utf8']) is str and
                type(row['input_bytes']) is int and type(row['judgment_bytes']) is int, 'public_raw_UTF8_fields')
        raw_case, raw_judgment = row['case_utf8'].encode('utf8'), row['judgment_utf8'].encode('utf8')
        require(len(raw_case) == row['input_bytes'] and len(raw_judgment) == row['judgment_bytes'], 'public_raw_byte_lengths')
        _, case = preserved(raw_case, row['input_sha256'], h)
        _, judgment = preserved(raw_judgment, row['judgment_sha256'], h)
        require(h.same(row['judgment'], judgment) and type(judgment) is dict and
                set(judgment) == checker.JUDGMENT_KEYS, 'public_raw_parsed_judgment_equality')
        supplied = checker.fragments(case, h)  # Original interval crosslinks and literal artifact fixity.
        require(type(judgment['answer_judgments']) is dict and
                set(judgment['answer_judgments']) == set(case['task']['answer_keys']), 'public_requested_fields')
        for entry in [*judgment['answer_judgments'].values(), *[judgment[k] for k in
                ('status_judgment', 'citation_judgment', 'full_query_judgment')]]:
            checker.entry(entry, supplied)  # Four labels + original-only Unicode citation bounds.
        require(type(judgment['limitations']) is list and all(type(v) is str and v.strip() for v in judgment['limitations']),
                'public_judgment_limitations')
        context = row['execution_context']
        require(type(context['context_id']) is int and context['context_id'] in contexts and
                h.same(context, contexts[context['context_id']]), 'public_context_binding')
        cases[identifier] = (raw_case, row['input_sha256'])
        judgments[identifier] = (raw_judgment, row['judgment_sha256'], context['context_id'])
        mapping.append({k: row[k] for k in ('case_id', 'trial_id', 'block', 'arm')})
    require(set(cases) == {'CASE-'+str(i).zfill(3) for i in range(1, 193)}, 'public_complete_case_IDs')
    rows = joined(cases, judgments, mapping, primary, contexts, h)
    require({row['trial_id'] for row in rows} == {row['trial_id'] for row in primary}, 'public_complete_trial_join')
    require(h.same(candidate, candidate_payload(rows, contexts, provenance)), 'public_candidate_table_or_field_mismatch')
    return {'state': 'PASS_PUBLIC_SEMANTIC_FIXITY_COUNTS_CHECK', 'reviewed_cases': len(rows),
        'primary_scores_changed': 0, 'private_inputs_read': False, 'semantic_judgments_adjudicated': 0,
        'limits': ['Reproduces supplied public bytes/citation bounds/frozen joins/counts; not private extraction or delivery attestation.',
                   'Does not authenticate opaque-to-condition mapping against the withheld private key or judge semantic entailment.']}


def check_public(args, checker, h):
    require('privatekey' not in re.sub('[^a-z0-9]', '', args.candidate.name.casefold()), 'public_check_private_key_alias_refused')
    no_links(args.candidate)
    candidate_raw = args.candidate.read_bytes()
    candidate = h.strict_json(candidate_raw.decode('utf8'))
    analysis = h.strict_json(exact(args.analysis, ANALYSIS_SHA).decode('utf8'))
    result = check_payload(candidate, analysis, checker, h)
    result.update(candidate_sha256=sha(candidate_raw), analysis_sha256=ANALYSIS_SHA)
    return result


def compile_candidate(args, checker, h):
    gate_raw = exact(args.root_acceptance, args.root_acceptance_sha256)
    gate = h.strict_json(gate_raw.decode('utf8'))
    require(gate.get('schema_version') == 'oct13-semantic-unblind-acceptance-v1' and
            gate.get('state') == 'ROOT_ACCEPTED_192_REVIEW_FOR_DESCRIPTIVE_UNBLINDING' and
            gate.get('reviewed_cases') == 192 and gate.get('compiler_sha256') == sha(Path(__file__).read_bytes()), 'root_acceptance_binding')
    for field in ('complete_model_visible_delivery_checked', 'saved_judgment_bytes_checked',
                  'mechanical_validation_checked', 'explicit_unblind_authorized'):
        require(gate.get(field) is True, 'root_acceptance_flag_required:'+field)
    require(gate.get('preparation_sha256') == PREPARATION_SHA and gate.get('analysis_sha256') == ANALYSIS_SHA,
            'accepted_preparation_analysis_binding')
    require(args.output.suffix == '.json' and not args.output.exists() and args.output.parent.is_dir()
            and not args.output.resolve().is_relative_to(args.study.resolve().parent.parent), 'new_private_output_required')
    no_links(args.output)
    manifest = h.strict_json(exact(args.preparation/'PRIVATE-preparation.json', PREPARATION_SHA).decode('utf8'))
    analysis = h.strict_json(exact(args.analysis, ANALYSIS_SHA).decode('utf8'))
    require(analysis['freeze_sha256'] == FREEZE_SHA and analysis['state'] == 'complete_frozen_census_analysis', 'frozen_analysis_binding')
    primary = analysis['tables']['reader_trials']
    require(len(primary) == 192 and len({r['trial_id'] for r in primary}) == 192, 'primary_192_census')
    index = h.strict_json(exact(args.judgment_index, gate['judgment_index_sha256']).decode('utf8'))
    require(set(index) == {'schema_version', 'contexts', 'judgments'} and
            index['schema_version'] == 'oct13-saved-semantic-judgment-index-v1' and
            type(index['contexts']) is list and type(index['judgments']) is list, 'judgment_index_schema')
    contexts = {}
    for row in index['contexts']:
        require(set(row) == {'context_id', 'cohort', 'original_partition'} and type(row['context_id']) is int
                and row['context_id'] > 0 and row['context_id'] not in contexts and
                row['cohort'] in {'initial', 'recovery'} and type(row['original_partition']) is int
                and 1 <= row['original_partition'] <= 3, 'execution_context_schema')
        contexts[row['context_id']] = row
    cases, original_partition = {}, {}
    for part in manifest['partitions']:
        folder = args.preparation/('reviewer-'+str(part['partition']))
        idx = h.strict_json(exact(folder/'index.json', part['index_sha256']).decode('utf8'))
        for row in idx['cases']:
            require(row['file'] == row['case_id']+'.json' and re.fullmatch(r'CASE-[0-9]{3}\.json', row['file']), 'case_basename')
            require(row['case_id'] not in cases, 'duplicate_input_case')
            cases[row['case_id']] = (exact(folder/row['file'], row['sha256'], row['bytes']), row['sha256'])
            original_partition[row['case_id']] = part['partition']
    judgments = {}
    for row in index['judgments']:
        require(set(row) == {'case_id', 'file', 'sha256', 'bytes', 'context_id'} and
                type(row['case_id']) is str and row['case_id'] in cases and row['case_id'] not in judgments and
                type(row['context_id']) is int and row['context_id'] in contexts and
                type(row['bytes']) is int and row['bytes'] > 0 and
                type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']) is not None and
                type(row['file']) is str and '\\' not in row['file'] and ':' not in row['file'],
                'saved_judgment_index_identity')
        relative = Path(row['file'])
        require(not relative.is_absolute() and '..' not in relative.parts and
                relative.name == row['case_id']+'.json' and
                all('privatekey' not in re.sub('[^a-z0-9]', '', part.casefold()) for part in relative.parts), 'saved_judgment_path')
        path = args.judgment_root/relative
        require(path.resolve().is_relative_to(args.judgment_root.resolve()), 'saved_judgment_path_escape')
        require(contexts[row['context_id']]['original_partition'] == original_partition[row['case_id']], 'execution_partition_binding')
        judgments[row['case_id']] = (exact(path, row['sha256'], row['bytes']), row['sha256'], row['context_id'])
    require(len(cases) == len(judgments) == 192, 'complete_192_review_required')
    review = {'schema_version': 'oct13-reader-semantic-judgments-v1', 'preparation_sha256': PREPARATION_SHA,
        'plan_sha256': PLAN_SHA, 'preparer_sha256': PREPARER_SHA, 'freeze_sha256': FREEZE_SHA,
        'cases': [h.strict_json(judgments[c][0].decode('utf8')) for c in sorted(judgments)]}
    with tempfile.TemporaryDirectory(prefix='accepted-semantic-merge-') as temporary:
        path = Path(temporary)/'judgments.json'; path.write_bytes(h.encoded(review, True))
        mechanical = checker.validate(args.preparation, path, PREPARATION_SHA, h)
    require(mechanical['reviewed_cases'] == 192, 'accepted_validator_full_census')
    # First and only condition-key read follows the independently bound full192
    # delivery/saved-byte/validator gate. A trusted root receipt authorizes this;
    # its hashes are fixity, not proof that an audit ran by themselves.
    require(args.condition_key.resolve() == (args.preparation/'PRIVATE-key.json').resolve(), 'explicit_original_condition_key_required')
    key = h.strict_json(exact(args.condition_key, gate['condition_mapping_sha256']).decode('utf8'))
    require(set(key) == {'mapping', 'no_write_trials'} and key['no_write_trials'] == [], 'all192_written_mapping_required')
    rows = joined(cases, judgments, key['mapping'], primary, contexts, h)
    require({r['trial_id'] for r in rows} == {r['trial_id'] for r in primary}, 'all192_primary_join_required')
    provenance = {'compiler_sha256': sha(Path(__file__).read_bytes()), 'root_unblind_acceptance_sha256': sha(gate_raw),
            'preparation_sha256': PREPARATION_SHA, 'analysis_sha256': ANALYSIS_SHA, 'freeze_sha256': FREEZE_SHA,
            'review_plan_sha256': PLAN_SHA, 'validator_sha256': CHECKER_SHA, 'preparer_sha256': PREPARER_SHA,
            'judgment_index_sha256': gate['judgment_index_sha256'], 'condition_mapping_sha256': gate['condition_mapping_sha256']}
    output = candidate_payload(rows, contexts, provenance)
    check_payload(output, analysis, checker, h)
    raw = h.encoded(output, True)
    with args.output.open('xb') as stream:
        stream.write(raw)
    return {'state': output['state'], 'output_sha256': sha(raw), 'census': output['census'], 'model_provider_calls': 0}


def self_check(checker, h):
    def entry(label):
        return {'label': label, 'rationale': 'Fictional evidence-bounded explanation.', 'citations': []}
    cases, judgments, mapping, primary = {}, {}, [], []
    combinations = [('direct', 'arm-a', ['supported', 'not_established'], 'supported', 'supported', False),
        ('direct', 'arm-a', ['supported'], 'supported', 'not_established', False),
        ('oracle', 'control', ['contradicted'], 'not_auditable', 'not_auditable', True),
        ('discovery', 'arm-b', ['supported'], 'supported', 'supported', True)]
    for number, (block, arm, labels, status, full, strict) in enumerate(combinations, 1):
        case_id, trial_id = 'CASE-'+str(number).zfill(3), 'fictional-'+str(number)
        keys = ['field'+str(i) for i in range(len(labels))]
        case = {'case_id': case_id, 'task': {'id': 'T', 'answer_keys': keys},
            'artifact_utf8': '{"flag":false,"zero":0,"extra":"\U0001f9ed e\u0301"}\r\n',
            'extraction_auditability': {'state': 'auditable'}}
        raw = h.encoded(case, True); cases[case_id] = (raw, sha(raw))
        judgment = {'case_id': case_id, 'input_sha256': sha(raw),
            'answer_judgments': {k: entry(label) for k, label in zip(keys, labels)}, 'status_judgment': entry(status),
            'citation_judgment': entry('contradicted' if number == 1 else 'supported'),
            'full_query_judgment': entry(full), 'limitations': []}
        raw = h.encoded(judgment, True).replace(b'\n', b'\r\n'); judgments[case_id] = (raw, sha(raw), number)
        mapping.append({'case_id': case_id, 'trial_id': trial_id, 'block': block, 'arm': arm})
        primary.append({'trial_id': trial_id, 'task_id': 'T', 'block': block, 'arm': arm, 'failure': None,
                        **{gate: strict for gate in GATES}})
    contexts = {i: {'context_id': i, 'cohort': 'initial' if i <= 3 else 'recovery', 'original_partition': 1} for i in range(1, 5)}
    rows = joined(cases, judgments, mapping, primary, contexts, h)
    direct = summarize(rows[:2])
    require(direct['answer_field_labels']['denominator'] == 3 and direct['answer_field_labels']['counts']['supported'] == 2,
            'fictional_field_denominator')
    require(direct['value_status_case_label_presence']['counts']['supported'] == 2 and
            direct['value_status_case_label_presence']['counts']['not_established'] == 1, 'fictional_overlapping_case_marginals')
    require(direct['support_typed_match_intersection']['counts']['all_supported__typed_mismatch'] == 1 and
            direct['review_consistency_diagnostic']['case_ids'] == ['CASE-001'], 'fictional_intersection_diagnostic')
    require(rows[1]['descriptive_flags']['all_values_and_status_supported'] and not rows[1]['descriptive_flags']['full_query_supported'],
            'supported_status_unresolved_query_must_remain_valid')
    for row in h.strict_json(h.encoded(rows).decode('utf8')):
        require(sha(row['case_utf8'].encode('utf8')) == row['input_sha256'] and
                sha(row['judgment_utf8'].encode('utf8')) == row['judgment_sha256'], 'fictional_UTF8_hash_roundtrip')
    rejected = []
    def reject(name, action):
        try:
            action()
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError('known_bad_accepted:'+name)
    reject('duplicate_mapping_case', lambda: joined(cases, judgments, mapping+[mapping[0]], primary, contexts, h))
    bad = copy.deepcopy(mapping); bad[1]['trial_id'] = bad[0]['trial_id']
    reject('duplicate_mapping_trial', lambda: joined(cases, judgments, bad, primary, contexts, h))
    bad = copy.deepcopy(primary); bad[0]['typed_answer_status_match'] = 0
    reject('integer_not_boolean_gate', lambda: joined(cases, judgments, mapping, bad, contexts, h))
    bad = copy.deepcopy(mapping); bad[0]['arm'] = 'wrong'
    reject('condition_join_mismatch', lambda: joined(cases, judgments, bad, primary, contexts, h))
    bad = dict(cases); bad['CASE-001'] = (cases['CASE-001'][0], '0'*64)
    reject('raw_case_hash', lambda: joined(bad, judgments, mapping, primary, contexts, h))
    reject('duplicate_JSON_key', lambda: h.strict_json('{"x":false,"x":0}'))
    # A full192 fictional public payload uses the actual accepted fragment/entry
    # validators and public table regenerator, without any private preparation.
    public_cases, public_judgments, public_mapping, public_primary = {}, {}, [], []
    text, start = 'A\U0001f9ed e\u0301 flag = false.', 7
    header = 'SOURCE '+h.encoded({'id': 'S', 'kind': 'source', 'revision': 1, 'chars': [start, start+len(text)]}).decode('utf8')+'\n'
    actual = {'packet': header+text}
    delivery = {'operation': 'supplied_packet', 'actual_result': actual, 'prompt_sha256': sha(b'fictional prompt'),
        'delivery_id': 'D001', 'actual_result_canonical_sha256': sha(h.encoded(actual)), 'source_fragments': [{
            'fragment_id': 'F0001', 'id': 'S', 'start': start, 'end': start+len(text), 'text': text,
            'source_body_sha256': sha(text.encode('utf8')), 'result_text_pointer': '/packet',
            'delivered_text_chars': [len(header), len(header)+len(text)]}]}
    for number in range(1, 193):
        template = (number-1) % 4
        old_id = 'CASE-'+str(template+1).zfill(3)
        case_id, trial_id = 'CASE-'+str(number).zfill(3), 'fictional-public-'+str(number)
        old_case = h.strict_json(cases[old_id][0].decode('utf8'))
        artifact_text = old_case['artifact_utf8']
        case = {'case_id': case_id, 'task': {'id': 'T', 'query': 'Fictional flag?',
            'answer_keys': old_case['task']['answer_keys'], 'answer_contract': {}},
            'artifact': h.strict_json(artifact_text), 'artifact_utf8': artifact_text,
            'artifact_sha256': sha(artifact_text.encode('utf8')), 'deliveries': [copy.deepcopy(delivery)],
            'extraction_auditability': {'state': 'auditable', 'reasons': []},
            'offset_unit': 'Unicode code points, half-open; source body and actual returned text'}
        raw = h.encoded(case, True); public_cases[case_id] = (raw, sha(raw))
        judgment = h.strict_json(judgments[old_id][0].decode('utf8'))
        judgment.update(case_id=case_id, input_sha256=sha(raw))
        judgment['status_judgment']['citations'] = [{'fragment_id': 'F0001', 'start': start, 'end': start+3}]
        raw = h.encoded(judgment, True).replace(b'\n', b'\r\n')
        public_judgments[case_id] = (raw, sha(raw), template+1)
        public_mapping.append({**mapping[template], 'case_id': case_id, 'trial_id': trial_id})
        public_primary.append({**primary[template], 'trial_id': trial_id})
    public_rows = joined(public_cases, public_judgments, public_mapping, public_primary, contexts, h)
    provenance = {'compiler_sha256': sha(Path(__file__).read_bytes()), 'preparation_sha256': PREPARATION_SHA,
        'analysis_sha256': ANALYSIS_SHA, 'freeze_sha256': FREEZE_SHA, 'review_plan_sha256': PLAN_SHA,
        'validator_sha256': CHECKER_SHA, 'preparer_sha256': PREPARER_SHA,
        **{k: sha(('fictional '+k).encode('ascii')) for k in
           ('root_unblind_acceptance_sha256', 'judgment_index_sha256', 'condition_mapping_sha256')}}
    payload = candidate_payload(public_rows, contexts, provenance)
    public_analysis = {'state': 'complete_frozen_census_analysis', 'freeze_sha256': FREEZE_SHA,
                       'tables': {'reader_trials': public_primary}}
    require(check_payload(payload, public_analysis, checker, h)['reviewed_cases'] == 192, 'fictional_public_normal')
    bad = copy.deepcopy(payload); bad['by_block'][0]['reviewed_artifacts'] += 1
    reject('public_tampered_count', lambda: check_payload(bad, public_analysis, checker, h))
    bad = copy.deepcopy(payload); bad['cases'][0]['input_sha256'] = '0'*64
    reject('public_tampered_raw_case_hash', lambda: check_payload(bad, public_analysis, checker, h))
    bad = copy.deepcopy(payload); bad['cases'][0]['judgment_sha256'] = '0'*64
    reject('public_tampered_raw_judgment_hash', lambda: check_payload(bad, public_analysis, checker, h))
    bad = copy.deepcopy(payload)
    value = h.strict_json(bad['cases'][0]['judgment_utf8'])
    value['status_judgment']['citations'][0]['end'] = start+len(text)+1
    raw = h.encoded(value, True)
    bad['cases'][0].update(judgment=value, judgment_utf8=raw.decode('utf8'), judgment_sha256=sha(raw), judgment_bytes=len(raw))
    reject('public_original_citation_bounds', lambda: check_payload(bad, public_analysis, checker, h))
    bad = copy.deepcopy(payload); bad['cases'][0]['frozen_primary_gates']['typed_answer_status_match'] = True
    reject('public_tampered_frozen_flag', lambda: check_payload(bad, public_analysis, checker, h))
    bad = copy.deepcopy(payload)
    value = h.strict_json(bad['cases'][0]['case_utf8']); value['task']['id'] = 'wrong-task'
    raw = h.encoded(value, True)
    bad['cases'][0].update(case_utf8=raw.decode('utf8'), input_sha256=sha(raw), input_bytes=len(raw))
    judgment = h.strict_json(bad['cases'][0]['judgment_utf8']); judgment['input_sha256'] = sha(raw)
    raw = h.encoded(judgment, True)
    bad['cases'][0].update(judgment=judgment, judgment_utf8=raw.decode('utf8'), judgment_sha256=sha(raw), judgment_bytes=len(raw))
    reject('public_rehashed_wrong_task_ID', lambda: check_payload(bad, public_analysis, checker, h))
    return {'state': 'PASS_FICTIONAL_COMPILER_CHECK', 'normal_check_groups': 6, 'known_bad_rejections': len(rejected),
        'rejections': rejected, 'failed': 0, 'skipped': 0, 'actual_cases_judgments_key_read': False,
        'actual_compilation_executed': False, 'model_provider_calls': 0,
        'limits': ['Full accepted-validator/192case/unblind integration is unexecuted.', 'Python3.10 grammar only; runtime not executed.',
                   'Actual figures, publication privacy review and semantic interpretation are unexecuted.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--self-check', action='store_true'); modes.add_argument('--compile', action='store_true')
    modes.add_argument('--check', action='store_true')
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--study', type=Path, default=HERE)
    for name in ('preparation', 'judgment-index', 'judgment-root', 'condition-key', 'analysis', 'root-acceptance', 'output'):
        parser.add_argument('--'+name, type=Path)
    parser.add_argument('--root-acceptance-sha256')
    args = parser.parse_args()
    if args.compile:
        require(all(getattr(args, name) is not None for name in ('preparation', 'judgment_index', 'judgment_root',
            'condition_key', 'analysis', 'root_acceptance', 'output', 'root_acceptance_sha256')), 'explicit_root_unblind_inputs_required')
    if args.check:
        require(args.candidate is not None and args.analysis is not None, 'public_candidate_and_pinned_analysis_required')
    checker, h = load_helpers(args.study)
    if args.self_check:
        result = self_check(checker, h)
    elif args.check:
        result = check_public(args, checker, h)
    else:
        result = compile_candidate(args, checker, h)
    sys.stdout.buffer.write(h.encoded(result, True))


if __name__ == '__main__':
    main()
