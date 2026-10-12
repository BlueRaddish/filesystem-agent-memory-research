"""Durable execution amendment; frozen retrieval functions remain untouched.

The frozen shuffled jobs are partitioned by their unique task/query. A task's
eight index/gate groups retain their original relative order and score cache.
Four workers use independent two-thread CPU sessions. Factorial timings therefore
describe execution only; the original 144 uncached timing observations run serially.
Completed task checkpoints are hash-checked and never scored again on resume.
"""
import argparse
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import tempfile
import threading
import time
import uuid

import benchmark as b

HERE = Path(__file__).resolve().parent
PACKETS = tuple(itertools.product((0, 1), (4096, 8192)))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def value_digest(value):
    return b.sha(b.dumps(value))


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def safe_relative(name):
    path = Path(name)
    require(not path.is_absolute() and '..' not in path.parts, 'Unsafe input path')
    result = (HERE/path).resolve()
    require(result.is_relative_to(HERE), 'Input escaped study directory')
    return result


def external(path):
    path = Path(path).resolve()
    require(not path.is_relative_to(HERE.parents[1]), 'Work/cache must be outside public repository')
    return path


def jobs_for(families):
    tasks = [t for f in families for t in f['tasks']]
    require(len({t['id'] for t in tasks}) == len(tasks), 'Task IDs must be unique')
    require(len({t['query'] for t in tasks}) == len(tasks), 'Query partition is not independent')
    require(len({b.sha(t['query']) for t in tasks}) == len(tasks), 'Query digest collision')
    jobs = [(f, t, size, a, c) for f in families for t in f['tasks']
            for size in (48, 144) for a in (0, 1) for c in (0, 1)]
    random.Random(1011).shuffle(jobs)
    grouped = OrderedDict()
    for index, job in enumerate(jobs):
        grouped.setdefault(job[1]['id'], []).append((index, job))
    require(all(len(group) == 8 for group in grouped.values()), 'Eight groups required per task')
    return jobs, grouped


def task_pin(group, run_pin):
    family, task, _, _, _ = group[0][1]
    return dict(run_pin=run_pin, task_id=task['id'], family_id=family['id'],
                query_sha256=b.sha(task['query']), task_input_sha256=value_digest(task),
                jobs=[dict(global_index=i, collection_size=j[2], cues=j[3], gate=j[4])
                      for i, j in group])


def row_for(index, engine_index, packet_index, family, task, size, a, c,
            engine, ranking, result, docs):
    expand, budget = PACKETS[packet_index]
    ranking_id = f'K{index*len(b.ENGINES)+engine_index+1:05}'
    return dict(id=f'R{(index*len(b.ENGINES)+engine_index)*len(PACKETS)+packet_index+1:05}',
                task_id=task['id'], family_id=family['id'], split=b.split(family['id']),
                stratum=family['stratum'], engine=engine, factors=f'{a}{expand}{c}',
                collection_size=size, budget=budget, ranking_id=ranking_id,
                **result, **b.retrieval_score(task, result, ranking, docs))


def task_result(group, all_docs, scorers, pin, worker_id):
    source = b.Scores(scorers, cache=True)
    rows, rankings = [], []
    for index, (family, task, size, a, c) in group:
        docs = b.make_collection(all_docs, family['id'], size)
        for engine_index, engine in enumerate(b.ENGINES):
            ranking = b.rank_docs(docs, task['query'], bool(a), bool(c), engine, source)
            ranking_id = f'K{index*len(b.ENGINES)+engine_index+1:05}'
            rankings.append(dict(id=ranking_id, task_id=task['id'], family_id=family['id'],
                                 collection_size=size, cues=a, gate=c, engine=engine, **ranking))
            for packet_index, (expand, budget) in enumerate(PACKETS):
                result = b.pack(docs, ranking, bool(a), bool(expand), budget)
                rows.append(row_for(index, engine_index, packet_index, family, task,
                                    size, a, c, engine, ranking, result, docs))
    return dict(pin=pin, rows=rows, rankings=rankings, worker_id=worker_id,
                models={name: model.manifest for name, model in scorers.items()},
                unique_cached_pair_count=len(source.values), inference_events=source.events)


def envelope(payload):
    return dict(schema_version=1, payload_sha256=value_digest(payload), payload=payload)


def unwrap(path, pin):
    data = read(path)
    require(data.get('schema_version') == 1, 'Checkpoint schema differs')
    payload = data.get('payload')
    require(isinstance(payload, dict) and data.get('payload_sha256') == value_digest(payload),
            'Checkpoint digest differs')
    require(payload.get('pin') == pin, 'Checkpoint input pins differ')
    return payload


def validate_chunk(payload, group, all_docs, expected_models):
    require(set(payload['models']) == set(expected_models), 'Checkpoint model names differ')
    for name, manifest in payload['models'].items():
        require(manifest['files'] == expected_models[name], 'Checkpoint model files differ')
        require(manifest['threads'] == 2 and manifest['batch_size'] == 12,
                'Checkpoint CPU/batch configuration differs')
    rankings = {r['id']: r for r in payload['rankings']}
    rows = {r['id']: r for r in payload['rows']}
    require(len(rankings) == len(payload['rankings']) == 48, 'Checkpoint rankings incomplete')
    require(len(rows) == len(payload['rows']) == 192, 'Checkpoint packet rows incomplete')
    expected_rows, expected_rankings = set(), set()
    for index, (family, task, size, a, c) in group:
        docs = b.make_collection(all_docs, family['id'], size)
        for engine_index, engine in enumerate(b.ENGINES):
            ranking_id = f'K{index*len(b.ENGINES)+engine_index+1:05}'
            expected_rankings.add(ranking_id)
            require(ranking_id in rankings, 'Checkpoint ranking absent')
            ranking = rankings[ranking_id]
            require(all(ranking.get(k) == v for k, v in dict(task_id=task['id'],
                    family_id=family['id'], collection_size=size, cues=a, gate=c,
                    engine=engine).items()), 'Checkpoint ranking schedule differs')
            eligible = ranking['eligible_ids']
            candidates = ranking['candidate_ids']
            require(len(set(eligible)) == len(eligible) and set(eligible).issubset(docs),
                    'Checkpoint eligibility invalid')
            require(len(set(candidates)) == len(candidates) and set(candidates).issubset(eligible)
                    and ranking['ranked_ids'] == candidates, 'Checkpoint candidate order invalid')
            for packet_index, (expand, budget) in enumerate(PACKETS):
                result = b.pack(docs, ranking, bool(a), bool(expand), budget)
                expected = row_for(index, engine_index, packet_index, family, task,
                                   size, a, c, engine, ranking, result, docs)
                expected_rows.add(expected['id'])
                require(rows.get(expected['id']) == expected, 'Checkpoint packet reconstruction differs')
    require(set(rows) == expected_rows and set(rankings) == expected_rankings,
            'Checkpoint IDs differ')


def verify_execution():
    original = b.verify_freeze()
    execution = read(HERE/'execution-freeze.json')
    require(execution['original_freeze_sha256'] == digest(HERE/'freeze.json'),
            'Original freeze digest differs')
    require(execution['runner_sha256'] == digest(__file__), 'Runner freeze digest differs')
    require(execution['workers'] == 4, 'Four factorial workers required')
    require(execution['model_files'] == original['model_files'], 'Execution model pins differ')
    for name, expected in execution.get('files', {}).items():
        require(digest(safe_relative(name)) == expected, 'Execution amendment input differs: '+name)
    interrupted = execution.get('interrupted_results')
    old = None
    if interrupted:
        path = safe_relative(interrupted['path'])
        require(digest(path) == interrupted['sha256'], 'Interrupted snapshot digest differs')
        old = read(path)
        require(old['planned_rows'] == 18432 and old['state'] == 'running',
                'Expected preserved interrupted snapshot')
        require(len({r['id'] for r in old['rows']}) == len(old['rows']),
                'Interrupted snapshot duplicates IDs')
    return original, execution, old


def timing_jobs(families):
    development = []
    for author in ('A', 'B'):
        development.extend(sorted((f for f in families if f['id'].startswith(author)
            and b.split(f['id']) == 'development'), key=lambda f:f['id'])[:3])
    jobs = []
    for family in development:
        for task in family['tasks']:
            for repeat in range(2):
                engines = list(b.ENGINES)
                random.Random(task['id']+str(repeat)).shuffle(engines)
                jobs.extend((family, task, repeat, engine) for engine in engines)
    require(len(jobs) == 144, 'Timing schedule differs')
    return jobs


def timing_run(families, all_docs, scorers, path, run_pin):
    pin = dict(run_pin=run_pin, schedule='frozen-serial-uncached-144')
    payload = unwrap(path, pin) if path.exists() else dict(pin=pin, rows=[])
    jobs = timing_jobs(families)
    require(len(payload['rows']) <= len(jobs), 'Too many timing checkpoints')
    for observed, (family, task, repeat, engine) in zip(payload['rows'], jobs):
        require(all(observed[k] == v for k, v in dict(task_id=task['id'],
            family_id=family['id'], repeat=repeat, engine=engine).items()),
            'Timing checkpoint schedule differs')
        require(isinstance(observed['seconds'], (int, float)) and math.isfinite(observed['seconds'])
                and observed['seconds'] >= 0,
                'Timing checkpoint duration invalid')
    for family, task, repeat, engine in jobs[len(payload['rows']):]:
        docs = b.make_collection(all_docs, family['id'], 144)
        source = b.Scores(scorers, cache=False)
        started = time.perf_counter()
        ranking = b.rank_docs(docs, task['query'], True, True, engine, source)
        result = b.pack(docs, ranking, True, True, 4096)
        payload['rows'].append(dict(task_id=task['id'], family_id=family['id'], engine=engine,
            repeat=repeat, seconds=time.perf_counter()-started,
            scored_pairs=sum(e['pairs'] for e in source.events),
            scorer_tokens=sum(e['input_pair_tokens'] for e in source.events),
            truncated_pairs=sum(e['truncated_pairs'] for e in source.events), packet_bytes=result['bytes']))
        b.atomic_json(path, envelope(payload))
        print(f"Timing {len(payload['rows'])}/144 serial uncached observations", flush=True)
    return payload['rows']


def load_scorers(cache, expected):
    from model_runtime import Scorer
    scorers = {name:Scorer(cache, name, threads=2, batch_size=12) for name in ('minilm', 'mixedbread')}
    require(all(model.manifest['files'] == expected[name] for name, model in scorers.items()),
            'Loaded models/tokenizers differ from freeze')
    return scorers


def run(cache, work, workers):
    cache, work = external(cache), external(work)
    original, execution, interrupted = verify_execution()
    require(workers == execution['workers'], 'Worker count differs from execution freeze')
    families = b.load_bank()
    jobs, grouped = jobs_for(families)
    require(len(jobs) == 768 and len(grouped) == 96, 'Original schedule size differs')
    all_docs = b.docs_for(families)
    run_pin = dict(original_freeze_sha256=digest(HERE/'freeze.json'),
                   execution_freeze_sha256=digest(HERE/'execution-freeze.json'),
                   runner_sha256=digest(__file__), model_files=original['model_files'],
                   query_sha256={tid:b.sha(group[0][1][1]['query']) for tid, group in grouped.items()})
    work.mkdir(parents=True, exist_ok=True)
    manifest = work/'manifest.json'
    if manifest.exists():
        require(read(manifest) == run_pin, 'External work directory belongs to different inputs')
    else:
        require(not any(work.iterdir()), 'New work directory must be empty')
        b.atomic_json(manifest, run_pin)
    chunks, pending = {}, []
    for task_id, group in grouped.items():
        pin = task_pin(group, run_pin)
        path = work/(task_id+'.json')
        if path.exists():
            payload = unwrap(path, pin)
            validate_chunk(payload, group, all_docs, original['model_files'])
            chunks[task_id] = payload
        else:
            pending.append((task_id, group, pin, path))
    print(f'Resume verified {len(chunks)}/96 completed task checkpoints; {len(pending)} tasks pending', flush=True)
    completion_path = work/'completion.json'
    public_names = ('retrieval-results.json', 'rankings.json', 'model-execution.json',
                    'timing-results.json', 'recovery-receipt.json')
    if completion_path.exists():
        completion = read(completion_path)
        require(completion.get('state') == 'complete' and completion.get('run_pin') == run_pin,
                'Completion input pins differ')
        require(len(chunks) == 96 and set(completion['files']) == set(public_names),
                'Completion checkpoint coverage differs')
        require(all(digest(HERE/name) == completion['files'][name] for name in public_names),
                'Completed public output digest differs')
        print('PASS: complete public outputs and all task checkpoints hash-verified; no scoring repeated.', flush=True)
        return
    local, lock, instances = threading.local(), threading.Lock(), {}
    instance_prefix = uuid.uuid4().hex[:12]

    def execute(item):
        if not hasattr(local, 'scorers'):
            local.scorers = load_scorers(cache, original['model_files'])
            with lock:
                local.worker_id = instance_prefix+':'+str(len(instances))
                instances[local.worker_id] = local.scorers
        task_id, group, pin, path = item
        payload = task_result(group, all_docs, local.scorers, pin, local.worker_id)
        validate_chunk(payload, group, all_docs, original['model_files'])
        b.atomic_json(path, envelope(payload))
        return task_id, payload

    # Every completed task is durable before it is returned. On errors retain all
    # checkpoints; unfinished tasks have no outcome and resume from their boundary.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(execute, item) for item in pending]
        try:
            for future in as_completed(futures):
                task_id, payload = future.result()
                chunks[task_id] = payload
                b.atomic_json(work/'progress.json', dict(completed_tasks=len(chunks), planned_tasks=96,
                    completed_rows=sum(len(c['rows']) for c in chunks.values()), state='running'))
                print(f'Checkpoint {len(chunks)}/96 tasks; {len(chunks)*192}/18432 packet comparisons', flush=True)
        except BaseException:
            for future in futures:
                future.cancel()
            raise
    require(len(chunks) == 96, 'Retrieval collection incomplete')
    rows = sorted((r for chunk in chunks.values() for r in chunk['rows']), key=lambda r:r['id'])
    rankings = sorted((r for chunk in chunks.values() for r in chunk['rankings']), key=lambda r:r['id'])
    require([r['id'] for r in rows] == [f'R{i:05}' for i in range(1, 18433)], 'Global packet IDs differ')
    require([r['id'] for r in rankings] == [f'K{i:05}' for i in range(1, 4609)], 'Global ranking IDs differ')
    if interrupted:
        by_id = {r['id']:r for r in rows}
        for old in interrupted['rows']:
            require(by_id.get(old['id']) == old, 'Interrupted outcome differs: '+old['id'])
    print(f'PASS: {len(interrupted["rows"]) if interrupted else 0} interrupted outcome rows exactly reproduced', flush=True)
    timing_path = work/'timing.json'
    timing_pin = dict(run_pin=run_pin, schedule='frozen-serial-uncached-144')
    warmup_path = work/'timing-warmups.json'
    warmup_pin = dict(run_pin=run_pin, schedule='resume-development-only-warmup-history')
    warmups = unwrap(warmup_path, warmup_pin) if warmup_path.exists() else dict(pin=warmup_pin, rows=[])
    timing_complete = timing_path.exists() and len(unwrap(timing_path, timing_pin)['rows']) == 144
    if timing_complete:
        timing = timing_run(families, all_docs, None, timing_path, run_pin)
        warmup = None
    else:
        # No thread uses these sessions after the pool closes. Reuse an exercised
        # worker instead of changing model configuration for the serial block.
        scorers = next(iter(instances.values())) if instances else load_scorers(cache, original['model_files'])
        warmup = None
        if not instances:
            first_dev = next(f for f in families if b.split(f['id']) == 'development')
            task = first_dev['tasks'][0]
            doc = all_docs[first_dev['records'][0]['id']]
            warmup = {name:model.score(task['query'], [b.render(doc, True)])[1]
                      for name, model in scorers.items()}
            warmups['rows'].append(dict(instance=instance_prefix, development_task=task['id'],
                preceding_completed_timing_rows=len(unwrap(timing_path, timing_pin)['rows']) if timing_path.exists() else 0,
                models={name:model.manifest for name, model in scorers.items()}, receipts=warmup))
            b.atomic_json(warmup_path, envelope(warmups))
        timing = timing_run(families, all_docs, scorers, timing_path, run_pin)
    ordered = [chunks[task_id] for task_id in grouped]
    worker_models = {}
    for chunk in ordered:
        require(chunk['worker_id'] not in worker_models or worker_models[chunk['worker_id']] == chunk['models'],
                'Worker model receipt changed')
        worker_models[chunk['worker_id']] = chunk['models']
    execution_result = dict(models=ordered[0]['models'], worker_models=worker_models,
        unique_cached_pair_count=sum(c['unique_cached_pair_count'] for c in ordered),
        inference_events=[dict(task_id=c['pin']['task_id'], worker_id=c['worker_id'], **event)
                          for c in ordered for event in c['inference_events']],
        execution_freeze_sha256=digest(HERE/'execution-freeze.json'),
        checkpoints={tid:digest(work/(tid+'.json')) for tid in grouped},
        reproduced_interrupted_rows=len(interrupted['rows']) if interrupted else 0,
        resume_timing_warmup=warmup,
        resume_timing_warmup_history=warmups['rows'],
        inference_event_order='Task first appearance in frozen shuffle; within each task original scorer-call order. Not global chronological order.',
        timing_limit='Four-worker factorial receipts include caching and CPU contention; use serial timing-results.json for engine latency.')
    b.atomic_json(HERE/'rankings.json', dict(rows=rankings))
    b.atomic_json(HERE/'model-execution.json', execution_result)
    b.atomic_json(HERE/'timing-results.json', dict(state='complete', rows=timing,
        pair_cache_enabled=False, includes_index_construction=True, excludes_model_load_and_download=True))
    # Completion is published last, after every checkpoint and interruption match.
    b.atomic_json(HERE/'retrieval-results.json', dict(state='complete', planned_rows=18432,
        execution_freeze_sha256=digest(HERE/'execution-freeze.json'), rows=rows))
    b.atomic_json(HERE/'recovery-receipt.json', dict(state='published_success', complete=True,
        overlap_matches=len(interrupted['rows']) if interrupted else 0,
        overlap_planned=len(interrupted['rows']) if interrupted else 0,
        exact_all_row_values_match=True, complete_retrieval_rows=len(rows), complete_rankings=len(rankings),
        complete_serial_timing_observations=len(timing),
        original_freeze_sha256=digest(HERE/'freeze.json'),
        execution_freeze_sha256=digest(HERE/'execution-freeze.json'), runner_sha256=digest(__file__)))
    b.atomic_json(completion_path, dict(state='complete', run_pin=run_pin,
        files={name:digest(HERE/name) for name in public_names}))
    print('PASS: 18432 retrieval packets, 4608 rankings, and 144 serial uncached timing observations.', flush=True)


def without_execution_time(rankings):
    return [{k:v for k, v in row.items() if k != 'rank_execution_seconds'} for row in rankings]


def serial_reference(group, all_docs, scorers):
    # Independent original-loop projection: grouping changes execution order only.
    source = b.Scores(scorers, cache=True)
    rows, rankings = [], []
    for index, (f, task, size, a, c) in group:
        docs = b.make_collection(all_docs, f['id'], size)
        for engine_index, engine in enumerate(b.ENGINES):
            ranking = b.rank_docs(docs, task['query'], bool(a), bool(c), engine, source)
            ranking_id = f'K{index*6+engine_index+1:05}'
            rankings.append(dict(id=ranking_id, task_id=task['id'], family_id=f['id'],
                                 collection_size=size, cues=a, gate=c, engine=engine, **ranking))
            for packet_index, (expand, budget) in enumerate(itertools.product((0, 1), (4096, 8192))):
                result = b.pack(docs, ranking, bool(a), bool(expand), budget)
                rows.append(dict(id=f'R{index*24+engine_index*4+packet_index+1:05}',
                    task_id=task['id'], family_id=f['id'], split=b.split(f['id']),
                    stratum=f['stratum'], engine=engine, factors=f'{a}{expand}{c}',
                    collection_size=size, budget=budget, ranking_id=ranking_id,
                    **result, **b.retrieval_score(task, result, ranking, docs)))
    return rows, rankings, source


def development_check(cache):
    freeze = b.verify_freeze()
    families = b.load_bank()
    _, grouped = jobs_for(families)
    task_id = min(tid for tid, group in grouped.items() if b.split(group[0][1][0]['id']) == 'development')
    group, docs = grouped[task_id], b.docs_for(families)
    serial = load_scorers(external(cache), freeze['model_files'])
    rows, rankings, source = serial_reference(group, docs, serial)
    separate = load_scorers(external(cache), freeze['model_files'])
    payload = task_result(group, docs, separate, dict(development_only=True), 'development-only')
    require(rows == payload['rows'], 'Development serial packet outcomes differ')
    require(without_execution_time(rankings) == without_execution_time(payload['rankings']),
            'Development serial ranking outcomes differ')
    require(len(source.values) == payload['unique_cached_pair_count'], 'Development cache partition differs')
    require([{k:v for k,v in e.items() if k != 'seconds'} for e in source.events] ==
            [{k:v for k,v in e.items() if k != 'seconds'} for e in payload['inference_events']],
            'Development scorer pair grouping differs')
    validate_chunk(payload, group, docs, freeze['model_files'])
    return dict(state='passed', development_task=task_id, held_out_tasks=0,
        compared_packet_rows=len(rows), compared_rankings=len(rankings),
        unique_cached_pairs=len(source.values), inference_events=len(source.events),
        exact_packet_and_ranking_match=True, exact_pair_grouping_match=True,
        original_freeze_sha256=digest(HERE/'freeze.json'), runner_sha256=digest(__file__))


def selfcheck():
    families = b.load_bank()
    jobs, grouped = jobs_for(families)
    require(len(jobs) == 768 and len(grouped) == 96, 'Frozen schedule count differs')
    reconstructed = sorted((index, job) for group in grouped.values() for index, job in group)
    require([job for _, job in reconstructed] == jobs, 'Task partition changed global ordering')
    require(all([i for i, _ in group] == sorted(i for i, _ in group) for group in grouped.values()),
            'Relative task order changed')
    require(len(timing_jobs(families)) == 144, 'Timing count differs')
    ids = [f'R{index*24+engine*4+packet+1:05}' for index in range(768)
           for engine in range(6) for packet in range(4)]
    require(ids == [f'R{i:05}' for i in range(1, 18433)], 'Packet numbering differs')
    class Fake:
        def __init__(self):
            self.manifest = dict(files={}, threads=2, batch_size=12)
        def score(self, query, texts):
            return [int(b.sha(query+'\n'+text)[:8], 16)/2**32 for text in texts], dict(
                seconds=0, pairs=len(texts), input_pair_tokens=0, truncated_pairs=0)
    group = next(iter(grouped.values()))
    docs = b.docs_for(families)
    scorers = {name:Fake() for name in ('minilm', 'mixedbread')}
    reference, rankings, source = serial_reference(group, docs, scorers)
    pin = task_pin(group, dict(test=True))
    payload = task_result(group, docs, scorers, pin, 'fake')
    require(reference == payload['rows'] and without_execution_time(rankings) ==
            without_execution_time(payload['rankings']), 'Deterministic partition differs')
    require(len(source.values) == payload['unique_cached_pair_count'], 'Cache query partition differs')
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)/'checkpoint.json'
        b.atomic_json(path, envelope(payload))
        loaded = unwrap(path, pin)
        validate_chunk(loaded, group, docs, {name:{} for name in scorers})
        changed = read(path)
        changed['payload']['rows'][0]['bytes'] += 1
        b.atomic_json(path, changed)
        try:
            unwrap(path, pin)
        except ValueError:
            pass
        else:
            raise AssertionError('Corrupt checkpoint accepted')
        b.atomic_json(path, envelope(payload))
        try:
            unwrap(path, {**pin, 'query_sha256':'different'})
        except ValueError:
            pass
        else:
            raise AssertionError('Different input checkpoint accepted')
    return dict(state='passed', model_calls=0, distinct_query_tasks=96,
        global_groups=768, expected_packets=18432, checkpoint_corruption_rejected=True,
        input_change_rejected=True, deterministic_serial_projection_match=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--selfcheck', action='store_true')
    mode.add_argument('--development-check', action='store_true')
    mode.add_argument('--run', action='store_true')
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if args.selfcheck:
        print(b.dumps(selfcheck()))
    elif args.development_check and args.cache:
        print(b.dumps(development_check(args.cache)))
    elif args.run and args.cache and args.work_dir:
        run(args.cache, args.work_dir, args.workers)
    else:
        parser.error('Use --selfcheck, --development-check --cache EXTERNAL, or --run --cache EXTERNAL --work-dir EXTERNAL --workers 4')
