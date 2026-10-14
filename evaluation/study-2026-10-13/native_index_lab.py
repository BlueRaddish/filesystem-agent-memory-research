"""Development-only SQLite FTS5 and frozen lexical references, stdlib only.

No provider, full-bank reader, extension loading or production index mutation.
Run --self-check for literal-query, transaction and checkpoint boundaries.
"""
import argparse
from collections import Counter, defaultdict
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import sqlite3
import _sqlite3
import statistics
import sys
import tempfile
import time

from artifact_contract import strict_json
from index_lab import PreparedIndex
import packing_lab
from study_common import documents, support_metrics

HERE = Path(__file__).resolve().parent
SOURCE_SHA = 'a4b7f77cf2311e1c2cd742df9996ddd5d5b7542b9a0a20f3eb305621f9f9a8fa'
BANK_SHA = '280e6be3f7380ed9c0bc1dbe3ec75dfba136113f230d08751e0f316b67cf9760'
NATIVE = {'fts_body_or': ('body_fts', 'OR'), 'fts_body_and': ('body_fts', 'AND'),
          'fts_search_or': ('search_fts', 'OR'), 'fts_search_and': ('search_fts', 'AND')}
REFERENCES = ('body_bm25', 'search_bm25')
ENGINES = (*NATIVE, *REFERENCES)
PACKERS, BUDGETS = ('whole_record', 'closure_passages'), (4096, 8192, 16384)
TOKENIZER, TOP_K, REPEATS = 'unicode61 remove_diacritics 2', 32, 3
PINS = ('NATIVE-INDEX-PLAN.md', 'native_index_lab.py', 'native-index-sources.json',
        'index_lab.py', 'packing_lab.py', 'study_common.py', 'artifact_contract.py')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode('utf8')).hexdigest()


def object_sha(value):
    return sha(canonical(value))


def file_sha(path):
    return sha(Path(path).read_bytes())


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return strict_json(Path(path).read_text(encoding='utf8'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('wb') as handle:
        handle.write((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf8'))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def seal(value):
    return {**value, 'checkpoint_sha256': object_sha(value)}


def check_seal(value):
    assert value['checkpoint_sha256'] == object_sha({k: v for k, v in value.items() if k != 'checkpoint_sha256'})


def private_root(value):
    path = Path(value).resolve()
    assert not path.is_relative_to(HERE.parents[1]), 'Private data must stay outside Git'
    return path


def load_dev(path):
    assert file_sha(path) == SOURCE_SHA
    data = read_json(path)
    assert data['source_bank_sha256'] == BANK_SHA
    families = data['families']
    assert len(families) == 24 and all(f['split'] == 'development' for f in families)
    docs, tasks, gold = documents(families), [], {}
    for family in families:
        for task in family['tasks']:
            tasks.append({'id': task['id'], 'query': task['query'], 'history': family['id'],
                          'template_group': family['template_family']})
            gold[task['id']] = {k: task[k] for k in ('evidence_sets', 'evidence_spans')}
    tasks.sort(key=lambda t: t['id'])
    assert len(docs) == 276 and len(tasks) == len(gold) == 72
    unique_rows(docs.values())  # Projection/schema validation, never retrieval scoring.
    for task in tasks:
        assert isinstance(task['query'], str) and task['query'].strip()
        task['query'].encode('utf8')
        assert re.fullmatch('[A-Za-z0-9_-]+', task['id'])
    for value in gold.values():
        assert value['evidence_sets'] and value['evidence_spans']
        for bundle in value['evidence_spans']:
            assert bundle
            for span in bundle:
                assert docs[span['id']]['kind'] == 'source'
                assert type(span['start']) is type(span['end']) is int
                assert 0 <= span['start'] < span['end'] <= len(docs[span['id']]['body'])
    return docs, tasks, gold


def search_text(doc):
    title = doc.get('title', '')
    title = '' if title is None else title
    assert isinstance(title, str) and isinstance(doc['scope'], str)
    aliases = doc.get('aliases', [])
    assert isinstance(aliases, list) and all(isinstance(alias, str) for alias in aliases)
    return '\n'.join([title, doc['scope'], *aliases, doc['body']])


def source_row(doc):
    identifier, revision, body = doc['id'], doc['revision'], doc['body']
    assert isinstance(identifier, str) and identifier
    assert not isinstance(revision, bool) and isinstance(revision, (str, int))
    assert isinstance(body, str) and body
    body.encode('utf8')
    surface = search_text(doc)
    surface.encode('utf8')
    return identifier, canonical(revision), body, surface


def unique_rows(docs):
    rows = [source_row(doc) for doc in docs]
    if len({row[0] for row in rows}) != len(rows):
        raise ValueError('duplicate_source_ids')
    return rows


class NativeIndex:
    def __init__(self, path, readonly=True):
        self.path = Path(path).resolve()
        target = self.path.as_uri() + '?mode=ro' if readonly else str(self.path)
        self.connection = sqlite3.connect(target, uri=readonly, isolation_level=None)

    @staticmethod
    def create(path, docs):
        rows = unique_rows(docs)
        path = Path(path)
        assert not path.exists(), 'Existing database cannot be silently replaced'
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, isolation_level=None)
        try:
            connection.execute('PRAGMA synchronous=FULL')
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('CREATE TABLE sources(source_id TEXT PRIMARY KEY, revision TEXT NOT NULL, body TEXT NOT NULL, search_text TEXT NOT NULL)')
            for table in ('body_fts', 'search_fts'):
                connection.execute("CREATE VIRTUAL TABLE " + table + " USING fts5(source_id UNINDEXED, revision UNINDEXED, text, tokenize='" + TOKENIZER + "')")
            for row in rows:
                NativeIndex._insert(connection, row)
            connection.commit()
            assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            for table in ('body_fts', 'search_fts'):
                connection.execute('INSERT INTO ' + table + '(' + table + ") VALUES('integrity-check')")
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _insert(connection, row):
        identifier, revision, body, surface = row
        connection.execute('INSERT INTO sources VALUES(?,?,?,?)', row)
        connection.execute('INSERT INTO body_fts(source_id,revision,text) VALUES(?,?,?)', (identifier, revision, body))
        connection.execute('INSERT INTO search_fts(source_id,revision,text) VALUES(?,?,?)', (identifier, revision, surface))

    def close(self):
        self.connection.close()

    def validate_sources(self, docs):
        expected = sorted(unique_rows(docs), key=lambda row: row[0])
        actual = self.connection.execute('SELECT source_id,revision,body,search_text FROM sources ORDER BY source_id COLLATE BINARY').fetchall()
        assert actual == expected, 'Source ledger projection mismatch'
        for table, field in (('body_fts', 2), ('search_fts', 3)):
            rows = self.connection.execute('SELECT source_id,revision,text FROM ' + table + ' ORDER BY source_id COLLATE BINARY').fetchall()
            assert rows == [(row[0], row[1], row[field]) for row in expected], 'FTS source/revision projection mismatch'

    def update_delete(self, upserts=(), deletions=()):
        rows = unique_rows(upserts)
        deletions = list(deletions)
        assert all(isinstance(i, str) and i for i in deletions)
        if len(set(deletions)) != len(deletions) or set(deletions) & {row[0] for row in rows}:
            raise ValueError('duplicate_or_overlapping_mutation_ids')
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            for row in rows:
                identifier = row[0]
                self.connection.execute('DELETE FROM sources WHERE source_id=?', (identifier,))
                for table in ('body_fts', 'search_fts'):
                    self.connection.execute('DELETE FROM ' + table + ' WHERE source_id=?', (identifier,))
                self._insert(self.connection, row)
            for identifier in deletions:
                if self.connection.execute('DELETE FROM sources WHERE source_id=?', (identifier,)).rowcount != 1:
                    raise ValueError('missing_deletion_source')
                for table in ('body_fts', 'search_fts'):
                    self.connection.execute('DELETE FROM ' + table + ' WHERE source_id=?', (identifier,))
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def rank(self, engine, expression):
        table, _ = NATIVE[engine]
        if expression is None:
            return []
        # Full matching-order fetch is intentionally bounded by this 276-record study.
        # At production scale use LIMIT plus a separately reported hit-count query.
        rows = self.connection.execute('SELECT source_id,bm25(' + table + ') AS score FROM ' + table +
            ' WHERE ' + table + ' MATCH ? ORDER BY score ASC,source_id COLLATE BINARY ASC', (expression,)).fetchall()
        assert len({row[0] for row in rows}) == len(rows)
        assert all(isinstance(score, (int, float)) and math.isfinite(score) and score <= 0 for _, score in rows)
        return [{'id': identifier, 'score': score} for identifier, score in rows]


class NativeTokenizer:
    def __init__(self):
        self.connection = sqlite3.connect(':memory:', isolation_level=None)
        self.connection.execute("CREATE VIRTUAL TABLE query_text USING fts5(text,tokenize='" + TOKENIZER + "')")
        self.connection.execute("CREATE VIRTUAL TABLE query_vocab USING fts5vocab(query_text,'instance')")

    def terms(self, query):
        assert isinstance(query, str)
        query.encode('utf8')
        self.connection.execute('DELETE FROM query_text')
        self.connection.execute('INSERT INTO query_text(rowid,text) VALUES(1,?)', (query,))
        rows = self.connection.execute('SELECT term FROM query_vocab ORDER BY offset ASC,term ASC').fetchall()
        return list(dict.fromkeys(row[0] for row in rows))

    def close(self):
        self.connection.close()


def literal_terms(terms, operator):
    assert operator in ('OR', 'AND')
    assert isinstance(terms, list) and all(isinstance(term, str) and term for term in terms)
    return (' ' + operator + ' ').join('"' + term.replace('"', '""') + '"' for term in terms) if terms else None


def runtime():
    connection = sqlite3.connect(':memory:')
    try:
        connection.execute('CREATE VIRTUAL TABLE probe USING fts5(text)')
        source_id = connection.execute('SELECT sqlite_source_id()').fetchone()[0]
        options = sorted(row[0] for row in connection.execute('PRAGMA compile_options'))
    finally:
        connection.close()
    return {'python': sys.version, 'sqlite_version': sqlite3.sqlite_version,
            'sqlite_source_id': source_id, 'compile_options_sha256': object_sha(options),
            'native_extension_sha256': file_sha(_sqlite3.__file__), 'fts5_probe_passed': True}


def material(dev):
    docs, tasks, _ = load_dev(dev)
    return {'source_sha256': SOURCE_SHA, 'source_bank_sha256': BANK_SHA,
        'documents_projection_sha256': object_sha(docs), 'queries_projection_sha256': object_sha(tasks),
        'code_pins': {name: file_sha(HERE / name) for name in PINS}, 'runtime': runtime(),
        'engines': list(ENGINES), 'packers': list(PACKERS), 'budgets': list(BUDGETS),
        'tokenizer': TOKENIZER, 'top_k': TOP_K, 'warmups_per_job': 1, 'timed_repeats_per_job': REPEATS,
        'workers': 1, 'scheduled_rankings': 432, 'scheduled_packets': 2592,
        'schedule': [{'task_id': t['id'], 'query_sha256': sha(t['query'])} for t in tasks]}


def prepare(args):
    root = private_root(args.work)
    root.mkdir(parents=True, exist_ok=True)
    assert not (root / 'manifest.json').exists() and not (root / 'run-started.json').exists()
    save(root / 'manifest.json', {'schema_version': 1, 'created_at': now(), 'material': material(args.development_bank),
                               'environment': {'platform': platform.platform()}})
    print(canonical({'status': 'prospective_review_pending', 'manifest_sha256': file_sha(root / 'manifest.json'),
                     'rankings': 432, 'packets': 2592, 'provider_calls': 0}))


def verified(args):
    root = private_root(args.work)
    frozen = read_json(root / 'manifest.json')
    assert frozen['material'] == material(args.development_bank), 'Frozen source/code/runtime changed'
    clearance = read_json(root / 'review-clearance.json')
    assert clearance.get('approved') is True and clearance.get('manifest_sha256') == file_sha(root / 'manifest.json')
    return root, frozen


def error_info(exception, phase):
    return {'phase': phase, 'class': type(exception).__name__,
            'sqlite_errorcode': getattr(exception, 'sqlite_errorcode', None),
            'sqlite_errorname': getattr(exception, 'sqlite_errorname', None),
            'private_message': str(exception)}


def build_indexes(root, docs, resume):
    native_path, build_path = root / 'sources.sqlite', root / 'native-build.json'
    native, reference = None, None
    if build_path.exists():
        built = read_json(build_path)
        check_seal(built)
    elif (root / 'native-build-pending.json').exists():
        assert read_json(root / 'native-build-pending.json')['source_projection_sha256'] == object_sha(docs)
        built = seal({'status': 'fault', 'error': {'phase': 'native_build', 'class': 'interrupted_build_unknown'},
                      'build_seconds': None, 'database_bytes': None, 'database_sha256': None})
        save(build_path, built)
    else:
        save(root / 'native-build-pending.json', {'source_projection_sha256': object_sha(docs)})
        started = time.perf_counter()
        try:
            NativeIndex.create(native_path, docs.values())
            built = {'status': 'ok', 'error': None, 'build_seconds': time.perf_counter() - started,
                     'database_bytes': native_path.stat().st_size, 'database_sha256': file_sha(native_path)}
        except Exception as exception:
            built = {'status': 'fault', 'error': error_info(exception, 'native_build'),
                     'build_seconds': time.perf_counter() - started, 'database_bytes': None, 'database_sha256': None}
        save(build_path, seal(built))
        (root / 'native-build-pending.json').unlink()
        built = read_json(build_path)
    if built['status'] == 'ok':
        assert file_sha(native_path) == built['database_sha256'], 'Persisted native index changed'
        previous_reopen_path = root / 'native-reopen-resumed.json'
        if not previous_reopen_path.exists(): previous_reopen_path = root / 'native-reopen.json'
        previous_reopen = read_json(previous_reopen_path) if previous_reopen_path.exists() else None
        if previous_reopen is not None: check_seal(previous_reopen)
        if previous_reopen is not None and previous_reopen['status'] == 'fault':
            built = {**built, 'status': 'fault'}  # Retained reopen faults are not retried.
    if built['status'] == 'ok':
        started = time.perf_counter()
        try:
            native = NativeIndex(native_path)
            reopened = time.perf_counter() - started
            started = time.perf_counter()
            native.validate_sources(docs.values())
            integrity = time.perf_counter() - started
            reopen = {'status': 'ok', 'reopen_seconds': reopened, 'source_integrity_seconds': integrity, 'error': None}
        except Exception as exception:
            if native is not None: native.close()
            native = None
            reopen = {'status': 'fault', 'reopen_seconds': None, 'source_integrity_seconds': None,
                      'error': error_info(exception, 'native_reopen_or_integrity')}
        save(root / ('native-reopen-resumed.json' if resume else 'native-reopen.json'), seal(reopen))
    reference_path = root / 'reference-preparation.json'
    previous_path = root / 'reference-preparation-resumed.json'
    if not previous_path.exists(): previous_path = reference_path
    previous = read_json(previous_path) if previous_path.exists() else None
    if previous is not None: check_seal(previous)
    if previous is None or previous['status'] == 'ok':
        started = time.perf_counter()
        try:
            reference = PreparedIndex(docs)
            receipt = {'status': 'ok', 'seconds': time.perf_counter() - started,
                       'index_digest': reference.digest, 'error': None}
        except Exception as exception:
            receipt = {'status': 'fault', 'seconds': time.perf_counter() - started,
                       'index_digest': None, 'error': error_info(exception, 'reference_preparation')}
        destination = root / ('reference-preparation-resumed.json' if previous is not None else 'reference-preparation.json')
        save(destination, seal(receipt))
    return native, reference


def ranking_identity(task, engine, manifest_sha):
    return object_sha({'task_id': task['id'], 'query_sha256': sha(task['query']), 'engine': engine,
                       'manifest_sha256': manifest_sha})


def validate_ranking(row, task, engine, manifest_sha, docs, tokenizer):
    check_seal(row)
    assert row['identity'] == ranking_identity(task, engine, manifest_sha)
    assert row['task_id'] == task['id'] and row['engine'] == engine
    assert row['status'] in ('ok', 'zero_hit', 'fault')
    ids = row['candidates']
    assert isinstance(ids, list) and len(ids) == len(set(ids)) <= TOP_K and set(ids) <= set(docs)
    if row['status'] == 'fault':
        assert ids == [] and row['ranked_hits'] == [] and row['error'] is not None
        return row
    assert row['error'] is None and len(row['timings_seconds']) == REPEATS
    assert all(type(x) is float and math.isfinite(x) and x >= 0 for x in row['timings_seconds'])
    if engine in NATIVE:
        terms = tokenizer.terms(task['query'])
        assert row['native_terms'] == terms and row['match_expression'] == literal_terms(terms, NATIVE[engine][1])
        hits = row['ranked_hits']
        assert row['total_hits'] == len(hits) and ids == [hit['id'] for hit in hits][:TOP_K]
        assert len({hit['id'] for hit in hits}) == len(hits) and {hit['id'] for hit in hits} <= set(docs)
        assert all(type(hit['score']) is float and math.isfinite(hit['score']) and hit['score'] <= 0 for hit in hits)
        assert hits == sorted(hits, key=lambda hit: (hit['score'], hit['id']))
        assert (row['status'] == 'zero_hit') is (len(hits) == 0)
    else:
        assert row['status'] == 'ok' and row['total_hits'] is None
        assert len(row['ranked_hits']) == len(set(row['ranked_hits'])) == len(docs)
        assert set(row['ranked_hits']) == set(docs) and ids == row['ranked_hits'][:TOP_K]
    return row


def rank_step(root, task, engine, manifest_sha, docs, native, reference, tokenizer):
    path = root / 'rankings' / (task['id'] + '-' + engine + '.json')
    pending = path.with_name(path.stem + '-pending.json')
    identity = ranking_identity(task, engine, manifest_sha)
    if path.exists():
        return validate_ranking(read_json(path), task, engine, manifest_sha, docs, tokenizer)
    row = {'identity': identity, 'task_id': task['id'], 'engine': engine, 'status': 'fault',
           'candidates': [], 'ranked_hits': [], 'total_hits': None, 'native_terms': None,
           'match_expression': None, 'normalization_seconds': None, 'timings_seconds': [], 'error': None}
    if pending.exists():
        assert read_json(pending)['identity'] == identity
        row['error'] = {'phase': 'ranking', 'class': 'interrupted_ranking_unknown'}
    else:
        save(pending, {'identity': identity})
        try:
            if engine in NATIVE:
                if native is None: raise RuntimeError('native_index_unavailable')
                if tokenizer is None: raise RuntimeError('native_tokenizer_unavailable')
                started = time.perf_counter()
                terms = tokenizer.terms(task['query'])
                expression = literal_terms(terms, NATIVE[engine][1])
                row.update(native_terms=terms, match_expression=expression,
                           normalization_seconds=time.perf_counter() - started)
                invoke = lambda: native.rank(engine, expression)
            else:
                if reference is None: raise RuntimeError('reference_index_unavailable')
                invoke = lambda: reference.rank(task['query'], engine)
            first = invoke()  # fixed untimed warm-up
            for _ in range(REPEATS):
                started = time.perf_counter()
                result = invoke()
                row['timings_seconds'].append(time.perf_counter() - started)
                assert result == first, 'Repeated native/reference ranking disagreement'
            row['ranked_hits'] = first
            row['candidates'] = ([hit['id'] for hit in first] if engine in NATIVE else first)[:TOP_K]
            row['total_hits'] = len(first) if engine in NATIVE else None
            row['status'] = 'zero_hit' if engine in NATIVE and not first else 'ok'
        except Exception as exception:
            row.update(status='fault', candidates=[], ranked_hits=[], total_hits=None,
                       error=error_info(exception, 'ranking'))
    row = seal(row)
    validate_ranking(row, task, engine, manifest_sha, docs, tokenizer)
    save(path, row)
    if pending.exists(): pending.unlink()
    return row


def blank_score():
    return {'declared_span_bundle_recovered': False, 'declared_whole_bundle_recovered': False,
            'best_declared_span_fraction': 0.0, 'observed_original_ids': []}


def packet_identity(cell, ranking, manifest_sha):
    return object_sha({'cell': cell, 'ranking_sha256': ranking['checkpoint_sha256'], 'manifest_sha256': manifest_sha})


def validate_packet(row, cell, ranking, manifest_sha, docs, gold):
    check_seal(row)
    assert row['identity'] == packet_identity(cell, ranking, manifest_sha)
    assert all(type(row[k]) is type(v) and row[k] == v for k, v in cell.items())
    assert type(row['fault']) is bool and row['ranking_status'] == ranking['status']
    candidate = ranking['status'] != 'fault' and any(set(bundle) <= set(ranking['candidates']) for bundle in gold['evidence_sets'])
    assert row['candidate_original_id_bundle_recovered'] is candidate
    if row['fault']:
        assert row['packet'] is None and row['error'] is not None
        score = blank_score()
    else:
        assert ranking['status'] != 'fault' and row['error'] is None
        packet = row['packet']
        score = support_metrics(gold, packet['observations'], docs)
        assert type(packet['bytes']) is int and packet['bytes'] == len(packet['packet'].encode('utf8')) <= cell['budget']
        assert packet['packet'] == '\n\n'.join(packing_lab._piece(docs[o['id']], o, cell['packer'] == 'whole_record') for o in packet['observations'])
        assert all(o['whole'] is (o['start'] == 0 and o['end'] == len(docs[o['id']]['body'])) for o in packet['observations'])
        selected = list(dict.fromkeys(o['id'] for o in packet['observations']))
        assert packet['ids'] == packet['selected_ids'] == selected
        receipt = packet['receipt']
        assert receipt['packet_sha256'] == sha(packet['packet']) and receipt['ranked_ids'] == ranking['candidates']
        assert receipt['method'] == cell['packer'] and receipt['budget'] == cell['budget']
        assert receipt['span_count'] == len(packet['observations'])
    for key, value in score.items():
        assert type(row[key]) is type(value) and row[key] == value
    selected_bundle = not row['fault'] and any(set(bundle) <= set(score['observed_original_ids']) for bundle in gold['evidence_sets'])
    assert row['selected_original_id_bundle_recovered'] is selected_bundle
    if ranking['status'] == 'zero_hit' and not row['fault']:
        assert row['packet']['bytes'] == 0 and row['packet']['observations'] == []
    return row


def packet_step(root, cell, task, ranking, manifest_sha, docs, gold):
    path = root / 'packets' / (object_sha(cell) + '.json')
    pending = path.with_name(path.stem + '-pending.json')
    identity = packet_identity(cell, ranking, manifest_sha)
    if path.exists():
        return validate_packet(read_json(path), cell, ranking, manifest_sha, docs, gold)
    row = {'identity': identity, **cell, **blank_score(), 'ranking_status': ranking['status'],
           'fault': True, 'packet': None, 'error': None, 'packing_seconds': None,
           'selected_original_id_bundle_recovered': False,
           'candidate_original_id_bundle_recovered': ranking['status'] != 'fault' and any(
               set(bundle) <= set(ranking['candidates']) for bundle in gold['evidence_sets'])}
    if pending.exists():
        assert read_json(pending)['identity'] == identity
        row['error'] = {'phase': 'packing', 'class': 'interrupted_packet_unknown'}
    elif ranking['status'] == 'fault':
        row['error'] = {'phase': 'ranking', 'class': ranking['error']['class']}
    else:
        save(pending, {'identity': identity})
        try:
            started = time.perf_counter()
            packet = packing_lab.pack(docs, task['query'], ranking['candidates'], cell['budget'], cell['packer'])
            row['packing_seconds'] = time.perf_counter() - started
            score = support_metrics(gold, packet['observations'], docs)
            row.update(**score, fault=False, packet=packet,
                       selected_original_id_bundle_recovered=any(set(bundle) <= set(score['observed_original_ids']) for bundle in gold['evidence_sets']))
            validate_packet(seal(row), cell, ranking, manifest_sha, docs, gold)
        except Exception as exception:
            row.update(**blank_score(), fault=True, packet=None, selected_original_id_bundle_recovered=False,
                       error=error_info(exception, 'packing_or_source_validation'))
    row = seal(row)
    validate_packet(row, cell, ranking, manifest_sha, docs, gold)
    save(path, row)
    if pending.exists(): pending.unlink()
    return row


def run(args):
    root, _ = verified(args)
    manifest_sha = file_sha(root / 'manifest.json')
    assert not (root / 'run-complete.json').exists(), 'Completed grid cannot be silently rerun'
    if (root / 'run-started.json').exists():
        assert args.resume, 'Existing stage needs explicit --resume'
        assert read_json(root / 'run-started.json')['manifest_sha256'] == manifest_sha
    else:
        save(root / 'run-started.json', {'started_at': now(), 'manifest_sha256': manifest_sha})
    docs, tasks, gold = load_dev(args.development_bank)
    started = time.perf_counter()
    native, reference = build_indexes(root, docs, args.resume)
    clock, tokenizer = time.perf_counter(), None
    previous_tokenizer_path = root / 'tokenizer-preparation-resumed.json'
    if not previous_tokenizer_path.exists(): previous_tokenizer_path = root / 'tokenizer-preparation.json'
    previous_tokenizer = read_json(previous_tokenizer_path) if previous_tokenizer_path.exists() else None
    if previous_tokenizer is not None: check_seal(previous_tokenizer)
    if previous_tokenizer is not None and previous_tokenizer['status'] == 'fault':
        tokenizer_receipt = previous_tokenizer
    else:
        try:
            tokenizer = NativeTokenizer()
            tokenizer_receipt = seal({'status': 'ok', 'seconds': time.perf_counter() - clock, 'error': None})
        except Exception as exception:
            tokenizer_receipt = seal({'status': 'fault', 'seconds': time.perf_counter() - clock,
                                       'error': error_info(exception, 'tokenizer_preparation')})
    save(root / ('tokenizer-preparation-resumed.json' if args.resume else 'tokenizer-preparation.json'),
         tokenizer_receipt)
    count = 0
    try:
        for task in tasks:
            for engine in ENGINES:
                ranking = rank_step(root, task, engine, manifest_sha, docs, native, reference, tokenizer)
                for packer in PACKERS:
                    for budget in BUDGETS:
                        cell = {'task_id': task['id'], 'history': task['history'], 'template_group': task['template_group'],
                                'engine': engine, 'packer': packer, 'budget': budget}
                        packet_step(root, cell, task, ranking, manifest_sha, docs, gold[task['id']])
                        count += 1
            print(canonical({'completed_tasks': count // 36, 'packets': count}), flush=True)
    finally:
        if tokenizer is not None: tokenizer.close()
        if native is not None: native.close()
    assert count == 2592
    save(root / 'run-complete.json', seal({'completed_at': now(), 'manifest_sha256': manifest_sha,
        'packets': count, 'current_execution_wall_seconds': time.perf_counter() - started, 'resumed_execution': bool(args.resume)}))


def numeric_summary(values, scheduled):
    values = [x for x in values if isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x) and x >= 0]
    return {'reported': len(values), 'missing': scheduled - len(values), 'sum': sum(values) if values else None,
            'median': statistics.median(values) if values else None, 'minimum': min(values) if values else None,
            'maximum': max(values) if values else None}


def outcome_groups(rows):
    groups = defaultdict(list)
    for row in rows: groups[(row['engine'], row['packer'], row['budget'])].append(row)
    result = []
    for key, cells in sorted(groups.items()):
        free = [r for r in cells if not r['fault']]
        result.append({'engine': key[0], 'packer': key[1], 'budget': key[2], 'scheduled': len(cells),
            'faults': sum(r['fault'] for r in cells), 'zero_hit_workflows': sum(r['ranking_status'] == 'zero_hit' for r in cells),
            'exact_span_bundle_recovered': sum(r['declared_span_bundle_recovered'] for r in cells),
            'mean_best_span_fraction': sum(r['best_declared_span_fraction'] for r in cells) / len(cells),
            'selected_original_id_bundle_recovered': sum(r['selected_original_id_bundle_recovered'] for r in cells),
            'whole_source_bundle_recovered': sum(r['declared_whole_bundle_recovered'] for r in cells),
            'candidate_top32_original_id_bundle_recovered': sum(r['candidate_original_id_bundle_recovered'] for r in cells),
            'fault_free_diagnostic': {'workflows': len(free), 'exact_span_bundle_recovered': sum(r['declared_span_bundle_recovered'] for r in free)}})
    return result


def safe_error(error):
    return {k: v for k, v in error.items() if k != 'private_message'} if error else None


def aggregate(args):
    root, frozen = verified(args)
    manifest_sha = file_sha(root / 'manifest.json')
    complete = read_json(root / 'run-complete.json')
    check_seal(complete)
    assert complete['packets'] == 2592 and complete['manifest_sha256'] == manifest_sha
    docs, tasks, gold = load_dev(args.development_bank)
    task_map = {t['id']: t for t in tasks}
    rankings = [read_json(p) for p in sorted((root / 'rankings').glob('*.json')) if not p.stem.endswith('-pending')]
    packets = [read_json(p) for p in sorted((root / 'packets').glob('*.json')) if not p.stem.endswith('-pending')]
    assert len(rankings) == 432 and len(packets) == 2592
    tokenizer_path = root / ('tokenizer-preparation-resumed.json' if complete['resumed_execution'] else 'tokenizer-preparation.json')
    tokenizer_receipt = read_json(tokenizer_path)
    check_seal(tokenizer_receipt)
    tokenizer = NativeTokenizer() if tokenizer_receipt['status'] == 'ok' else None
    try:
        rank_map = {}
        for row in rankings:
            key = row['task_id'], row['engine']
            assert key not in rank_map and key[1] in ENGINES
            validate_ranking(row, task_map[key[0]], key[1], manifest_sha, docs, tokenizer)
            rank_map[key] = row
        cells = set()
        for row in packets:
            task = task_map[row['task_id']]
            assert row['packer'] in PACKERS and row['budget'] in BUDGETS
            cell = {'task_id': task['id'], 'history': task['history'], 'template_group': task['template_group'],
                    **{key: row[key] for key in ('engine', 'packer', 'budget')}}
            key = object_sha(cell)
            assert key not in cells
            cells.add(key)
            validate_packet(row, cell, rank_map[(task['id'], row['engine'])], manifest_sha, docs, gold[task['id']])
    finally:
        if tokenizer is not None: tokenizer.close()
    engine_summaries = []
    for engine in ENGINES:
        rows = [r for r in rankings if r['engine'] == engine]
        assert len(rows) == 72
        engine_summaries.append({'engine': engine, 'scheduled_queries': 72,
            'ranking_faults': sum(r['status'] == 'fault' for r in rows),
            'zero_hit_queries': sum(r['status'] == 'zero_hit' for r in rows),
            'candidate_count': numeric_summary([len(r['candidates']) if r['status'] != 'fault' else None for r in rows], 72),
            'normalization_seconds': numeric_summary([r['normalization_seconds'] for r in rows], 72),
            'warm_ranking_seconds': numeric_summary([t for r in rows for t in r['timings_seconds']], 72 * REPEATS),
            'fault_classes': dict(Counter(r['error']['class'] for r in rows if r['status'] == 'fault'))})
    native_build = read_json(root / 'native-build.json')
    reference_build = read_json(root / 'reference-preparation.json')
    check_seal(native_build)
    check_seal(reference_build)
    native_build['error'], reference_build['error'] = safe_error(native_build['error']), safe_error(reference_build['error'])
    native_build.pop('checkpoint_sha256', None)
    reference_build.pop('checkpoint_sha256', None)
    reopen_path = root / ('native-reopen-resumed.json' if complete['resumed_execution'] else 'native-reopen.json')
    if not reopen_path.exists(): reopen_path = root / 'native-reopen.json'
    reopen = read_json(reopen_path) if reopen_path.exists() else {'status': 'unavailable', 'error': None}
    if 'checkpoint_sha256' in reopen:
        check_seal(reopen)
        reopen.pop('checkpoint_sha256')
    reopen['error'] = safe_error(reopen['error'])
    tokenizer_receipt['error'] = safe_error(tokenizer_receipt['error'])
    tokenizer_receipt.pop('checkpoint_sha256')
    resumed_reference = read_json(root / 'reference-preparation-resumed.json') if (root / 'reference-preparation-resumed.json').exists() else None
    if resumed_reference is not None:
        check_seal(resumed_reference)
        resumed_reference.pop('checkpoint_sha256')
        resumed_reference['error'] = safe_error(resumed_reference['error'])
    result = {'schema_version': 1, 'scope': 'development-only SQLite FTS5 supplement', 'status': 'complete',
        'provider_calls': 0, 'main_experiment_changed': False, 'confirmation_claim': False,
        'manifest_sha256': manifest_sha, 'frozen_material': {k: v for k, v in frozen['material'].items() if k != 'schedule'},
        'sample': {'histories': 24, 'tasks': 72, 'records': 276, 'ranking_jobs': 432, 'packets': 2592},
        'index_preparation': {'native_build': native_build, 'native_reopen': reopen, 'reference_build': reference_build,
                              'reference_resumed_preparation': resumed_reference,
                              'tokenizer_setup': tokenizer_receipt},
        'engine_diagnostics': engine_summaries, 'all_scheduled_workflows': outcome_groups(packets),
        'failures': {'ranking_faults': sum(r['status'] == 'fault' for r in rankings),
            'packet_faults': sum(r['fault'] for r in packets),
            'zero_hit_queries': sum(r['status'] == 'zero_hit' for r in rankings),
            'zero_hit_workflows': sum(r['ranking_status'] == 'zero_hit' for r in packets),
            'packet_error_phases': dict(Counter(r['error']['phase'] for r in packets if r['fault']))},
        'packing_seconds': numeric_summary([r['packing_seconds'] for r in packets], 2592),
        'execution': complete,
        'sources': read_json(HERE / 'native-index-sources.json')['sources'],
        'limitations': ['Development only; no confirmation, answer-quality or main-winner inference.',
            'Native and reference tokenization, hit predicates and scoring differ; no algorithm-equivalence claim.',
            'Small serial warm repetitions on a shared host; no causal latency/hardware claim.',
            'Faults remain failed scheduled workflows; zero hits are never filled with unrelated IDs.']}
    save(HERE / 'native-index-results.json', result)
    print(canonical({'status': 'aggregated', 'public_result_sha256': file_sha(HERE / 'native-index-results.json'),
                     'faults': result['failures']['packet_faults'], 'zero_hit_queries': result['failures']['zero_hit_queries']}))


def self_check():
    def record(identifier, body, revision=1):
        return {'id': identifier, 'revision': revision, 'body': body, 'scope': 'all', 'kind': 'source',
                'title': 'fixture', 'aliases': [], 'links': [], 'supersedes': [], 'incorporates': []}
    tokenizer = NativeTokenizer()
    assert tokenizer.terms('Café, 青灯; v1.2 OR and') == ['cafe', '青灯', 'v1', '2', 'or', 'and']
    assert tokenizer.terms('?!') == [] and literal_terms([], 'OR') is None
    assert literal_terms(['a"b'], 'OR') == '"a""b"'
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        first = record('D1', 'Café 青灯 oldtoken and ordinary rule')
        second = record('D2', 'deleteonly OR injection keyword')
        path = root / 'native.sqlite'
        NativeIndex.create(path, [first, second])
        reopened = NativeIndex(path)
        reopened.validate_sources([first, second])
        expression = literal_terms(tokenizer.terms('Café 青灯'), 'AND')
        assert [h['id'] for h in reopened.rank('fts_body_and', expression)] == ['D1']
        assert reopened.rank('fts_body_or', literal_terms(['notpresentzx'], 'OR')) == []
        injection = "'; DROP TABLE sources; -- OR \"x\""
        hits = reopened.rank('fts_body_or', literal_terms(tokenizer.terms(injection), 'OR'))
        assert [h['id'] for h in hits] == ['D2']
        reopened.validate_sources([first, second])
        reopened.close()
        try:
            NativeIndex.create(root / 'duplicate.sqlite', [first, first])
        except ValueError:
            pass
        else:
            raise AssertionError('Duplicate source IDs accepted')
        assert not (root / 'duplicate.sqlite').exists()
        revised = record('D1', 'Café 青灯 newtoken revised rule', 2)
        writer = NativeIndex(path, readonly=False)
        writer.update_delete([revised], ['D2'])
        writer.validate_sources([revised])
        try:
            writer.update_delete([record('D1', 'uncommittedtoken', 3)], ['missing'])
        except ValueError:
            pass
        else:
            raise AssertionError('Missing deletion silently accepted')
        writer.validate_sources([revised])
        writer.close()
        reopened = NativeIndex(path)
        reopened.validate_sources([revised])
        for engine in NATIVE:
            assert [h['id'] for h in reopened.rank(engine, literal_terms(['newtoken'], NATIVE[engine][1]))] == ['D1']
            for term in ('oldtoken', 'deleteonly', 'uncommittedtoken'):
                assert reopened.rank(engine, literal_terms([term], NATIVE[engine][1])) == []
        reopened.close()
        docs = {'D1': revised}
        task = {'id': 'T', 'query': 'newtoken', 'history': 'H', 'template_group': 'fictional'}
        manifest = '0' * 64
        rank_identity = ranking_identity(task, 'fts_body_or', manifest)
        save(root / 'rankings' / 'T-fts_body_or-pending.json', {'identity': rank_identity})
        fault = rank_step(root, task, 'fts_body_or', manifest, docs, None, None, tokenizer)
        assert fault['status'] == 'fault' and fault['error']['class'] == 'interrupted_ranking_unknown'
        assert rank_step(root, task, 'fts_body_or', manifest, docs, None, None, tokenizer) == fault
        ranking = seal({'identity': ranking_identity(task, 'body_bm25', manifest), 'task_id': 'T', 'engine': 'body_bm25',
            'status': 'ok', 'candidates': ['D1'], 'ranked_hits': ['D1'], 'total_hits': None,
            'native_terms': None, 'match_expression': None, 'normalization_seconds': None,
            'timings_seconds': [0.0, 0.0, 0.0], 'error': None})
        validate_ranking(ranking, task, 'body_bm25', manifest, docs, tokenizer)
        gold = {'evidence_sets': [['D1']], 'evidence_spans': [[{'id': 'D1', 'start': 0, 'end': 5}]]}
        cell = {'task_id': 'T', 'history': 'H', 'template_group': 'fictional', 'engine': 'body_bm25',
                'packer': 'whole_record', 'budget': 2000}
        packet = packet_step(root, cell, task, ranking, manifest, docs, gold)
        assert not packet['fault'] and packet['declared_span_bundle_recovered']
        changed = copy.deepcopy(packet)
        changed['packet']['observations'][0]['text'] = 'altered'
        changed = seal({k: v for k, v in changed.items() if k != 'checkpoint_sha256'})
        try:
            validate_packet(changed, cell, ranking, manifest, docs, gold)
        except AssertionError:
            pass
        else:
            raise AssertionError('Altered source observation accepted')
        assert numeric_summary([None], 1)['sum'] is None
    tokenizer.close()
    print('native_index_lab self-check passed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--stage', choices=('prepare', 'run', 'aggregate'))
    parser.add_argument('--development-bank', type=Path)
    parser.add_argument('--work', type=Path)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    assert args.stage and args.development_bank and args.work
    {'prepare': prepare, 'run': run, 'aggregate': aggregate}[args.stage](args)


if __name__ == '__main__':
    main()
