"""Import exact public JSON into a Gemini-authored HTML template, without model retyping."""
import argparse
import json
from pathlib import Path

SLOT = 'const STUDY_DATA = {"__DATA_INJECTION_SLOT__":true};'


def inject(template, data):
    if template.count(SLOT) != 1:
        raise ValueError('Expected exactly one Gemini-authored data assignment slot')
    if not isinstance(data, dict):
        raise ValueError('Viewer data must be an object')
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    # JSON remains exact after decoding, and source strings cannot close a script.
    for character in ('&', '<', '>', '\u2028', '\u2029'):
        payload = payload.replace(character, '\\u' + format(ord(character), '04x'))
    assert json.loads(payload) == data
    return template.replace(SLOT, 'const STUDY_DATA = ' + payload + ';')


def selfcheck():
    template = '<script>' + SLOT + '</script>'
    data = {'label': '\u9752\u706f', 'value': '</script>&\u2028'}
    output = inject(template, data)
    assert output.count('</script>') == 1 and '\\u003c/script\\u003e' in output
    for value in (template.replace(SLOT, ''), template + SLOT):
        try:
            inject(value, data)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing or repeated slot accepted')
    print('Viewer import check passed: one slot, exact JSON, safe script embedding')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--template')
    parser.add_argument('--data')
    parser.add_argument('--output')
    args = parser.parse_args()
    selfcheck()
    if not args.self_check:
        if not all((args.template, args.data, args.output)):
            parser.error('--template, --data and --output are required')
        result = inject(Path(args.template).read_text(encoding='utf8'),
                        json.loads(Path(args.data).read_text(encoding='utf8')))
        destination = Path(args.output)
        staged = destination.with_suffix('.tmp')
        staged.write_text(result, encoding='utf8', newline='\n')
        staged.replace(destination)
        print('Imported exact data into Gemini-authored viewer')
