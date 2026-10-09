"""Outcome-selected UTF-8 diagnostic; reuses the unchanged frozen main runner."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import time

import run_study as main

HERE = Path(__file__).resolve().parent
INPUTS = ('run_followup.py', 'run_study.py', 'cases.json', 'secondary-cases.json',
          'unicode-case.json', 'results.json', 'followup-plan.md')


def cases():
    return {c['id']: c for c in main.read_cases() +
            json.loads((HERE / 'unicode-case.json').read_text(encoding='utf8'))['cases']}


def jobs():
    selected = [('h1_sablefin', arm) for arm in
                ('source_only', 'unlinked_current', 'linked_current')]
    selected.append(('unicode-lantern', 'source_only'))
    return [dict(trial_id=f'D{n:03}', case_id=case, condition=arm,
                 regime='fidelity_first', onboarding='unbriefed')
            for n, (case, arm) in enumerate(selected, 1)]


def freeze():
    value = dict(study='Outcome-selected transport diagnostic, not main replication',
                 utc_frozen_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                 files={p: main.sha((HERE / p).read_bytes()) for p in INPUTS},
                 jobs=jobs(), workers=4, model='muse-spark-1.3-contributor',
                 reasoning_effort='high', regime=main.REGIMES['fidelity_first'],
                 reader_prompt_sha256=main.sha(main.PROMPT.encode()),
                 transport_change='Same private adapter invoked with Python -X utf8',
                 selected_after_main_outcomes=True, scored_retry_policy='none')
    (HERE / 'followup-freeze.json').write_text(main.dumps(value) + '\n', encoding='utf8')
    print('Frozen four diagnostic trials')


def run(args):
    frozen = json.loads((HERE / 'followup-freeze.json').read_text(encoding='utf8'))
    for p, expected in frozen['files'].items():
        assert main.sha((HERE / p).read_bytes()) == expected, 'Changed diagnostic input: ' + p
    command = json.loads(Path(args.reader_command_file).read_text(encoding='utf8'))
    assert isinstance(command, list) and all(isinstance(x, str) for x in command)
    assert any(command[n:n + 2] == ['-X', 'utf8'] for n in range(len(command))), 'UTF-8 mode required'
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    corpus = cases()
    results = []
    with ThreadPoolExecutor(max_workers=frozen['workers']) as executor:
        pending = [executor.submit(main.trial, j, corpus[j['case_id']], command, work)
                   for j in frozen['jobs']]
        for future in as_completed(pending):
            result = future.result()
            results.append(result)
            print(result['trial_id'], result['condition'], result['score']['complete_task'],
                  result['termination'], flush=True)
    output = dict(schema_version=1,
                  freeze_sha256=main.sha((HERE / 'followup-freeze.json').read_bytes()),
                  trials=sorted(results, key=lambda v: v['trial_id']))
    Path(args.output).write_text(main.dumps(output) + '\n', encoding='utf8')


def selfcheck():
    corpus = cases()
    selected = jobs()
    assert len(selected) == 4 and len({j['trial_id'] for j in selected}) == 4
    for j in selected:
        assert j['case_id'] in corpus
        assert j['condition'] in {a['id'] for a in corpus[j['case_id']]['conditions']}
    unicode_case = corpus['unicode-lantern']
    assert unicode_case['gold']['expected_artifact']['decisions']['accepted_label'] == '\u9752\u706f'
    assert unicode_case['gold']['expected_artifact']['decisions']['symbol'] == '\u03bb'
    print('Diagnostic self-check passed: fixed selection, existing conditions, Unicode gold')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('freeze')
    sub.add_parser('selfcheck')
    running = sub.add_parser('run')
    running.add_argument('--reader-command-file', required=True)
    running.add_argument('--work', required=True)
    running.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.command == 'freeze':
        freeze()
    elif args.command == 'selfcheck':
        selfcheck()
    else:
        run(args)
