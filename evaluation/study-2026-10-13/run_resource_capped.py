"""Historical resource recovery with unchanged scored methods and durable inputs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf8', newline='\n') as handle:
        handle.write(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)

def verify_pins(root, pins):
    for name, expected in pins.items():
        if sha(root / name) != expected:
            raise ValueError('Pinned bytes changed: ' + name)

def commands(work, cache, adapter, freeze):
    return [
        ('grid', ['benchmark_runner.py', '--run', '--work', str(work), '--cache', str(cache), '--freeze-sha256', freeze, '--workers', '1']),
        ('timing', ['benchmark_runner.py', '--timing', '--work', str(work), '--cache', str(cache), '--freeze-sha256', freeze]),
        ('maintenance', ['maintenance_lab.py', '--run', '--work', str(work / 'maintenance'), '--output', str(HERE / 'maintenance-results.json')]),
        ('readers', ['reader_trials.py', '--run', '--work', str(work), '--adapter-command', str(adapter), '--freeze-sha256', freeze, '--workers', '2']),
        ('analysis', ['analyze_results.py', '--analyze', '--freeze-sha256', freeze, '--prepare-receipt', str(work / 'prepare-receipt.json'), '--worker-receipts', str(work), '--output', str(HERE)])]

def execute(stages, work, original_freeze, resource_sha, invoke):
    history = []
    for name, args in stages:
        state = {'stage': name, 'state': 'running', 'utc': datetime.now(timezone.utc).isoformat(),
                 'freeze_sha256': original_freeze, 'resource_freeze_sha256': resource_sha,
                 'actual_local_grid_workers': 1, 'actual_reader_workers': 2, 'completed': history}
        save(work / 'collection-state.json', state)
        print('START ' + name, flush=True)
        start = datetime.now(timezone.utc).isoformat()
        try:
            code = invoke(name, args)
        except OSError as error:
            history.append({'stage': name, 'start_utc': start, 'end_utc': datetime.now(timezone.utc).isoformat(),
                            'exit_code': None, 'launch_error_type': type(error).__name__})
            save(work / 'collection-state.json', {**state, 'state': 'failed_requires_inspection', 'completed': history})
            return 1, history
        history.append({'stage': name, 'start_utc': start, 'end_utc': datetime.now(timezone.utc).isoformat(), 'exit_code': code})
        state.update(state='failed_requires_inspection' if code else 'complete', completed=history)
        save(work / 'collection-state.json', state)
        if code:
            return code, history
        print('COMPLETE ' + name, flush=True)
    save(work / 'collection-state.json', {**state, 'stage': 'all', 'state': 'complete'})
    return 0, history

def self_check():
    stages = commands(Path('private'), Path('cache'), Path('adapter.json'), 'f' * 64)
    assert [name for name, _ in stages] == ['grid', 'timing', 'maintenance', 'readers', 'analysis']
    assert stages[0][1][-2:] == ['--workers', '1']
    assert stages[3][1][-2:] == ['--workers', '2']
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / 'core').write_bytes(b'original')
        pins = {'core': sha(root / 'core')}
        verify_pins(root, pins)
        (root / 'core').write_bytes(b'changed')
        try:
            verify_pins(root, pins)
            raise AssertionError('Mutation accepted')
        except ValueError:
            pass
        seen = []
        def fake(name, args):
            seen.append(name)
            return 73 if name == 'timing' else 0
        code, history = execute(stages, root, 'f' * 64, 'r' * 64, fake)
        assert code == 73 and seen == ['grid', 'timing'] and len(history) == 2
        state = json.loads((root / 'collection-state.json').read_text())
        assert state['state'] == 'failed_requires_inspection' and state['completed'][-1]['exit_code'] == 73
        def unavailable(name, args):
            raise OSError('Synthetic launch failure')
        code, history = execute(stages, root, 'f' * 64, 'r' * 64, unavailable)
        assert code == 1 and len(history) == 1 and history[0]['exit_code'] is None
    print('Resource wrapper self-check passed; no model/provider calls')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--work', type=Path)
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--adapter-command', type=Path)
    parser.add_argument('--resource-freeze-sha256')
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return 0
    if not all((args.work, args.cache, args.adapter_command, args.resource_freeze_sha256)):
        parser.error('Supply private work/cache/adapter and exact resource-freeze SHA')
    for private in (args.work, args.cache, args.adapter_command):
        if private.resolve().is_relative_to(HERE.parent.parent):
            parser.error('Work, model cache and adapter must remain outside the repository')
    resource_path = HERE / 'resource-freeze.json'
    assert sha(resource_path) == args.resource_freeze_sha256
    resource = json.loads(resource_path.read_text(encoding='utf8'))
    assert resource['state'] == 'frozen_after_owned_grid_interruption_before_main_readers'
    assert resource['actual_local_grid_workers'] == 1 and resource['actual_reader_workers'] == 2
    assert sha(HERE / 'freeze.json') == resource['original_freeze_sha256']
    original = json.loads((HERE / 'freeze.json').read_text(encoding='utf8'))
    verify_pins(HERE, original['files'])
    verify_pins(HERE, resource['source_pins'])
    verify_pins(args.work / 'checkpoints', resource['preserved_checkpoints'])
    verify_pins(args.work / 'worker-history', resource['preserved_worker_history'])
    assert not any(p.is_file() for p in (args.work / 'errors').rglob('*')), 'Unsettled diagnostic errors need explicit audit'
    assert not list((args.work / 'reader-checkpoints').glob('*.json')), 'Reader recovery is not authorized by this handoff'
    assert not list((args.work / 'reader-artifacts').glob('*')), 'Existing provider call artifacts need separate recovery'
    invocation = 'resource-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    logdir = args.work / invocation
    logdir.mkdir()
    save(logdir / 'started.json', {'resource_freeze_sha256': args.resource_freeze_sha256,
                                 'original_freeze_sha256': resource['original_freeze_sha256'],
                                 'preserved_checkpoint_count': len(resource['preserved_checkpoints'])})
    def invoke(name, stage):
        with (logdir / (name + '-stdout.txt')).open('wb') as out, (logdir / (name + '-stderr.txt')).open('wb') as err:
            process = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(HERE / stage[0]), *stage[1:]],
                                     stdout=out, stderr=err, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return process.returncode
    code, history = execute(commands(args.work, args.cache, args.adapter_command, resource['original_freeze_sha256']),
                            args.work, resource['original_freeze_sha256'], args.resource_freeze_sha256, invoke)
    verify_pins(args.work / 'checkpoints', resource['preserved_checkpoints'])
    verify_pins(args.work / 'worker-history', resource['preserved_worker_history'])
    save(logdir / 'completed.json', {'exit_code': code, 'stages': history, 'resource_freeze_sha256': args.resource_freeze_sha256})
    if code == 0:
        save(HERE / 'resource-receipt.json', {'state': 'complete', 'resource_freeze_sha256': args.resource_freeze_sha256,
             'original_freeze_sha256': resource['original_freeze_sha256'], 'actual_local_grid_workers': 1,
             'actual_reader_workers': 2, 'historical_schedule_reader_workers': 6,
             'preserved_checkpoint_count': len(resource['preserved_checkpoints']),
             'all_preserved_checkpoint_bytes_unchanged': True, 'stages': history, 'source_pins': resource['source_pins']})
    return code

if __name__ == '__main__':
    sys.exit(main())
