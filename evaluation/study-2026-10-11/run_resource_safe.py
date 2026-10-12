"""Cap actual factorial concurrency without changing the frozen runner contract."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import threading
import uuid

import run_resumable as runner

HERE = Path(__file__).resolve().parent
REQUESTED_WORKERS = 4
ACTUAL_MAX_WORKERS = 2
AMENDMENT_FILES = {'run_resource_safe.py', 'RESOURCE-AMENDMENT.md'}


class ResourceSafeExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers=None, *args, **kwargs):
        runner.require(type(max_workers) is int and max_workers == REQUESTED_WORKERS,
                       'Resource wrapper requires the original four-worker request')
        super().__init__(ACTUAL_MAX_WORKERS, *args, **kwargs)


def verify_resource_freeze(resource, work, task_ids, identities, study=HERE):
    runner.require(resource.get('schema_version') == 1, 'Resource freeze schema differs')
    runner.require(resource.get('requested_workers') == REQUESTED_WORKERS and
                   resource.get('actual_max_workers') == ACTUAL_MAX_WORKERS,
                   'Resource worker pins differ')
    runner.require(all(resource.get(key) == value for key, value in identities.items()),
                   'Resource base identities differ')
    files = resource.get('files', {})
    runner.require(set(files) == AMENDMENT_FILES, 'Resource amendment files differ')
    runner.require(all(runner.digest(study/name) == expected for name, expected in files.items()),
                   'Resource amendment digest differs')
    previous = resource.get('previous_checkpoint_sha256')
    runner.require(isinstance(previous, dict) and set(previous).issubset(task_ids),
                   'Resource checkpoint IDs differ')
    current = {tid:runner.digest(work/(tid+'.json')) for tid in task_ids
               if (work/(tid+'.json')).exists()}
    runner.require(all(current.get(tid) == expected for tid, expected in previous.items()),
                   'Previously accepted checkpoint bytes changed')
    return current


def start_history(work, resource_sha256, extra_checkpoints):
    path = work/'resource-started.json'
    pin = dict(schema_version=1, resource_freeze_sha256=resource_sha256,
               requested_workers=REQUESTED_WORKERS, actual_max_workers=ACTUAL_MAX_WORKERS)
    if path.exists():
        history = runner.read(path)
        runner.require(all(history.get(key) == value for key, value in pin.items()),
                       'Resource start history pins differ')
        runner.require(isinstance(history.get('attempts'), list) and history['attempts'],
                       'Resource start history is empty or invalid')
    else:
        runner.require(not extra_checkpoints,
                       'Unpinned checkpoints require matching resource start history')
        history = dict(**pin, attempts=[])
    return path, history


def run(cache, work):
    cache, work = runner.external(cache), runner.external(work)
    _, execution, _ = runner.verify_execution()
    identities = dict(original_freeze_sha256=runner.digest(HERE/'freeze.json'),
                      execution_freeze_sha256=runner.digest(HERE/'execution-freeze.json'),
                      runner_sha256=runner.digest(HERE/'run_resumable.py'))
    resource_path = HERE/'resource-freeze.json'
    resource = runner.read(resource_path)
    resource_sha256 = runner.digest(resource_path)
    _, grouped = runner.jobs_for(runner.b.load_bank())
    before = verify_resource_freeze(resource, work, set(grouped), identities)
    previous = resource['previous_checkpoint_sha256']
    history_path, history = start_history(work, resource_sha256, set(before)-set(previous))
    reused_worker_ids = {runner.read(work/(tid+'.json'))['payload']['worker_id'] for tid in before}
    attempt_id = uuid.uuid4().hex
    history['attempts'].append(dict(attempt_id=attempt_id,
        started_utc=datetime.now(timezone.utc).isoformat(), state='started',
        existing_reuse_count=len(before), checkpoint_sha256=before))
    runner.b.atomic_json(history_path, history)
    print(f'Resource wrapper started: requested workers=4, actual cap=2; '
          f'{len(before)} existing checkpoints await frozen-runner validation', flush=True)
    original_executor = runner.ThreadPoolExecutor
    try:
        runner.ThreadPoolExecutor = ResourceSafeExecutor
        # Original run validates every accepted/extra chunk before opening its pool.
        runner.run(cache, work, REQUESTED_WORKERS)
    finally:
        runner.ThreadPoolExecutor = original_executor
    after = {tid:runner.digest(work/(tid+'.json')) for tid in grouped}
    runner.require(all(after.get(tid) == expected for tid, expected in before.items()),
                   'Reused checkpoint bytes changed during resource run')
    model_execution = runner.read(HERE/'model-execution.json')
    runner.require(model_execution['checkpoints'] == after, 'Published checkpoint hashes differ')
    worker_models = model_execution['worker_models']
    worker_ids = set(worker_models)
    runner.require(reused_worker_ids.issubset(worker_ids), 'Reused worker IDs absent from publication')
    fresh_worker_ids = worker_ids-reused_worker_ids
    fresh_instance_ids = {wid.split(':')[0] for wid in fresh_worker_ids}
    runner.require(len(fresh_worker_ids) <= ACTUAL_MAX_WORKERS and len(fresh_instance_ids) <= 1,
                   'Fresh worker IDs exceed resource cap or run identity')
    runner.require(model_execution['reproduced_interrupted_rows'] == execution['required_overlap_rows'],
                   'Preserved interrupted overlap receipt differs')
    history['attempts'][-1]['state'] = 'complete'
    history['attempts'][-1]['completed_utc'] = datetime.now(timezone.utc).isoformat()
    runner.b.atomic_json(history_path, history)
    receipt = dict(state='complete', attempt_id=attempt_id, **identities,
        resource_freeze_sha256=resource_sha256,
        requested_workers=REQUESTED_WORKERS, actual_max_workers=ACTUAL_MAX_WORKERS,
        frozen_previous_checkpoint_count=len(previous), existing_reuse_count=len(before),
        previous_checkpoint_sha256=previous,
        reused_checkpoint_sha256_before=before,
        reused_checkpoint_sha256_after={tid:after[tid] for tid in before},
        checkpoint_sha256=after, reused_checkpoint_bytes_unchanged=True,
        worker_run_ids=sorted(worker_ids), reused_worker_run_ids=sorted(reused_worker_ids),
        fresh_worker_run_ids=sorted(fresh_worker_ids), fresh_run_instance_ids=sorted(fresh_instance_ids),
        worker_models_sha256={wid:runner.value_digest(models) for wid, models in worker_models.items()},
        model_execution_sha256=runner.digest(HERE/'model-execution.json'),
        reproduced_interrupted_rows=model_execution['reproduced_interrupted_rows'],
        serial_timing_threads_per_model=2, serial_timing_schedule='unchanged-144-uncached',
        timing_limit_override='Original model-execution timing_limit retains historical four-worker wording. '
            'Reused chunks predate this resource cap; fresh factorial collection is capped at two workers. '
            'Factorial receipts include caching/contention and are not engine latency; use serial timing-results.json.')
    runner.b.atomic_json(HERE/'resource-receipt.json', receipt)
    print('PASS: resource cap=2, reused checkpoint bytes unchanged, frozen overlap verified.', flush=True)


def selfcheck():
    active = peak = 0
    lock = threading.Lock()
    first_pair = threading.Barrier(ACTUAL_MAX_WORKERS)

    def fake_task(index):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            if index < ACTUAL_MAX_WORKERS:
                first_pair.wait(timeout=5)
            return index
        finally:
            with lock:
                active -= 1

    with ResourceSafeExecutor(max_workers=REQUESTED_WORKERS) as pool:
        futures = [pool.submit(fake_task, index) for index in range(12)]
        assert [future.result() for future in futures] == list(range(12))
        assert pool._max_workers == ACTUAL_MAX_WORKERS
    assert peak == ACTUAL_MAX_WORKERS and active == 0
    for requested in (None, 1, 2, 3, 5, 4.0):
        try:
            ResourceSafeExecutor(max_workers=requested)
        except ValueError:
            pass
        else:
            raise AssertionError('Unexpected worker contract accepted')
    with tempfile.TemporaryDirectory() as folder:
        study = Path(folder)/'study'
        work = Path(folder)/'work'
        study.mkdir()
        work.mkdir()
        for name in AMENDMENT_FILES:
            (study/name).write_text(name, encoding='utf8')
        (work/'task.json').write_text('accepted bytes', encoding='utf8')
        identities = dict(original_freeze_sha256='original', execution_freeze_sha256='execution',
                          runner_sha256='runner')
        resource = dict(schema_version=1, **identities, requested_workers=REQUESTED_WORKERS,
            actual_max_workers=ACTUAL_MAX_WORKERS,
            files={name:runner.digest(study/name) for name in AMENDMENT_FILES},
            previous_checkpoint_sha256={'task':runner.digest(work/'task.json')})
        before = verify_resource_freeze(resource, work, {'task'}, identities, study)
        assert before == resource['previous_checkpoint_sha256']
        bad = {**resource, 'runner_sha256':'different'}
        try:
            verify_resource_freeze(bad, work, {'task'}, identities, study)
        except ValueError:
            pass
        else:
            raise AssertionError('Different resource base pin accepted')
        (work/'task.json').write_text('changed checkpoint', encoding='utf8')
        try:
            verify_resource_freeze(resource, work, {'task'}, identities, study)
        except ValueError:
            pass
        else:
            raise AssertionError('Changed accepted checkpoint bytes allowed')
        (work/'task.json').write_text('accepted bytes', encoding='utf8')
        (study/'RESOURCE-AMENDMENT.md').write_text('changed amendment', encoding='utf8')
        try:
            verify_resource_freeze(resource, work, {'task'}, identities, study)
        except ValueError:
            pass
        else:
            raise AssertionError('Different amendment pin accepted')
        try:
            start_history(work, 'resource-sha', {'extra'})
        except ValueError:
            pass
        else:
            raise AssertionError('Unproven extra checkpoint accepted')
        path, history = start_history(work, 'resource-sha', set())
        history['attempts'].append(dict(state='started'))
        runner.b.atomic_json(path, history)
        assert start_history(work, 'resource-sha', {'extra'})[1] == history
        try:
            start_history(work, 'wrong-resource-sha', {'extra'})
        except ValueError:
            pass
        else:
            raise AssertionError('Different start-history pin accepted')
    return dict(state='passed', model_calls=0, fake_tasks=12, peak_active_fake_tasks=peak,
                requested_workers=REQUESTED_WORKERS, actual_max_workers=ACTUAL_MAX_WORKERS,
                wrong_worker_contract_rejected=True, bad_base_pin_rejected=True,
                accepted_checkpoint_tamper_rejected=True,
                bad_amendment_pin_rejected=True, unproven_extra_checkpoint_rejected=True,
                matching_resume_history_accepted=True, bad_resume_history_pin_rejected=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--selfcheck', action='store_true')
    mode.add_argument('--run', action='store_true')
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--work-dir', type=Path)
    args = parser.parse_args()
    if args.selfcheck:
        print(runner.b.dumps(selfcheck()))
    elif args.cache and args.work_dir:
        run(args.cache, args.work_dir)
    else:
        parser.error('Use --selfcheck or --run --cache EXTERNAL --work-dir EXTERNAL')
