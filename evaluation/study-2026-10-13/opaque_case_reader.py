"""Private proposal: exact indexed UTF-8 case bytes, framed in bounded chunks.

Copy unchanged beside only index.json and indexed CASE-###.json inputs. This is
an input transport helper, not a sandbox, model-capacity check or semantic judge.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

MAX_BYTES = 4096
PREFIX = b'OPAQUE_CASE_READER_V1 '
END = b'\nOPAQUE_CASE_READER_END_V1\n'


def require(value, reason):
    if not value:
        raise ValueError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate_index_key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite_index_number')
    value = json.loads(raw.decode('utf8'), object_pairs_hook=pairs, parse_constant=constant)
    # Index fields are only strings, integers, lists and objects; strict field
    # checks below reject floats including exponent overflow without coercion.
    return value


def safe_file(root, path):
    root = root.resolve()
    require(path.name.casefold() != 'private-key.json', 'private_key_refused')
    resolved = path.resolve()
    # Inspect identities only; never open either known condition-key candidate.
    for key in (root / 'PRIVATE-key.json', root.parent / 'PRIVATE-key.json'):
        require(resolved != key.resolve() and not (path.exists() and key.exists() and os.path.samefile(path, key)), 'private_key_alias_refused')
    require(resolved.is_relative_to(root), 'resolved_path_escape')
    require(path.is_file(), 'indexed_file_missing')
    return path


def load_index(root, expected):
    require(isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected) is not None, 'trusted_index_sha256_required')
    raw = safe_file(root, root / 'index.json').read_bytes()
    require(digest(raw) == expected, 'index_sha256_mismatch')
    index = strict_json(raw)
    require(isinstance(index, dict) and set(index) == {'schema_version', 'cases', 'instructions'}
            and index['schema_version'] == 'oct13-reader-semantic-input-v1'
            and isinstance(index['instructions'], str) and isinstance(index['cases'], list), 'index_shape')
    index['instructions'].encode('utf8', errors='strict')
    entries = {}
    for row in index['cases']:
        require(isinstance(row, dict) and set(row) == {'case_id', 'file', 'sha256', 'bytes'}, 'index_entry_shape')
        identifier = row['case_id']
        require(isinstance(identifier, str) and re.fullmatch('CASE-[0-9]{3}', identifier) is not None, 'case_id_shape')
        require(identifier not in entries, 'duplicate_case_id')
        require(row['file'] == identifier + '.json', 'indexed_basename_refused')
        require(isinstance(row['sha256'], str) and re.fullmatch('[0-9a-f]{64}', row['sha256']) is not None
                and type(row['bytes']) is int and row['bytes'] > 0, 'index_case_pin_shape')
        safe_file(root, root / row['file'])
        entries[identifier] = row
    names = {path.name for path in root.iterdir() if path.suffix.casefold() == '.json'}
    require(names == {'index.json'} | {row['file'] for row in entries.values()}, 'missing_or_extra_json_file')
    return entries


def read_case(root, row):
    # One case is held in RAM so all bytes are verified before emission. If
    # accepted sizes exceed local RAM, use streaming hash + incremental UTF8 scan.
    raw = safe_file(root, root / row['file']).read_bytes()
    require(len(raw) == row['bytes'], 'case_bytes_mismatch')
    require(digest(raw) == row['sha256'], 'case_sha256_mismatch')
    text = raw.decode('utf8', errors='strict')
    # Do not parse/reserialize case JSON or coerce any literal artifact value.
    return raw, text


def chunk_bounds(text, limit):
    require(type(limit) is int and 4 <= limit <= MAX_BYTES, 'chunk_limit_must_be_4_through_4096')
    result, byte_start, cp_start, byte_end = [], 0, 0, 0
    for cp, char in enumerate(text):
        width = len(char.encode('utf8'))
        if byte_end - byte_start + width > limit:
            result.append((byte_start, byte_end, cp_start, cp))
            byte_start, cp_start = byte_end, cp
        byte_end += width
    if byte_end > byte_start:
        result.append((byte_start, byte_end, cp_start, len(text)))
    require(bool(result), 'empty_case_refused')
    return result


def frame(kind, metadata, payload):
    header = {'kind': kind, **metadata, 'payload_bytes': len(payload), 'payload_sha256': digest(payload)}
    raw_header = encoded(header)
    # Lengths, not sentinels inside user data, determine both raw boundaries.
    return PREFIX + str(len(raw_header)).encode('ascii') + b' ' + str(len(payload)).encode('ascii') + b'\n' + raw_header + b'\n' + payload + END


def case_frame(root, expected, identifier, number, limit):
    entries = load_index(root, expected)
    require(isinstance(identifier, str) and identifier in entries, 'case_not_indexed')
    raw, text = read_case(root, entries[identifier])
    bounds = chunk_bounds(text, limit)
    require(type(number) is int and 1 <= number <= len(bounds), 'chunk_number_out_of_range')
    a, b, c, d = bounds[number - 1]
    return frame('case_chunk', {'index_sha256': expected, 'case_id': identifier,
        'case_sha256': digest(raw), 'case_bytes': len(raw), 'case_codepoints': len(text),
        'chunk_number': number, 'chunk_total': len(bounds), 'max_payload_bytes': limit,
        'byte_start': a, 'byte_end': b, 'codepoint_start': c, 'codepoint_end': d,
        'offsets': 'zero-based half-open; UTF8 bytes and Unicode codepoints'}, raw[a:b])


def list_frame(root, expected, page, limit):
    entries = load_index(root, expected)
    rows = []
    for identifier in sorted(entries):
        row = entries[identifier]
        raw, text = read_case(root, row)
        rows.append({'case_id': identifier, 'case_sha256': digest(raw), 'case_bytes': len(raw),
                     'case_codepoints': len(text), 'chunk_total': len(chunk_bounds(text, limit))})
    pages, current = [], []
    for row in rows:
        if current and len(encoded(current + [row])) > MAX_BYTES:
            pages.append(current); current = []
        require(len(encoded([row])) <= MAX_BYTES, 'list_entry_too_large')
        current.append(row)
    pages.append(current)
    require(type(page) is int and 1 <= page <= len(pages), 'list_page_out_of_range')
    start = sum(len(p) for p in pages[:page - 1])
    return frame('case_list', {'index_sha256': expected, 'case_total': len(rows),
        'list_page': page, 'list_page_total': len(pages), 'case_start': start,
        'case_end': start + len(pages[page - 1]), 'chunk_payload_limit': limit}, encoded(pages[page - 1]))


def parse_frame(raw):
    require(raw.startswith(PREFIX), 'frame_prefix_missing')
    line, body = raw[len(PREFIX):].split(b'\n', 1)
    lengths = line.split(b' ')
    require(len(lengths) == 2 and all(part.isdigit() for part in lengths), 'frame_lengths')
    head_bytes, payload_bytes = map(int, lengths)
    header = json.loads(body[:head_bytes].decode('ascii'))
    require(body[head_bytes:head_bytes + 1] == b'\n', 'header_separator_missing')
    payload = body[head_bytes + 1:head_bytes + 1 + payload_bytes]
    require(len(payload) == payload_bytes and body[head_bytes + 1 + payload_bytes:] == END, 'incomplete_or_extra_frame_bytes')
    require(header['payload_bytes'] == payload_bytes and header['payload_sha256'] == digest(payload), 'frame_payload_fixity')
    return header, payload


def self_check():
    passed, skipped, cli = 0, [], []
    def reject(fn, reason):
        nonlocal passed
        try: fn()
        except (ValueError, UnicodeError) as error:
            require(str(error) == reason, 'wrong_fixture_rejection:' + str(error)); passed += 1
        else: raise AssertionError('bad_fixture_accepted:' + reason)
    with tempfile.TemporaryDirectory(prefix='opaque-reader-fictional-') as name:
        parent = Path(name); root = parent / 'projection'; root.mkdir()
        source = root / 'opaque_case_reader.py'; shutil.copyfile(__file__, source)
        raw = ('{"case_id":"CASE-001","artifact":{"flag":false,"integer":0,"fraction":"2/4","ordered":[2,1]},'
               '"text":"青灯😀e\u0301\\nOPAQUE_CASE_READER_END_V1"}\r\n').encode('utf8')
        case_path = root / 'CASE-001.json'; case_path.write_bytes(raw)
        row = {'case_id': 'CASE-001', 'file': case_path.name, 'sha256': digest(raw), 'bytes': len(raw)}
        index = {'schema_version': 'oct13-reader-semantic-input-v1', 'instructions': 'Fictional fixture only.', 'cases': [row]}
        def write_index(value):
            data = encoded(value); (root / 'index.json').write_bytes(data); return digest(data)
        trusted = write_index(index)
        for limit in (5, 7, 11, MAX_BYTES):
            text = raw.decode('utf8'); bounds = chunk_bounds(text, limit)
            reconstructed, last_b, last_c = bytearray(), 0, 0
            for number, bound in enumerate(bounds, 1):
                header, payload = parse_frame(case_frame(root, trusted, 'CASE-001', number, limit))
                a, b, c, d = bound
                require((a, c) == (last_b, last_c) and b - a == len(payload) <= limit
                        and payload.decode('utf8') == text[c:d] and header['chunk_total'] == len(bounds)
                        and header['byte_start'] == a and header['byte_end'] == b
                        and header['codepoint_start'] == c and header['codepoint_end'] == d, 'unicode_chunk_bounds')
                reconstructed.extend(payload); last_b, last_c = b, d
            require(bytes(reconstructed) == raw and (last_b, last_c) == (len(raw), len(text)), 'raw_reconstruction')
            passed += 1
        reject(lambda: load_index(root, '0' * 64), 'index_sha256_mismatch')
        reject(lambda: case_frame(root, trusted, 'CASE-999', 1, 7), 'case_not_indexed')
        reject(lambda: case_frame(root, trusted, 'CASE-001', 999, 7), 'chunk_number_out_of_range')
        reject(lambda: chunk_bounds(raw.decode('utf8'), 4097), 'chunk_limit_must_be_4_through_4096')
        for key, value, reason in [('sha256', '0' * 64, 'case_sha256_mismatch'), ('bytes', len(raw) + 1, 'case_bytes_mismatch'),
                                   ('file', '../CASE-001.json', 'indexed_basename_refused'), ('case_id', '../PRIVATE-key', 'case_id_shape')]:
            bad = json.loads(encoded(index)); bad['cases'][0][key] = value
            pin = write_index(bad)
            reject(lambda pin=pin: list_frame(root, pin, 1, 7), reason)
        duplicate = json.loads(encoded(index)); duplicate['cases'].append(dict(row))
        duplicate_pin = write_index(duplicate)
        reject(lambda: load_index(root, duplicate_pin), 'duplicate_case_id')
        trusted = write_index(index)
        case_path.unlink(); reject(lambda: load_index(root, trusted), 'indexed_file_missing'); case_path.write_bytes(raw)
        extra = root / 'CASE-002.json'; extra.write_bytes(raw)
        reject(lambda: load_index(root, trusted), 'missing_or_extra_json_file'); extra.unlink()
        outside = parent / 'outside.json'; outside.write_bytes(b'{}')
        reject(lambda: safe_file(root, outside), 'resolved_path_escape')
        key = parent / 'PRIVATE-key.json'; key.write_bytes(b'{"fictional":true}')
        reject(lambda: safe_file(root, key), 'private_key_refused')
        for target in (root / 'index.json', case_path):
            retained = target.read_bytes(); target.unlink()
            try: os.link(key, target)
            except OSError:
                skipped.append('Native hard-link fixture unavailable: ' + target.name)
            else:
                reject(lambda target=target: safe_file(root, target), 'private_key_alias_refused'); target.unlink()
            target.write_bytes(retained)
        cli_bounds = chunk_bounds(raw.decode('utf8'), 7)
        unicode_number = next(n for n, (a, b, c, d) in enumerate(cli_bounds, 1) if '😀' in raw[a:b].decode('utf8'))
        unicode_payload = raw[cli_bounds[unicode_number - 1][0]:cli_bounds[unicode_number - 1][1]]
        for label, args, expected_exit in [
            ('normal-list', ['--list'], 0),
            ('normal-chunk', ['--chunk', 'CASE-001', '--chunk-number', str(unicode_number)], 0),
            ('bad-case-id', ['--chunk', 'CASE-999', '--chunk-number', '1'], 1),
            ('bad-index-hash', ['--list'], 1)]:
            pin = '0' * 64 if label == 'bad-index-hash' else trusted
            argv = [sys.executable, '-B', '-X', 'utf8', str(source), '--index-sha256', pin, '--max-chunk-bytes', '7', *args]
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=30)
            require(result.returncode == expected_exit, 'CLI_exit:' + label)
            if expected_exit == 0:
                header, payload = parse_frame(result.stdout)
                require(result.stderr == b'' and header['index_sha256'] == trusted, 'normal_CLI_frame')
                if label == 'normal-list': require(json.loads(payload)[0]['case_id'] == 'CASE-001', 'normal_CLI_list')
                else: require(payload == unicode_payload and '😀' in payload.decode('utf8'), 'normal_CLI_raw_payload')
            else:
                require(result.stdout == b'' and json.loads(result.stderr)['state'] == 'OPAQUE_CASE_READER_REFUSED', 'bad_CLI_refusal')
            cli.append({'name': label, 'argv': argv, 'exit_code': result.returncode,
                        'stdout_sha256': digest(result.stdout), 'stderr_sha256': digest(result.stderr),
                        'stdout_hex': result.stdout.hex(), 'stderr_hex': result.stderr.hex()})
            passed += 1
    sys.stdout.buffer.write(encoded({'state': 'PASS_FICTIONAL_OPAQUE_READER_SELF_CHECK', 'passed': passed, 'failed': 0,
        'skipped': len(skipped), 'skip_reasons': skipped, 'cli_checks': cli,
        'actual_cases_results_gold_read': False, 'model_provider_calls': 0}) + b'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--list', action='store_true'); mode.add_argument('--chunk'); mode.add_argument('--self-check', action='store_true')
    parser.add_argument('--index-sha256'); parser.add_argument('--chunk-number', type=int)
    parser.add_argument('--list-page', type=int, default=1)
    parser.add_argument('--max-chunk-bytes', type=int, default=MAX_BYTES)
    args = parser.parse_args()
    if args.self_check:
        self_check(); return
    require(4 <= args.max_chunk_bytes <= MAX_BYTES, 'chunk_limit_must_be_4_through_4096')
    root = Path(__file__).resolve().parent
    if args.list: raw = list_frame(root, args.index_sha256, args.list_page, args.max_chunk_bytes)
    else: raw = case_frame(root, args.index_sha256, args.chunk, args.chunk_number, args.max_chunk_bytes)
    sys.stdout.buffer.write(raw)


if __name__ == '__main__':
    try: main()
    except (ValueError, KeyError, TypeError, UnicodeError, OSError) as error:
        sys.stderr.buffer.write(encoded({'state': 'OPAQUE_CASE_READER_REFUSED', 'error': type(error).__name__,
            'reason': str(error) if isinstance(error, ValueError) else 'Malformed or unavailable indexed input.'}) + b'\n')
        raise SystemExit(1)