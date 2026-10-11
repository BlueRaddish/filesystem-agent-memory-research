"""Structural artifact check only; source-derived truth belongs to the evaluator."""
import argparse
import json
from pathlib import Path


def validate(value, answer_keys):
    errors = []
    if not isinstance(value, dict):
        return ['artifact must be an object']
    if value.get('status') not in ('ready', 'hold'):
        errors.append('status must be ready or hold')
    answer = value.get('answer')
    if not isinstance(answer, dict):
        errors.append('answer must be an object')
    else:
        errors.extend('missing answer key: ' + k for k in answer_keys if k not in answer)
    evidence = value.get('evidence')
    if not isinstance(evidence, list) or not all(isinstance(x, str) and x.strip()
                                              for x in evidence):
        errors.append('evidence must be an array of nonempty strings')
    return errors


def selfcheck():
    assert not validate({'status': 'hold', 'answer': {'x': None, 'extra': True},
                         'evidence': ['A07R01:S2']}, ['x'])
    assert validate({'status': 'complete', 'answer': {}, 'evidence': []}, ['x'])
    assert validate({'status': 'ready', 'answer': {'x': 0}, 'evidence': [None]}, ['x'])
    assert validate([], [])
    print('PASS: structural checker self-check')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact', nargs='?', type=Path)
    parser.add_argument('--answer-keys', default='[]', help='JSON array; no expected values')
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    if args.self_check:
        selfcheck()
        return 0
    if not args.artifact:
        parser.error('artifact is required')
    keys = json.loads(args.answer_keys)
    if not isinstance(keys, list) or not all(isinstance(k, str) and k for k in keys):
        parser.error('answer keys must be nonempty strings')
    try:
        value = json.loads(args.artifact.read_text(encoding='utf-8'))
        errors = validate(value, keys)
    except (OSError, ValueError, UnicodeError):
        errors = ['artifact is unreadable or is invalid UTF-8 JSON']
    print(json.dumps({'schema_valid': not errors, 'errors': errors}, ensure_ascii=True))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
