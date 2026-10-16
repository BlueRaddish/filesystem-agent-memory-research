"""Read-only checks for the scoped pruning extension, not the historical study."""
import ast
from datetime import date
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CATALOG = ROOT / 'sources/pruning-longitudinal-memory.json'
REVIEW = ROOT / 'research/pruning-and-longitudinal-memory.md'
NAVIGATION = ('README.md', 'research/synthesis.md', 'sources/README.md', '.gitattributes')
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('historical_checks', ROOT / 'scripts/check_repository.py')
historical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(historical)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('Nonfinite JSON: ' + value)
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    # Iterative traversal bounds call-stack use for large result/source arrays.
    todo = [result]
    while todo:
        item = todo.pop()
        if isinstance(item, float):
            require(math.isfinite(item), 'Nonfinite JSON number')
        elif isinstance(item, dict):
            todo.extend(item.values())
        elif isinstance(item, list):
            todo.extend(item)
    return result


def strings(value):
    todo = [value]
    while todo:
        item = todo.pop()
        if isinstance(item, str):
            yield item
        elif isinstance(item, dict):
            todo.extend(item.keys())
            todo.extend(item.values())
        elif isinstance(item, list):
            todo.extend(item)


def catalog_check(rows, prose):
    require(isinstance(rows, list) and rows, 'Missing extension catalog')
    identifiers, urls = set(), set()
    for row in rows:
        require(isinstance(row, dict) and all(k in row for k in historical.REQUIRED), 'Missing source fields')
        identifier = row['id']
        require(isinstance(identifier, str) and re.fullmatch(r'PL\d{2}', identifier), 'Invalid extension source ID')
        require(identifier not in identifiers and row['url'] not in urls, 'Duplicate extension ID or primary URL')
        identifiers.add(identifier)
        urls.add(row['url'])
        for key in historical.REQUIRED:
            if key not in ('year', 'topics'):
                require(isinstance(row[key], str) and row[key].strip(), 'Empty source metadata')
        require(type(row['year']) is int and 1900 <= row['year'] <= 2026, 'Invalid source year')
        require(historical.https_url(row['url']), 'Non-HTTPS primary source')
        require(isinstance(row['topics'], list) and row['topics'] and
                all(isinstance(t, str) and t.strip() for t in row['topics']), 'Invalid topics')
        require(date.fromisoformat(row['accessed']) <= date(2026, 10, 16), 'Access after extension cutoff')
    citations = re.findall(r'\[(PL\d{2})\]\((https://[^\s)]+)\)', prose)
    mapping = {row['id']: row['url'] for row in rows}
    require(citations and all(mapping.get(identifier) == url for identifier, url in citations), 'Citation/catalog mismatch')
    require({identifier for identifier, _ in citations} == identifiers, 'Uncited extension source')
    prior = {row['url']: row['id'] for name in historical.CATALOGS
             for row in strict_json((ROOT / 'sources' / name).read_bytes())}
    return {'records': len(rows), 'citations': len(citations),
            'historical_url_overlap': [{'extension': r['id'], 'historical': prior[r['url']]}
                                       for r in rows if r['url'] in prior]}


def check():
    files = sorted(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files += [CATALOG, REVIEW] + [ROOT / name for name in NAVIGATION]
    links = 0
    json_files = 0
    compressed_records = 0
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        require(not path.is_symlink() and path.resolve().is_relative_to(ROOT), 'Linked or escaping file: ' + relative)
        if path.suffix == '.gz':
            for raw_line, value in historical.compressed_jsonl_lines(path):
                text = raw_line + '\n' + '\n'.join(strings(value))
                require(not re.search(r'[A-Za-z0-9_.+-]+@(?:gmail|hotmail|outlook|ucsd)\.', text, re.I),
                        'Personal-account shape: ' + relative)
                compressed_records += 1
            continue
        raw = path.read_bytes()
        text = raw.decode('utf8', errors='ignore')
        if path.suffix == '.json':
            value = strict_json(raw)
            json_files += 1
            text += '\n' + '\n'.join(strings(value))
        require(not any(rule.search(text) for rule in historical.LEAK_PATTERNS), 'Sensitive shape: ' + relative)
        require(not re.search(r'[A-Za-z0-9_.+-]+@(?:gmail|hotmail|outlook|ucsd)\.', text, re.I), 'Personal-account shape: ' + relative)
        if path.suffix == '.py':
            ast.parse(raw, filename=relative, feature_version=(3, 10))
        elif path.suffix == '.png':
            require(raw.startswith(b'\x89PNG\r\n\x1a\n'), 'Invalid PNG: ' + relative)
        elif path.suffix == '.svg':
            tree = ET.fromstring(raw)
            require(tree.tag.endswith('svg') and not any(e.tag.endswith('script') for e in tree.iter()), 'Invalid SVG: ' + relative)
        elif path.suffix == '.md':
            for link in historical.LINK.findall(text):
                parts = urlsplit(link)
                if parts.scheme or link.startswith('#'):
                    continue
                destination = (path.parent / unquote(parts.path)).resolve()
                require(destination.is_relative_to(ROOT) and destination.exists(), 'Broken local link: ' + relative + ' -> ' + link)
                links += 1
        else:
            require(path.suffix in ('.json', '.py', '.png', '.svg') or path.name == '.gitattributes', 'Unexpected file type: ' + relative)
    sources = catalog_check(strict_json(CATALOG.read_bytes()), REVIEW.read_text(encoding='utf8'))
    return {'state': 'SCOPED_RELEASE_CHECK_PASSED', 'files': len(files), 'json_files': json_files,
            'compressed_records': compressed_records,
            'local_links': links, 'source_catalog': sources,
            'scope': 'Extension bytes and navigation; no historical raw-data replay, source reproduction, or semantic truth validation.',
            'python_compatibility': '3.10 syntax, current installed runtime only'}


def self_check():
    require(strict_json('{"a": [1, true, "text"]}') == {'a': [1, True, 'text']}, 'Normal JSON rejected')
    rejected = 0
    for raw in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}'):
        try:
            strict_json(raw)
        except ValueError:
            rejected += 1
    require(rejected == 3, 'Malformed JSON accepted')
    row = dict(id='PL01', title='Fixture', year=2026, url='https://example.org/source', kind='fixture',
               venue_or_status='fixture', topics=['fixture'], evidence_note='fixture', limitation='fixture',
               review_level='fixture', accessed='2026-10-16')
    catalog_check([row], '[PL01](https://example.org/source)')
    for bad, prose in [([row, row], '[PL01](https://example.org/source)'),
                       ([dict(row, accessed='2026-10-17')], '[PL01](https://example.org/source)'),
                       ([row], '[PL01](https://example.org/wrong)')]:
        try:
            catalog_check(bad, prose)
        except ValueError:
            rejected += 1
    require(rejected == 6, 'Invalid catalog/citation accepted')
    return {'state': 'SELF_CHECK_PASSED', 'negative_controls': rejected}


if __name__ == '__main__':
    if sys.argv[1:] == ['--self-check']:
        print(json.dumps(self_check(), indent=2))
    elif not sys.argv[1:]:
        print(json.dumps(check(), indent=2))
    else:
        raise SystemExit('Use no arguments for read-only release checks, or --self-check')
