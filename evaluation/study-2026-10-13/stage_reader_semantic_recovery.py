"""Prospective opaque-case recovery projection. Never launch, judge or parse ratings.

--plan reads metadata/indices/auxiliary text, not case payloads or judgments.
--stage additionally hashes all original inputs and copies raw unjudged case bytes.
Saved-output hashes are carried from sealed structural receipts; only their file
names/sizes/mtimes are observed here. Root independently owns saved-byte/native QA.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import sys
import tempfile

BYTE_CAP = 450000
CASE_CAP = 18
MANIFEST_SHA = '63b780718cdee616a7dadf6ec0d07fe802fb966e351eaf30bc5acf543353f42e'
STAGING_RECEIPT_SHA = '226bbb0a0d7b6b483f733eb21ad8141379bec13bcd1535b2878eb6c595a3afd1'
HELPER_SHA = 'cfb1864f1a22e17ada4048b3b2cfab73801c75a8b1da9c50a58f95acdac3ecb9'
PLAN_SHA = '3c06cf6c3a4ee965743a4f0ca1a515f16fd42eb292f2d3ca5cf63c59091a200a'
PREPARATION_SHA = '46d910d5a96046d333de5760d63a637ee3268ac3c365ec3e0a07131612cb861c'
VALIDATOR_SHA = '16107e4e83ddb623c404e667024c460605bfda67fcd8133e32e49f94cf8cecf5'
BOUNDARY_PINS = {
    1: 'fcbe27d813f564833a97a78b3b95c5c7a79b7ecb6b6dc6857e52a2982c7f36f3',
    2: '86766adc5af0ea48385d539023a13742ca694f25867a41ee6a0e38bd74d6cf9d',
    3: 'a2fdc979664ce4fc813955fec23cfad04d4c27cecd8c22c00ada2ab34b90f068'}
STARTUP_SOURCE = """from pathlib import Path
import sys
for name in ['instructions.md', 'SEMANTIC-REVIEW-PLAN.md']:
    raw = Path(name).read_bytes()
    raw.decode('utf8', errors='strict')
    sys.stdout.buffer.write(raw)
"""


def require(test, message):
    if not test:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def duplicate_free(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate_JSON_key')
        result[key] = value
    return result


def decoded(raw):
    def bad_constant(value):
        raise ValueError('nonfinite_JSON:'+value)
    result = json.loads(raw.decode('utf8', errors='strict'),
                        object_pairs_hook=duplicate_free, parse_constant=bad_constant)
    encoded(result)  # Refuse escaped lone surrogates too.
    return result


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False)+'\n').encode('utf8', errors='strict')


def no_links(path):
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            require(not stat.S_ISLNK(info.st_mode) and
                    not getattr(info, 'st_file_attributes', 0) & 0x400 and
                    (not stat.S_ISREG(info.st_mode) or info.st_nlink == 1),
                    'link_hardlink_or_reparse_point:'+str(item))


def child(root, name):
    require(isinstance(name, str) and name and '\\' not in name and
            not PureWindowsPath(name).is_absolute() and not PurePosixPath(name).is_absolute(),
            'unsafe_relative_path')
    parts = name.split('/')
    require(all(part not in ('', '.', '..') and ':' not in part for part in parts), 'path_escape')
    require(all('privatekey' not in re.sub('[^a-z0-9]', '', part.casefold()) for part in parts),
            'private_key_alias_refused')
    result = root.joinpath(*parts)
    no_links(result)
    require(result.resolve().is_relative_to(root.resolve()), 'resolved_path_escape')
    return result


def exact(path, pin):
    no_links(path)
    raw = path.read_bytes()
    require(sha(raw) == pin, 'hash_mismatch:'+path.name)
    return raw


def create(path, raw):
    no_links(path)
    with path.open('xb') as stream:
        stream.write(raw)


def copy_record(source, destination, row):
    raw = exact(child(source, row['file']), row['sha256'])
    require(len(raw) == row['bytes'], 'case_byte_count_changed')
    raw.decode('utf8', errors='strict')
    create(child(destination, row['file']), raw)  # No case JSON parse/reserialization.


def index_rows(index):
    require(type(index) is dict and set(index) == {'schema_version', 'cases', 'instructions'} and
            index['schema_version'] == 'oct13-reader-semantic-input-v1' and
            type(index['instructions']) is str and type(index['cases']) is list, 'index_schema')
    rows = index['cases']
    seen = set()
    for row in rows:
        require(type(row) is dict and set(row) == {'case_id', 'file', 'sha256', 'bytes'}, 'index_row_schema')
        case = row['case_id']
        require(type(case) is str and re.fullmatch(r'CASE-[0-9]{3}', case) is not None and
                row['file'] == case+'.json', 'case_identity_or_basename')
        require(case not in seen, 'duplicate_case_id')
        seen.add(case)
        require(type(row['bytes']) is int and row['bytes'] > 0 and
                type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']) is not None,
                'case_size_or_hash')
    require(rows == sorted(rows, key=lambda row: row['case_id']), 'index_order')
    return rows


def balanced(rows, retained):
    require(len(retained) == len(set(retained)) and set(retained) <= {r['case_id'] for r in rows},
            'unknown_or_duplicate_retained_case')
    remaining = sorted((r for r in rows if r['case_id'] not in retained),
                       key=lambda row: (-row['bytes'], row['case_id']))
    require(all(r['bytes'] <= BYTE_CAP for r in remaining), 'single_case_exceeds_byte_cap')
    if not remaining:
        return []
    count = max((sum(r['bytes'] for r in remaining)+BYTE_CAP-1)//BYTE_CAP,
                (len(remaining)+CASE_CAP-1)//CASE_CAP)
    # Deterministic greedy packing, not a minimum-bin optimizer. If a placement
    # fails, increase bin count and restart; the ceiling is one bin per case.
    while count <= len(remaining):
        groups, sizes = [[] for _ in range(count)], [0]*count
        for row in remaining:
            possible = [i for i in range(count) if len(groups[i]) < CASE_CAP and sizes[i]+row['bytes'] <= BYTE_CAP]
            if not possible:
                break
            i = min(possible, key=lambda i: (sizes[i], i))
            groups[i].append(row)
            sizes[i] += row['bytes']
        else:
            return [sorted(group, key=lambda row: row['case_id']) for group in groups if group]
        count += 1
    raise ValueError('packing_failed')


def output_stats(folder, records):
    no_links(folder)
    require(folder.is_dir() and {p.name for p in folder.iterdir()} == {r['name'] for r in records},
            'saved_output_filename_census_changed')
    result = {}
    for record in records:
        path = child(folder, record['name'])
        require(path.is_file(), 'saved_output_not_file')
        info = path.stat()
        require(info.st_size == record['bytes'] and info.st_mtime_ns == record['mtime_ns'],
                'saved_output_stat_changed:'+path.name)
        result[path.name] = {'bytes': info.st_size, 'mtime_ns': info.st_mtime_ns,
                             'sha256_from_sealed_receipt': record['sha256']}
    return result


def inspect(source, boundary_paths):
    no_links(source)
    manifest = decoded(exact(source/'PRIVATE-staging.json', MANIFEST_SHA))
    exact(source/'PRIVATE-staging-receipt.json', STAGING_RECEIPT_SHA)
    for key, pin in [('helper_sha256', HELPER_SHA), ('rubric_sha256', PLAN_SHA),
                     ('preparation_sha256', PREPARATION_SHA), ('validator_sha256', VALIDATOR_SHA)]:
        require(manifest[key] == pin, 'staging_identity_changed:'+key)
    parts, input_records, seen = [], {}, set()
    require([p['partition'] for p in manifest['partitions']] == [1, 2, 3], 'original_partition_census')
    for part in manifest['partitions']:
        number = part['partition']
        folder = child(source, 'inputs/reviewer-'+str(number))
        index = decoded(exact(folder/'index.json', part['index_sha256']))
        rows = index_rows(index)
        require(len(rows) == (64, 63, 65)[number-1], 'original_case_count')
        require(not seen.intersection(r['case_id'] for r in rows), 'cross_partition_duplicate')
        seen.update(r['case_id'] for r in rows)
        names = {'index.json', 'opaque_case_reader.py', 'SEMANTIC-REVIEW-PLAN.md', 'instructions.md'} | {r['file'] for r in rows}
        require({p.name for p in folder.iterdir()} == names, 'original_input_filename_census')
        for name in sorted(names):
            rel = 'inputs/reviewer-'+str(number)+'/'+name
            record = manifest['projected_input_files'][rel]
            path = child(source, rel)
            require(path.is_file() and path.stat().st_size == record['bytes'], 'original_input_size_changed')
            input_records[rel] = record
        for row in rows:
            require(input_records['inputs/reviewer-'+str(number)+'/'+row['file']] ==
                    {'bytes': row['bytes'], 'sha256': row['sha256']}, 'index_manifest_disagrees')
        helper = exact(folder/'opaque_case_reader.py', HELPER_SHA)
        rubric = exact(folder/'SEMANTIC-REVIEW-PLAN.md', PLAN_SHA)
        template = exact(folder/'instructions.md', part['instructions_sha256']).decode('utf8')
        boundary = decoded(exact(boundary_paths[number], BOUNDARY_PINS[number]))
        retained = boundary['completed_saved_case_ids' if number == 1 else 'completed_case_ids']
        records = boundary['output_files_at_stop' if number == 1 else 'output_files']
        require(len(retained) == (10, 38, 37)[number-1], 'retained_case_count')
        require({r['name'] for r in records if r['name'].endswith('.json')} == {case+'.json' for case in retained},
                'receipt_saved_case_census')
        require(all(re.fullmatch('[0-9a-f]{64}', r['sha256']) for r in records), 'receipt_output_hash')
        stats = output_stats(child(source, 'outputs/reviewer-'+str(number)), records)
        groups = balanced(rows, retained)
        parts.append({'number': number, 'old': part, 'folder': folder, 'index': index,
                      'rows': rows, 'retained': retained, 'records': records, 'output_stats': stats,
                      'groups': groups, 'helper': helper, 'rubric': rubric, 'template': template,
                      'native_prefix_sha256': boundary['full_failed_prefix_sha256' if number == 1 else 'native_prefix_sha256'],
                      'native_prefix_bytes': boundary['full_failed_prefix_bytes' if number == 1 else 'native_prefix_bytes']})
    require(seen == {'CASE-'+str(i).zfill(3) for i in range(1, 193)}, 'complete_original_case_census')
    require(input_records == manifest['projected_input_files'] and len(input_records) == 204, 'original_204_census')
    return parts, input_records


def literal(source):
    source.encode('ascii')
    require(not any(line.startswith("'@") for line in source.splitlines()), 'literal_terminator')
    return "@'\n"+source.rstrip('\n')+"\n'@ | python -B -X utf8 -"


def revised_instructions(part, number, group, pin, folder, output):
    text = part['template']
    replacements = [
        ('# Supplemental evidence-bounded review: partition '+str(part['number']),
         '# Supplemental evidence-bounded review: recovery context '+str(number)),
        (str(part['old']['input_directory']), str(folder)),
        (str(part['old']['output_directory']), str(output)),
        (part['old']['index_sha256'], pin),
        ("exactly this partition's "+str(len(part['rows']))+' opaque cases',
         "exactly this partition's "+str(len(group))+' opaque cases'),
        ('complete '+str(len(part['rows']))+'-case census', 'complete '+str(len(group))+'-case census'),
        ('After all '+str(len(part['rows']))+' create-new judgments', 'After all '+str(len(group))+' create-new judgments'),
        ('absent. Create it once.', 'absent. Its parent already exists. Create only this leaf once with mkdir();\n'
         'do not use parents=True, retry a failed mkdir, or reuse an existing leaf.')]
    for old, new in replacements:
        require(old in text, 'instruction_template_marker_missing')
        text = text.replace(old, new)
    return text+'\n## Prospective recovery scope\n\n'+(
        'This is a new context for previously unjudged cases from original partition '+str(part['number'])+'. '
        'Retained judgments are withheld and must not be reread or rated again. Start every listed case at chunk 1; '
        'no partial read from an earlier task carries into this context. The frozen rubric is unchanged. '
        'The revised execution grouping adds fresh contexts without an independence, reliability, capacity or sandbox claim.\n')


def plan_record(parts, source, destination, amendment_pin):
    groups = []
    number = 4
    for part in parts:
        for group in part['groups']:
            groups.append({'context': number, 'original_partition': part['number'], 'cases': len(group),
                           'case_bytes': sum(row['bytes'] for row in group),
                           'case_ids': [row['case_id'] for row in group]})
            number += 1
    return {'state': 'PROSPECTIVE_PLAN_NO_TASKS_OR_RATINGS', 'source_sha256': sha(Path(__file__).read_bytes()),
            'source_directory': str(source), 'new_directory': str(destination),
            'original_staging_manifest_sha256': MANIFEST_SHA, 'original_staging_receipt_sha256': STAGING_RECEIPT_SHA,
            'structural_receipts': {str(k): v for k, v in BOUNDARY_PINS.items()}, 'amendment_sha256': amendment_pin,
            'byte_cap': BYTE_CAP, 'case_cap': CASE_CAP, 'maximum_concurrent_launches_proposed': 3,
            'retained_cases': sum(len(p['retained']) for p in parts),
            'unjudged_cases': sum(row['cases'] for row in groups), 'new_contexts': len(groups),
            'total_planned_contexts_including_original_three': 3+len(groups), 'contexts': groups,
            'original_boundaries': [{'partition': p['number'], 'retained_case_ids': p['retained'],
                'output_records_and_stat_snapshot': p['output_stats'], 'native_prefix_sha256': p['native_prefix_sha256'],
                'native_prefix_bytes': p['native_prefix_bytes']} for p in parts],
            'provider_or_task_calls': 0, 'judgments_created': 0,
            'limits': ['Plan reads no case payloads. Stage copies UTF8 payloads without parsing case JSON.',
                'Saved judgment contents are never opened; their hashes come from sealed structural receipts, with current stat checks only.',
                'Publication/root acceptance must precede fresh tasks. Staging is not launch permission.',
                'Bytes/case caps do not establish token capacity, complete model-visible delivery or enforced confinement.',
                'Root must audit actual native full-chunk delivery and exact saved output bytes before accepting each judgment.']}


def stage(parts, inputs, source, destination, record):
    # Validate all 204 original byte pins before any new directory is created.
    for rel, pin in inputs.items():
        raw = exact(child(source, rel), pin['sha256'])
        require(len(raw) == pin['bytes'], 'original_input_bytes_changed')
        raw.decode('utf8', errors='strict')
    destination.mkdir()
    (destination/'inputs').mkdir()
    (destination/'outputs').mkdir()  # Parent only; each reviewer creates its own absent leaf.
    (destination/'launch-prompts').mkdir()
    generated = {}
    for planned in record['contexts']:
        part = parts[planned['original_partition']-1]
        group = next(g for g in part['groups'] if [r['case_id'] for r in g] == planned['case_ids'])
        number = planned['context']
        folder = destination/'inputs'/('reviewer-'+str(number))
        output = destination/'outputs'/('reviewer-'+str(number))
        folder.mkdir()
        index_raw = encoded({**part['index'], 'cases': group})
        pin = sha(index_raw)
        create(folder/'index.json', index_raw)
        for row in group:
            copy_record(part['folder'], folder, row)
        create(folder/'opaque_case_reader.py', part['helper'])
        create(folder/'SEMANTIC-REVIEW-PLAN.md', part['rubric'])
        text = revised_instructions(part, number, group, pin, folder, output)
        create(folder/'instructions.md', text.encode('utf8'))
        initial = literal(STARTUP_SOURCE)
        prompt = (f'Review exactly {len(group)} opaque cases in one fresh recovery context. First call the shell tool with '
                  f'workdir={folder}, max_output_tokens=12000, and EXACT cmd:\n{initial}\n'
                  'Then obey the full instructions and frozen rubric just read, including scope, all-current-case frames, '
                  'create-new sibling outputs and stop/report rules. Use this literal here-string form for every multiline Python program. '
                  'No other reads/delegations/providers. No model override.')
        require(len(prompt.encode('utf8')) <= 1000, 'launch_prompt_too_large')
        create(destination/'launch-prompts'/('reviewer-'+str(number)+'.txt'), prompt.encode('utf8'))
        planned.update({'index_sha256': pin, 'input_directory': str(folder), 'output_directory': str(output),
                        'instructions_sha256': sha(text.encode('utf8')), 'prompt_sha256': sha(prompt.encode('utf8')),
                        'prompt_bytes': len(prompt.encode('utf8'))})
        for path in folder.iterdir():
            raw = path.read_bytes()
            generated[path.relative_to(destination).as_posix()] = {'bytes': len(raw), 'sha256': sha(raw)}
        require(not output.exists(), 'reviewer_output_leaf_must_be_absent')
    for rel, pin in inputs.items():
        raw = exact(child(source, rel), pin['sha256'])
        require(len(raw) == pin['bytes'], 'original_input_postfixity_failed')
    for part in parts:
        require(output_stats(source/'outputs'/('reviewer-'+str(part['number'])), part['records']) == part['output_stats'],
                'original_saved_output_stat_postfixity_failed')
    record.update({'state': 'STAGED_NOT_LAUNCHED_NO_RERATINGS', 'utc': datetime.now(timezone.utc).isoformat(),
                   'all204_original_input_sha256_pins_unchanged': True,
                   'saved_output_filename_size_mtime_unchanged': True,
                   'projected_input_files': generated, 'reviewer_output_leaves_absent': True})
    create(destination/'PRIVATE-recovery-staging.json', encoded(record))
    return {'state': record['state'], 'manifest_sha256': sha(encoded(record)), 'new_contexts': len(record['contexts']),
            'retained_cases': record['retained_cases'], 'unjudged_cases': record['unjudged_cases'],
            'provider_or_task_calls': 0, 'judgments_created': 0}


def self_check():
    checks = []
    def reject(name, action):
        try:
            action()
        except (ValueError, FileExistsError):
            checks.append(name)
        else:
            raise AssertionError('known_bad_accepted:'+name)
    with tempfile.TemporaryDirectory(prefix='fictional-semantic-recovery-') as temporary:
        root = Path(temporary)
        source, target = root/'source', root/'target'
        source.mkdir(); target.mkdir()
        raw = '{"literal":"\u03b1\U0001f9ed e\u0301\\r\\n","false":false,"fraction":1.25,"extra":[null,0]}\r\n'.encode('utf8')
        row = {'case_id': 'CASE-001', 'file': 'CASE-001.json', 'sha256': sha(raw), 'bytes': len(raw)}
        index = {'schema_version': 'oct13-reader-semantic-input-v1', 'instructions': 'Fictional only.', 'cases': [row]}
        require(index_rows(decoded(encoded(index))) == [row], 'normal_index')
        create(source/row['file'], raw)
        copy_record(source, target, row)
        require((target/row['file']).read_bytes() == raw, 'literal_unicode_copy_changed')
        checks.append('normal_strict_index_and_literal_UTF8_raw_copy')
        rows = [{'case_id': 'CASE-'+str(i).zfill(3), 'bytes': 100000} for i in range(1, 11)]
        groups = balanced(rows, ['CASE-001'])
        require([len(g) for g in groups] == [3, 3, 3] and sum(len(g) for g in groups) == 9, 'normal_balancing')
        require(all(sum(r['bytes'] for r in g) <= BYTE_CAP and len(g) <= CASE_CAP for g in groups), 'normal_caps')
        checks.append('normal_retained_complement_and_deterministic_caps')
        reject('duplicate_case_ID_refused', lambda: index_rows({**index, 'cases': [row, row]}))
        reject('path_escape_refused', lambda: child(source, '../CASE-001.json'))
        reject('private_key_alias_refused', lambda: child(source, 'PRIVATE_key.json'))
        reject('wrong_case_hash_refused', lambda: copy_record(source, target, {**row, 'sha256': '0'*64}))
        reject('existing_output_refused', lambda: copy_record(source, target, row))
        reject('unknown_retained_ID_refused', lambda: balanced(rows, ['CASE-999']))
        reject('single_case_over_cap_refused', lambda: balanced([{'case_id': 'CASE-002', 'bytes': BYTE_CAP+1}], []))
        reject('duplicate_JSON_key_refused', lambda: decoded(b'{"x":0,"x":1}'))
        # Native hardlinks need no symlink privilege on the current NTFS route.
        # Reject before opening bytes, even if a link has an allowed-looking name.
        os.link(source/row['file'], source/'allowed-looking.json')
        reject('native_hardlink_refused_before_read', lambda: exact(source/'allowed-looking.json', row['sha256']))
    return {'state': 'PASS_FICTIONAL_BOUNDARY_SELF_CHECK', 'passed': len(checks), 'failed': 0, 'skipped': 0,
            'checks': checks, 'actual_cases_or_judgments_read': 0, 'tasks_or_provider_calls': 0,
            'unexecuted': ['Actual staging, native directory-symlink/junction creation, fresh-task transport, Python3.10 runtime, semantic review.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--self-check', action='store_true')
    mode.add_argument('--plan', action='store_true')
    mode.add_argument('--stage', action='store_true')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--boundary', action='append', nargs=2, metavar=('PARTITION', 'RECEIPT'))
    parser.add_argument('--out', type=Path)
    parser.add_argument('--amendment', type=Path)
    parser.add_argument('--amendment-sha256')
    args = parser.parse_args()
    if args.self_check:
        result = self_check()
    else:
        require(all((args.source, args.boundary, args.out, args.amendment, args.amendment_sha256)), 'missing_required_staging_argument')
        require(len(args.boundary) == 3 and {n for n, p in args.boundary} == {'1', '2', '3'}, 'three_unique_boundaries_required')
        source, destination = args.source.absolute(), args.out.absolute()
        no_links(source); no_links(destination)
        require(source.parent == destination.parent and source != destination, 'new_projection_must_be_sibling')
        require(not destination.exists(), 'new_projection_already_exists_no_retry')
        exact(args.amendment, args.amendment_sha256)
        parts, inputs = inspect(source, {int(n): Path(p) for n, p in args.boundary})
        result = plan_record(parts, source, destination, args.amendment_sha256)
        if args.stage:
            result = stage(parts, inputs, source, destination, result)
    sys.stdout.buffer.write(encoded(result))


if __name__ == '__main__':
    main()
