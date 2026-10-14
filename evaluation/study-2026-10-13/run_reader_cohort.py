"""Prospective 72-job oracle/discovery coordinator; no core scoring copy.

--prepare freezes private inputs without calls. --run requires root clearance.
--self-check uses the original frozen worker with isolated fake trial functions.
"""
import argparse
import ast
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
import contextlib
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
CORE_FREEZE = 'fda01f88f50dbb6e66a312ca9ab775c8603643ebe8b7f74b596a7250bc39524c'
READER_SHA = 'aa1632e9702524c28c9985e7b68306048aeca54f8aa23649e6207c263f2292bf'
WORKERS = 2


def require(value, reason):
    if not value:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode('utf8')).hexdigest()


def file_hash(path):
    return digest(Path(path).read_bytes())


def running_python_image():
    # Windows App Execution Aliases identify argv but may not be readable files.
    # Bind the current process image instead; this does not attest future alias routing.
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        query = kernel.GetModuleFileNameW
        query.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint]
        query.restype = ctypes.c_uint
        buffer = ctypes.create_unicode_buffer(32768)
        length = query(None, buffer, len(buffer))
        require(0 < length < len(buffer), 'python_process_image_query_failed')
        path = Path(buffer.value).resolve()
    else:
        path = Path(sys.executable).resolve()
    require(path.is_file(), 'python_process_image_missing')
    return {'path': str(path), 'sha256': file_hash(path)}


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite_json')
    value = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)
    def check(item):
        if isinstance(item, str):
            item.encode('utf8')
        elif isinstance(item, float):
            require(math.isfinite(item), 'nonfinite_json')
        elif isinstance(item, list):
            for member in item: check(member)
        elif isinstance(item, dict):
            for key, member in item.items(): check(key); check(member)
    check(value)
    return value


def read(path):
    return strict_json(Path(path).read_text(encoding='utf8'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('wb') as stream:
        stream.write((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf8'))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def private_path(path):
    result = Path(path).resolve()
    require(not result.is_relative_to(HERE.parents[1]), 'private_path_inside_repository')
    return result


def verified_core():
    require(file_hash(HERE / 'freeze.json') == CORE_FREEZE, 'core_freeze_changed')
    freeze = read(HERE / 'freeze.json')
    require(isinstance(freeze.get('files'), dict), 'core_pin_map_missing')
    for name, pin in freeze['files'].items():
        target = (HERE / name).resolve()
        require(target.is_relative_to(HERE.parents[1]) and file_hash(target) == pin, 'core_pin_changed:' + name)
    require(freeze['files'].get('reader_trials.py') == READER_SHA, 'reader_source_not_frozen')
    return freeze['files']


def original_function(source, expected_sha, name):
    require(digest(source.encode('utf8')) == expected_sha, 'function_source_changed')
    tree = ast.parse(source)
    found = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
    require(len(found) == 1 and isinstance(found[0], ast.FunctionDef), 'original_function_not_unique')
    node = found[0]
    require(not node.decorator_list, 'unexpected_original_decorator')
    return node, digest(ast.dump(node, include_attributes=False)), digest(ast.get_source_segment(source, node))


def bind_function(node, namespace):
    # Exact-source AST reuse has a deliberate ceiling: it depends on this frozen
    # source layout. Never extract arbitrary unverified code. A shared worker
    # refactor belongs to a new study, not this operational amendment.
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'verified_frozen_reader', 'exec'), namespace)
    return namespace[node.name]


def select_jobs(planned):
    jobs = planned.get('jobs')
    require(isinstance(jobs, list) and len(jobs) == 192, 'schedule_192_required')
    require(len({job['trial_id'] for job in jobs}) == 192, 'duplicate_scheduled_trial')
    require({block: sum(job['block'] == block for job in jobs) for block in ('oracle', 'discovery', 'direct')}
        == {'oracle': 24, 'discovery': 48, 'direct': 120}, 'schedule_block_census')
    selected = [job for job in jobs if job['block'] in ('oracle', 'discovery')]
    require(len(selected) == 72, 'cohort_72_required')
    return selected


def checkpoint(path, job, fingerprint, expected_sha=None):
    require(path.is_file(), 'checkpoint_missing')
    if expected_sha is not None:
        require(file_hash(path) == expected_sha, 'checkpoint_bytes_changed')
    saved = read(path)
    require(set(saved) == {'fingerprint', 'result'} and saved['fingerprint'] == fingerprint, 'checkpoint_identity_changed')
    require(isinstance(saved['result'], dict) and all(canonical(saved['result'].get(key)) == canonical(value)
        for key, value in job.items()), 'checkpoint_job_changed')
    return saved['result']


def literal_path_assignment(source_path, name, bindings=None):
    """Resolve only bounded Path/literal/__file__/ROOT expressions; never import."""
    tree = ast.parse(source_path.read_bytes().decode('utf8'))
    matches = [node.value for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
    require(len(matches) == 1, 'private_dependency_assignment_not_unique:' + name)
    environment = {'__file__': source_path, **(bindings or {})}
    def resolve(node, depth=0):
        require(depth < 12, 'private_path_expression_depth')
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and '\x00' not in node.value:
            return node.value
        if isinstance(node, ast.Name) and node.id in environment:
            return environment[node.id]
        if isinstance(node, ast.Call) and not node.keywords:
            if isinstance(node.func, ast.Name) and node.func.id == 'Path' and len(node.args) == 1:
                return Path(resolve(node.args[0], depth + 1))
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'resolve' and not node.args:
                return Path(resolve(node.func.value, depth + 1)).resolve()
        if isinstance(node, ast.Attribute) and node.attr == 'parent':
            return Path(resolve(node.value, depth + 1)).parent
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            require(isinstance(node.right, ast.Constant) and isinstance(node.right.value, str), 'private_path_rhs_not_literal')
            return Path(resolve(node.left, depth + 1)) / resolve(node.right, depth + 1)
        raise ValueError('private_dependency_expression_not_literal:' + name)
    return Path(resolve(matches[0])).resolve()


def private_runtime(args, expected):
    paths = {name: private_path(getattr(args, name)) for name in ('adapter_command', 'adapter_source', 'wrapper_source', 'pinned_binary')}
    require(all(path.is_file() for path in paths.values()), 'private_runtime_file_missing')
    for name, public_key in (('adapter_source', 'private_adapter_sha256'), ('wrapper_source', 'private_wrapper_sha256'), ('pinned_binary', 'pinned_binary_sha256')):
        require(file_hash(paths[name]) == expected[public_key], 'private_runtime_source_changed:' + name)
    command = read(paths['adapter_command'])
    require(isinstance(command, list) and len(command) == 4 and all(isinstance(item, str) and item and '\x00' not in item for item in command), 'adapter_argv_shape')
    require(command[1:3] == ['-X', 'utf8'] and Path(command[3]).resolve() == paths['wrapper_source'], 'wrapper_argv_source_link')
    require(Path(command[0]).resolve() == Path(sys.executable).resolve(), 'adapter_interpreter_not_current_python')
    require(literal_path_assignment(paths['wrapper_source'], 'BASE') == paths['adapter_source'], 'wrapper_base_adapter_link')
    root = literal_path_assignment(paths['adapter_source'], 'ROOT')
    require(root == paths['adapter_source'].parent, 'adapter_root_source_link')
    require(literal_path_assignment(paths['adapter_source'], 'EXE', {'ROOT': root}) == paths['pinned_binary'], 'adapter_exe_binary_link')
    return paths, command


def material(args):
    pins = verified_core()
    work = private_path(args.work)
    expected = read(HERE / 'runtime-public.json')
    paths, command = private_runtime(args, expected)
    selected = select_jobs(read(HERE / 'reader-schedule.json'))
    source = (HERE / 'reader_trials.py').read_bytes().decode('utf8')
    node, ast_sha, segment_sha = original_function(source, READER_SHA, 'execute')
    value = {'core_freeze_sha256': CORE_FREEZE, 'core_file_pins': pins,
        'helper_sha256': file_hash(Path(__file__)), 'amendment_sha256': file_hash(HERE / 'READER-PHASE-AMENDMENT.md'),
        'execute_ast_sha256': ast_sha, 'execute_source_segment_sha256': segment_sha,
        'workers': WORKERS, 'selected_jobs_sha256': digest(canonical(selected)),
        'selected_trial_ids': [job['trial_id'] for job in selected], 'selected_count': 72,
        'runtime_public_sha256': file_hash(HERE / 'runtime-public.json'), 'python_version': sys.version,
        'adapter_command_interpreter': {'argv': command[0], 'canonical_identity': str(Path(command[0]).resolve())},
        'python_process_image': running_python_image(), 'work': str(work),
        'private_runtime_files': {name: {'path': str(path), 'sha256': file_hash(path)} for name, path in paths.items()}}
    return value, selected, node, command, expected


def prepare(args):
    value, selected, _, _, _ = material(args)
    root = private_path(args.work) / 'reader-cohort'
    require(not root.exists(), 'cohort_manifest_directory_already_exists')
    fingerprint = digest(CORE_FREEZE + ':reader-trials-v1')
    existing = {}
    for job in selected:
        path = Path(value['work']) / 'reader-checkpoints' / (job['trial_id'] + '.json')
        if path.exists():
            checkpoint(path, job, fingerprint)
            existing[job['trial_id']] = file_hash(path)
    save(root / 'manifest.json', {'schema_version': 'reader-cohort-v1', 'state': 'prepared_not_executed',
        'material': value, 'existing_checkpoint_sha256': existing})
    print(canonical({'state': 'prepared_not_executed', 'cohort': 72, 'workers': WORKERS,
        'manifest_sha256': file_hash(root / 'manifest.json'), 'reader_calls': 0}))


def load_execute(node, args, command, expected, checkpoints):
    if str(HERE) not in sys.path: sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location('oct13_verified_reader_for_cohort', HERE / 'reader_trials.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ('artifact_contract', 'index_lab', 'packing_lab', 'study_common'):
        require(Path(sys.modules[name].__file__).resolve() == (HERE / (name + '.py')).resolve(), 'imported_core_module_path_changed')
    namespace = module.__dict__
    namespace.update(args=SimpleNamespace(work=args.work), checkpoints=checkpoints, command=command,
        expected=expected, fingerprint=digest(CORE_FREEZE + ':reader-trials-v1'))
    return bind_function(node, namespace)


def run(args):
    value, selected, node, command, expected = material(args)
    args.work = Path(value['work'])
    root = args.work / 'reader-cohort'
    require(isinstance(args.phase_sha256, str) and file_hash(root / 'manifest.json') == args.phase_sha256, 'exact_phase_manifest_sha_required')
    manifest = read(root / 'manifest.json')
    require(canonical(manifest['material']) == canonical(value), 'phase_material_changed')
    clearance = read(root / 'review-clearance.json')
    require(clearance.get('approved') is True and clearance.get('manifest_sha256') == args.phase_sha256, 'root_phase_clearance_missing')
    require(not (root / 'cohort-complete.json').exists(), 'completed_cohort_cannot_rerun')
    # Acquire ownership before touching progress. A hard kill leaves this lock
    # for root to inspect/remove after confirming no live cohort process.
    # It does not coordinate another host or the separate frozen reader CLI.
    lock = root / 'active.lock'
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf8') as stream:
            stream.write(canonical({'pid': os.getpid(), 'manifest_sha256': args.phase_sha256}))
            stream.flush(); os.fsync(stream.fileno())
        consume(args, root, value, selected, node, command, expected)
    finally:
        lock.unlink()


def consume(args, root, value, selected, node, command, expected):
    require(file_hash(root / 'manifest.json') == args.phase_sha256, 'locked_phase_manifest_changed')
    manifest = read(root / 'manifest.json')
    state_path = root / 'state.json'
    if state_path.exists():
        require(args.resume, 'explicit_resume_required')
        state = read(state_path)
        require(state.get('manifest_sha256') == args.phase_sha256, 'resume_phase_identity_changed')
    else:
        require(not args.resume, 'resume_state_missing')
        state = {'manifest_sha256': args.phase_sha256, 'checkpoint_sha256': {}, 'recovered_after_interrupt': []}
    checkpoints = args.work / 'reader-checkpoints'
    checkpoints.mkdir(parents=True, exist_ok=True)
    fingerprint = digest(CORE_FREEZE + ':reader-trials-v1')
    baseline = manifest['existing_checkpoint_sha256']
    require(set(state['checkpoint_sha256']) <= {job['trial_id'] for job in selected}, 'state_trial_outside_cohort')
    for job in selected:
        identifier, path = job['trial_id'], checkpoints / (job['trial_id'] + '.json')
        pinned = state['checkpoint_sha256'].get(identifier, baseline.get(identifier))
        if pinned is not None or path.exists():
            checkpoint(path, job, fingerprint, pinned)
            if pinned is None:
                require(args.resume, 'unexpected_unlogged_checkpoint')
                state['recovered_after_interrupt'].append(identifier)
            state['checkpoint_sha256'][identifier] = file_hash(path)
    save(state_path, state)
    execute = load_execute(node, args, command, expected, checkpoints)
    results = []
    pool, futures, phase = ThreadPoolExecutor(max_workers=WORKERS), {}, 'submission'
    try:
        for job in selected:
            futures[pool.submit(execute, job)] = job
        for future in as_completed(futures):
            phase = 'future_result'
            result, job = future.result(), futures[future]
            path = checkpoints / (job['trial_id'] + '.json')
            phase = 'checkpoint_validation'
            require(canonical(checkpoint(path, job, fingerprint)) == canonical(result), 'returned_checkpoint_value_changed')
            prior = state['checkpoint_sha256'].get(job['trial_id'])
            require(prior is None or file_hash(path) == prior, 'cached_checkpoint_was_rewritten')
            state['checkpoint_sha256'][job['trial_id']] = file_hash(path)
            phase = 'state_persistence'
            save(state_path, state)
            results.append(result)
    except BaseException as error:
        # Cancel before waiting: context-manager shutdown would otherwise let
        # queued paid trials start while waiting for already running jobs.
        for future in futures:
            future.cancel()
        pool.shutdown(wait=True, cancel_futures=True)
        cancelled = [job['trial_id'] for future, job in futures.items() if future.cancelled()]
        unsubmitted = [job['trial_id'] for job in selected if job['trial_id'] not in {j['trial_id'] for j in futures.values()}]
        retained, future_errors = {}, []
        for future, job in futures.items():
            if future.cancelled(): continue
            path = checkpoints / (job['trial_id'] + '.json')
            if path.is_file(): retained[job['trial_id']] = file_hash(path)
            if future.exception() is not None:
                future_errors.append({'trial_id': job['trial_id'], 'class': type(future.exception()).__name__})
        save(root / 'cohort-failure.json', {'schema_version': 'reader-cohort-failure-v1',
            'manifest_sha256': args.phase_sha256, 'phase': phase, 'error_class': type(error).__name__,
            'scheduled_trials': 72, 'cancelled_unstarted_trial_ids': cancelled,
            'cancelled_unstarted_count': len(cancelled), 'unsubmitted_trial_ids': unsubmitted,
            'unsubmitted_count': len(unsubmitted), 'not_started_count': len(cancelled) + len(unsubmitted),
            'retained_checkpoint_sha256': retained, 'retained_checkpoint_count': len(retained),
            'future_errors': future_errors, 'automatic_retry': False,
            'meaning': 'Coordinator failure; no invented failed trial rows. Running original jobs were allowed to finish and their existing checkpoints remain retained.'})
        raise
    else:
        pool.shutdown(wait=True)
    require(len(results) == len({row['trial_id'] for row in results}) == 72, 'cohort_result_census')
    save(root / 'cohort-complete.json', {'schema_version': 'reader-cohort-v1', 'state': 'cohort_complete',
        'manifest_sha256': args.phase_sha256, 'freeze_sha256': CORE_FREEZE, 'scheduled_trials': 72,
        'workers': WORKERS, 'selected_trial_ids': value['selected_trial_ids'],
        'checkpoint_sha256': state['checkpoint_sha256'], 'results': sorted(results, key=lambda row: row['trial_id']),
        'publication': 'Private cohort only; not a192-reader completion. Frozen full CLI later reuses these checkpoints.'})
    print(canonical({'state': 'cohort_complete', 'scheduled_trials': 72, 'private_receipt_sha256': file_hash(root / 'cohort-complete.json')}))


def self_check():
    def must_fail(call):
        try: call()
        except (ValueError, AssertionError, UnicodeError): return
        raise AssertionError('negative_check_accepted')
    source = (HERE / 'reader_trials.py').read_bytes().decode('utf8')
    node, ast_sha, segment_sha = original_function(source, READER_SHA, 'execute')
    must_fail(lambda: original_function(source + '\n', READER_SHA, 'execute'))
    must_fail(lambda: strict_json('{"x":1e999}'))
    must_fail(lambda: strict_json('"\\ud800"'))
    image = running_python_image()
    assert Path(image['path']).is_file() and file_hash(image['path']) == image['sha256']
    jobs = [{'trial_id': f'X{i:03d}', 'block': 'oracle' if i < 24 else 'discovery' if i < 72 else 'direct',
             'arm': 'fixture', 'family_id': 'F', 'task_id': 'T', 'collection_size': 144} for i in range(192)]
    planned = {'jobs': list(reversed(jobs))}
    assert select_jobs(planned) == [job for job in planned['jobs'] if job['block'] != 'direct'] and WORKERS == 2
    must_fail(lambda: select_jobs({'jobs': jobs[:-1]}))
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory); checkpoints = root / 'reader-checkpoints'; checkpoints.mkdir()
        runtime_args = SimpleNamespace(adapter_command=root / 'command.json', adapter_source=root / 'adapter.py',
            wrapper_source=root / 'wrapper.py', pinned_binary=root / 'native.bin')
        adapter_bytes = b'from pathlib import Path\nROOT = Path(__file__).resolve().parent\nEXE = ROOT / "native.bin"\n'
        wrapper_bytes = ('from pathlib import Path\nBASE = Path(' + repr(str(runtime_args.adapter_source)) + ')\n').encode('utf8')
        runtime_args.adapter_source.write_bytes(adapter_bytes)
        runtime_args.wrapper_source.write_bytes(wrapper_bytes)
        runtime_args.pinned_binary.write_bytes(b'fictional binary bytes')
        save(runtime_args.adapter_command, [sys.executable, '-X', 'utf8', str(runtime_args.wrapper_source)])
        expected_runtime = {'private_adapter_sha256': file_hash(runtime_args.adapter_source),
            'private_wrapper_sha256': file_hash(runtime_args.wrapper_source), 'pinned_binary_sha256': file_hash(runtime_args.pinned_binary)}
        private_runtime(runtime_args, expected_runtime)
        runtime_args.adapter_source.write_bytes(b'# changed fake adapter\n')
        must_fail(lambda: private_runtime(runtime_args, expected_runtime))
        runtime_args.adapter_source.write_bytes(adapter_bytes)
        wrong_binary = root / 'wrong-native.bin'; wrong_binary.write_bytes(runtime_args.pinned_binary.read_bytes())
        must_fail(lambda: private_runtime(SimpleNamespace(**{**vars(runtime_args), 'pinned_binary': wrong_binary}), expected_runtime))
        wrong_adapter = root / 'wrong-adapter.py'; wrong_adapter.write_bytes(adapter_bytes)
        must_fail(lambda: private_runtime(SimpleNamespace(**{**vars(runtime_args), 'adapter_source': wrong_adapter}), expected_runtime))
        save(runtime_args.adapter_command, ['shell command string'])
        must_fail(lambda: private_runtime(runtime_args, expected_runtime))
        calls = []
        def fake_trial(job, work, command, expected):
            calls.append(job['trial_id'])
            if job['trial_id'] == 'FAIL': raise OSError('fictional fault')
            return {**job, 'outcome': {'artifact_written': False, 'complete_task': False}, 'failure': None}
        namespace = {'__builtins__': __builtins__, 'Path': Path, 'json': json, 'subprocess': subprocess,
            'strict_json': strict_json, 'save': save, 'digest': digest, 'trial': fake_trial,
            'args': SimpleNamespace(work=root), 'checkpoints': checkpoints, 'command': ['fake'], 'expected': {}, 'fingerprint': 'fixture',
            'bank': lambda: {'families': [{'id': 'F', 'tasks': [{'id': 'T'}]}]}, 'documents': lambda families: {},
            'collection': lambda docs, family, size: {}, 'score': lambda *args: {'artifact_written': False, 'complete_task': False}}
        execute = bind_function(node, namespace)
        job = {'trial_id': 'OK', 'family_id': 'F', 'task_id': 'T', 'collection_size': 144, 'block': 'oracle', 'arm': 'fixture'}
        failed_job = {**job, 'trial_id': 'FAIL'}
        with contextlib.redirect_stdout(io.StringIO()):
            first, failed = execute(job), execute(failed_job)
            before = (checkpoints / 'FAIL.json').read_bytes()
            assert execute(job) == first and execute(failed_job) == failed
        assert calls == ['OK', 'FAIL'] and failed['failure'] == 'trial_execution_error'
        assert (checkpoints / 'FAIL.json').read_bytes() == before
        checkpoint(checkpoints / 'OK.json', job, 'fixture')
        wrong = read(checkpoints / 'OK.json'); wrong['fingerprint'] = 'changed'; save(checkpoints / 'OK.json', wrong)
        must_fail(lambda: checkpoint(checkpoints / 'OK.json', job, 'fixture'))
        must_fail(lambda: execute(job))
        invoke_node, _, _ = original_function(source, READER_SHA, 'invoke_recorded')
        invoke = bind_function(invoke_node, namespace)
        class FakeTransport:
            count = 0
            def invoke(self, *args):
                self.count += 1
                return None, {'accepted': False, 'usage': None, 'failure': 'fictional_rejection'}
        fake = FakeTransport()
        invoke(fake, [], 'prompt', root, 'false', {})
        cached = invoke(fake, [], 'prompt', root, 'false', {})
        assert fake.count == 1 and cached[0] is None and cached[1]['accepted'] is False
        save(root / 'unknown-pending.json', {'identity': digest('prompt{}')})
        unknown = invoke(fake, [], 'prompt', root, 'unknown', {})
        assert fake.count == 1 and unknown[0] is None and unknown[1]['failure'] == 'interrupted_call_no_receipt'
        # Drive this coordinator's real persistence/collection path with the
        # same extracted worker and fake trials, not a second runner harness.
        cohort_root, cohort_work = root / 'phase', root / 'work'
        cohort_root.mkdir(); cohort_work.mkdir()
        cohort_checkpoints = cohort_work / 'reader-checkpoints'
        cohort_checkpoints.mkdir()
        cohort_args = SimpleNamespace(work=cohort_work, phase_sha256='f' * 64, resume=False)
        selected = select_jobs(planned)
        save(cohort_root / 'manifest.json', {'existing_checkpoint_sha256': {}})
        cohort_args.phase_sha256 = file_hash(cohort_root / 'manifest.json')
        namespace.update(args=SimpleNamespace(work=cohort_work), checkpoints=cohort_checkpoints,
            fingerprint=digest(CORE_FREEZE + ':reader-trials-v1'))
        previous_loader = globals()['load_execute']
        globals()['load_execute'] = lambda *args: bind_function(node, namespace)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                consume(cohort_args, cohort_root, {'selected_trial_ids': [j['trial_id'] for j in selected]}, selected, node, [], {})
            complete = read(cohort_root / 'cohort-complete.json')
            assert complete['scheduled_trials'] == 72 and len(complete['results']) == 72
            assert not (HERE / 'cohort-complete.json').exists()
            calls_before_resume = len(calls)
            (cohort_root / 'cohort-complete.json').unlink()  # simulated interruption before completion receipt
            cohort_args.resume = True
            with contextlib.redirect_stdout(io.StringIO()):
                consume(cohort_args, cohort_root, {'selected_trial_ids': [j['trial_id'] for j in selected]}, selected, node, [], {})
            assert len(calls) == calls_before_resume
            path = cohort_checkpoints / (selected[0]['trial_id'] + '.json')
            altered = read(path); altered['result']['failure'] = 'mutated'; save(path, altered)
            must_fail(lambda: consume(cohort_args, cohort_root, {'selected_trial_ids': []}, selected, node, [], {}))
            assert len(calls) == calls_before_resume
            # Both real fake-worker threads are blocked before the coordinator
            # observes a synthetic future fault. Release them only after queued
            # futures have been cancelled, proving shutdown does not drain work.
            failure_root, failure_work = root / 'failure-phase', root / 'failure-work'
            failure_root.mkdir(); failure_work.mkdir()
            failure_checkpoints = failure_work / 'reader-checkpoints'; failure_checkpoints.mkdir()
            save(failure_root / 'manifest.json', {'existing_checkpoint_sha256': {}})
            failure_args = SimpleNamespace(work=failure_work, phase_sha256=file_hash(failure_root / 'manifest.json'), resume=False)
            release, both_started = threading.Event(), threading.Event()
            started, started_lock = [], threading.Lock()
            def blocked_trial(job, *args):
                with started_lock:
                    started.append(job['trial_id'])
                    if len(started) == 2: both_started.set()
                require(release.wait(10), 'synthetic_active_worker_timeout')
                return {**job, 'outcome': {'artifact_written': False, 'complete_task': False}, 'failure': None}
            namespace.update(args=SimpleNamespace(work=failure_work), checkpoints=failure_checkpoints, trial=blocked_trial)
            real_pool = globals()['ThreadPoolExecutor']
            class BlockedPool(real_pool):
                submissions = 0
                def submit(self, function, job):
                    self.submissions += 1
                    if self.submissions == 3:
                        require(both_started.wait(10), 'synthetic_workers_not_started')
                        fault = Future(); fault.set_exception(ValueError('synthetic_future_failure'))
                        return fault
                    return super().submit(function, job)
                def shutdown(self, wait=True, *, cancel_futures=False):
                    if cancel_futures:
                        super().shutdown(wait=False, cancel_futures=True)
                        release.set()
                    return super().shutdown(wait=wait, cancel_futures=cancel_futures)
            globals()['ThreadPoolExecutor'] = BlockedPool
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    must_fail(lambda: consume(failure_args, failure_root, {'selected_trial_ids': [j['trial_id'] for j in selected]}, selected, node, [], {}))
                failed_cohort = read(failure_root / 'cohort-failure.json')
                assert failed_cohort['phase'] == 'future_result' and failed_cohort['cancelled_unstarted_count'] == 69
                assert len(started) == 2 and set(failed_cohort['retained_checkpoint_sha256']) == set(started)
                assert not (failure_root / 'cohort-complete.json').exists()
                for job in selected[:2]: checkpoint(failure_checkpoints / (job['trial_id'] + '.json'), job, namespace['fingerprint'])
            finally:
                globals()['ThreadPoolExecutor'] = real_pool
                release.set()
        finally:
            globals()['load_execute'] = previous_loader
    must_fail(lambda: private_path(HERE / 'private-fixture'))
    print(canonical({'state': 'PASS', 'workers': WORKERS, 'original_execute_ast_sha256': ast_sha,
        'original_execute_source_segment_sha256': segment_sha,
        'checks': ['verified source mutation rejection', 'exact72 selection/order', 'original worker success/cache/fault envelope',
                   'checkpoint mutation rejection', 'false cached call no retry', 'unknown pending call no retry',
                   'coordinator72 persistence/cache resume with original fake worker', 'queued cancellation and active checkpoint retention',
                   'private path/runtime source/wrapper BASE/adapter EXE/argv boundaries',
                   'readable running Python image distinct from command alias', 'strict JSON boundaries'],
        'actual_reader_calls': 0, 'actual_cohort_success': 'UNREACHED: root clearance and paid collection intentionally pending'}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--self-check', action='store_true')
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--run', action='store_true')
    for name in ('work', 'adapter-command', 'adapter-source', 'wrapper-source', 'pinned-binary'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--phase-sha256')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.self_check:
        self_check()
    else:
        require(all(getattr(args, name) is not None for name in ('work', 'adapter_command', 'adapter_source', 'wrapper_source', 'pinned_binary')), 'private_work_and_runtime_paths_required')
        (prepare if args.prepare else run)(args)


if __name__ == '__main__':
    main()
