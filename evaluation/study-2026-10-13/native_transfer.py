"""Prospective, model-free BEAM publisher-message-ID transfer; private outputs.

Doctor/prepare do not rank. Run/aggregate require exact root clearance.
The single self-check uses fictional SQLite/packing fixtures, never BEAM ranks.
"""
import argparse
from collections import Counter, defaultdict
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from statistics import median
import sys
import tempfile
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REUSED = {
    'external_eval.py': '8dd02fc85d47915e1732f80f3c012c14d99d01d086515501fd7f58fa835a67f5',
    'external_probe.py': 'cdb10212822f617fd9087701ed18a7085d75db7e14a1856f26505820c605d72b',
    'native_index_lab.py': '7382bd47522dd514468e8ff316955bac7388b9133b790d0b245c2efca60707bf',
    'index_lab.py': 'e469b8ac206cdf24b294a15df278ae8f1e3b5f624509b72923486c5b6760f9d8',
    'packing_lab.py': '646f250eaeb5c1e453077d5666ae9afbe253c447ac092233bb05fc1eda07477c',
    'artifact_contract.py': '208860f54a38b69539f057c0a9a993fc82e65b771555d78c79b6116e7e8dc9a6',
    'study_common.py': 'ee7d7930801aa8fbc94d5417484f0bb08ba1003e52b43982fcdae2f392cbefb2',
}


def require(value, code):
    if not value:
        raise ValueError(code)


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


for _name, _pin in REUSED.items():
    require(file_hash(HERE / _name) == _pin, 'reused_source_changed:' + _name)
import external_eval as external
import native_index_lab as lab
import packing_lab

ENGINES = ('fts_body_or', 'fts_search_or', 'body_bm25', 'search_bm25')
PACKERS, BUDGETS = ('whole_record', 'sentence_neighbors'), (4096, 8192, 16384)
OWN = ('NATIVE-TRANSFER-PLAN.md', 'native_transfer.py', 'native-transfer-sources.json')


def classify(row, category, docs):
    # This is mechanical publisher-label availability, never semantic validation.
    try:
        groups = external.criteria(row.get('source_chat_ids', []))
    except (AssertionError, TypeError, ValueError):
        return 'malformed_criterion_group', {}, set(), 'invalid_support_shape'
    required = set().union(*groups.values())
    if not required <= set(docs):
        return 'malformed_criterion_group', groups, required, 'unresolved_support_ids'
    if category == 'abstention':
        require(not required, 'unexpected_abstention_support')
        return 'unlabeled_abstention', groups, required, 'unlabeled_abstention'
    if not required:
        return 'missing_non_abstention_support', groups, required, 'empty_non_abstention_support'
    if not all(groups.values()):
        return 'malformed_criterion_group', groups, required, 'empty_criterion_group'
    return 'valid_positive', groups, required, None


def load_histories(root):
    ledger = lab.read_json(HERE / 'native-transfer-sources.json')
    require(ledger['dataset']['revision'] == 'b2da22eac88bb0874c64665f13457eb99835774a', 'dataset_revision')
    selection = ledger['selection']
    ordered = sorted(selection['candidate_paths'], key=lambda path: (
        hashlib.sha256((selection['selection_seed'] + path).encode()).hexdigest(), path))
    require(len(ordered) == 20 and len(set(ordered)) == 20, 'candidate_frame')
    require(ordered[:5] == selection['excluded_original_five'] and ordered[5:25] == selection['selected_paths'], 'selection_changed')
    tree_path = root / 'tree-pinned.json'
    require(file_hash(tree_path) == ledger['dataset']['tree']['sha256'], 'pinned_tree_changed')
    tree = lab.read_json(tree_path)
    require(not tree['truncated'] and tree['sha'] == ledger['dataset']['revision'], 'incomplete_tree')
    tree_files = {row['path']: row for row in tree['tree'] if row['type'] == 'blob'}
    require(sorted(path for path in tree_files if path.startswith('chats/100K/') and path.endswith('/chat.json')) == sorted(ordered), 'tree_frame_changed')
    for entry in ledger['files']:
        path = (root / entry['local_relative']).resolve()
        require(path.is_relative_to(root) and path.is_file(), 'data_path_missing_or_escaped')
        data = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        require(len(data) == entry['bytes'] and hashlib.sha256(data).hexdigest() == entry['sha256'], 'data_fixity_changed')
        require(blob == entry['git_blob_sha1'] == tree_files[entry['upstream_path']]['sha'], 'publisher_blob_changed')
    entries = {entry['upstream_path']: entry for entry in ledger['files']}
    def read_source(relative):
        entry = entries[relative]
        data = (root / entry['local_relative']).read_bytes()
        require(hashlib.sha256(data).hexdigest() == entry['sha256'] and len(data) == entry['bytes'], 'source_changed_before_projection')
        return lab.strict_json(data.decode('utf8'))
    for n, path in enumerate(selection['selected_paths'], 1):
        history = f'NT{n:02d}'
        docs = external.project(read_source(path))
        raw = read_source(path.removesuffix('chat.json') + 'probing_questions/probing_questions.json')
        queries = []
        for category in sorted(raw):
            require(isinstance(category, str) and isinstance(raw[category], list), 'question_category_shape')
            for ordinal, row in enumerate(raw[category], 1):
                query = row['question']
                require(isinstance(query, str) and query.strip(), 'question_shape')
                query.encode('utf8')
                status, groups, required, code = classify(row, category, docs)
                label = {'status': status, 'code': code,
                         'groups': {key: sorted(value) for key, value in groups.items()}}
                queries.append({'id': history + f'Q{len(queries)+1:02d}', 'query': query,
                    'category': category, 'ordinal': ordinal, 'label_status': status,
                    'label_code': code, 'groups': groups, 'required': required,
                    'label_sha256': lab.object_sha(label)})
        require(len(queries) == 20, 'question_count_changed')
        yield {'history': history, 'upstream_path': path, 'docs': docs, 'queries': queries}


def audit(histories):
    output, totals = [], Counter()
    for history in histories:
        queries, docs = history['queries'], history['docs']
        counts = Counter(query['label_status'] for query in queries)
        totals.update(counts)
        output.append({'history': history['history'], 'upstream_path': history['upstream_path'],
            'messages': len(docs), 'questions_available': len(queries), 'label_availability': dict(counts),
            'source_projection_sha256': external.sha(docs),
            'query_projection_sha256': lab.object_sha([{'id': q['id'], 'query': q['query']} for q in queries]),
            'labels_projection_sha256': lab.object_sha([{'id': q['id'], 'label_sha256': q['label_sha256']} for q in queries]),
            'non_abstention_schedule': [{'id': q['id'], 'query_sha256': lab.sha(q['query']),
                'label_status': q['label_status'], 'label_sha256': q['label_sha256']}
                for q in queries if q['label_status'] != 'unlabeled_abstention'],
            'category_nominal': dict(Counter(q['category'] for q in queries if q['category'] != 'abstention')),
            'category_valid': dict(Counter(q['category'] for q in queries if q['label_status'] == 'valid_positive'))})
    require(len(output) == 15 and dict(totals) == {'unlabeled_abstention': 30, 'valid_positive': 264,
        'missing_non_abstention_support': 5, 'malformed_criterion_group': 1}, 'frozen_label_census_changed')
    return {'histories': output, 'questions_available': 300, 'label_availability': dict(totals),
            'nominal_queries': 270, 'valid_positive_queries': 264, 'ranking_jobs': 1080,
            'label_unscorable_ranking_jobs': 24, 'packet_rows': 6480, 'label_unscorable_packet_rows': 144}


def material(root):
    return {'source_audit': audit(load_histories(root)), 'code_pins': {name: file_hash(HERE / name) for name in (*OWN, *REUSED)},
        'runtime': lab.runtime(), 'engines': list(ENGINES), 'packers': list(PACKERS), 'budgets': list(BUDGETS),
        'top_k': lab.TOP_K, 'tokenizer': lab.TOKENIZER, 'warmups': 1, 'repeats': lab.REPEATS, 'workers': 1}, None


def prepare(root):
    require(not (root / 'manifest.json').exists() and not (root / 'run-started.json').exists(), 'manifest_already_exists')
    value, _ = material(root)
    lab.save(root / 'manifest.json', {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'material': value, 'scoring_started': False, 'state': 'PROSPECTIVE_ROOT_REVIEW_PENDING'})
    return {'state': 'PROSPECTIVE_ROOT_REVIEW_PENDING', 'manifest_sha256': file_hash(root / 'manifest.json'), 'provider_calls': 0}


def clearance(root, manifest_sha):
    require(isinstance(manifest_sha, str) and file_hash(root / 'manifest.json') == manifest_sha, 'manifest_hash_required_or_changed')
    saved = lab.read_json(root / 'manifest.json')
    current, _ = material(root)
    require(saved['material'] == current, 'source_code_runtime_or_schedule_changed')
    reviewed = lab.read_json(root / 'review-clearance.json')
    require(reviewed.get('approved') is True and reviewed.get('manifest_sha256') == manifest_sha, 'exact_root_clearance_required')
    return load_histories(root)


def ranking(root, query, engine, manifest_sha, docs, native, reference, tokenizer):
    task = {'id': query['id'], 'query': query['query']}
    if query['label_status'] == 'valid_positive':
        return lab.rank_step(root, task, engine, manifest_sha, docs, native, reference, tokenizer)
    path = root / 'rankings' / (query['id'] + '-' + engine + '.json')
    identity = lab.ranking_identity(task, engine, manifest_sha)
    row = lab.seal({'identity': identity, 'task_id': query['id'], 'engine': engine,
        'status': 'label_unscorable', 'label_sha256': query['label_sha256'], 'label_code': query['label_code'],
        'candidates': [], 'ranked_hits': [], 'retrieval_attempted': False})
    if path.exists():
        require(lab.read_json(path) == row, 'cached_unscorable_ranking_changed')
    else:
        lab.save(path, row)
    return row


def validate_ranking(row, query, engine, manifest_sha, docs, tokenizer):
    if query['label_status'] == 'valid_positive':
        return lab.validate_ranking(row, {'id': query['id'], 'query': query['query']}, engine, manifest_sha, docs, tokenizer)
    lab.check_seal(row)
    require(row['identity'] == lab.ranking_identity({'id': query['id'], 'query': query['query']}, engine, manifest_sha), 'unscorable_rank_identity')
    require(row['task_id'] == query['id'] and row['engine'] == engine, 'unscorable_rank_fields_changed')
    require(row['status'] == 'label_unscorable' and row['retrieval_attempted'] is False and row['candidates'] == row['ranked_hits'] == [], 'unscorable_rank_state')
    require(row['label_sha256'] == query['label_sha256'] and row['label_code'] == query['label_code'], 'unscorable_label_changed')
    return row


def order_ids(row):
    return [hit['id'] for hit in row['ranked_hits']] if row['engine'].startswith('fts_') else row['ranked_hits']


def packet_identity(cell, rank, query, manifest_sha):
    return lab.object_sha({'cell': cell, 'ranking_sha256': rank['checkpoint_sha256'],
        'label_sha256': query['label_sha256'], 'manifest_sha256': manifest_sha})


def bundle_diagnostic(query, docs, cell):
    if query['label_status'] != 'valid_positive':
        return None
    cost = sum(external.whole_cost(docs[identifier], cell['packer'] == 'whole_record')
        for identifier in query['required']) + 2 * (len(query['required']) - 1)
    return {'required_bundle_bytes': cost, 'whole_feasible': cost <= cell['budget'],
        'kind': 'exact_whole_wrapper_cost' if cell['packer'] == 'whole_record' else 'optimistic_single_body_lean_wrapper_lower_bound'}


def validate_packet(row, cell, query, rank, manifest_sha, docs):
    lab.check_seal(row)
    require(row['identity'] == packet_identity(cell, rank, query, manifest_sha), 'packet_identity_changed')
    require(all(row[key] == value for key, value in cell.items()) and row['label_status'] == query['label_status'], 'packet_cell_changed')
    require(row['ranking_status'] == rank['status'], 'packet_ranking_state_changed')
    require(lab.canonical(row['bundle_diagnostic']) == lab.canonical(bundle_diagnostic(query, docs, cell)), 'bundle_diagnostic_changed')
    status = row['status']
    if query['label_status'] != 'valid_positive':
        require(status == 'label_unscorable' and row['metrics'] is None and row['packet'] is None,
            'unscorable_has_invented_metric')
        require(row['error'] == {'phase': 'publisher_label', 'class': query['label_code']}, 'unscorable_reason_changed')
    elif status == 'ok':
        packet = row['packet']
        require(rank['status'] in ('ok', 'zero_hit') and row['error'] is None, 'measured_packet_rank_fault')
        require(type(packet['bytes']) is int and packet['bytes'] == len(packet['packet'].encode('utf8')) <= cell['budget'], 'packet_bytes_changed')
        require(packet['receipt']['ranked_ids'] == rank['candidates'] and packet['receipt']['method'] == cell['packer']
            and packet['receipt']['budget'] == cell['budget'], 'packet_candidate_or_method_changed')
        require(packet['ids'] == packet['selected_ids'] == list(dict.fromkeys(o['id'] for o in packet['observations'])), 'packet_ids_changed')
        require(all(o['whole'] is (o['start'] == 0 and o['end'] == len(docs[o['id']]['body'])) for o in packet['observations']), 'packet_whole_flag_changed')
        measure = external.measure(query, docs, order_ids(rank), packet, cell['budget'])
        require(lab.canonical(row['metrics']) == lab.canonical(measure), 'packet_metric_changed')
        if rank['status'] == 'zero_hit':
            require(packet['bytes'] == 0 and packet['observations'] == [], 'zero_hit_tail_filled')
    else:
        require(status in ('retrieval_fault', 'packing_fault') and row['metrics'] is None
            and row['packet'] is None and isinstance(row['error'], dict), 'invalid_fault_row')
        require(status != 'retrieval_fault' or rank['status'] == 'fault', 'invented_retrieval_fault')
    return row


def packet_step(root, cell, query, rank, manifest_sha, docs):
    path = root / 'packets' / (lab.object_sha(cell) + '.json')
    pending = path.with_name(path.stem + '-pending.json')
    identity = packet_identity(cell, rank, query, manifest_sha)
    if path.exists():
        return validate_packet(lab.read_json(path), cell, query, rank, manifest_sha, docs)
    row = {'identity': identity, **cell, 'label_status': query['label_status'], 'ranking_status': rank['status'],
        'status': 'packing_fault', 'metrics': None, 'packet': None, 'packing_seconds': None, 'error': None,
        'bundle_diagnostic': bundle_diagnostic(query, docs, cell)}
    if query['label_status'] != 'valid_positive':
        row.update(status='label_unscorable', error={'phase': 'publisher_label', 'class': query['label_code']})
    elif pending.exists():
        require(lab.read_json(pending)['identity'] == identity, 'pending_packet_identity_changed')
        row['error'] = {'phase': 'packing', 'class': 'interrupted_packet_unknown'}
    elif rank['status'] == 'fault':
        row.update(status='retrieval_fault', error={'phase': 'ranking', 'class': rank['error']['class']})
    else:
        lab.save(pending, {'identity': identity})
        started = time.perf_counter()
        try:
            packet = packing_lab.pack(docs, query['query'], rank['candidates'], cell['budget'], cell['packer'])
            packing_seconds = time.perf_counter() - started
            metrics = external.measure(query, docs, order_ids(rank), packet, cell['budget'])
            row.update(status='ok', packet=packet, metrics=metrics, packing_seconds=packing_seconds)
            validate_packet(lab.seal(row), cell, query, rank, manifest_sha, docs)
        except Exception as error:
            row.update(status='packing_fault', packet=None, metrics=None, error=lab.error_info(error, 'packing_or_source_validation'))
    row = lab.seal(row)
    validate_packet(row, cell, query, rank, manifest_sha, docs)
    lab.save(path, row)
    if pending.exists():
        pending.unlink()
    return row


def build_step(root, docs, resume):
    # One history at a time bounds retained memory; larger corpora need a new protocol.
    path, pending = root / 'index-stage.json', root / 'index-stage-pending.json'
    identity = lab.object_sha(docs)
    if path.exists():
        row = lab.read_json(path); lab.check_seal(row)
        require(row['source_projection_sha256'] == identity, 'index_source_changed')
        if row['status'] == 'fault':
            return None, None
    elif pending.exists():
        require(lab.read_json(pending)['source_projection_sha256'] == identity, 'pending_index_source_changed')
        lab.save(path, lab.seal({'status': 'fault', 'source_projection_sha256': identity,
            'error': {'phase': 'history_index_preparation', 'class': 'interrupted_preparation_unknown'}}))
        return None, None
    else:
        lab.save(pending, {'source_projection_sha256': identity})
    native, reference = lab.build_indexes(root, docs, resume)
    if not path.exists():
        lab.save(path, lab.seal({'status': 'complete', 'source_projection_sha256': identity,
            'native_available': native is not None, 'reference_available': reference is not None}))
    if pending.exists():
        pending.unlink()
    return native, reference


def state_check(root, state):
    lab.check_seal(state)
    require(isinstance(state.get('recorded_file_sha256'), dict), 'invalid_checkpoint_ledger')
    for relative, expected in state['recorded_file_sha256'].items():
        path = (root / relative).resolve()
        require(path.is_relative_to(root) and path.is_file() and file_hash(path) == expected, 'recorded_checkpoint_changed')


def track(root, state, path, resume, recovered=False, refresh=False):
    relative = path.relative_to(root).as_posix()
    actual = file_hash(path)
    if relative in state['recorded_file_sha256']:
        old = state['recorded_file_sha256'][relative]
        if old != actual and refresh:
            archive = path.parent / 'receipt-history' / (old + '.json')
            require(resume and archive.is_file() and file_hash(archive) == old, 'preparation_refresh_without_archived_receipt')
            state.setdefault('preparation_refreshes', []).append({'path': relative, 'old_sha256': old, 'new_sha256': actual})
            state['recorded_file_sha256'][relative] = actual
        else:
            require(old == actual, 'cached_checkpoint_rewritten')
    else:
        state['recorded_file_sha256'][relative] = actual
        if recovered:
            require(resume, 'unlogged_cached_row_requires_resume')
            state.setdefault('recovered_after_interrupt', []).append(relative)
    lab.save(root / 'state.json', lab.seal(state))


def archive_resumed_receipts(root, state, folder, resume):
    if not resume: return
    for path in folder.glob('*-resumed.json'):
        old = file_hash(path)
        archive = folder / 'receipt-history' / (old + '.json')
        if not archive.exists():
            archive.parent.mkdir(exist_ok=True)
            archive.write_bytes(path.read_bytes())
        require(file_hash(archive) == old, 'archived_receipt_changed')
        track(root, state, archive, resume)


def track_preparation(root, state, folder, resume):
    for path in sorted(folder.iterdir()):
        if path.is_file() and (path.suffix == '.sqlite' or path.name in (
                'index-stage.json', 'index-stage-pending.json', 'native-build.json',
                'native-reopen.json', 'native-reopen-resumed.json', 'reference-preparation.json',
                'reference-preparation-resumed.json', 'tokenizer-preparation.json',
                'tokenizer-preparation-resumed.json', 'tokenizer-preparation-pending.json',
                'native-build-pending.json')):
            track(root, state, path, resume, refresh=path.name.endswith('-resumed.json'))


def tokenizer_step(root, manifest_sha, resume):
    path = root / ('tokenizer-preparation-resumed.json' if resume else 'tokenizer-preparation.json')
    prior = root / 'tokenizer-preparation-resumed.json'
    if not prior.exists(): prior = root / 'tokenizer-preparation.json'
    previous = lab.read_json(prior) if prior.exists() else None
    if previous is not None:
        lab.check_seal(previous)
        require(previous['manifest_sha256'] == manifest_sha, 'tokenizer_manifest_changed')
        if previous['status'] == 'fault': return None
    pending = root / 'tokenizer-preparation-pending.json'
    if pending.exists():
        require(lab.read_json(pending)['manifest_sha256'] == manifest_sha, 'pending_tokenizer_manifest_changed')
        lab.save(path, lab.seal({'status': 'fault', 'manifest_sha256': manifest_sha, 'seconds': None,
            'error': {'phase': 'tokenizer_preparation', 'class': 'interrupted_tokenizer_unknown'}}))
        return None
    lab.save(pending, {'manifest_sha256': manifest_sha})
    started = time.perf_counter(); tokenizer = None
    try:
        tokenizer = lab.NativeTokenizer()
        receipt = {'status': 'ok', 'manifest_sha256': manifest_sha, 'seconds': time.perf_counter()-started, 'error': None}
    except Exception as error:
        receipt = {'status': 'fault', 'manifest_sha256': manifest_sha, 'seconds': time.perf_counter()-started,
            'error': lab.error_info(error, 'tokenizer_preparation')}
    lab.save(path, lab.seal(receipt)); pending.unlink()
    return tokenizer


def run(root, manifest_sha, resume):
    histories = clearance(root, manifest_sha)
    expected = lab.read_json(root / 'manifest.json')['material']['source_audit']
    lock = root / 'coordinator.lock'
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf8') as stream:
            stream.write(lab.canonical({'pid': os.getpid(), 'manifest_sha256': manifest_sha})); stream.flush(); os.fsync(stream.fileno())
        state_path = root / 'state.json'
        if (root / 'run-started.json').exists():
            require(resume, 'explicit_resume_required')
            require(lab.read_json(root / 'run-started.json')['manifest_sha256'] == manifest_sha, 'started_manifest_changed')
        else:
            require(not resume, 'resume_without_started_stage')
            lab.save(root / 'run-started.json', {'manifest_sha256': manifest_sha, 'started_utc': lab.now()})
        if state_path.exists():
            state = lab.read_json(state_path); state_check(root, state)
            require(state['manifest_sha256'] == manifest_sha, 'state_manifest_changed')
            state.pop('checkpoint_sha256')
        else:
            state = {'manifest_sha256': manifest_sha, 'recorded_file_sha256': {}, 'recovered_after_interrupt': []}
        if (root / 'complete.json').exists():
            complete = lab.read_json(root / 'complete.json')
            require(resume and complete['manifest_sha256'] == manifest_sha
                and complete['state_sha256'] == file_hash(state_path), 'cached_completion_changed')
            print(lab.canonical({'state': 'CACHED_COMPLETION_RETAINED', 'packet_rows': expected['packet_rows']}))
            return
        archive_resumed_receipts(root, state, root, resume)
        tokenizer = tokenizer_step(root, manifest_sha, resume)
        track_preparation(root, state, root, resume)
        count = 0
        try:
            for history in histories:
                folder = root / 'histories' / history['history']; folder.mkdir(parents=True, exist_ok=True)
                archive_resumed_receipts(root, state, folder, resume)
                docs = history['docs']; native, reference = build_step(folder, docs, resume)
                track_preparation(root, state, folder, resume)
                try:
                    for query in history['queries']:
                        if query['label_status'] == 'unlabeled_abstention':
                            continue
                        for engine in ENGINES:
                            rank_path = folder / 'rankings' / (query['id'] + '-' + engine + '.json')
                            was_cached = rank_path.exists()
                            rank = ranking(folder, query, engine, manifest_sha, docs, native, reference, tokenizer)
                            track(root, state, rank_path, resume, recovered=was_cached)
                            for packer in PACKERS:
                                for budget in BUDGETS:
                                    cell = {'history': history['history'], 'task_id': query['id'], 'category': query['category'],
                                            'engine': engine, 'packer': packer, 'budget': budget}
                                    packet_path = folder / 'packets' / (lab.object_sha(cell) + '.json')
                                    was_cached = packet_path.exists()
                                    packet_step(folder, cell, query, rank, manifest_sha, docs)
                                    track(root, state, packet_path, resume, recovered=was_cached)
                                    count += 1
                finally:
                    if native is not None: native.close()
                    native = reference = docs = None
                print(lab.canonical({'history': history['history'], 'nominal_packet_rows': count}), flush=True)
        finally:
            if tokenizer is not None: tokenizer.close()
        require(count == expected['packet_rows'], 'packet_census')
        require(sum('/rankings/' in name for name in state['recorded_file_sha256']) == expected['ranking_jobs']
            and sum('/packets/' in name for name in state['recorded_file_sha256']) == expected['packet_rows'], 'engine_packet_identity_census')
        clearance(root, manifest_sha)  # Recheck inputs/code/runtime before completion, without ranking.
        lab.save(root / 'complete.json', {'manifest_sha256': manifest_sha, 'ranking_jobs': expected['ranking_jobs'],
            'packet_rows': expected['packet_rows'], 'state_sha256': file_hash(root / 'state.json'), 'completed_utc': lab.now()})
    except BaseException as error:
        lab.save(root / 'coordinator-failure.json', {'manifest_sha256': manifest_sha, 'error_class': type(error).__name__,
            'automatic_retry': False, 'meaning': 'Private completed/pending per-cell records retained; no invented result rows.'})
        raise
    finally:
        lock.unlink()


def preparation_states(root, history_ids):
    stages = [('tokenizer', 'coordinator', root, ('tokenizer-preparation.json', 'tokenizer-preparation-resumed.json'))]
    for history in history_ids:
        folder = root / 'histories' / history
        for phase, names in (
            ('index_stage', ('index-stage.json',)), ('native_build', ('native-build.json',)),
            ('native_reopen_source_integrity', ('native-reopen.json', 'native-reopen-resumed.json')),
            ('reference_preparation', ('reference-preparation.json', 'reference-preparation-resumed.json'))):
            stages.append((phase, history, folder, names))
    output = []
    for phase, scope, folder, names in stages:
        path = next((folder / name for name in reversed(names) if (folder / name).exists()), None)
        entry = {'phase': phase, 'scope': scope, 'status': 'not_reached', 'error_class': None}
        if path is not None:
            row = lab.read_json(path); lab.check_seal(row)
            require(row['status'] in ('ok', 'complete', 'fault'), 'invalid_preparation_status')
            entry.update(status=row['status'], error_class=(row.get('error') or {}).get('class'))
            for key in ('native_available', 'reference_available'):
                if key in row: entry[key] = row[key]
        output.append(entry)
    return output


def summarize(rows):
    valid = [row for row in rows if row['label_status'] == 'valid_positive']
    measured = [row for row in valid if row['status'] == 'ok']
    faults = len(valid) - len(measured)
    bounded = [key for key in external.METRICS if key in ('whole_bundle', 'whole_fraction', 'whole_group_fraction',
        'selected_bundle', 'selected_fraction', 'whole_feasible') or key.startswith('candidate_')]
    per_history = []
    for history in sorted({row['history'] for row in rows}):
        group = [row for row in valid if row['history'] == history]
        done = [row for row in group if row['status'] == 'ok']
        bounds = {key: [sum(float(row['metrics'][key]) for row in done)/len(group),
            (sum(float(row['metrics'][key]) for row in done)+len(group)-len(done))/len(group)]
            if group else None for key in bounded}
        per_history.append({'history': history, 'nominal_queries': sum(row['history'] == history for row in rows),
            'valid_queries': len(group), 'measured_queries': len(done), 'algorithm_faults': len(group)-len(done),
            'whole_bundle_verified_rate': sum(row['metrics']['whole_bundle'] for row in done)/len(group) if group else None,
            'fraction_boolean_fault_bounds': bounds,
            'fault_free_metric_means': {key: sum(float(row['metrics'][key]) for row in done)/len(done)
                if done else None for key in external.METRICS}})
    macro_bounds = {key: [sum(h['fraction_boolean_fault_bounds'][key][n] for h in per_history)/len(per_history)
        for n in (0, 1)] if per_history and all(h['valid_queries'] for h in per_history) else None for key in bounded}
    feasible = [row for row in valid if row['bundle_diagnostic']['whole_feasible']]
    feasible_measured = [row for row in feasible if row['status'] == 'ok']
    costs = [row['bundle_diagnostic']['required_bundle_bytes'] for row in valid]
    return {'nominal_queries': len(rows), 'valid_queries': len(valid), 'label_unscorable': len(rows)-len(valid),
        'measured_queries': len(measured), 'algorithm_faults': faults,
        'native_zero_hits': sum(row['ranking_status'] == 'zero_hit' for row in measured),
        'whole_bundle_verified_count': sum(row['metrics']['whole_bundle'] for row in measured),
        'whole_bundle_query_weighted_verified_rate': sum(row['metrics']['whole_bundle'] for row in measured)/len(valid) if valid else None,
        'whole_bundle_macro_history_verified_rate': sum(h['whole_bundle_verified_rate'] for h in per_history)/len(per_history) if per_history and all(h['valid_queries'] for h in per_history) else None,
        'fraction_boolean_query_weighted_fault_bounds': {key: [sum(float(row['metrics'][key]) for row in measured)/len(valid),
            (sum(float(row['metrics'][key]) for row in measured)+faults)/len(valid)] if valid else None for key in bounded},
        'fraction_boolean_macro_history_fault_bounds': macro_bounds,
        'fault_free_metric_means': {key: sum(float(row['metrics'][key]) for row in measured)/len(measured) if measured else None for key in external.METRICS},
        'fault_free_macro_history_metric_means': {key: sum(h['fault_free_metric_means'][key] for h in per_history
            if h['measured_queries'])/sum(bool(h['measured_queries']) for h in per_history)
            if any(h['measured_queries'] for h in per_history) else None for key in external.METRICS},
        'fault_free_macro_history_count': sum(bool(h['measured_queries']) for h in per_history),
        'bundle_cost_min_median_max': [min(costs), median(costs), max(costs)] if costs else None,
        'feasible_only_conditional': {'valid_scheduled_queries': len(feasible), 'measured_queries': len(feasible_measured),
            'algorithm_faults': len(feasible)-len(feasible_measured),
            'whole_bundle_verified_rate': sum(row['metrics']['whole_bundle'] for row in feasible_measured)/len(feasible) if feasible else None,
            'fault_free_whole_bundle_rate': sum(row['metrics']['whole_bundle'] for row in feasible_measured)/len(feasible_measured) if feasible_measured else None},
        'per_history': per_history}


def aggregate(root, manifest_sha):
    histories = clearance(root, manifest_sha)
    expected = lab.read_json(root / 'manifest.json')['material']['source_audit']
    complete = lab.read_json(root / 'complete.json'); state = lab.read_json(root / 'state.json'); state_check(root, state)
    require(complete['manifest_sha256'] == manifest_sha and complete['packet_rows'] == expected['packet_rows']
        and complete['ranking_jobs'] == expected['ranking_jobs'] and complete['state_sha256'] == file_hash(root / 'state.json'), 'completion_changed')
    rows, ranks = [], []
    tokenizer = lab.NativeTokenizer()
    try:
        for history in histories:
            folder = root / 'histories' / history['history']
            for query in history['queries']:
                if query['label_status'] == 'unlabeled_abstention': continue
                for engine in ENGINES:
                    rank = validate_ranking(lab.read_json(folder / 'rankings' / (query['id']+'-'+engine+'.json')),
                        query, engine, manifest_sha, history['docs'], tokenizer); ranks.append(rank)
                    for packer in PACKERS:
                        for budget in BUDGETS:
                            cell = {'history': history['history'], 'task_id': query['id'], 'category': query['category'],
                                    'engine': engine, 'packer': packer, 'budget': budget}
                            row = validate_packet(lab.read_json(folder / 'packets' / (lab.object_sha(cell)+'.json')),
                                cell, query, rank, manifest_sha, history['docs'])
                            rows.append({key: row[key] for key in ('history', 'task_id', 'category', 'engine', 'packer',
                                'budget', 'label_status', 'ranking_status', 'status', 'metrics', 'bundle_diagnostic')})
    finally:
        tokenizer.close()
    require(len(rows) == expected['packet_rows'] and len(ranks) == expected['ranking_jobs']
        and sum(row['status'] == 'label_unscorable' for row in rows) == expected['label_unscorable_packet_rows'], 'aggregate_census')
    cells, categories, paired = [], [], []
    for engine in ENGINES:
        for packer in PACKERS:
            for budget in BUDGETS:
                selected = [row for row in rows if (row['engine'], row['packer'], row['budget']) == (engine, packer, budget)]
                identity = {'engine': engine, 'packer': packer, 'budget': budget}
                cells.append({**identity, **summarize(selected)})
                for category in sorted({row['category'] for row in selected}):
                    categories.append({**identity, 'category': category, **summarize([row for row in selected if row['category'] == category])})
                reference = {row['task_id']: row for row in rows if (row['engine'], row['packer'], row['budget']) == ('body_bm25', packer, budget)}
                done = [(row, reference[row['task_id']]) for row in selected if row['status'] == 'ok' and reference[row['task_id']]['status'] == 'ok']
                differences = [int(a['metrics']['whole_bundle'])-int(b['metrics']['whole_bundle']) for a, b in done]
                per_history = []
                for history in sorted({row['history'] for row in selected}):
                    pairs = [(a, b) for a, b in done if a['history'] == history]
                    delta = [int(a['metrics']['whole_bundle'])-int(b['metrics']['whole_bundle']) for a, b in pairs]
                    per_history.append({'history': history, 'measured_pairs': len(pairs),
                        'mean_whole_bundle_difference': sum(delta)/len(delta) if delta else None})
                summaries = summarize(selected), summarize(list(reference.values()))
                bounds_a = summaries[0]['fraction_boolean_macro_history_fault_bounds']['whole_bundle']
                bounds_b = summaries[1]['fraction_boolean_macro_history_fault_bounds']['whole_bundle']
                paired.append({**identity, 'reference': 'body_bm25', 'nominal_pairs': expected['nominal_queries'],
                    'valid_label_pairs': expected['valid_positive_queries'],
                    'measured_pairs': len(done), 'gains': sum(x > 0 for x in differences), 'ties': sum(x == 0 for x in differences),
                    'regressions': sum(x < 0 for x in differences), 'pair_query_weighted_mean_whole_bundle_difference': sum(differences)/len(differences) if differences else None,
                    'pair_macro_history_mean_whole_bundle_difference': sum(h['mean_whole_bundle_difference'] for h in per_history
                        if h['measured_pairs'])/sum(bool(h['measured_pairs']) for h in per_history) if any(h['measured_pairs'] for h in per_history) else None,
                    'pair_macro_history_count': sum(bool(h['measured_pairs']) for h in per_history), 'per_history': per_history,
                    'all_valid_macro_difference_fault_bounds': [bounds_a[0]-bounds_b[1], bounds_a[1]-bounds_b[0]] if bounds_a and bounds_b else None})
    preparation = preparation_states(root, sorted({row['history'] for row in rows}))
    result = {'schema_version': 1, 'state': 'PRIVATE_AGGREGATE_ROOT_OUTCOME_REVIEW_REQUIRED', 'manifest_sha256': manifest_sha,
        'questions_before_engines': expected, 'ranking_state_counts': dict(Counter(row['status'] for row in ranks)),
        'packet_state_counts': dict(Counter(row['status'] for row in rows)), 'preparation_states': preparation,
        'preparation_state_counts': dict(Counter(row['phase'] + ':' + row['status'] for row in preparation)),
        'cells': cells, 'conditional_categories': categories,
        'paired_measured_only': paired, 'provider_calls': 0, 'main_score_adjustment': False,
        'limitations': ['Synthetic histories; publisher support is a mechanical proxy, not semantic/human truth.',
            'Label-unscorable rows are null; valid-label operational faults remain scheduled with explicit counts.',
            'Host-concurrent clocks are operational; no token-speed or algorithm-equivalence claim.']}
    destination = root / 'aggregate.json'
    require(not destination.exists(), 'aggregate_already_exists')
    lab.save(destination, result)
    return {'state': result['state'], 'private_aggregate_sha256': file_hash(destination)}


def self_check():
    global clearance, packet_step
    def reject(call):
        try: call()
        except (AssertionError, ValueError, TypeError, FileNotFoundError): return
        raise AssertionError('known_failing_case_accepted')
    chat = [{'time_anchor': None, 'turns': [[{'id': 1, 'role': 'user', 'content': 'Café alpha 🛰. Keep the note.',
        'answer': 'UNSEEN'}, {'id': 2, 'role': 'assistant', 'content': 'Beta detail.'}]]}]
    docs = external.project(chat)
    changed = copy.deepcopy(chat); changed[0]['turns'][0][0]['answer'] = 'CHANGED GOLD'
    assert docs == external.project(changed) and all('UNSEEN' not in lab.search_text(d) for d in docs.values())
    reject(lambda: external.document_id(True))
    reject(lambda: external.project([{'time_anchor': None, 'turns': [[chat[0]['turns'][0][0]] * 2]}]))
    assert classify({'source_chat_ids': []}, 'summarization', docs)[0] == 'missing_non_abstention_support'
    assert classify({'source_chat_ids': {'present': [1], 'empty': []}}, 'knowledge_update', docs)[0] == 'malformed_criterion_group'
    query = {'id': 'NT01Q03', 'query': 'café alpha', 'category': 'fixture', 'ordinal': 1,
        'groups': {'listed_ids': {'M000001'}}, 'required': {'M000001'}, 'label_status': 'valid_positive',
        'label_code': None, 'label_sha256': 'fixture-valid-label'}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory); folder = root / 'histories' / 'NT01'; folder.mkdir(parents=True)
        native, reference = build_step(folder, docs, False); tokenizer = lab.NativeTokenizer()
        try:
            rank = ranking(folder, query, 'fts_body_or', 'fixture-manifest', docs, native, reference, tokenizer)
            assert rank['status'] == 'ok' and rank['candidates'] == ['M000001']
            cell = {'history': 'NT01', 'task_id': query['id'], 'category': 'fixture', 'engine': 'fts_body_or', 'packer': 'whole_record', 'budget': 4096}
            packet = packet_step(folder, cell, query, rank, 'fixture-manifest', docs)
            assert packet['metrics']['whole_bundle'] and packet_step(folder, cell, query, rank, 'fixture-manifest', docs) == packet
            bad = copy.deepcopy(packet); bad['packet']['observations'][0]['text'] = 'tampered'
            bad = lab.seal({key: value for key, value in bad.items() if key != 'checkpoint_sha256'})
            reject(lambda: validate_packet(bad, cell, query, rank, 'fixture-manifest', docs))
            missing = {**query, 'id': 'NT01Q04', 'query': 'zzznomatch', 'label_status': 'missing_non_abstention_support', 'label_code': 'empty_non_abstention_support', 'label_sha256': 'missing'}
            skipped = ranking(folder, missing, 'fts_body_or', 'fixture-manifest', docs, None, None, None)
            blank = packet_step(folder, {**cell, 'task_id': missing['id']}, missing, skipped, 'fixture-manifest', docs)
            assert skipped['retrieval_attempted'] is False and blank['metrics'] is None and blank['status'] == 'label_unscorable'
            zero_query = {**query, 'id': 'NT01Q05', 'query': 'zzznomatch'}
            zero = ranking(folder, zero_query, 'fts_body_or', 'fixture-manifest', docs, native, reference, tokenizer)
            zero_packet = packet_step(folder, {**cell, 'task_id': zero_query['id']}, zero_query, zero, 'fixture-manifest', docs)
            assert zero['status'] == 'zero_hit' and zero_packet['metrics']['whole_bundle'] is False and zero_packet['packet']['bytes'] == 0
            pending_query = {**query, 'id': 'NT01Q06'}
            task = {'id': pending_query['id'], 'query': pending_query['query']}
            lab.save(folder / 'rankings' / (pending_query['id']+'-body_bm25-pending.json'), {'identity': lab.ranking_identity(task, 'body_bm25', 'fixture-manifest')})
            fault = ranking(folder, pending_query, 'body_bm25', 'fixture-manifest', docs, None, None, None)
            assert fault['status'] == 'fault' and ranking(folder, pending_query, 'body_bm25', 'fixture-manifest', docs, None, None, None) == fault
            pending_cell = {**cell, 'packer': 'sentence_neighbors'}
            lab.save(folder / 'packets' / (lab.object_sha(pending_cell)+'-pending.json'), {'identity': packet_identity(pending_cell, rank, query, 'fixture-manifest')})
            unknown = packet_step(folder, pending_cell, query, rank, 'fixture-manifest', docs)
            assert unknown['status'] == 'packing_fault' and unknown['error']['class'] == 'interrupted_packet_unknown'
            assert packet_step(folder, pending_cell, query, rank, 'fixture-manifest', docs) == unknown
            unknown_folder = root / 'histories' / 'NT02'; unknown_folder.mkdir()
            lab.save(unknown_folder / 'index-stage-pending.json', {'source_projection_sha256': lab.object_sha(docs)})
            assert build_step(unknown_folder, docs, True) == (None, None)
            unknown_build_sha = file_hash(unknown_folder / 'index-stage.json')
            assert build_step(unknown_folder, docs, True) == (None, None)
            assert file_hash(unknown_folder / 'index-stage.json') == unknown_build_sha
            prep = preparation_states(root, ['NT02'])
            assert next(row for row in prep if row['phase'] == 'index_stage')['status'] == 'fault'
            assert all(row['status'] == 'not_reached' for row in prep if row['phase'] != 'index_stage')
            reject(lambda: clearance(root, 'wrong-manifest'))
        finally:
            tokenizer.close(); native.close()
    # Only the external clearance boundary is replaced below. The coordinator,
    # persistence, SQLite, packers and aggregate consume wholly fictional data.
    original_clearance, original_packet_step = clearance, packet_step
    fixture_queries = [query, zero_query, missing]
    expected = {'nominal_queries': 3, 'valid_positive_queries': 2, 'ranking_jobs': 12,
                'packet_rows': 72, 'label_unscorable_packet_rows': 24}
    def fixture_clearance(root, manifest_sha):
        require(file_hash(root / 'manifest.json') == manifest_sha, 'fixture_manifest_changed')
        return iter([{'history': 'NT01', 'docs': copy.deepcopy(docs), 'queries': fixture_queries}])
    def fixture_root(root):
        root.mkdir()
        lab.save(root / 'manifest.json', {'material': {'source_audit': expected}})
        return file_hash(root / 'manifest.json')
    try:
        clearance = fixture_clearance
        with tempfile.TemporaryDirectory() as directory:
            normal = Path(directory) / 'normal'; manifest_sha = fixture_root(normal)
            run(normal, manifest_sha, False)
            state = lab.read_json(normal / 'state.json'); state_check(normal, state)
            assert isinstance(state['recorded_file_sha256'], dict) and isinstance(state['checkpoint_sha256'], str)
            assert sum('/rankings/' in name for name in state['recorded_file_sha256']) == 12
            assert sum('/packets/' in name for name in state['recorded_file_sha256']) == 72
            sealed_state = file_hash(normal / 'state.json')
            run(normal, manifest_sha, True)
            assert file_hash(normal / 'state.json') == sealed_state
            aggregate(normal, manifest_sha)
            result = lab.read_json(normal / 'aggregate.json')
            assert result['packet_state_counts'] == {'ok': 48, 'label_unscorable': 24}
            assert len(result['preparation_states']) == 5 and all(row['status'] in ('ok', 'complete') for row in result['preparation_states'])
            assert len(result['cells']) == 24 and all(c['nominal_queries'] == 3 and c['valid_queries'] == 2 for c in result['cells'])
            uneven = summarize([{**packet, 'history': 'A'}, {**packet, 'history': 'B'},
                {**packet, 'history': 'B', 'status': 'packing_fault', 'metrics': None},
                {**blank, 'history': 'B'}])
            assert uneven['nominal_queries'] == 4 and uneven['valid_queries'] == 3
            assert uneven['whole_bundle_query_weighted_verified_rate'] == 2/3
            assert uneven['whole_bundle_macro_history_verified_rate'] == .75
            assert uneven['fraction_boolean_query_weighted_fault_bounds']['whole_bundle'] == [2/3, 1]
            assert uneven['fraction_boolean_macro_history_fault_bounds']['whole_bundle'] == [.75, 1]
            packet_path = next((normal / 'histories' / 'NT01' / 'packets').glob('*.json'))
            original_bytes = packet_path.read_bytes(); packet_path.write_bytes(original_bytes + b' ')
            reject(lambda: state_check(normal, state))
            packet_path.write_bytes(original_bytes)
            state_check(normal, state)
            bad_state = copy.deepcopy(state); bad_state['recorded_file_sha256'] = 'collision-regression'
            bad_state.pop('checkpoint_sha256'); bad_state = lab.seal(bad_state)
            try: state_check(normal, bad_state)
            except (AttributeError, AssertionError, ValueError): pass
            else: raise AssertionError('ledger_checksum_collision_accepted')

            interrupted = Path(directory) / 'interrupted'; manifest_sha = fixture_root(interrupted)
            calls = 0
            def interrupt_packet(root, cell, task, rank, pin, sources):
                nonlocal calls
                calls += 1
                if calls == 2:
                    path = root / 'packets' / (lab.object_sha(cell) + '-pending.json')
                    lab.save(path, {'identity': packet_identity(cell, rank, task, pin)})
                    raise KeyboardInterrupt('fictional interruption')
                return original_packet_step(root, cell, task, rank, pin, sources)
            packet_step = interrupt_packet
            try: run(interrupted, manifest_sha, False)
            except KeyboardInterrupt: pass
            else: raise AssertionError('fixture_interruption_not_reached')
            packet_step = original_packet_step
            assert not (interrupted / 'complete.json').exists() and not (interrupted / 'coordinator.lock').exists()
            reject(lambda: aggregate(interrupted, manifest_sha))
            reject(lambda: run(interrupted, manifest_sha, False))
            folder = interrupted / 'histories' / 'NT01'
            cached_path = next(path for path in (folder / 'packets').glob('*.json') if not path.name.endswith('-pending.json'))
            cached_sha = file_hash(cached_path)
            # Simulate a sealed ranking failure saved just before state tracking.
            fault = ranking(folder, zero_query, 'body_bm25', manifest_sha, docs, None, None, None)
            assert fault['status'] == 'fault'
            fault_path = folder / 'rankings' / (zero_query['id'] + '-body_bm25.json')
            fault_sha = file_hash(fault_path)
            run(interrupted, manifest_sha, True)
            assert file_hash(cached_path) == cached_sha and file_hash(fault_path) == fault_sha
            resumed_state = lab.read_json(interrupted / 'state.json'); state_check(interrupted, resumed_state)
            assert fault_path.relative_to(interrupted).as_posix() in resumed_state['recovered_after_interrupt']
            aggregate(interrupted, manifest_sha)
            resumed = lab.read_json(interrupted / 'aggregate.json')
            assert resumed['packet_state_counts'] == {'ok': 41, 'packing_fault': 1, 'retrieval_fault': 6, 'label_unscorable': 24}
            assert all(row['valid_queries'] == 2 for row in resumed['cells'])
            assert sum(row['algorithm_faults'] for row in resumed['cells']) == 7
            assert all(row['fraction_boolean_query_weighted_fault_bounds']['whole_bundle'][0]
                       <= row['fraction_boolean_query_weighted_fault_bounds']['whole_bundle'][1] for row in resumed['cells'])
    finally:
        clearance, packet_step = original_clearance, original_packet_step
    print(lab.canonical({'state': 'PASS_FICTIONAL_FIXTURES_ONLY', 'checks': ['source/gold stripping', 'integer IDs/duplicate rejection',
        'empty/malformed labels', 'real original SQLite rank + Unicode whole packet', 'source packet tamper rejection',
        'label-unscorable null/no lookup', 'zero-hit no tail-fill', 'pending cached ranking/packet no retry', 'clearance rejection',
        'coordinator persisted ledger/seal separation', 'cached completion unchanged', 'complete-census aggregate',
        'checkpoint mutation rejection', 'interruption/resume unknown-pending retained', 'known fault no retry',
        'preparation fault/no retry/not-reached census', 'unequal-history fault denominator bounds'],
        'actual_beam_rankings': 0, 'provider_calls': 0, 'actual_transfer_success': 'UNREACHED'}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    for name in ('self-check', 'doctor', 'prepare', 'run', 'aggregate'): action.add_argument('--'+name, action='store_true')
    parser.add_argument('--work', type=Path)
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.self_check: self_check(); return
    require(args.work is not None, 'private_work_required')
    root = lab.private_root(args.work)
    require(root.is_dir(), 'prefetched_private_root_missing')
    if args.doctor:
        value, _ = material(root)
        result = {'state': 'PASS_SOURCE_RUNTIME_LABEL_DOCTOR_NO_RANKING', 'material': value, 'provider_calls': 0}
    elif args.prepare: result = prepare(root)
    elif args.run: run(root, args.manifest_sha256, args.resume); return
    else: result = aggregate(root, args.manifest_sha256)
    print(lab.canonical(result))


if __name__ == '__main__':
    main()
