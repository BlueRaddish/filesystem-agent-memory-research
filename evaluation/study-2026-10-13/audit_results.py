"""Independent source-only audit of the frozen October 13 execution.

No model is loaded, no provider is called, and no scored result is replaced.
The default audit independently rebuilds every packet from published intervals,
recomputes support gates, and checks the private execution records when supplied.
--repack-all additionally replays the frozen packing policy using retained top32
IDs. Full learned rankings cannot be independently recomputed from top64/hash
receipts without inference; this limit is retained in the public audit result.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile
import time
import unicodedata

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASELINE = 'c21fcce413317eff50e16fd9f8b1a0d8f7eabc5a'
PROSPECTIVE_COMMIT = 'b920aa0353aef5bd8e9521259a348fcbd6a08980'
OBSERVABLE = ('id', 'kind', 'revision', 'authored_at', 'title', 'scope', 'body',
    'links', 'supersedes', 'incorporates', 'path', 'valid_from', 'valid_to', 'time_scope', 'category')
METHODS = ('body_bm25', 'search_bm25', 'word_tfidf', 'char_tfidf', 'field_bm25',
    'rrf_word_char', 'entity_rrf', 'clause_rrf', 'sentence_maxsim', 'coverage_mmr',
    'scope_temporal', 'graph_diffusion', 'pseudo_feedback', 'dense_body', 'dense_search',
    'dense_windows', 'dense_window_rrf', 'minilm_body', 'mixedbread_body',
    'minilm_passages', 'shallow_tree')
PACKERS = ('whole_record', 'ranked_body', 'sentence_neighbors', 'closure_passages',
    'original_first', 'diversity_passages', 'coverage_bundles', 'authority_pairs')
EXTENDED = {'body_bm25', 'entity_rrf', 'dense_window_rrf', 'minilm_passages'}
BUDGETS = (4096, 8192, 16384)
BYTE_CAP, RESERVE = 32768, 512
SHA = re.compile(r'^[0-9a-f]{64}$')
SENSITIVE = re.compile(rb'(?i)(?:C:[\\/]+Users[\\/]|/[U]sers/|/[h]ome/|'
    rb'[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com)[A-Za-z0-9.-]+\.[A-Za-z]{2,}|'
    rb'(?:api[_-]?key|access[_-]?token|refresh[_-]?token|authorization)\s*[:=]\s*[\"\']?[A-Za-z0-9_./+-]{20,}|'
    rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def pretty(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)


def checker_stdout(value, line_ending):
    require(line_ending in ('\n', '\r\n'), 'Unknown checker stdout line ending')
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + line_ending).encode('utf8')


def checker_line_ending(receipt):
    # Bind the execution's retained bytes, rather than the auditor host's newline.
    for ending in ('\n', '\r\n'):
        if sha(checker_stdout(receipt['check'], ending)) == receipt['checker_stdout_sha256']:
            return ending
    raise ValueError('Recorded checker stdout is not frozen LF/CRLF JSON')


def write_receipt(value, task, docs, recorded):
    """Bind every written artifact and checker receipt without retrying failures."""
    from artifact_contract import validate
    raw = (pretty(value) + '\n').encode('utf8')
    require(len(raw) <= 20000 and isinstance(recorded, dict), 'Written artifact/receipt unavailable')
    code = recorded.get('checker_exit')
    if code is None:
        checked = recorded.get('check')
        errors = ('checker_output_invalid', 'checker_timeout', 'checker_execution_error')
        require(isinstance(checked, dict) and set(checked) == {'schema_valid', 'errors'}
            and checked['schema_valid'] is False and checked['errors'] in [[error] for error in errors],
            'Unknown retained checker failure')
        stdout = b''  # The frozen failure branches discard captured streams.
    else:
        require(type(code) is int and code in (0, 1), 'Unknown retained checker exit')
        checked = validate(value, task, docs)
        code = 0 if checked['schema_valid'] else 1
        stdout = checker_stdout(checked, checker_line_ending(recorded))
    expected = {'written': 'artifacts/result.json', 'artifact_sha256': sha(raw), 'artifact_bytes': len(raw),
        'check': checked, 'checker_exit': code, 'checker_stdout_sha256': sha(stdout), 'checker_stderr_sha256': sha(b'')}
    same(recorded, expected, 'Independent write checker receipt differs')
    return expected


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode('utf8')).hexdigest()


def file_sha(path):
    state = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            state.update(block)
    return state.hexdigest()


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def finite_float(value):
        result = float(value)
        require(math.isfinite(result), 'Nonfinite JSON number')
        return result
    def valid_unicode(value):
        if isinstance(value, str):
            value.encode('utf8')
        elif isinstance(value, dict):
            for key, item in value.items():
                valid_unicode(key)
                valid_unicode(item)
        elif isinstance(value, list):
            for item in value:
                valid_unicode(item)
    value = json.loads(Path(path).read_text(encoding='utf8'), object_pairs_hook=pairs,
        parse_float=finite_float,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    valid_unicode(value)
    return value


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty(value) + '\n', encoding='utf8', newline='\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same(left, right, message):
    # JSON spelling distinguishes bool from integer recursively.
    require(compact(left) == compact(right), message)


def cells(method):
    return [(p, b) for p in (PACKERS if method in EXTENDED else ('whole_record', 'closure_passages')) for b in BUDGETS]


def project_documents(families):
    result = {}
    for family in families:
        slug = re.sub(r'[^a-z0-9]+', '-', unicodedata.normalize('NFKD', family['name']).encode('ascii', 'ignore').decode().lower()).strip('-') or 'workstream'
        for source in family['records']:
            require(source['id'] not in result, 'Duplicate bank ID')
            doc = {key: source[key] for key in OBSERVABLE if key in source}
            doc.update(family_id=family['id'], branch=slug, aliases=[family['name'], *family['aliases']],
                path=source.get('path', '1-Projects/' + slug + '/records/' + source['id'] + '.md'))
            result[doc['id']] = doc
    return result


def collection(docs, family, size):
    if size == 'all':
        return dict(docs)
    own = [d for d in docs.values() if d['family_id'] == family]
    noise = sorted((d for d in docs.values() if d['family_id'] != family), key=lambda d: sha(family + ':noise-oct13-v1:' + d['id']))
    chosen = own + noise[:144 - len(own)]
    require(len(chosen) == 144, 'Wrong local corpus size')
    return {d['id']: d for d in sorted(chosen, key=lambda d: d['id'])}


def observations(items, docs):
    result = []
    for item in items:
        require(item['id'] in docs, 'Observation outside collection')
        doc = docs[item['id']]
        a, b = item['start'], item['end']
        require(type(a) is int and type(b) is int and 0 <= a < b <= len(doc['body']), 'Invalid source interval')
        require(item['source_hash'] == sha(doc['body']), 'Source body hash mismatch')
        whole = a == 0 and b == len(doc['body'])
        if 'whole' in item:
            require(type(item['whole']) is bool and item['whole'] == whole, 'Whole-body marker mismatch')
        if 'text' in item:
            require(item['text'] == doc['body'][a:b], 'Source slice mismatch')
        result.append({**item, 'text': doc['body'][a:b], 'whole': whole})
    return result


def packet_text(items, docs, method):
    pieces = []
    for item in observations(items, docs):
        doc = docs[item['id']]
        header = {'id': doc['id'], 'chars': [item['start'], item['end']], 'kind': doc['kind'], 'revision': doc['revision']}
        if method == 'whole_record':
            header.update({k: doc.get(k) for k in ('title', 'scope', 'aliases', 'authored_at', 'links', 'supersedes', 'incorporates')})
            if 'time_scope' in doc:
                header['time_scope'] = doc['time_scope']
        pieces.append('SOURCE ' + compact(header) + '\n' + item['text'])
    return '\n\n'.join(pieces)


def support(task, items, docs):
    spans, whole = {}, set()
    for item in observations(items, docs):
        spans.setdefault(item['id'], []).append((item['start'], item['end']))
        if item['whole']:
            whole.add(item['id'])
    united = {}
    for identifier, ranges in spans.items():
        merged = []
        for start, end in sorted(ranges):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(end, merged[-1][1])
            else:
                merged.append([start, end])
        united[identifier] = merged
    flags = [[any(a <= s['start'] and b >= s['end'] for a, b in united.get(s['id'], [])) for s in alt] for alt in task['evidence_spans']]
    return {'declared_span_bundle_recovered': any(all(alt) for alt in flags),
        'declared_whole_bundle_recovered': any(set(ids) <= whole for ids in task['evidence_sets']),
        'best_declared_span_fraction': max(sum(alt) / len(alt) for alt in flags),
        'observed_original_ids': sorted(i for i in spans if docs[i]['kind'] == 'source')}


def candidate(task, top):
    result = {}
    for k in (8, 16, 32, 64):
        observed = set(top[:k])
        result[str(k)] = {'declared_original_bundle_in_candidates': any(set(alt) <= observed for alt in task['evidence_sets']),
            'best_declared_span_id_fraction': max(sum(s['id'] in observed for s in alt) / len(alt) for alt in task['evidence_spans'])}
    return result


def collection_hash(docs):
    projected = {}
    for i in sorted(docs):
        doc = docs[i]
        row = {'id': i, 'body': doc['body'], 'revision': doc.get('revision')}
        for key in ('title', 'scope', 'effective_from', 'effective_to'):
            alias = {'effective_from': 'valid_from', 'effective_to': 'valid_to'}.get(key)
            row[key] = doc.get(key, doc.get(alias, '') if alias else '') or ''
        for key in ('aliases', 'links', 'supersedes'):
            row[key] = list(doc.get(key, []))
        row['incorporates'] = [item['id'] for item in doc.get('incorporates', [])]
        projected[i] = row
    return sha(compact(projected))


def view_states(docs):
    reverse = {i: [] for i in docs}
    for i in sorted(docs):
        for old in docs[i]['supersedes']:
            if old in reverse:
                reverse[old].append(i)
    def compatible(a, b):
        if a['scope'] != b['scope'] and 'all' not in (a['scope'], b['scope']):
            return False
        left, right = a.get('time_scope'), b.get('time_scope')
        return left is None and right is None or left is not None and right is not None and (left == right or isinstance(left, str) and isinstance(right, str) and 'all' in (left, right))
    states = {}
    for i, doc in docs.items():
        if doc['kind'] != 'derived':
            continue
        ledger = {source['id']: source['revision'] for source in doc['incorporates']}
        invalid, stale, missing = not ledger or len(ledger) != len(doc['incorporates']), False, []
        for source, revision in ledger.items():
            if source not in docs:
                missing.append(source)
                invalid = True
                continue
            stale |= docs[source]['kind'] != 'source' or docs[source]['revision'] != revision
            pending, visited = list(reverse[source]), set()
            while pending:
                new = pending.pop(0)
                if new in visited:
                    continue
                visited.add(new)
                if docs[new]['kind'] == 'source' and compatible(doc, docs[new]) and ledger.get(new) != docs[new]['revision']:
                    stale = True
                pending.extend(reverse[new])
        states[i] = {'state': 'unverifiable' if invalid else 'stale' if stale else 'declared_current', 'missing_declared_sources': sorted(missing)}
    return states


def answer_agreement(value, task):
    """Independent typed endpoint: explicit scalar kinds plus recursive JSON equality."""
    def typed(item, rule):
        kinds = rule['type'] if isinstance(rule['type'], list) else [rule['type']]
        kind = 'null' if item is None else 'boolean' if type(item) is bool else 'integer' if type(item) is int else 'string' if isinstance(item, str) else 'array' if isinstance(item, list) else 'unsupported'
        if kind not in kinds:
            return False
        if 'enum' in rule and not any(compact(item) == compact(allowed) for allowed in rule['enum']):
            return False
        if kind == 'array':
            if not all(typed(entry, rule['items']) for entry in item):
                return False
            if rule.get('comparison') == 'unordered_unique' and len({compact(entry) for entry in item}) != len(item):
                return False
        return True
    def normalize(item, rule):
        if isinstance(item, list):
            result = [normalize(entry, rule['items']) for entry in item]
            return sorted(result, key=lambda entry: json.dumps(entry, ensure_ascii=False, sort_keys=True)) if rule.get('comparison') == 'unordered_unique' else result
        if isinstance(item, str) and rule.get('normalization', 'none') in ('NFC', 'NFKC'):
            return unicodedata.normalize(rule['normalization'], item)
        return item
    if not isinstance(value, dict) or not isinstance(value.get('answer'), dict):
        return {'typed_answer_status_match': False, 'matching_fields': [], 'mismatching_fields': list(task['answer_keys'])}
    matches, misses = [], []
    for key in task['answer_keys']:
        expected, actual = task['expected']['answer'][key], value['answer'].get(key)
        rule = task['answer_contract']['fields'][key]
        unresolved = task['answer_contract'].get('unresolved_policy', {})
        conditional = actual is None and value.get('status') == 'hold' and key != unresolved.get('reason_field', 'hold_reason') and unresolved.get('allow_null_when_status_hold')
        correct = key in value['answer'] and (typed(actual, rule) or conditional) and type(actual) is type(expected) and compact(normalize(actual, rule)) == compact(normalize(expected, rule))
        (matches if correct else misses).append(key)
    status = value.get('status') == task['expected']['status']
    return {'typed_answer_status_match': not misses and status, 'status_match': status, 'matching_fields': matches, 'mismatching_fields': misses}


def rows_in(path):
    """Strict JSON rows from one bounded public shard, never the whole study."""
    # The writer targets 40 MiB and the protocol rejects shards >=50 MiB. This
    # bounds serialized input retained at once; decoded Python objects use more
    # memory. If that ceiling is too large, use a strict streaming parser rather
    # than relaxing JSON grammar or silently skipping envelope validation.
    path = Path(path)
    require(path.stat().st_size < 50 * 1024 * 1024, 'Oversized JSON shard')
    envelope = load(path)
    require(isinstance(envelope, dict) and isinstance(envelope.get('rows'), list), 'Missing rows array')
    for value in envelope['rows']:
        require(isinstance(value, dict), 'Result row is not an object')
        yield value


def freeze_inputs(expected):
    require(SHA.fullmatch(expected or '') and file_sha(HERE / 'freeze.json') == expected, 'Wrong freeze digest')
    value = load(HERE / 'freeze.json')
    for relative, digest in value['files'].items():
        path = (HERE / relative).resolve()
        require(path.is_relative_to(REPO), 'Freeze path escapes repository')
        digest = digest['sha256'] if isinstance(digest, dict) else digest
        require(file_sha(path) == digest, 'Frozen input changed: ' + relative)
    return value


def expected_schedule(families):
    groups = {}
    for family in families:
        if family['split'] == 'confirmation':
            groups.setdefault(family['template_family'], []).append(family)
    jobs = []
    arms = [('body_whole', 'body_bm25', 'whole_record'), ('search_body', 'search_bm25', 'ranked_body'),
        ('entity_closure', 'entity_rrf', 'closure_passages'), ('dense_closure', 'dense_window_rrf', 'closure_passages'),
        ('minilm_closure', 'minilm_passages', 'closure_passages')]
    for group in sorted(groups):
        chosen = sorted(groups[group], key=lambda f: sha(f['id'] + ':reader-oct13-v1'))[:2]
        start = int(sha(group + ':reader-task-oct13-v1')[:8], 16) % 3
        for number, family in enumerate(chosen):
            task = family['tasks'][(start + number) % 3]
            base = {'family_id': family['id'], 'template_family': group, 'task_id': task['id'], 'collection_size': 144}
            jobs.extend({**base, 'block': 'direct', 'arm': a, 'ranker': r, 'packer': p, 'budget': 8192} for a, r, p in arms)
            jobs.append({**base, 'block': 'oracle', 'arm': 'oracle_originals', 'budget': None})
            if number == 0:
                for entry in (False, True):
                    for helper in (False, True):
                        jobs.append({**base, 'block': 'discovery', 'arm': 'entry' + str(int(entry)) + '_helper' + str(int(helper)),
                            'entrypoint': entry, 'helper': helper, 'budget': BYTE_CAP, 'rounds': 8, 'actions': 32})
    random.Random(1013).shuffle(jobs)
    for number, job in enumerate(jobs, 1):
        job['trial_id'] = 'X' + str(number).zfill(3)
    return jobs


class Auditor:
    def __init__(self, freeze_sha, work=None, cache=None, repack=False):
        self.freeze_sha, self.freeze = freeze_sha, freeze_inputs(freeze_sha)
        # Build the runner's frozen identity once. Rehashing all frozen files for
        # every checkpoint would add redundant I/O without new evidence.
        from benchmark_runner import verify_freeze
        self.runner_freeze = verify_freeze(freeze_sha)
        self.work, self.cache, self.repack = work, cache, repack
        if work:
            require(not work.resolve().is_relative_to(REPO), 'Private work is inside repository')
        if cache:
            require(not cache.resolve().is_relative_to(REPO), 'Private cache is inside repository')
        self.families = load(HERE / 'challenge-bank.json')['families']
        self.by_family = {f['id']: f for f in self.families}
        self.tasks = {(f['id'], t['id']): t for f in self.families for t in f['tasks']}
        self.docs = project_documents(self.families)
        self.counts = Counter()
        self.files = {}
        self.checkpoint_cache = None
        self.current_collection = None
        self.current_family = None
        self.current_hash = None
        self.current_states = None
        self.rankings = {}

    def checkpoint(self, family, task, size):
        key = sha(family + '\n' + task + '\n' + str(size))
        if self.checkpoint_cache is None or self.checkpoint_cache[0] != key:
            value = load(self.work / 'checkpoints' / (key + '.json'))
            from benchmark_runner import query_fingerprint
            fingerprint = query_fingerprint(self.runner_freeze, family, task, self.tasks[family, task]['query'], size)
            require(value['fingerprint'] == fingerprint and value['freeze_sha256'] == self.freeze_sha and value['state'] == 'complete_query', 'Private query checkpoint identity changed')
            self.checkpoint_cache = (key, value)
        return self.checkpoint_cache[1]

    def corpus(self, family, size):
        key = (family, size)
        if self.current_family != key:
            self.current_collection = collection(self.docs, family, size)
            self.current_family = key
            self.current_hash = collection_hash(self.current_collection)
            self.current_states = view_states(self.current_collection)
        return self.current_collection

    def grid(self):
        manifest = load(HERE / 'grid-manifest.json')
        require(manifest['state'] == 'complete_grid_collection' and manifest['freeze_sha256'] == self.freeze_sha, 'Incomplete/different grid')
        same(manifest['rankers'], list(METHODS), 'Ranker list differs')
        rank_seen, packet_seen = set(), set()
        shard_names = [s['file'] for s in manifest['shards']]
        require(len(set(shard_names)) == len(shard_names), 'Duplicate shard file')
        actual_names = {p.relative_to(HERE).as_posix() for p in (HERE / 'results').glob('*.json')}
        require(actual_names == set(shard_names), 'Unlisted/missing public shard')
        # Rankings precede packets per template, retaining just that small group.
        last_group = None
        for shard in manifest['shards']:
            path = HERE / shard['file']
            require(path.resolve().is_relative_to(HERE / 'results'), 'Shard path escapes results')
            require(path.stat().st_size == shard['bytes'] < 50 * 1024 * 1024 and file_sha(path) == shard['sha256'], 'Shard bytes changed')
            self.files[shard['file']] = shard['sha256']
            count = 0
            for row in rows_in(path):
                count += 1
                group = row['template_family']
                if last_group != group:
                    self.rankings = {}
                    last_group = group
                family, task_id, size, method = row['family_id'], row['task_id'], row['size'], row['ranker']
                require((family, task_id) in self.tasks and method in METHODS and size in ('144', 'all'), 'Unknown grid cell')
                require(self.by_family[family]['template_family'] == group and self.by_family[family]['split'] == row['split'], 'Grid analysis metadata differs')
                task, docs = self.tasks[family, task_id], self.corpus(family, size)
                is_rank = 'packer' not in row
                key = (family, task_id, size, method) if is_rank else (family, task_id, size, method, row['packer'], row['budget'])
                seen = rank_seen if is_rank else packet_seen
                require(key not in seen, 'Duplicate grid cell')
                seen.add(key)
                if self.work:
                    saved = self.checkpoint(family, task_id, size)
                    saved = saved['rankings'][method] if is_rank else saved['packets'][method + '|' + row['packer'] + '|' + str(row['budget'])]
                    same(saved, row, 'Public/private grid checkpoint differs')
                self.counts['rankings' if is_rank else 'packets'] += 1
                if is_rank:
                    self.rankings[key] = row
                    if row['state'] != 'complete':
                        self.counts['ranking_faults'] += 1
                        continue
                    require(len(row['top64']) == 64 and len(set(row['top64'])) == 64 and set(row['top64']) <= set(docs), 'Ranking top64 is not a unique in-corpus prefix')
                    require(row['documents'] == len(docs) and SHA.fullmatch(row['full_ranking_sha256']), 'Ranking census/hash invalid')
                    require(row['collection_sha256'] == self.current_hash == row['execution']['collection_sha256'], 'Retained retrieval collection hash differs')
                    require(row['execution']['ranking_sha256'] == row['full_ranking_sha256'], 'Full ranking receipt binding differs')
                    same(candidate(task, row['top64']), row['candidate_recovery'], 'Candidate endpoint differs')
                    continue
                require((row['packer'], row['budget']) in cells(method), 'Unscheduled packer/budget')
                rank = self.rankings[family, task_id, size, method]
                if row['state'] != 'complete':
                    self.counts['packet_faults'] += 1
                    require(SHA.fullmatch(row['error_message_sha256']), 'Fault lacks safe error hash')
                    continue
                require(rank['state'] == 'complete', 'Successful pack after ranking fault')
                text = packet_text(row['observations'], docs, row['packer'])
                require(len(text.encode('utf8')) == row['bytes'] <= row['budget'] and sha(text) == row['packet_sha256'], 'Independent packet byte/hash reconstruction differs')
                same(list(dict.fromkeys(o['id'] for o in row['observations'])), row['selected_ids'], 'Selected ID order differs')
                require(row['collection_documents'] == len(docs) and SHA.fullmatch(row['packing_receipt_sha256']), 'Packet collection/receipt invalid')
                metrics = support(task, row['observations'], docs)
                same(metrics, {k: row[k] for k in metrics}, 'Independent support endpoint differs')
                selected_states = {i: self.current_states[i] for i in row['selected_ids'] if i in self.current_states}
                same(selected_states, row['selected_derived_states'], 'Selected derived ledger state differs')
                require(row['selected_stale_views'] == sum(state['state'] == 'stale' for state in selected_states.values()) and row['selected_unverifiable_views'] == sum(state['state'] == 'unverifiable' for state in selected_states.values()), 'Derived view state totals differ')
                self.counts['independently_rebuilt_packets'] += 1
                if self.repack:
                    from packing_lab import pack
                    recreated = pack(docs, task['query'], rank['top64'][:32], row['budget'], row['packer'])
                    require(recreated['packet'] == text and sha(compact(recreated['receipt'])) == row['packing_receipt_sha256'], 'Frozen packing replay differs')
                    self.counts['frozen_packer_replays'] += 1
            require(count == shard['rows'], 'Shard row census differs')
        expected_ranks = {(f['id'], t['id'], s, m) for f in self.families for t in f['tasks'] for s in ('144', 'all') for m in METHODS}
        expected_packets = {(*key, p, b) for key in expected_ranks for p, b in cells(key[-1])}
        require(rank_seen == expected_ranks and packet_seen == expected_packets, 'Grid full factorial census differs')
        for key in ('rankings', 'packets', 'ranking_faults', 'packet_faults'):
            require(self.counts[key] == manifest['counts'].get(key, 0), 'Manifest count differs: ' + key)
        require(len(rank_seen) == 12096 and len(packet_seen) == 114048, 'Planned grid scale differs')
        if self.work:
            expected_checkpoints = {sha(f['id'] + '\n' + t['id'] + '\n' + size) + '.json' for f in self.families for t in f['tasks'] for size in ('144', 'all')}
            require({p.name for p in (self.work / 'checkpoints').glob('*.json')} == expected_checkpoints, 'Private checkpoint census differs')
            covered = []
            prepared = load(HERE / 'preparation.json')
            historical = load(HERE.parent / 'study-2026-10-11/model-execution.json')['models']
            for worker in manifest['workers']:
                path = self.work / ('worker-' + str(worker['worker']) + '-receipt.json')
                require(file_sha(path) == worker['receipt_sha256'], 'Worker receipt binding changed')
                receipt = load(path)
                require(receipt['state'] == 'complete_partition' and receipt['freeze_sha256'] == self.freeze_sha, 'Worker execution incomplete/unfrozen')
                same(receipt['counts'], worker['counts'], 'Worker counters differ')
                same(receipt['templates'], worker['templates'], 'Worker template coverage differs')
                covered.extend(receipt['templates'])
                same(receipt['models']['dense']['files'], prepared['dense_model']['files'], 'Worker dense model files differ')
                for name, model in receipt['models']['cross_encoders'].items():
                    same(model['files'], historical[name]['files'], 'Worker cross-encoder files differ')
                for name, index in receipt['document_indexes'].items():
                    require(index['index_cache_hit'] is True and all(index[k] == prepared['dense_indexes'][name][k] for k in ('index_key', 'vector_sha256', 'index_manifest_sha256')), 'Worker vector-cache reuse differs')
                self.counts['worker_receipts_verified'] += 1
            require(len(covered) == len(set(covered)) == 16 and set(covered) == {f['template_family'] for f in self.families}, 'Worker template partition omits/duplicates groups')

    def preparation(self):
        prepared = load(HERE / 'preparation.json')
        require(file_sha(HERE / 'preparation.json') == self.freeze['prepare_receipt_sha256'], 'Public preparation not byte-identical to bound preparation')
        require(prepared['global_documents'] == len(self.docs) == 1110 and prepared['development_documents'] == 276 and prepared['training_rows'] == 19872, 'Preparation census differs')
        require(prepared['confirmation_endpoints_scored'] == 0, 'Preparation scored confirmation')
        for name, digest in prepared['implementation_pins'].items():
            require(file_sha(HERE / name) == digest, 'Prepared implementation differs')
        require(prepared['decision_model_sha256'] == file_sha(HERE / 'decision-model.json'), 'Prepared tree differs')
        tree = load(HERE / 'decision-model.json')
        identity = tree.get('training_identity', tree.get('identity', {}))
        development = [f for f in self.families if f['split'] == 'development']
        groups = sorted({f['template_family'] for f in self.families}, key=lambda group: sha(group + ':oct13-split-v1'))
        require({f['template_family'] for f in development} == set(groups[:4]), 'Development split differs from prospective recipe')
        require(identity['development_only'] is True and identity['confirmation_records_used_for_training'] == 0, 'Decision training includes confirmation')
        same(identity['development_family_ids'], sorted(f['id'] for f in development), 'Development family training metadata differs')
        same(identity['query_ids'], [t['id'] for f in development for t in f['tasks']], 'Development training query list differs')
        dev_docs = project_documents(development)
        require(identity['document_ids_sha256'] == sha(compact(sorted(dev_docs))), 'Development training document set differs')
        positive_rows = sum(len(set.union(*(set(ids) for ids in t['evidence_sets']))) for f in development for t in f['tasks'])
        require(tree['training_rows'] == 19872 and tree['positive_rows'] == positive_rows, 'Tree fit row/positive counts differ')
        require(prepared['bank_sha256'] == file_sha(HERE / 'challenge-bank.json'), 'Prepared bank differs')
        if self.work:
            require(file_sha(self.work / 'prepare-receipt.json') == self.freeze['prepare_receipt_sha256'], 'Private preparation differs')
        if self.cache:
            spec = load(HERE / 'dense-model-spec.json')
            models = [('dense-minilm', spec['files'])]
            historical = load(HERE.parent / 'study-2026-10-11/model-execution.json')['models']
            models.extend((name, model['files']) for name, model in historical.items())
            for folder, files in models:
                for relative, pinned in files.items():
                    path = self.cache / folder / relative
                    require(path.stat().st_size == pinned['bytes'] and file_sha(path) == pinned['sha256'], 'Pinned model file changed')
                    self.counts['model_files_verified'] += 1
            for value in prepared['dense_indexes'].values():
                folder = self.cache / 'dense-indexes' / value['index_key']
                require(file_sha(folder / 'vectors.npy') == value['vector_sha256'] and file_sha(folder / 'manifest.json') == value['index_manifest_sha256'], 'Prepared vector cache changed')
                self.counts['dense_indexes_verified'] += 1
        self.counts['prepared_implementation_pins'] = len(prepared['implementation_pins'])

    def calls(self, row, root):
        expected = load(HERE / 'runtime-public.json')
        calls = row['calls']
        names = ['direct'] if row['block'] != 'discovery' else ['round-' + str(n) for n in range(1, len(calls) + 1)]
        recorded = []
        for name, call in zip(names, calls):
            if 'control_receipt' in call:
                from reader_trials import runtime
                same(runtime().safe_controls(call['control_receipt']), call['control_receipt'], 'Call controls contain non-allowlisted fields')
            prompt_file = root / (('public' if name == 'direct' else name) + '-prompt.json')
            prompt = load(prompt_file)['prompt']
            require(load(prompt_file)['prompt_sha256'] == sha(prompt) == call['intended_prompt_sha256'], 'Saved call prompt hash differs')
            wire = (pretty({'prompt': prompt, 'reasoning_effort': 'high', 'timeout_seconds': 300}) + '\n').encode('utf8')
            if call.get('failure') != 'interrupted_call_no_receipt':
                require(call['wire_input_sha256'] == sha(wire) and call['input_utf8_bytes'] == len(wire), 'Actual transport input differs')
            saved_path, pending_path = root / (name + '-call.json'), root / (name + '-pending.json')
            if saved_path.exists():
                saved = load(saved_path)
                require(saved['identity'] == sha(prompt + json.dumps(expected, sort_keys=True)), 'Call identity differs')
                local = dict(call)
                local['resume_reused_call'] = False
                same(local, saved['call'], 'Public/private call differs')
                require(not pending_path.exists(), 'Completed call retains an ambiguous pending marker')
                if call['accepted']:
                    require(isinstance(saved['text'], str) and call['response_text_sha256'] == sha(saved['text']), 'Returned text differs')
                else:
                    require(saved['text'] is None, 'Rejected call contains credited text')
                recorded.append((name, prompt, saved['text'], call))
            else:
                require(call.get('failure') == 'interrupted_call_no_receipt' and pending_path.exists() and not call['accepted'], 'Unreceipted call is not a retained interrupted failure')
                require(load(pending_path)['identity'] == sha(prompt + json.dumps(expected, sort_keys=True)), 'Pending call identity differs')
                recorded.append((name, prompt, None, call))
                self.counts['unknown_pending_calls_retained'] += 1
            self.counts['recorded_reader_calls'] += 1
            if call.get('resume_reused_call'):
                require(row.get('latency_comparable') is False, 'Resumed trial mislabels latency')
                self.counts['reused_receipted_calls'] += 1
            if not call['accepted']:
                self.counts['rejected_calls_retained'] += 1
                continue
            control = call['control_receipt']
            required = ('fresh_process', 'fresh_ephemeral_session', 'workspace_root_absent', 'previous_inputs_absent',
                'foreign_personal_skills_disabled', 'provider_store_false', 'provider_continuation_keys_absent',
                'same_call_user_input_unchanged', 'web_and_artifact_tools_disabled', 'shell_and_writes_disabled',
                'all_upstream_user_text_matches', 'all_non_bookkeeping_native_attempts_failed_unavailable')
            require(all(control.get(key) is True for key in required), 'Accepted call local isolation is unverified')
            require(control['enabled_skill_count'] == 0 and control['initial_upstream_user_inputs'] == 1 and control['reasoning_effort'] == 'high', 'Accepted call native configuration differs')
            require(control['native_tools_advertised'] == ['muse.write_todos'] and control['advertised_tool_audit'] == 'actual upstream request', 'Accepted call tool inventory differs')
            require(control['native_filesystem_tools_advertised'] is False and control['native_session_tools_advertised'] is False, 'Native collection access advertised')
            require(control['intended_prompt_utf8_sha256'] == sha(prompt) and control['measured_upstream_request_text_count'] >= 1, 'Upstream user text identity is unverified')
            for public, receipt in (('private_adapter_sha256', 'adapter_source_sha256'), ('private_wrapper_sha256', 'wrapper_source_sha256'), ('pinned_binary_sha256', 'pinned_binary_sha256')):
                require(control[receipt] == expected[public], 'Accepted call runtime bytes differ')
            require(call['model'] == expected['model'], 'Accepted call model differs')
            self.counts['accepted_local_freshness_calls_verified'] += 1
        require({p.name for p in root.glob('*-call.json')} == {name + '-call.json' for name, _, _, _ in recorded if (root / (name + '-call.json')).exists()}, 'Unlisted call record suggests a scored retry')
        require({p.name for p in root.glob('*-pending.json')} == {name + '-pending.json' for name, _, _, call in recorded if call.get('failure') == 'interrupted_call_no_receipt'}, 'Unlisted pending call')
        return recorded

    def readers(self):
        scheduled = load(HERE / 'reader-schedule.json')
        same(scheduled['jobs'], expected_schedule(self.families), 'Reader schedule recipe differs')
        result = load(HERE / 'reader-results.json')
        require(result['freeze_sha256'] == self.freeze_sha and result['state'] == 'complete' and result['scheduled_trials'] == 192, 'Reader census/freeze differs')
        rows = {r['trial_id']: r for r in result['results']}
        require(len(rows) == len(result['results']) == 192 and set(rows) == {j['trial_id'] for j in scheduled['jobs']}, 'Missing/duplicate reader trial')
        for job in scheduled['jobs']:
            row = rows[job['trial_id']]
            same({key: row[key] for key in job}, job, 'Reader trial inputs differ')
            require(row['state'] == 'recorded', 'Unretained reader attempt')
            docs = collection(self.docs, job['family_id'], '144')
            task = self.tasks[job['family_id'], job['task_id']]
            metric = support(task, row['actual_prewrite_source_observations'], docs)
            metric.update(answer_agreement(row['artifact'], task))
            write = row['write_receipt']
            metric['artifact_written'] = bool(write)
            metric['contract_valid'] = bool(write and write.get('check', {}).get('schema_valid'))
            cited = set(write.get('check', {}).get('cited_original_ids', [])) if write else set()
            metric['declared_original_citation_set'] = any(set(alt) <= cited for alt in task['evidence_sets'])
            metric['complete_task'] = all(metric[key] for key in ('artifact_written', 'contract_valid', 'typed_answer_status_match', 'declared_span_bundle_recovered', 'declared_original_citation_set'))
            metric['clean_protocol'] = row['outcome']['clean_protocol']
            metric['clean_complete_task'] = metric['complete_task'] and metric['clean_protocol']
            same(metric, row['outcome'], 'Reader gates differ')
            if row['failure']:
                self.counts['reader_failure_rows_retained'] += 1
            self.counts['reader_trials'] += 1
            if not self.work:
                continue
            saved = load(self.work / 'reader-checkpoints' / (job['trial_id'] + '.json'))
            require(saved['fingerprint'] == sha(self.freeze_sha + ':reader-trials-v1'), 'Reader checkpoint fingerprint differs')
            same(saved['result'], row, 'Private/public reader differs')
            root = self.work / 'reader-artifacts' / job['trial_id']
            recorded = self.calls(row, root)
            if write:
                path = root / 'artifacts/result.json'
                require(file_sha(path) == write['artifact_sha256'], 'Actual saved artifact differs')
                same(load(path), row['artifact'], 'Actual saved artifact JSON differs')
                if row['failure'] != 'trial_execution_error':
                    write_receipt(row['artifact'], task, docs, write)
                    if write['checker_exit'] is None:
                        self.counts['final_checker_failures_retained'] += 1
                        self.counts['checker_failure_replays_skipped'] += 1
                    else:
                        self.rerun_checker(root, write)
                self.counts['actual_artifacts_verified'] += 1
            else:
                require(not (root / 'artifacts/result.json').exists(), 'Unreported artifact exists')
            if job['block'] == 'discovery' and row['failure'] != 'trial_execution_error':
                self.discovery(row, docs, task, recorded)
            elif job['block'] != 'discovery' and recorded:
                from packing_lab import pack
                from benchmark_runner import build_packet
                packet = pack(docs, task['query'], task['evidence_sets'][0], 10**8, 'whole_record') if job['block'] == 'oracle' else build_packet(job['family_id'], job['task_id'], job['ranker'], job['packer'], job['budget'], 144, self.work)
                expected_obs = [{k: o[k] for k in ('id', 'start', 'end', 'source_hash')} for o in packet['observations']] if recorded[0][3]['accepted'] else []
                same(expected_obs, row['actual_prewrite_source_observations'], 'Direct supplied evidence differs')
                require(row['events'][0]['packet_sha256'] == sha(packet['packet']) and row['events'][0]['packet_bytes'] == len(packet['packet'].encode('utf8')), 'Direct packet receipt differs')
                from reader_trials import DIRECT, contract_projection
                prompt = DIRECT + '\nTASK AND CONTRACT\n' + json.dumps(contract_projection(task), ensure_ascii=False, sort_keys=True) + '\nSUPPLIED EVIDENCE\n' + packet['packet']
                require(recorded[0][1] == prompt, 'Direct prompt contains different evidence')
                same(row['events'][0]['response_text'], recorded[0][2], 'Direct response receipt differs')
                if recorded[0][2] is not None:
                    from artifact_contract import strict_json
                    try:
                        parsed = strict_json(recorded[0][2])
                    except ValueError:
                        parsed = None
                    same(parsed, row['artifact'], 'Direct artifact is not the retained response JSON')
                # The direct reader sets clean False only on an unverified call;
                # artifact parse/shape failures retain clean True by design.
                clean = all(c['accepted'] and not c.get('control_receipt', {}).get('native_failed_unavailable_count', 0) for _, _, _, c in recorded)
                require(clean == row['outcome']['clean_protocol'], 'Direct clean protocol gate differs')

    def rerun_checker(self, root, write):
        command = [sys.executable, '-X', 'utf8', str(HERE / 'artifact_contract.py'), '--check', str(root / 'artifacts/result.json'),
            '--task-contract', str(root / 'task-contract.json'), '--source-bounds', str(root / 'source-bounds.json')]
        proc = subprocess.run(command, capture_output=True, timeout=15, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        checker_line_ending(write)  # Independently bind the retained execution bytes.
        stdouts = [checker_stdout(write['check'], ending) for ending in ('\n', '\r\n')]
        require(proc.returncode == write['checker_exit'] and proc.stdout in stdouts and sha(proc.stderr) == write['checker_stderr_sha256'], 'Actual artifact checker replay differs')
        self.counts['actual_checker_replays'] += 1

    def discovery(self, row, docs, task, recorded):
        from artifact_contract import strict_json, validate
        from reader_trials import DISCOVERY, HELPER, ENTRYPOINT, contract_projection
        from packing_lab import pack
        from index_lab import PreparedIndex
        paths = {d['path']: i for i, d in docs.items()}
        files = {path: packet_text([{'id': i, 'start': 0, 'end': len(docs[i]['body']), 'source_hash': sha(docs[i]['body'])}], docs, 'whole_record') for path, i in paths.items()}
        if row['entrypoint']:
            files['README.md'] = ENTRYPOINT
        index = PreparedIndex(docs) if row['helper'] else None
        history, pending, delivered, prewrite, deliveries = [], [], [], [], []
        events, cumulative, forbidden, final_write = [], 0, 0, None
        clean, done = True, False
        writes = [n for n, e in enumerate(row['events']) if e['executed'] is True and isinstance(e['action'], dict) and e['action'].get('tool') == 'write']
        last_write = writes[-1] if writes else None
        for number, (_, prompt, text, call) in enumerate(recorded, 1):
            state = {'response_number': number, 'responses_remaining_after_this': 8 - number, 'actions_remaining': 32 - len(events), 'returned_bytes_remaining': BYTE_CAP - cumulative, 'artifact_written': final_write is not None}
            intended = DISCOVERY + (HELPER if row['helper'] else '') + '\nTASK AND CONTRACT\n' + json.dumps(contract_projection(task), ensure_ascii=False, sort_keys=True) + '\nSTATE\n' + json.dumps(state) + '\nYOUR REPLAYED TRIAL HISTORY\n' + json.dumps(history, ensure_ascii=False, sort_keys=True)
            require(prompt == intended, 'Discovery replay history differs')
            if pending:
                deliveries.append({'round': number, 'sources': pending, 'upstream_text_verified': bool(call['accepted'])})
            delivered.extend(pending)
            pending = []
            if text is None:
                break
            try:
                reply = strict_json(text)
                require(isinstance(reply, dict) and set(reply) == {'actions', 'done'} and type(reply['done']) is bool and isinstance(reply['actions'], list) and len(reply['actions']) <= 4, 'Invalid response')
            except (ValueError, TypeError):
                clean = False
                history.append({'assistant': text, 'host': {'error': 'invalid_action_response', 'required_keys': ['actions', 'done']}})
                continue
            results = []
            for action in reply['actions']:
                if len(events) >= 32 or cumulative >= BYTE_CAP - RESERVE:
                    break
                event = row['events'][len(events)]
                same(event['action'], action, 'Action history differs')
                require(event['seq'] == len(events) + 1 and event['round'] == number, 'Action sequence differs')
                if event['executed'] is True and isinstance(action, dict) and action.get('tool') == 'write' and event['result'].get('error') == 'whole_result_exceeds_remaining_byte_budget':
                    require(len(events) == last_write, 'Overwritten capped write checker receipt is unavailable')
                expected, seen, executed = self.action_result(action, docs, paths, files, task, index, event,
                    row['write_receipt'] if len(events) == last_write else None)
                if isinstance(action, dict) and action.get('tool') not in ('list', 'read', 'search', 'write') and not (action.get('tool') == 'retrieve' and row['helper']):
                    forbidden += 1
                if executed and action.get('tool') == 'write':
                    final_write = expected
                    prewrite = list(delivered)
                    if expected['checker_exit'] is None:
                        self.counts['discovery_checker_failure_receipts_retained'] += 1
                cost = len(pretty(expected).encode('utf8'))
                remaining = BYTE_CAP - cumulative
                if cost > remaining - RESERVE:
                    expected = {'error': 'whole_result_exceeds_remaining_byte_budget', 'requested_bytes': cost, 'remaining_bytes': remaining}
                    cost = len(pretty(expected).encode('utf8'))
                    seen = []
                require(cost <= remaining, 'Return cap exceeded')
                cumulative += cost
                same(event['result'], expected, 'Independent action result differs')
                same(event['delivered_source_observations'], seen, 'Action source exposure differs')
                require(event['executed'] is executed and event['charged_returned_bytes'] == cost and event['cumulative_returned_bytes'] == cumulative, 'Return charging differs')
                pending.extend(seen)
                events.append(event)
                results.append(expected)
            history.append({'assistant': reply, 'host_results': results})
            if reply['done']:
                done = True
                break
        require(len(events) == len(row['events']) and cumulative == row['returned_tool_bytes'] <= BYTE_CAP and len(recorded) <= 8 and len(events) <= 32, 'Discovery action/return census differs')
        same(prewrite, row['actual_prewrite_source_observations'], 'Strictly pre-write delivered evidence differs')
        same(final_write, row['write_receipt'], 'Last successful discovery write receipt differs')
        same(deliveries, [{k: d[k] for k in ('round', 'sources', 'upstream_text_verified')} for d in row['source_delivery_history']], 'Source delivery history differs')
        clean = clean and done and not forbidden and all(e['executed'] for e in events) and all(c['accepted'] and not c.get('control_receipt', {}).get('native_failed_unavailable_count', 0) for _, _, _, c in recorded)
        require(clean == row['outcome']['clean_protocol'], 'Discovery clean protocol gate differs')
        self.counts['discovery_action_results_reconstructed'] += len(events)
        self.counts['discovery_histories_replayed'] += 1

    def action_result(self, action, docs, paths, files, task, index, event, final_receipt=None):
        from packing_lab import pack
        def relative(value, empty=False):
            require(isinstance(value, str) and not any(c in value for c in ('\\', ':', '\x00')) and not value.startswith('/') and '..' not in value.split('/') and (value or empty), 'Invalid relative path')
            from pathlib import PurePosixPath
            return PurePosixPath(value).as_posix() if value else ''
        try:
            require(isinstance(action, dict), 'Invalid action')
            tool = action.get('tool')
            seen = []
            if tool == 'list':
                prefix = relative(action.get('prefix', ''), True)
                start = prefix + '/' if prefix else ''
                children = set()
                for path in files:
                    if path.startswith(start):
                        first, separator, _ = path[len(start):].partition('/')
                        children.add(start + first + ('/' if separator else ''))
                result = {'children': sorted(children), 'recursive': False}
            elif tool == 'read':
                path = relative(action.get('path'))
                require(path in files, 'Missing file')
                result = {'path': path, 'text': files[path]}
                if path in paths:
                    i = paths[path]
                    seen = [{'id': i, 'start': 0, 'end': len(docs[i]['body']), 'source_hash': sha(docs[i]['body'])}]
            elif tool == 'search':
                query, prefix = action.get('query'), relative(action.get('prefix', ''), True)
                require(isinstance(query, str) and query.strip() and len(query) <= 1000, 'Invalid query')
                matches = []
                for path, i in sorted(paths.items()):
                    if docs[i]['kind'] != 'source' or prefix and path != prefix and not path.startswith(prefix + '/'):
                        continue
                    offset = 0
                    for line_number, line in enumerate(docs[i]['body'].splitlines(keepends=True), 1):
                        end = offset + len(line.rstrip('\r\n'))
                        if query.casefold() in line.casefold():
                            matches.append({'path': path, 'id': i, 'line': line_number, 'start': offset, 'end': end, 'text': docs[i]['body'][offset:end]})
                        offset += len(line)
                result = {'matches': matches[:40], 'total_matches': len(matches), 'truncated': len(matches) > 40}
                seen = [{'id': m['id'], 'start': m['start'], 'end': m['end'], 'source_hash': sha(docs[m['id']]['body'])} for m in matches[:40]]
            elif tool == 'retrieve' and index is not None:
                query = action.get('query')
                require(isinstance(query, str) and query.strip() and len(query) <= 1000, 'Invalid query')
                packet = pack(docs, query, index.rank(query, 'entity_rrf')[:32], 8192, 'closure_passages')
                result = {'packet': packet['packet'], 'policy': 'entity_rrf_closure_passages_8192', 'bytes': packet['bytes'], 'query': query}
                seen = [{k: o[k] for k in ('id', 'start', 'end', 'source_hash')} for o in packet['observations']]
            elif tool == 'write':
                require(relative(action.get('path')) == 'artifacts/result.json', 'Invalid write path')
                raw = (pretty(action.get('content')) + '\n').encode('utf8')
                require(len(raw) <= 20000, 'Oversized artifact')
                result = event['result']
                if result.get('error') == 'whole_result_exceeds_remaining_byte_budget':
                    # The frozen host writes before applying its return cap. Rebuild
                    # its bound final receipt without writing or invoking a child;
                    # discovery applies the return cap afterward. Earlier capped
                    # checker metadata was overwritten and cannot be invented.
                    result = final_receipt
                result = write_receipt(action.get('content'), task, docs, result)
            else:
                raise ValueError('Unavailable tool')
            return result, seen, True
        except (ValueError, TypeError, KeyError):
            return {'error': 'action_rejected', 'action_tool': action.get('tool') if isinstance(action, dict) else None}, [], False

    def timing(self):
        data = load(HERE / 'warm-timing.json')
        require(data['state'] == 'complete_warm_timing' and data['freeze_sha256'] == self.freeze_sha and data['query_embedding_or_pair_cache_enabled'] is False, 'Timing state/configuration differs')
        development = sorted((f for f in self.families if f['split'] == 'development'), key=lambda f: sha(f['id'] + ':oct13-timing-v1'))
        chosen = []
        for f in development:
            if f['template_family'] not in {c['template_family'] for c in chosen}:
                chosen.append(f)
        for f in development:
            if f not in chosen and len(chosen) < 6:
                chosen.append(f)
        expected = {(f['id'], f['tasks'][0]['id'], m, r) for f in chosen[:6] for m in METHODS for r in (1, 2, 3)}
        seen = set()
        for row in data['rows']:
            key = (row['family_id'], row['task_id'], row['ranker'], row['repetition'])
            require(key not in seen and key in expected and math.isfinite(row['seconds']) and row['seconds'] >= 0, 'Timing row invalid')
            require(row['size'] == '144' and row['budget'] == 8192 and row['packer'] == 'closure_passages' and row['packet_bytes'] <= 8192, 'Timing packet policy differs')
            require(not row['pairs_or_vector_usage'].get('query_embedding_cache_hit') and not row['pairs_or_vector_usage'].get('dense_score_cache_hit'), 'Uncached timing reused query cache')
            seen.add(key)
        require(seen == expected and len(seen) == 378 and len(data['warmup']) == 21, 'Timing census differs')
        self.counts['warm_timing_rows'] = len(seen)

    def maintenance(self):
        data = load(HERE / 'maintenance-results.json')
        require(data['state'] == 'complete_engineered_replay' and data['seeds'] == 64 and data['events_per_seed'] == 20, 'Maintenance configuration differs')
        policies = ('no_invalidation', 'ttl_5', 'global', 'direct_dependencies', 'transitive_dependencies')
        expected = {(seed, step, missing, policy) for seed in range(64) for step in range(1, 21) for missing in (False, True) for policy in policies}
        seen, summary = set(), {}
        for row in data['rows']:
            key = (row['seed'], row['step'], row['missing_declared_edge'], row['policy'])
            require(key in expected and key not in seen, 'Maintenance row missing/duplicate')
            seen.add(key)
            total = summary.setdefault((row['policy'], row['missing_declared_edge']), Counter())
            total['queries'] += 1
            total['stale_reuses'] += row['stale_reuse']
            total['rebuilds'] += row['rebuilds']
            total['unnecessary_rebuild_queries'] += row['unnecessary_rebuild']
        require(seen == expected and len(seen) == 12800, 'Maintenance census differs')
        for row in data['summary']:
            same(dict(summary[row['policy'], row['missing_declared_edge']]), {k: row[k] for k in ('queries', 'stale_reuses', 'rebuilds', 'unnecessary_rebuild_queries')}, 'Maintenance summary differs')
        require(data['commit_checks']['multi_host_atomicity_tested'] is False, 'Maintenance overclaims atomicity')
        self.counts['engineered_maintenance_rows'] = len(seen)

    def baseline(self):
        options = {'capture_output': True, 'check': True, 'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)}
        proc = subprocess.run(['git', 'ls-tree', '-r', '--full-tree', BASELINE], cwd=REPO, **options)
        rows = proc.stdout.decode('utf8').splitlines()
        count = 0
        for row in rows:
            header, relative = row.split('\t', 1)
            mode, kind, blob = header.split()
            require(kind == 'blob', 'Unexpected baseline object')
            # Root README and attributes are deliberately mutable navigation files.
            if relative in ('README.md', '.gitattributes'):
                continue
            target = REPO / relative
            require(target.is_file(), 'Baseline file removed')
            raw = target.read_bytes()
            actual = hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\x00' + raw).hexdigest()
            require(actual == blob, 'Historical baseline blob changed: ' + relative)
            count += 1
        self.counts['historical_baseline_blobs_verified'] = count
        self.counts['baseline_navigation_files_excluded'] = 2

    def publication(self):
        options = {'capture_output': True, 'check': True, 'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)}
        proc = subprocess.run(['git', 'ls-tree', '-r', '--full-tree', PROSPECTIVE_COMMIT], cwd=REPO, **options)
        blobs = {row.split('\t', 1)[1]: row.split('\t', 1)[0].split()[2] for row in proc.stdout.decode('utf8').splitlines()}
        files = {**self.freeze['files'], 'freeze.json': self.freeze_sha}
        for relative in files:
            path = (HERE / relative).resolve()
            key = path.relative_to(REPO).as_posix()
            raw = path.read_bytes()
            actual = hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\x00' + raw).hexdigest()
            require(blobs.get(key) == actual, 'Prospective Git commit differs from frozen input: ' + relative)
        require(self.freeze['confirmation_outcomes_available_at_freeze'] is False, 'Freeze claims outcomes existed')
        if self.work:
            receipt = load(self.work / 'freeze-publication-receipt.json')
            require(receipt['state'] == 'prospective_inputs_published_before_main_scoring' and receipt['commit'] == PROSPECTIVE_COMMIT and receipt['freeze_sha256'] == self.freeze_sha, 'Private publication receipt differs')
            same(receipt['files'], self.freeze['files'], 'Published input pin list differs')
            require(receipt['remote_main_verified'] is True and receipt['fresh_checkout_frozen_bytes_verified'] is True, 'Publication verification receipt incomplete')
        self.counts['prospective_git_blobs_verified'] = len(files)

    def privacy(self):
        scanned, hits = 0, []
        for path in sorted(HERE.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            if path.suffix.lower() not in ('.json', '.md', '.py', '.svg', '.txt'):
                continue
            with path.open('rb') as stream:
                tail = b''
                for block in iter(lambda: stream.read(65536), b''):
                    combined = tail + block
                    if SENSITIVE.search(combined):
                        hits.append(path.relative_to(HERE).as_posix())
                        break
                    tail = combined[-1024:]
            scanned += 1
        require(not hits, 'Bounded public privacy scan hit: ' + ', '.join(hits))
        self.counts['public_text_files_privacy_scanned'] = scanned

    def run(self):
        started = time.perf_counter()
        for name in ('publication', 'preparation', 'grid', 'timing', 'readers', 'maintenance', 'baseline', 'privacy'):
            getattr(self, name)()
            print(compact({'audit_phase': name, 'state': 'passed', 'counts': dict(self.counts)}), flush=True)
        return {'schema_version': 1, 'state': 'passed', 'freeze_sha256': self.freeze_sha,
            'audited_utc': datetime.now(timezone.utc).isoformat(), 'prospective_commit': PROSPECTIVE_COMMIT,
            'audit_source_sha256': file_sha(Path(__file__)), 'private_execution_checked': self.work is not None,
            'pinned_cache_checked': self.cache is not None, 'frozen_packer_replay_enabled': self.repack,
            'counts': dict(self.counts), 'checked_shards': self.files,
            'result_file_sha256': {name: file_sha(HERE / name) for name in ('grid-manifest.json', 'reader-results.json', 'warm-timing.json', 'maintenance-results.json')},
            'elapsed_seconds': time.perf_counter() - started,
            'limitations': ['Full model ranking/score hashes cannot be independently recomputed from top64/hash receipts without inference.',
                'Exact source intervals and citation ID sets do not independently establish semantic entailment.',
                'Native adapter controls establish measured local freshness and user-text identity, not provider-side memory erasure or hidden system-prefix identity.',
                'Pattern-based public privacy scanning is bounded and supplements human review; it cannot prove absence of all identifying information.',
                'Named frozen checker-failure receipts are retained without retry; discarded diagnostic streams do not independently establish their original cause.',
                'Overwritten capped write checker metadata is unavailable; that discovery history cannot receive complete replay acceptance.',
                'Engineering replay is not a distributed-concurrency or LLM-maintenance experiment.']}


def self_check():
    docs = {'S': {'id': 'S', 'kind': 'source', 'revision': 1, 'title': 'rule', 'scope': 'all', 'aliases': ['fixture'],
        'authored_at': '2026-10-13', 'body': '青灯: seven days.\nOnly with approval.', 'links': [], 'supersedes': [], 'incorporates': []}}
    body = docs['S']['body']
    task = {'evidence_sets': [['S']], 'evidence_spans': [[{'id': 'S', 'start': 0, 'end': 16}]]}
    a = {'id': 'S', 'start': 0, 'end': 7, 'source_hash': sha(body)}
    b = {'id': 'S', 'start': 7, 'end': 16, 'source_hash': sha(body)}
    require(support(task, [a, b], docs)['declared_span_bundle_recovered'], 'Adjacent interval union failed')
    require(not support(task, [a, {**b, 'start': 8}], docs)['declared_span_bundle_recovered'], 'Gapped source interval falsely covered')
    from packing_lab import pack
    for method in PACKERS:
        result = pack(docs, 'approval seven', ['S'], 8192, method)
        require(packet_text(result['observations'], docs, method) == result['packet'], 'Independent wrapper reconstruction failed')
    try:
        packet_text([{**a, 'source_hash': '0' * 64}], docs, 'ranked_body')
    except ValueError:
        pass
    else:
        raise AssertionError('Corrupt body accepted')
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / 'rows.json'
        records = [{'n': n, 'text': 'bracket ] comma, escaped quote " λ' * 50} for n in range(100)]
        save(path, {'kind': 'fixture', 'rows': records})
        same(list(rows_in(path)), records, 'Strict shard rows parser differs')
        for malformed in ('{"rows":[{"n":1,"n":2}]}', '{"rows":[{"n":1}{"n":2}]}',
                '{"rows":[{"n":NaN}]}', '{"rows":[{"n":1e999}]}', '{"rows":[{"n":1}]',
                '{"rows":[{"n":1}]} trailing', r'{"rows":[{"text":"\ud800"}]}'):
            path.write_text(malformed, encoding='utf8')
            try:
                list(rows_in(path))
            except ValueError:
                pass
            else:
                raise AssertionError('Malformed JSON shard accepted')
        # Independent replay verifies a same-batch read/write receives no credit,
        # then a second-round write receives the delivered first-round source.
        from reader_trials import Filesystem, DISCOVERY, HELPER, contract_projection
        replay_docs = {'S': {**docs['S'], 'path': '1-Projects/fixture/source.md', 'branch': 'fixture'}}
        replay_task = {**task, 'id': 'DEV', 'query': 'seven approval', 'answer_keys': ['days'],
            'answer_contract': {'fields': {'days': {'type': 'integer'}}, 'additional_fields': False},
            'expected': {'status': 'ready', 'answer': {'days': 7}}}
        fs = Filesystem(replay_docs, replay_task, Path(temporary) / 'fixture', True, True)
        write = {'tool': 'write', 'path': 'artifacts/result.json', 'content': {'status': 'ready', 'answer': {'days': 7}, 'evidence': ['S']}}
        replies = [{'actions': [{'tool': 'read', 'path': replay_docs['S']['path']}, write], 'done': False}, {'actions': [write], 'done': True}]
        history, calls = [], []
        for number, reply in enumerate(replies, 1):
            state = {'response_number': number, 'responses_remaining_after_this': 8 - number, 'actions_remaining': 32 - len(fs.events), 'returned_bytes_remaining': BYTE_CAP - fs.bytes, 'artifact_written': fs.write_receipt is not None}
            prompt = DISCOVERY + HELPER + '\nTASK AND CONTRACT\n' + json.dumps(contract_projection(replay_task), ensure_ascii=False, sort_keys=True) + '\nSTATE\n' + json.dumps(state) + '\nYOUR REPLAYED TRIAL HISTORY\n' + json.dumps(history, ensure_ascii=False, sort_keys=True)
            fs.deliver(number, 0)
            if fs.deliveries and fs.deliveries[-1]['round'] == number:
                fs.deliveries[-1]['upstream_text_verified'] = True
            results = [fs.action(action, number) for action in reply['actions']]
            history.append({'assistant': reply, 'host_results': results})
            calls.append(('round-' + str(number), prompt, compact(reply), {'accepted': True}))
        row = {'entrypoint': True, 'helper': True, 'events': fs.events, 'returned_tool_bytes': fs.bytes,
            'actual_prewrite_source_observations': [{k: o[k] for k in ('id', 'start', 'end', 'source_hash')} for o in fs.prewrite],
            'source_delivery_history': fs.deliveries, 'write_receipt': fs.write_receipt, 'outcome': {'clean_protocol': True}}
        checker = Auditor.__new__(Auditor)
        checker.counts = Counter()
        checker.discovery(row, replay_docs, replay_task, calls)
        require(checker.counts['discovery_histories_replayed'] == 1, 'Independent discovery replay was not exercised')
        damaged = json.loads(compact(row))
        damaged['events'][0]['charged_returned_bytes'] += 1
        try:
            checker.discovery(damaged, replay_docs, replay_task, calls)
        except ValueError:
            pass
        else:
            raise AssertionError('Forged return charging accepted')
        capped = {'result': {'error': 'whole_result_exceeds_remaining_byte_budget',
            'requested_bytes': len(pretty(fs.write_receipt).encode('utf8')), 'remaining_bytes': 513}}
        rebuilt, seen, executed = checker.action_result(write, replay_docs, {}, {}, replay_task, None, capped, fs.write_receipt)
        require(executed and not seen, 'Successful capped write was replayed as rejected')
        same(rebuilt, fs.write_receipt, 'Capped successful write receipt reconstruction differs')
        for field, value in (('checker_exit', 9), ('checker_exit', False),
                ('checker_stdout_sha256', '0' * 64), ('checker_stderr_sha256', 'f' * 64)):
            damaged = {**fs.write_receipt, field: value}
            try:
                write_receipt(write['content'], replay_task, replay_docs, damaged)
            except ValueError:
                pass
            else:
                raise AssertionError('Forged write checker receipt accepted')
        for error in ('checker_output_invalid', 'checker_timeout', 'checker_execution_error'):
            failed = {**fs.write_receipt, 'check': {'schema_valid': False, 'errors': [error]},
                'checker_exit': None, 'checker_stdout_sha256': sha(b''), 'checker_stderr_sha256': sha(b'')}
            same(write_receipt(write['content'], replay_task, replay_docs, failed), failed, 'Named checker failure was replaced')
    require(sum(len(cells(m)) for m in METHODS) == 198, 'Independent schedule count differs')
    require(compact([False]) != compact([0]), 'Typed JSON agreement collapses booleans')
    typed_task = {'answer_keys': ['value'], 'answer_contract': {'fields': {'value': {'type': 'array', 'items': {'type': ['boolean', 'integer']}}}},
        'expected': {'status': 'ready', 'answer': {'value': [False]}}}
    require(not answer_agreement({'status': 'ready', 'answer': {'value': [0]}}, typed_task)['typed_answer_status_match'], 'Nested bool/integer false match')
    print(compact({'state': 'passed', 'checks': ['Unicode wrappers/separators', 'source hash rejection', 'adjacent/gapped interval union', 'strict bounded JSON strings/malformed rejection', 'prospective cell count', 'recursive bool/integer distinction', 'independent discovery action/history/prewrite replay', 'forged byte-charge rejection', 'successful capped write receipt', 'all write checker metadata bound', 'named checker failures retained without retry']}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--audit', action='store_true')
    parser.add_argument('--inputs-only', action='store_true', help='Verify input/cache/history identities and public privacy bytes without parsing or grading outcome files.')
    parser.add_argument('--freeze-sha256')
    parser.add_argument('--work', type=Path)
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--repack-all', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.self_check:
        return self_check()
    if args.inputs_only and args.freeze_sha256:
        checker = Auditor(args.freeze_sha256, args.work, args.cache)
        for phase in ('publication', 'preparation', 'baseline', 'privacy'):
            getattr(checker, phase)()
        result = {'state': 'passed_inputs_only', 'freeze_sha256': args.freeze_sha256, 'audit_source_sha256': file_sha(__file__),
            'counts': dict(checker.counts), 'confirmation_outcomes_parsed_interpreted_or_graded': False,
            'public_privacy_byte_scan_may_read_outcome_files': True}
        if args.output:
            save(args.output, result)
        print(compact(result))
        return result
    if not args.audit or not args.freeze_sha256 or not args.output:
        parser.error('Use --self-check or --audit --freeze-sha256 DIGEST --output FILE [--work PRIVATE --cache PRIVATE]')
    result = Auditor(args.freeze_sha256, args.work, args.cache, args.repack_all).run()
    save(args.output, result)
    return result


if __name__ == '__main__':
    main()
