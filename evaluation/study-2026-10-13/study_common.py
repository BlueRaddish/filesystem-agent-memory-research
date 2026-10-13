"""Shared boundaries for the independent October 13 fictional challenge study."""
import hashlib
import json
from pathlib import Path
import re
import unicodedata

HERE = Path(__file__).resolve().parent
OBSERVABLE_FIELDS = ('id', 'kind', 'revision', 'authored_at', 'title', 'scope', 'body',
    'links', 'supersedes', 'incorporates', 'path', 'valid_from', 'valid_to', 'time_scope', 'category')


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode('utf8')).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf8', newline='\n')
    temporary.replace(path)


def bank():
    return json.loads((HERE / 'challenge-bank.json').read_text(encoding='utf8'))


def documents(families):
    docs = {}
    for family in families:
        name = re.sub(r'[^a-z0-9]+', '-', unicodedata.normalize('NFKD', family['name']).encode('ascii', 'ignore').decode().lower()).strip('-')
        branch = name or 'workstream'
        for record in family['records']:
            assert record['id'] not in docs
            # Gold/task fields never cross the retrieval interface. Group identity
            # is retained only for collection sampling and analysis, not features.
            doc = {key: record[key] for key in OBSERVABLE_FIELDS if key in record}
            assert doc['body'].strip(), 'Empty original/derived bodies are excluded by the bank contract'
            doc.update(family_id=family['id'], branch=branch,
                       aliases=[family['name'], *family['aliases']],
                       path=record.get('path', '1-Projects/' + branch + '/records/' + record['id'] + '.md'))
            docs[doc['id']] = doc
    return docs


def collection(all_docs, family_id, size):
    if size == 'all':
        return dict(all_docs)
    own = [d for d in all_docs.values() if d['family_id'] == family_id]
    other = [d for d in all_docs.values() if d['family_id'] != family_id]
    other.sort(key=lambda d: digest(family_id + ':noise-oct13-v1:' + d['id']))
    selected = own + other[:int(size) - len(own)]
    assert len(selected) == int(size)
    return {d['id']: d for d in sorted(selected, key=lambda d: d['id'])}


def merge_intervals(intervals):
    output = []
    for start, end in sorted(intervals):
        if output and start <= output[-1][1]:
            output[-1][1] = max(end, output[-1][1])
        else:
            output.append([start, end])
    return output


def support_metrics(task, observations, docs):
    intervals = {}
    whole = set()
    for item in observations:
        record = docs[item['id']]
        start, end = item['start'], item['end']
        assert type(start) is int and type(end) is int and 0 <= start < end <= len(record['body'])
        assert item['text'] == record['body'][start:end], 'Source-exact boundary failed'
        assert item['source_hash'] == digest(record['body'])
        intervals.setdefault(item['id'], []).append((start, end))
        if start == 0 and end == len(record['body']):
            whole.add(item['id'])
    intervals = {key: merge_intervals(value) for key, value in intervals.items()}
    alternatives = task['evidence_spans']
    covered = []
    for spans in alternatives:
        flags = [any(a <= span['start'] and b >= span['end'] for a, b in intervals.get(span['id'], [])) for span in spans]
        covered.append({'complete': all(flags), 'covered_spans': sum(flags), 'declared_spans': len(flags)})
    return {'declared_span_bundle_recovered': any(x['complete'] for x in covered),
            'declared_whole_bundle_recovered': any(set(ids) <= whole for ids in task['evidence_sets']),
            'best_declared_span_fraction': max(x['covered_spans'] / x['declared_spans'] for x in covered),
            'observed_original_ids': sorted(set(intervals) & {i for i, d in docs.items() if d['kind'] == 'source'})}


def self_check():
    docs = {'D': {'body': '青灯: a rule; then a condition.', 'kind': 'source'}}
    body = docs['D']['body']
    task = {'evidence_sets': [['D']], 'evidence_spans': [[{'id': 'D', 'start': 0, 'end': 11}]]}
    obs = [{'id': 'D', 'start': 0, 'end': 5, 'text': body[:5], 'source_hash': digest(body)},
           {'id': 'D', 'start': 5, 'end': 11, 'text': body[5:11], 'source_hash': digest(body)}]
    result = support_metrics(task, obs, docs)
    assert result['declared_span_bundle_recovered'] and not result['declared_whole_bundle_recovered']
    obs[1]['start'] = 6
    obs[1]['text'] = body[6:11]
    assert not support_metrics(task, obs, docs)['declared_span_bundle_recovered']
    assert merge_intervals([(2, 4), (0, 2), (6, 7)]) == [[0, 4], [6, 7]]
    print('study_common self-check passed')


if __name__ == '__main__':
    self_check()
