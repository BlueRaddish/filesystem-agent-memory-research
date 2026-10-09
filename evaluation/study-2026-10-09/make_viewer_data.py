"""Compact public data for the portable viewer; original receipts remain authoritative."""
import json
from pathlib import Path
import sys
import run_study as main

HERE = Path(__file__).resolve().parent


def build():
    names = ('results.json', 'followup-results.json', 'maintenance-results.json',
             'summary.json', 'adjudication.json')
    inputs = {n: json.loads((HERE / n).read_text(encoding='utf8')) for n in names}
    audit = {v['trial_id']: v for v in inputs['adjudication.json']['trial_adjudications']}
    rows = []
    for t in inputs['results.json']['trials']:
        score = t['score']
        row = {k: t[k] for k in ('trial_id', 'case_id', 'hypothesis', 'condition',
                               'regime', 'onboarding', 'termination', 'turns',
                               'actions', 'returned_bytes', 'seconds')}
        row.update({k: score[k] for k in ('complete_task', 'critical_pass',
                    'artifact_written', 'citation_complete', 'origin_read_complete',
                    'post_write_checks_pass', 'reader_saw_post_write_check',
                    'wrong_fields', 'artifact')})
        row['sensitivity_complete_task'] = audit[t['trial_id']]['sensitivity_complete_task']
        row['recorded_tokens'] = (sum(c['usage'].get('input_tokens', 0) +
                                      c['usage'].get('output_tokens', 0) for c in t['calls'])
                                  if t['calls'] else None)
        row['native_unavailable_attempts'] = sum(c['control_receipt'].get(
            'native_failed_unavailable_count', 0) for c in t['calls'])
        rows.append(row)
    maintenance = []
    for t in inputs['maintenance-results.json']['traces']:
        value = {k: t[k] for k in ('id', 'hypothesis', 'condition_id', 'summary')}
        value['checkpoints'] = [{k: v for k, v in p.items() if k != 'file_manifest'}
                                for p in t['checkpoints']]
        maintenance.append(value)
    diagnostics = [{**{k:t[k] for k in ('trial_id','case_id','condition','turns',
                    'actions','returned_bytes','seconds','termination')}, 'score':t['score']}
                   for t in inputs['followup-results.json']['trials']]
    return dict(schema_version=1, source_sha256={n: main.sha((HERE/n).read_bytes()) for n in names},
                primary_label='Frozen rubric; source audit is posthoc sensitivity',
                main_trials=rows, maintenance=maintenance, diagnostics=diagnostics,
                audit_metrics=inputs['adjudication.json']['metrics'],
                failure_partition=inputs['adjudication.json']['frozen_failure_primary_class_counts'],
                onboarding=inputs['summary.json']['onboarding'],
                aborted=[dict(attempt=1, launched=28, receipts=25, meaningful_original_reads=0),
                         dict(attempt=2, launched=25, receipts=22, meaningful_original_reads=0)])


def selfcheck(data):
    rows=data['main_trials']
    assert len(rows)==86 and len({v['trial_id'] for v in rows})==86
    principal=[v for v in rows if v['onboarding']=='unbriefed']
    assert len(principal)==80
    assert sum(v['complete_task'] for v in principal)==60
    assert sum(v['sensitivity_complete_task'] for v in principal)==77
    assert len(data['diagnostics'])==4 and len(data['maintenance'])==5
    stale=next(v for v in rows if v['trial_id']=='T043')
    assert stale['artifact']['config']['jitter_ms']==200
    assert not stale['sensitivity_complete_task']


if __name__=='__main__':
    data=build()
    selfcheck(data)
    if '--self-check' not in sys.argv:
        (HERE/'viewer-data.json').write_text(main.dumps(data)+'\n',encoding='utf8')
    print('Viewer data check passed: 80 main + six onboarding; four separate diagnostics')
