"""Postcollection compatibility entrypoint for compact saved observations.

Only the reader support alias is scoped to the frozen analyzer's exact-body
normalization helper. Scores and statistics stay in the frozen implementation.
The run gate binds bytes for a trusted caller; it does not attest audit execution.
Provenance is separate from the unchanged frozen analysis metadata.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import argparse
import copy
import hashlib
import importlib
import json
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
CORE_SHA = 'fda01f88f50dbb6e66a312ca9ab775c8603643ebe8b7f74b596a7250bc39524c'
AUDITOR_SHA = '649640c0faae4a6bd9f60854a13e78c13613340fc81665ec3bb1418207c48f75'
RESULT_FILES = ('grid-manifest.json', 'reader-results.json', 'warm-timing.json', 'maintenance-results.json')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def parse_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError('nonfinite_json_number')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)


def read_json(path):
    return parse_json(Path(path).read_text(encoding='utf8'))


def verify_core(study):
    require(sha(study / 'freeze.json') == CORE_SHA, 'original_main_freeze_changed')
    pins = read_json(study / 'freeze.json')['files']
    require(isinstance(pins, dict) and len(pins) == 32, 'original_32_inputs_changed')
    require(all(sha(study / name) == digest for name, digest in pins.items()), 'original_32_inputs_changed')
    return pins


def frozen_modules(study):
    verify_core(study)
    sys.path.insert(0, str(study))
    analyzer = importlib.import_module('analyze_results')
    readers = importlib.import_module('reader_trials')
    for module in (analyzer, readers, importlib.import_module('study_common')):
        require(Path(module.__file__).resolve() == (study / (module.__name__ + '.py')).resolve(),
            'frozen_module_resolved_elsewhere')
    return analyzer, readers


def validate_run(study, arguments, source_sha256, audit_path, audit_sha256):
    require(sha(Path(__file__)) == source_sha256, 'exact_reviewed_compatibility_source_required')
    audit_bytes = Path(audit_path).read_bytes()
    require(hashlib.sha256(audit_bytes).hexdigest() == audit_sha256, 'exact_accepted_raw_audit_required')
    audit = parse_json(audit_bytes.decode('utf8'))
    require(isinstance(audit, dict) and audit.get('state') == 'passed', 'passed_raw_audit_required')
    require(audit.get('freeze_sha256') == CORE_SHA, 'audit_freeze_changed')
    require(audit.get('audit_source_sha256') == AUDITOR_SHA, 'accepted_auditor_source_required')
    for flag in ('private_execution_checked', 'pinned_cache_checked', 'frozen_packer_replay_enabled'):
        require(audit.get(flag) is True, 'audit_required_flag_not_true:' + flag)
    pins = verify_core(study)
    require(sha(study / 'audit_results.py') == AUDITOR_SHA, 'accepted_auditor_source_changed')
    recorded = audit.get('result_file_sha256')
    require(isinstance(recorded, dict) and set(recorded) == set(RESULT_FILES), 'audit_result_file_set_changed')
    current = {name: sha(study / name) for name in RESULT_FILES}
    require(current == recorded, 'audited_main_result_bytes_changed')
    require(isinstance(arguments, list) and len(arguments) > 1 and all(isinstance(item, str) for item in arguments),
        'original_analysis_argv_required')
    program = Path(arguments[0])
    require(arguments[0] == 'analyze_results.py' or program.resolve() == (study / 'analyze_results.py').resolve(),
        'original_analysis_program_required')
    require('--analyze' in arguments[1:] and not any(item.split('=', 1)[0] in ('--self-check', '--preview-fixtures')
        for item in arguments[1:]), 'only_original_actual_analysis_arguments_allowed')
    # The original analyzer still parses every forwarded token. This check binds
    # its freeze selector without rewriting or reconstructing the caller's argv.
    selectors = [arguments[index + 1] for index, item in enumerate(arguments[:-1]) if item == '--freeze-sha256']
    selectors += [item.split('=', 1)[1] for item in arguments[1:] if item.startswith('--freeze-sha256=')]
    require(selectors == [CORE_SHA], 'original_analysis_freeze_argument_required')
    return {'wrapper_source_sha256': source_sha256, 'accepted_raw_audit_sha256': audit_sha256,
        'accepted_auditor_source_sha256': AUDITOR_SHA, 'original_main_freeze_sha256': CORE_SHA,
        'original_32_file_sha256': pins, 'audited_result_file_sha256': current}


def delegate(analyzer, readers, arguments):
    """Assign the original complete argv unchanged, then call the frozen main."""
    prior = sys.argv
    try:
        sys.argv = list(arguments)
        with reader_support_boundary(analyzer, readers):
            return analyzer.main()
    finally:
        sys.argv = prior


def save(path, value):
    with Path(path).open('x', encoding='utf8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def run_frozen_analysis(study, arguments, source_sha256, audit_path, audit_sha256, provenance_dir):
    binding = validate_run(study, arguments, source_sha256, audit_path, audit_sha256)
    require(not provenance_dir.resolve().is_relative_to(study.parents[1]), 'provenance_must_stay_outside_public_repository')
    analyzer, readers = frozen_modules(study)
    provenance_dir.mkdir(parents=True, exist_ok=False)
    pending = {'schema_version': 1, 'state': 'pending_explicit_analysis_invocation',
        'started_utc': datetime.now(timezone.utc).isoformat(), **binding, 'original_analysis_argv': list(arguments),
        'boundary': 'Only reader_trials.support_metrics alias delegates frozen analyze_results.support; exact retained text is validated.',
        'gate_limit': 'Caller-supplied hashes establish fixity, not cryptographic proof of audit execution.',
        'frozen_analysis_metadata_rewritten': False, 'automatic_retry': False}
    save(provenance_dir / 'pending.json', pending)
    try:
        result = delegate(analyzer, readers, arguments)
    except BaseException as error:
        save(provenance_dir / 'receipt.json', {**pending, 'state': 'failed_requires_inspection',
            'finished_utc': datetime.now(timezone.utc).isoformat(), 'failure_class': type(error).__name__})
        raise
    save(provenance_dir / 'receipt.json', {**pending, 'state': 'completed_explicit_analysis_invocation',
        'finished_utc': datetime.now(timezone.utc).isoformat()})
    return result

@contextmanager
def reader_support_boundary(analyzer, readers):
    """Reuse frozen source expansion; leave all scorer/statistical code unchanged."""
    original = readers.support_metrics
    common = importlib.import_module('study_common')
    if original is not common.support_metrics:
        raise ValueError('reader_support_alias_already_changed')

    def normalized(task, observations, docs):
        analyzer.require(isinstance(observations, list), 'Saved observations must be a list')
        for item in observations:
            analyzer.require(isinstance(item, dict), 'Saved observation must be an object')
            # The frozen helper already checks IDs, non-bool integer bounds and
            # UTF-8 body SHA before expanding text. Preserve its metric and kind
            # semantics; reject inconsistent existing text instead of replacing it.
            if 'text' in item:
                identifier, start, end = item.get('id'), item.get('start'), item.get('end')
                analyzer.require(isinstance(identifier, str) and identifier in docs, 'Observation names unknown source')
                body = docs[identifier]['body']
                analyzer.require(type(start) is int and type(end) is int and 0 <= start < end <= len(body),
                    'Invalid source character interval')
                analyzer.require(isinstance(item['text'], str) and item['text'] == body[start:end],
                    'Retained observation text differs from exact source')
        return analyzer.support(task, observations, docs)

    readers.support_metrics = normalized
    try:
        yield
    finally:
        readers.support_metrics = original


def self_check(study):
    analyzer, readers = frozen_modules(study)
    common = importlib.import_module('study_common')
    body = '青灯 λ e\u0301 👩🏽‍🔬: timeout is13minutes.\nOnly with approval.'
    docs = {'S': {'id': 'S', 'kind': 'source', 'body': body},
        'V': {'id': 'V', 'kind': 'derived', 'body': 'An illustrative derived view.'}}
    task = {'id': 'FICTIONAL', 'answer_keys': ['minutes'],
        'answer_contract': {'fields': {'minutes': {'type': 'integer'}}, 'additional_fields': False},
        'expected': {'status': 'ready', 'answer': {'minutes': 13}},
        'evidence_sets': [['S']], 'evidence_spans': [[{'id': 'S', 'start': 0, 'end': len(body)}]]}
    value = {'status': 'ready', 'answer': {'minutes': 13}, 'evidence': ['S']}
    write = {'check': {'schema_valid': True, 'cited_original_ids': ['S']}}
    rich = [{'id': 'S', 'start': 0, 'end': len(body), 'source_hash': common.digest(body), 'text': body, 'whole': True}]
    saved = [{k: item[k] for k in ('id', 'start', 'end', 'source_hash')} for item in rich]
    original_score, original_support = readers.score, readers.support_metrics
    baseline = original_score(value, task, docs, rich, write, True)
    empty_baseline = original_score(value, task, docs, [], write, True)
    derived = {'id': 'V', 'start': 0, 'end': len(docs['V']['body']), 'source_hash': common.digest(docs['V']['body'])}
    derived_rich = {**derived, 'text': docs['V']['body']}
    derived_baseline = original_score(value, task, docs, [derived_rich], write, True)
    try:
        original_score(value, task, docs, saved, write, True)
    except KeyError as error:
        assert error.args == ('text',)
    else:
        raise AssertionError('Frozen compact-observation failure was not reproduced')
    before = copy.deepcopy((docs, task, value, write, rich, saved))
    passed, rejected = [], []
    with reader_support_boundary(analyzer, readers):
        assert readers.score is original_score and common.support_metrics is original_support
        for name, observations, expected in [('existing_exact_text', rich, baseline),
                ('missing_text', saved, baseline), ('empty_observations', [], empty_baseline)]:
            assert readers.score(value, task, docs, observations, write, True) == expected
            passed.append(name)
        assert readers.score(value, task, docs, [derived], write, True) == derived_baseline
        passed.append('derived_record_retains_frozen_original_evidence_semantics')
        damages = [('wrong_hash', {**saved[0], 'source_hash': '0' * 64}),
            ('wrong_existing_text', {**rich[0], 'text': 'invented'}),
            ('null_existing_text', {**rich[0], 'text': None}),
            ('unknown_id', {**saved[0], 'id': 'UNKNOWN'}),
            ('negative_start', {**saved[0], 'start': -1}),
            ('past_end', {**saved[0], 'end': len(body) + 1}),
            ('reversed_bounds', {**saved[0], 'start': 4, 'end': 3}),
            ('empty_interval', {**saved[0], 'end': 0}),
            ('bool_start', {**saved[0], 'start': False}),
            ('bool_end', {**saved[0], 'end': True}),
            ('float_start', {**saved[0], 'start': 0.0}),
            ('string_end', {**saved[0], 'end': str(len(body))}),
            ('UTF8_byte_end_is_not_Unicode_end', {**saved[0], 'end': len(body.encode('utf8'))})]
        for name, damaged in damages:
            try:
                readers.score(value, task, docs, [damaged], write, True)
            except (ValueError, AssertionError, KeyError, TypeError):
                rejected.append(name)
            else:
                raise AssertionError('Invalid saved observation accepted: ' + name)
    assert readers.support_metrics is original_support and readers.score is original_score
    assert (docs, task, value, write, rich, saved) == before
    argv = sys.argv
    seen = []
    def fictional_main():
        seen.append(list(sys.argv))
        assert readers.score(value, task, docs, saved, write, True) == baseline
        return 'fictional_main_return'
    fake = SimpleNamespace(require=analyzer.require, support=analyzer.support, main=fictional_main)
    arguments = [str(study / 'analyze_results.py'), '--analyze', '--freeze-sha256', CORE_SHA, '--output', 'FICTIONAL-NOT-A-DIRECTORY']
    assert delegate(fake, readers, arguments) == 'fictional_main_return'
    assert seen == [arguments] and sys.argv is argv
    def fictional_error(): raise ValueError('fictional downstream failure')
    fake.main = fictional_error
    try: delegate(fake, readers, arguments)
    except ValueError as error: assert str(error) == 'fictional downstream failure'
    else: raise AssertionError('Downstream failure swallowed')
    assert readers.support_metrics is original_support and sys.argv is argv
    return {'state': 'PASS_FICTIONAL_PORTABLE_BOUNDARY_ONLY', 'existing_and_missing_scores_identical': True,
        'frozen_missing_text_error_reproduced': 'KeyError:text', 'normal_cases': passed,
        'known_bad_cases_rejected': rejected, 'original_score_and_common_support_unchanged': True,
        'inputs_unchanged': True, 'unchanged_entrypoint_arguments_and_return_delegated': True,
        'alias_and_arguments_restored_after_exception': True, 'actual_analysis_invocations': 0,
        'actual_outcomes_parsed_or_graded': False, 'model_or_provider_calls': 0}



def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    divider = arguments.index('--') if '--' in arguments else len(arguments)
    original = arguments[divider + 1:] if divider < len(arguments) else []
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--self-check', action='store_true')
    mode.add_argument('--run', action='store_true')
    parser.add_argument('--study', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--source-sha256')
    parser.add_argument('--audit-json', type=Path)
    parser.add_argument('--audit-sha256')
    parser.add_argument('--provenance-dir', type=Path)
    args = parser.parse_args(arguments[:divider])
    study = args.study.resolve()
    if args.self_check:
        require(not original and not any((args.source_sha256, args.audit_json, args.audit_sha256, args.provenance_dir)),
            'self_check_does_not_accept_actual_run_inputs')
        result = self_check(study)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return result
    require(args.source_sha256 and args.audit_json and args.audit_sha256 and args.provenance_dir and original,
        'run_requires_exact_source_audit_provenance_and_original_argv')
    return run_frozen_analysis(study, original, args.source_sha256, args.audit_json,
        args.audit_sha256, args.provenance_dir)


if __name__ == '__main__':
    main()
