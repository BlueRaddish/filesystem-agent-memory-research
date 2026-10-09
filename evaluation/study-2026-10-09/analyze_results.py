"""Analyze observed pilot receipts. No reader calls; --self-check exports nothing.

Usage: python analyze_results.py --self-check
       python analyze_results.py --input results.json --maintenance maintenance-results.json
Figures describe this engineered pilot, with denominators and paired blocks. They
do not estimate population performance or turn source coverage into recall truth.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
REGIMES = ('matched', 'fidelity_first')
HYPOTHESES = ('H1', 'H2', 'H3', 'H5', 'H7', 'H8')
COLORS = {'matched': '#3B6B9B', 'fidelity_first': '#C27B29',
          'correct': '#3D8070', 'incorrect': '#A24E62'}
ARM_LABELS = {
    'source_only': 'Sources', 'unlinked_current': 'Unlinked view',
    'linked_current': 'Linked view', 'generic_headers': 'Generic headers',
    'problem_scope_alias_headers': 'Problem/scope cues',
    'prose_obligations': 'Prose', 'structured_obligations': 'Rows',
    'fixed_chunks': 'Fixed chunks', 'coherent_capsules': 'Coherent units',
    'explicit_eligibility': 'Eligibility', 'no_dependency_links': 'No links',
    'dependency_links': 'Dependency links', 'unbriefed': 'Entry, unbriefed',
    'no_entry': 'No entry', 'schema_taught': 'Schema taught',
    'canonical': 'Canonical', 'duplicated_copies': 'Project copies',
    'update_triggered': 'Update triggered', 'handoff_triggered': 'Handoff triggered',
    'fixed_period': 'Fixed period'}
MECHANISMS = {'H1': 'Current views', 'H2': 'Problem/scope cues',
              'H3': 'Passage boundaries', 'H4': 'Canonical/copy replay',
              'H5': 'Eligibility', 'H6': 'Capped maintenance replay',
              'H7': 'Dependency links', 'H8': 'Obligation format'}
FAILURE_LABELS = {
    'artifact_absent': 'No authorized artifact write',
    'semantic_mismatch': 'Exact artifact/focus gate failed',
    'critical_mismatch': 'Critical artifact gate failed',
    'written_critical_mismatch': 'Written critical rubric mismatch',
    'citation_incomplete': 'Sufficient citation gate missed',
    'check_incomplete': 'Post-final-write check gate missed',
    'forbidden_attempt': 'Forbidden tool/check attempt',
    'infrastructure_error': 'Infrastructure interruption',
    'origin_proxy_incomplete': 'Original-read proxy incomplete'}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def token_usage(usage):
    """Only recognized observed counters; absent/partial counters are not estimates."""
    if not isinstance(usage, dict):
        return None
    if number(usage.get('total_tokens')):
        return usage['total_tokens']
    for a, b in (('input_tokens', 'output_tokens'), ('prompt_tokens', 'completion_tokens')):
        if number(usage.get(a)) and number(usage.get(b)):
            return usage[a] + usage[b]
    return None


def total_tokens(trial):
    """Recorded accepted-call metadata only; never total/provider trial cost."""
    calls = trial.get('calls', [])
    counts = [token_usage(call.get('usage')) for call in calls]
    return sum(counts) if counts and all(v is not None for v in counts) else None


def adapter_diagnostics(trial):
    calls = trial.get('calls', [])
    counters = [token_usage(c.get('usage')) for c in calls]
    reported = trial.get('failed_adapter_calls')
    failed = reported if number(reported) else int(bool(trial.get('infrastructure_error')))
    names = Counter()
    count = 0
    for call in calls:
        receipt = call.get('control_receipt', {})
        tools = receipt.get('native_failed_unavailable_tools', [])
        if isinstance(tools, list): names.update(set(t for t in tools if isinstance(t, str)))
        value = receipt.get('native_failed_unavailable_count')
        if number(value): count += value
    return {'accepted_calls_recorded': len(calls),
            'accepted_calls_with_recognized_tokens': sum(v is not None for v in counters),
            'accepted_calls_without_recognized_tokens': sum(v is None for v in counters),
            'recorded_accepted_call_tokens': sum(v for v in counters if v is not None) if any(v is not None for v in counters) else None,
            'failed_adapter_calls': failed,
            'failed_adapter_count_basis': 'explicit trial counter' if number(reported) else 'one if infrastructure_error; otherwise zero',
            'failed_adapter_token_usage': 'unmeasured',
            'native_failed_unavailable_attempts_reported': count,
            'accepted_call_receipts_naming_each_unavailable_tool': dict(names),
            'native_name_count_limit':'Names count call receipts, not per-tool attempt totals; total unavailable attempts use the separate reported counter.'}


def artifact_state(trial):
    score = trial.get('score', {})
    if not score.get('artifact_written'): return 'No authorized write'
    return 'Written rubric pass' if score.get('semantic_artifact_correct') else 'Written rubric mismatch'


def convention_diagnostics(trials):
    """Describe frozen-gate sensitivities; never alter a trial score."""
    status_only=[]
    empty_container=[]
    qualified_ids=[]
    labels=Counter()
    for trial in trials:
        score=trial.get('score',{})
        if not score.get('artifact_written'): continue
        wrong=score.get('wrong_fields',{})
        if set(wrong)=={'status'} and score.get('focused_question_pass',True):
            observed=wrong['status'].get('observed')
            labels[str(observed)]+=1
            status_only.append({'trial_id':trial['trial_id'],'case_id':trial['case_id'],
                                'expected_status':wrong['status'].get('expected'),'observed_status':observed,
                                'citation_complete':score.get('citation_complete'),
                                'post_write_checks_pass':score.get('post_write_checks_pass')})
        if set(wrong)=={'historical'} and wrong['historical'].get('expected')=={} and isinstance(wrong['historical'].get('observed'),dict):
            empty_container.append({'trial_id':trial['trial_id'],'case_id':trial['case_id'],
                                    'observed_historical':wrong['historical'].get('observed')})
        evidence=score.get('artifact',{}).get('evidence',[])
        if not score.get('citation_complete') and isinstance(evidence,list) and any(isinstance(v,str) and (':S' in v or '](' in v) for v in evidence):
            qualified_ids.append({'trial_id':trial['trial_id'],'case_id':trial['case_id'],
                                  'evidence':evidence,'critical_pass':score.get('critical_pass'),
                                  'origin_read_complete':score.get('origin_read_complete')})
    return {'status_only_written_mismatch_count':len(status_only),'status_only_observed_labels':dict(labels),
            'status_only_records':status_only,'empty_historical_container_only_mismatch_count':len(empty_container),
            'empty_historical_container_records':empty_container,
            'qualified_citation_format_candidates':qualified_ids,
            'limits':'Descriptive diagnostics only, no rescoring. Qualified citations can coexist with genuinely missing evidence; additional history is not automatically source-supported.'}


def event_action(event):
    value = event.get('action')
    return value if isinstance(value, dict) else {}


def trace_counts(trial):
    events = trial.get('events', [])
    writes = [e for e in events if e.get('executed') and event_action(e).get('tool') == 'write']
    checks = [e for e in events if event_action(e).get('tool') == 'check']
    last_write = max((e.get('seq', 0) for e in writes), default=None)
    return {
        'executed_writes': len(writes),
        'check_attempts': len(checks),
        'executed_checks': sum(bool(e.get('executed')) for e in checks),
        'denied_checks': sum(not e.get('executed') for e in checks),
        'successful_checks_after_final_write': sum(
            bool(e.get('executed')) and e.get('result', {}).get('exit') == 0 and
            last_write is not None and e.get('seq', 0) > last_write for e in checks)}


def failure_flags(trial):
    s = trial.get('score', {})
    return {
        'artifact_absent': not s.get('artifact_written', False),
        'semantic_mismatch': not s.get('semantic_artifact_correct', False),
        'critical_mismatch': not s.get('critical_pass', False),
        'written_critical_mismatch': bool(s.get('artifact_written')) and not s.get('critical_pass', False),
        'citation_incomplete': not s.get('citation_complete', False),
        'check_incomplete': not s.get('post_write_checks_pass', False),
        'forbidden_attempt': s.get('forbidden_attempts', 0) > 0,
        'infrastructure_error': bool(trial.get('infrastructure_error')),
        'origin_proxy_incomplete': not s.get('origin_read_complete', False)}


def aggregate(trials):
    n = len(trials)
    flags = Counter({k: 0 for k in FAILURE_LABELS})
    for trial in trials:
        flags.update(k for k, v in failure_flags(trial).items() if v)
    complete = sum(bool(t.get('score', {}).get('complete_task')) for t in trials)
    critical = sum(not t.get('score', {}).get('critical_pass', False) for t in trials)
    correct = sum(bool(t.get('score', {}).get('semantic_artifact_correct')) for t in trials)
    ratios = [t['score']['originals_read'] / t['score']['required_sources'] for t in trials
              if number(t.get('score', {}).get('originals_read')) and
              number(t.get('score', {}).get('required_sources')) and t['score']['required_sources'] > 0]
    costs = {'recorded_accepted_call_tokens': [total_tokens(t) for t in trials],
             'returned_bytes': [t.get('returned_bytes') for t in trials],
             'actions': [t.get('actions') for t in trials],
             'seconds': [t.get('seconds') for t in trials]}
    traces = [trace_counts(t) for t in trials]
    inspections = [t['score']['reader_saw_post_write_check'] for t in trials
                   if isinstance(t.get('score', {}).get('reader_saw_post_write_check'), bool)]
    adapters = [adapter_diagnostics(t) for t in trials]
    native_names = Counter()
    for diagnostic in adapters: native_names.update(diagnostic['accepted_call_receipts_naming_each_unavailable_tool'])
    return {'n': n, 'complete_task': complete, 'complete_task_rate': complete / n if n else None,
            'semantic_correct': correct, 'critical_gate_failed_trials': critical,
            'critical_gate_failure_rate': critical / n if n else None,
            'written_artifact_critical_mismatch_trials': sum(failure_flags(t)['written_critical_mismatch'] for t in trials),
            'unwritten_infrastructure_critical_gate_failures': sum(not t['score'].get('critical_pass',False) and
                                                                  not t['score'].get('artifact_written',False) and
                                                                  bool(t.get('infrastructure_error')) for t in trials),
            'failure_flag_counts': dict(flags),
            'origin_read_complete_trials': sum(bool(t.get('score', {}).get('origin_read_complete')) for t in trials),
            'mean_authored_original_read_fraction': statistics.mean(ratios) if ratios else None,
            'reader_check_result_inspection_proxy': {'observed_n': len(inspections),
                                                     'received_in_later_turn': sum(inspections),
                                                     'rate': sum(inspections)/len(inspections) if inspections else None},
            'adapter_usage_coverage': {
                'accepted_calls_recorded': sum(d['accepted_calls_recorded'] for d in adapters),
                'accepted_calls_with_recognized_tokens': sum(d['accepted_calls_with_recognized_tokens'] for d in adapters),
                'accepted_calls_without_recognized_tokens': sum(d['accepted_calls_without_recognized_tokens'] for d in adapters),
                'failed_adapter_calls_unmeasured': sum(d['failed_adapter_calls'] for d in adapters),
                'native_failed_unavailable_attempts_reported_in_accepted_calls': sum(d['native_failed_unavailable_attempts_reported'] for d in adapters),
                'accepted_call_receipts_naming_each_unavailable_tool': dict(native_names)},
            'costs': {k: {'observed_n': sum(number(v) for v in vals),
                          'missing_n': sum(not number(v) for v in vals),
                          'median': statistics.median([v for v in vals if number(v)]) if any(number(v) for v in vals) else None,
                          'sum': sum(v for v in vals if number(v))} for k, vals in costs.items()},
            'trace_totals': {k: sum(t[k] for t in traces) for k in trace_counts({})}}


def load_plan(directory):
    cases = []
    mechanism_traces = []
    for name in ('cases.json', 'secondary-cases.json'):
        path = directory / name
        if path.exists():
            data = read_json(path)
            # Only authored design metadata enters coverage panels, never gold outcomes.
            cases.extend({'id': c['id'], 'family': c.get('family', c['id']),
                          'hypothesis': c['hypothesis'],
                          'arms': [a['id'] for a in c['conditions']]} for c in data.get('cases', []))
            mechanism_traces.extend({'id': c['id'], 'hypothesis': c['hypothesis'],
                                     'conditions': [a['id'] for a in c['conditions']]}
                                    for c in data.get('maintenance_cases', []))
    freeze = directory / 'freeze.json'
    return {'cases': cases, 'maintenance_cases': mechanism_traces,
            'frozen_jobs': read_json(freeze).get('jobs', []) if freeze.exists() else []}


def validate_trials(data):
    trials = data.get('trials')
    if not isinstance(trials, list) or not trials:
        raise ValueError('No observed trials: figures and summary will not be exported.')
    ids = [t.get('trial_id') for t in trials]
    if any(not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('Trial IDs must be present and unique; duplicate runs cannot silently enter denominators.')
    for t in trials:
        for key in ('case_id', 'condition', 'regime', 'hypothesis', 'score'):
            if key not in t:
                raise ValueError('Missing trial field: ' + key)
    return trials


def onboarding_arms(trials):
    arms={}
    for trial in trials:
        if trial.get('onboarding','unbriefed')!='unbriefed':
            cid=trial['case_id']
            if cid in arms and arms[cid]!=trial['condition']:
                raise ValueError('Onboarding family has multiple selected arms: '+cid)
            arms[cid]=trial['condition']
    return arms


def onboarding_group(trials,cid,arm,onboarding):
    return [t for t in trials if t['case_id']==cid and t['condition']==arm
            and t.get('onboarding','unbriefed')==onboarding and t['regime']=='fidelity_first']


def make_summary(trials, plan, maintenance, provenance, aborted_batches=()):
    main = [t for t in trials if t.get('onboarding', 'unbriefed') == 'unbriefed']
    onboarding = [t for t in trials if t.get('onboarding', 'unbriefed') != 'unbriefed']
    groups = defaultdict(list)
    for t in main:
        groups[(t['hypothesis'], t['condition'], t['regime'])].append(t)
    ids = {t['trial_id'] for t in trials}
    jobs = plan['frozen_jobs']
    selected_onboarding_arms=onboarding_arms(trials)
    expected_ids = {j['trial_id'] for j in jobs}
    return {'schema_version': 1, 'generated_utc': datetime.now(timezone.utc).isoformat(),
            'status': 'analysis of recorded receipts; engineered fictional pilot',
            'provenance': provenance,
            'limits': ['Paired arms within author-created family blocks; no population-performance inference.',
                       'All recorded current-freeze attempts remain in denominators, including infrastructure interruptions.',
                       'Earlier aborted infrastructure batches remain separately disclosed, not pooled across changed execution controls.',
                       'Failure flags overlap; their counts must not be summed as exclusive causes.',
                       'Original-source reads measure coverage of an authored set, not recall truth or causal use.',
                       'Sufficient citations and full-original reads are separate measurements.',
                       'Token counters describe recorded accepted calls only; failed adapters have unmeasured provider usage.',
                       'Default/untouched artifacts can fail scoring gates during infrastructure failure without any written-domain decision.',
                       'semantic_artifact_correct names the frozen exact artifact/focus gate, not an independent factual-correctness judgment.',
                       'Later reader-turn receipt of a check result is a separate proxy, not proof of inspection or causal use.',
                       'Onboarding uses three selected families without independent replication.',
                       'H4/H6 traces are prescribed deterministic mechanisms, not reader or LLM benefits.'],
            'trial_counts': {'recorded': len(trials), 'main_unbriefed': len(main),
                             'additional_onboarding': len(onboarding), 'frozen_planned': len(jobs) if jobs else None,
                             'missing_frozen_trial_ids': sorted(expected_ids - ids) if jobs else None,
                             'unexpected_trial_ids': sorted(ids - expected_ids) if jobs else None},
            'all_recorded': aggregate(trials), 'main_unbriefed': aggregate(main),
            'convention_diagnostics': convention_diagnostics(main),
            'archived_aborted_batches': [{'path': path, 'sha256': digest,
                                         'pooled_into_current_freeze': False,
                                         'recorded_receipts': len(batch.get('trials', [])),
                                         'summary': aggregate(batch.get('trials', [])),
                                         'adapter_diagnostics': [adapter_diagnostics(t) for t in batch.get('trials', [])],
                                         'status': batch.get('status')}
                                        for path, digest, batch in aborted_batches],
            'by_arm_regime': [{'hypothesis': h, 'condition': a, 'regime': r, **aggregate(ts)}
                              for (h, a, r), ts in sorted(groups.items())],
            'onboarding': [{'case_id': cid, 'condition':selected_onboarding_arms[cid],
                            'onboarding': o, **aggregate(onboarding_group(trials,cid,selected_onboarding_arms[cid],o))}
                           for cid in sorted({t['case_id'] for t in onboarding})
                           for o in ('unbriefed', 'no_entry', 'schema_taught')],
            'per_trial': [{'trial_id': t['trial_id'], 'case_id': t['case_id'],
                           'hypothesis': t['hypothesis'], 'condition': t['condition'],
                           'regime': t['regime'], 'onboarding': t.get('onboarding', 'unbriefed'),
                           'termination': t.get('termination'), 'complete_task': t['score'].get('complete_task'),
                           'semantic_correct': t['score'].get('semantic_artifact_correct'),
                           'critical_pass': t['score'].get('critical_pass'),
                           'reader_saw_post_write_check': t['score'].get('reader_saw_post_write_check'),
                           'failure_flags': failure_flags(t), 'artifact_state': artifact_state(t),
                           'adapter_diagnostics': adapter_diagnostics(t),
                           'recorded_accepted_call_tokens': total_tokens(t),
                           'returned_bytes': t.get('returned_bytes'), 'actions': t.get('actions'),
                           'seconds': t.get('seconds'), 'trace_counts': trace_counts(t)} for t in trials],
            'coverage_plan': plan,
            'maintenance': {'available': bool(maintenance), 'status': maintenance.get('status') if maintenance else None,
                            'traces': [{'id': t.get('id'), 'hypothesis': t.get('hypothesis'),
                                        'condition_id': t.get('condition_id'), 'passed': t.get('passed'),
                                        'summary': t.get('summary', {})} for t in maintenance.get('traces', [])]}}


def setup_style():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.titlesize': 12, 'axes.labelsize': 10,
                         'xtick.labelsize': 9, 'ytick.labelsize': 9,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'figure.facecolor': 'white', 'axes.facecolor': 'white',
                         'savefig.facecolor': 'white', 'svg.hashsalt': 'fictional-pilot-2026-10-09'})


def finish(fig, figures, stem, title, note):
    fig.suptitle(title, fontsize=16, y=.99)
    fig.text(.02, .012, note, fontsize=9, color='#555555', va='bottom')
    fig.tight_layout(rect=(.015, .055, .99, .95))
    for extension in ('png', 'svg'):
        fig.savefig(figures / (stem + '.' + extension), dpi=200, bbox_inches='tight')
        if extension == 'svg':
            path = figures / (stem + '.svg')
            path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf8').splitlines()).rstrip() + '\n', encoding='utf8', newline='\n')
    plt.close(fig)


def planned_arms(hypothesis, plan, trials):
    arms = []
    for c in plan['cases']:
        if c['hypothesis'] == hypothesis:
            arms.extend(c['arms'])
    arms.extend(t['condition'] for t in trials if t['hypothesis'] == hypothesis)
    return list(dict.fromkeys(arms))


def rate_panels(main, plan, figures, critical=False):
    if critical:
        critical_gate_panels(main, plan, figures)
        return
    fig, axes = plt.subplots(3, 2, figsize=(13, 11))
    for ax, h in zip(axes.flat, HYPOTHESES):
        arms = planned_arms(h, plan, main)
        for ri, regime in enumerate(REGIMES):
            heights, labels = [], []
            for arm in arms:
                group = [t for t in main if (t['hypothesis'], t['condition'], t['regime']) == (h, arm, regime)]
                total = len(group)
                count = sum(not t['score'].get('critical_pass', False) if critical else bool(t['score'].get('complete_task')) for t in group)
                heights.append(count / total if total else 0)
                labels.append(f'{count}/{total}' if total else 'unobserved')
            positions = [i + (ri - .5) * .36 for i in range(len(arms))]
            bars = ax.bar(positions, heights, width=.34, color=COLORS[regime], label=regime.replace('_', ' '))
            for bar, label in zip(bars, labels):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height()+.025, label, ha='center', fontsize=8)
        ax.set_title(h + ' · ' + MECHANISMS[h])
        ax.set_xticks(range(len(arms)), [ARM_LABELS.get(a, a) for a in arms])
        ax.set_ylim(0, 1.18)
        ax.set_yticks([0, .25, .5, .75, 1])
        ax.set_ylabel('Critical-error trial fraction' if critical else 'Complete-task fraction')
        ax.grid(axis='y', alpha=.18)
    axes.flat[0].legend(frameon=False, fontsize=9)
    finish(fig, figures, '02_critical_errors' if critical else '01_complete_task',
           'Observed critical errors by arm and regime' if critical else 'Frozen-rubric complete continuation by arm and regime',
           'Labels are count/recorded current-freeze trials; infrastructure interruptions included. Paired fictional families; descriptive fractions, no population inference.')


def critical_gate_panels(main, plan, figures):
    fig,axes=plt.subplots(3,2,figsize=(14,11))
    categories=[('Written critical rubric mismatch','#A24E62'),
                ('Unwritten infrastructure gate failure','#8C969E'),
                ('Other unwritten gate failure','#D2C3AC')]
    for ax,h in zip(axes.flat,HYPOTHESES):
        groups=[(a,r) for a in planned_arms(h,plan,main) for r in REGIMES]
        counts=[];ns=[]
        for a,r in groups:
            group=[t for t in main if (t['hypothesis'],t['condition'],t['regime'])==(h,a,r)]
            ns.append(len(group))
            failures=[t for t in group if not t['score'].get('critical_pass',False)]
            counts.append([sum(bool(t['score'].get('artifact_written')) for t in failures),
                           sum(not t['score'].get('artifact_written') and bool(t.get('infrastructure_error')) for t in failures),
                           sum(not t['score'].get('artifact_written') and not t.get('infrastructure_error') for t in failures)])
        bottom=[0]*len(groups)
        for ci,(label,color) in enumerate(categories):
            heights=[row[ci]/n if n else 0 for row,n in zip(counts,ns)]
            ax.bar(range(len(groups)),heights,bottom=bottom,color=color,label=label,width=.7)
            bottom=[a+b for a,b in zip(bottom,heights)]
        for i,(row,n) in enumerate(zip(counts,ns)):
            ax.text(i,bottom[i]+.025,f'{sum(row)}/{n}' if n else 'unobserved',ha='center',fontsize=8)
        ax.set_xticks(range(len(groups)),[ARM_LABELS.get(a,a)+'\n'+('M' if r=='matched' else 'F') for a,r in groups],rotation=20,ha='right')
        ax.set_ylim(0,1.18);ax.set_yticks([0,.5,1]);ax.set_ylabel('Critical gate-failure fraction')
        ax.set_title(h+' · critical artifact gate');ax.grid(axis='y',alpha=.18)
    axes.flat[0].legend(frameon=False,fontsize=8)
    finish(fig,figures,'02_critical_errors','Critical gate failures separated by artifact production',
           'Labels are failed gates/recorded trials. Written mismatches may include status/focus conventions; untouched drafts are not authored decisions. M=matched; F=fidelity first.')


def heatmap(main, plan, figures):
    fig, axes = plt.subplots(3, 2, figsize=(15, 13))
    cmap = ListedColormap(['#B35C6D', '#4B8775'])
    cmap.set_bad('#EEEEEE')
    for ax, h in zip(axes.flat, HYPOTHESES):
        ids = [c['id'] for c in plan['cases'] if c['hypothesis'] == h]
        ids.extend(t['case_id'] for t in main if t['hypothesis'] == h and t['case_id'] not in ids)
        ids = list(dict.fromkeys(ids))
        columns = [(a, r) for a in planned_arms(h, plan, main) for r in REGIMES]
        values, annotations = [], []
        for cid in ids:
            row, text = [], []
            for a, r in columns:
                group = [t for t in main if (t['case_id'], t['condition'], t['regime']) == (cid, a, r)]
                count = sum(bool(t['score'].get('complete_task')) for t in group)
                row.append(count / len(group) if group else float('nan'))
                text.append(f'{count}/{len(group)}' if group else '—')
            values.append(row); annotations.append(text)
        if values and columns:
            ax.imshow(values, vmin=0, vmax=1, cmap=cmap, aspect='auto')
            for y, row in enumerate(annotations):
                for x, text in enumerate(row): ax.text(x, y, text, ha='center', va='center', fontsize=8)
        ax.set_title(h + ' · complete-task results')
        ax.set_yticks(range(len(ids)), ids)
        ax.set_xticks(range(len(columns)), [ARM_LABELS.get(a, a)+'\n'+('M' if r=='matched' else 'F') for a, r in columns], rotation=25, ha='right')
    finish(fig, figures, '03_case_arm_heatmap', 'Frozen-rubric case-arm outcomes with paired regimes',
           'Each cell is frozen complete-task passes/recorded trials; gray means unobserved. M=matched, F=fidelity first. Families, not cells, define paired blocks.')


def failure_plot(main, figures):
    fig, ax = plt.subplots(figsize=(11, 6))
    keys = list(FAILURE_LABELS)
    for ri, r in enumerate(REGIMES):
        group = [t for t in main if t['regime'] == r]
        counts = aggregate(group)['failure_flag_counts']
        positions = [i+(ri-.5)*.34 for i in range(len(keys))]
        bars = ax.barh(positions, [counts[k] for k in keys], height=.32, color=COLORS[r], label=r.replace('_', ' ')+f' (N={len(group)})')
        for bar in bars: ax.text(bar.get_width()+.1, bar.get_y()+bar.get_height()/2, str(round(bar.get_width())), va='center', fontsize=9)
    ax.set_yticks(range(len(keys)), [FAILURE_LABELS[k] for k in keys])
    ax.invert_yaxis(); ax.set_xlabel('Recorded trials with flag'); ax.legend(frameon=False)
    ax.grid(axis='x', alpha=.18)
    finish(fig, figures, '04_overlapping_failure_flags', 'Observed failure and discovery-proxy flags',
           'Flags overlap. Exact/focus gates include convention-sensitive status labels and historical containers; untouched-draft failures are separate from written rubric mismatches.')


def cost_plot(main, figures):
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    metrics = [('recorded_accepted_call_tokens', 'Recorded accepted-call tokens'), ('returned_bytes', 'Returned tool bytes'),
               ('actions', 'Tool action attempts'), ('seconds', 'Wall-clock seconds')]
    for ax, (metric, label) in zip(axes.flat, metrics):
        missing = 0
        for ri, r in enumerate(REGIMES):
            for ci, state in enumerate(('No authorized write','Written rubric mismatch','Written rubric pass')):
                group = [t for t in main if t['regime'] == r and artifact_state(t) == state]
                vals = [(total_tokens(t) if metric == 'recorded_accepted_call_tokens' else t.get(metric)) for t in group]
                missing += sum(not number(v) for v in vals)
                vals = [v for v in vals if number(v)]
                pos = ci + (ri-.5)*.28
                if vals:
                    box = ax.boxplot([vals], positions=[pos], widths=.24, patch_artist=True, showfliers=False, manage_ticks=False)
                    box['boxes'][0].set_facecolor(COLORS[r]); box['boxes'][0].set_alpha(.6)
                    ax.scatter([pos]*len(vals), vals, s=13, color=COLORS[r], alpha=.7, zorder=3)
                    ax.annotate(f'n={len(vals)}', (pos, max(vals)), xytext=(0, 6), textcoords='offset points', ha='center', fontsize=8)
        ax.set_xticks([0,1,2],['No authorized write','Written rubric mismatch','Written rubric pass'])
        ax.set_ylabel(label); ax.set_title(f'{label} · missing counters: {missing}')
        ax.margins(y=.18); ax.grid(axis='y', alpha=.18)
    axes.flat[0].legend(handles=[Line2D([0],[0],color=COLORS[r],lw=6,label=r.replace('_',' ')) for r in REGIMES], frameon=False)
    finish(fig, figures, '05_costs_conditional_on_correctness', 'Recorded costs by artifact production state',
           'Accepted-call metadata only; failed adapter/provider usage is unmeasured. Written rubric mismatches include convention sensitivities, separately listed in summary. Descriptive conditional costs.')


def origin_plot(main, plan, figures):
    fig, axes = plt.subplots(3, 2, figsize=(13, 11))
    for ax, h in zip(axes.flat, HYPOTHESES):
        arms = planned_arms(h, plan, main)
        for ri, r in enumerate(REGIMES):
            heights, labels = [], []
            for a in arms:
                group = [t for t in main if (t['hypothesis'],t['condition'],t['regime']) == (h,a,r)]
                agg = aggregate(group)
                heights.append(agg['mean_authored_original_read_fraction'] or 0)
                labels.append(f"{agg['origin_read_complete_trials']}/{agg['n']} full" if group else 'unobserved')
            bars = ax.bar([i+(ri-.5)*.36 for i in range(len(arms))], heights, width=.34,color=COLORS[r],label=r.replace('_',' '))
            for bar,text in zip(bars,labels): ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+.025,text,ha='center',fontsize=8)
        ax.set_title(h+' · authored original-source set')
        ax.set_xticks(range(len(arms)),[ARM_LABELS.get(a,a) for a in arms])
        ax.set_ylim(0,1.2); ax.set_yticks([0,.25,.5,.75,1]); ax.set_ylabel('Mean fully returned original fraction'); ax.grid(axis='y',alpha=.18)
    handles,labels=axes.flat[0].get_legend_handles_labels()
    fig.legend(handles,labels,frameon=False,ncols=2,loc='upper center',bbox_to_anchor=(.5,.965))
    finish(fig,figures,'06_original_source_coverage_proxy','Full-original read coverage proxy',
           'Denominator is the authored sufficient-source set, not every important fact. Labels show full-set reads/trials. Search hits, citations and derived views do not count as full original reads.')


def trace_plot(main, figures):
    fig, (ax, inspection_ax) = plt.subplots(2,1,figsize=(15,9),sharex=True)
    groups = [(h,r) for h in HYPOTHESES for r in REGIMES]
    keys = [('executed_writes','Executed writes','#597AA1'),('executed_checks','Executed checks','#6D9C89'),
            ('successful_checks_after_final_write','Successful checks after final write','#C58E46'),('denied_checks','Denied check attempts','#AD6776')]
    labels=[]
    for h,r in groups:
        n=sum((t['hypothesis'],t['regime'])==(h,r) for t in main)
        labels.append(f'{h} '+('M' if r=='matched' else 'F')+f'\nN={n}')
    for ki,(key,label,color) in enumerate(keys):
        means=[]
        for h,r in groups:
            group=[trace_counts(t)[key] for t in main if (t['hypothesis'],t['regime'])==(h,r)]
            means.append(statistics.mean(group) if group else 0)
        ax.bar([i+(ki-1.5)*.2 for i in range(len(groups))],means,width=.19,label=label,color=color)
    ax.set_ylabel('Observed attempts per recorded trial'); ax.grid(axis='y',alpha=.18)
    ax.legend(frameon=False,ncols=2)
    for offset,key,label,color in [(-.17,'post_write_checks_pass','Host check execution gate','#3D8070'),
                                   (.17,'reader_saw_post_write_check','Result returned before later reader turn','#926EAB')]:
        heights=[]
        for h,r in groups:
            group=[t['score'][key] for t in main if (t['hypothesis'],t['regime'])==(h,r)
                   and isinstance(t['score'].get(key),bool)]
            heights.append(sum(group)/len(group) if group else float('nan'))
        inspection_ax.bar([i+offset for i in range(len(groups))],heights,width=.32,color=color,label=label)
    inspection_ax.set_xticks(range(len(groups)),labels);inspection_ax.set_ylim(0,1.15)
    inspection_ax.set_ylabel('Observed-trial fraction');inspection_ax.legend(frameon=False,ncols=2,fontsize=9)
    inspection_ax.grid(axis='y',alpha=.18)
    finish(fig,figures,'07_write_check_trace_counts','Authorized artifact-write and local-check traces',
           'M=matched, F=fidelity first. Checks follow final writes; denied attempts did not execute. Later-turn result receipt is an inspection proxy, separate from host execution and the complete-task gate.')


def onboarding_plot(trials, figures):
    selected=onboarding_arms(trials)
    ids=sorted(selected)
    fig,axes=plt.subplots(1,max(1,len(ids)),figsize=(max(8,5*len(ids)),5),squeeze=False)
    for ax,cid in zip(axes.flat,ids):
        groups=[onboarding_group(trials,cid,selected[cid],o) for o in ('unbriefed','no_entry','schema_taught')]
        for offset,key,label,color in [(-.22,'complete_task','Complete','#3D8070'),(0,'critical_pass','Critical pass','#3B6B9B'),(.22,'origin_read_complete','Full origin proxy','#C27B29')]:
            heights=[sum(bool(t['score'].get(key)) for t in group)/len(group) if group else 0 for group in groups]
            ax.bar([i+offset for i in range(3)],heights,width=.21,color=color,label=label)
        ax.set_xticks(range(3),[ARM_LABELS[o]+f'\nN={len(g)}' for o,g in zip(('unbriefed','no_entry','schema_taught'),groups)],rotation=15)
        ax.set_ylim(0,1.15);ax.set_yticks([0,.5,1]);ax.set_title(cid);ax.grid(axis='y',alpha=.18)
    if not ids: axes.flat[0].text(.5,.5,'No onboarding receipts recorded',ha='center',transform=axes.flat[0].transAxes)
    handles,labels=axes.flat[0].get_legend_handles_labels()
    fig.legend(handles,labels,frameon=False,ncols=3,loc='upper center',bbox_to_anchor=(.5,.965),fontsize=9)
    axes.flat[0].set_ylabel('Recorded-trial fraction')
    finish(fig,figures,'08_onboarding_blocks','Exploratory onboarding blocks · fidelity-first regime',
           'Three selected families and baseline arms; these extra runs are not independent replications or a general onboarding-effect estimate.')


def coverage_plot(trials,plan,maintenance,figures):
    fig,ax=plt.subplots(figsize=(12,6));ax.axis('off')
    rows=[]
    for h in ('H1','H2','H3','H4','H5','H6','H7','H8'):
        families=sum(c['hypothesis']==h for c in plan['cases'])
        families+=sum(c['hypothesis']==h for c in plan['maintenance_cases'])
        main=sum(t['hypothesis']==h and t.get('onboarding','unbriefed')=='unbriefed' for t in trials)
        extra=sum(t['hypothesis']==h and t.get('onboarding','unbriefed')!='unbriefed' for t in trials)
        traces=[t for t in maintenance.get('traces',[]) if t.get('hypothesis')==h]
        rows.append([h,MECHANISMS[h],str(families) if plan['cases'] else 'unavailable',str(main),str(extra),str(len(traces)),
                     'Prescribed replay' if h in ('H4','H6') else 'Reader pilot'])
    table=ax.table(cellText=rows,colLabels=['Hypothesis','Mechanism','Authored families','Main reader runs','Onboarding runs','Executed replay arms','Evidence type'],loc='center',cellLoc='left',colWidths=[.08,.24,.13,.12,.12,.15,.16])
    table.auto_set_font_size(False);table.set_fontsize(9);table.scale(1,2.1)
    for (row,col),cell in table.get_celld().items():
        cell.set_edgecolor('#D7DDE1')
        cell.set_facecolor('#DEE7ED' if row==0 else ('#F6F8F9' if row%2 else 'white'))
    finish(fig,figures,'09_hypothesis_coverage','Authored plan and observed mechanism coverage',
           'Counts distinguish reader trials from deterministic replay arms. One collaborative LLM-authored corpus; families and conditions do not establish statistical independence.')


def critical_paths_plot(main,figures):
    written=[t for t in main if t['score'].get('artifact_written')]
    counts=Counter(h+': '+k for t in written for h in [t['hypothesis']] for k in t['score'].get('critical_errors',{}))
    items=counts.most_common(18)
    fig,ax=plt.subplots(figsize=(12,max(5,len(items)*.34)))
    if items:
        colors=['#926EAB' if k.endswith(': status') or k.endswith('focused_question_or_empty') else '#A45D6F' for k,n in items]
        ax.barh(range(len(items)),[n for k,n in items],color=colors)
        ax.set_yticks(range(len(items)),[k for k,n in items]);ax.invert_yaxis();ax.set_xlabel('Recorded trials with mismatched assertion')
        for i,(_,n) in enumerate(items):ax.text(n+.1,i,str(n),va='center')
        ax.grid(axis='x',alpha=.18)
        ax.legend(handles=[Line2D([0],[0],color='#926EAB',lw=6,label='Status/focus assertion'),
                           Line2D([0],[0],color='#A45D6F',lw=6,label='Other critical assertion')],frameon=False,fontsize=9)
    else:
        ax.axis('off');ax.text(.5,.5,f'No written critical rubric mismatches recorded.\n{len(written)} trials wrote an artifact; {len(main)-len(written)} did not.',ha='center',transform=ax.transAxes,fontsize=14)
    finish(fig,figures,'10_critical_assertion_paths','Critical rubric paths in observed written artifacts',
           'Status/focus conventions can fail without wrong governing facts; see summary diagnostics. Unwritten drafts are excluded here but retained in complete/gate denominators. No frozen score changes.')


def maintenance_plots(maintenance,figures):
    traces=maintenance.get('traces',[])
    h4=[t for t in traces if t.get('hypothesis')=='H4']
    if h4:
        fig,axes=plt.subplots(3,1,figsize=(12,10),sharex=True)
        for trace in h4:
            checkpoints=trace.get('checkpoints',[]);label=ARM_LABELS.get(trace.get('condition_id'),trace.get('condition_id','unknown'))
            x=list(range(len(checkpoints)))
            repair=[]
            for cp in checkpoints:
                repair.append(sum(m.get('category')=='repair' and (m.get('step',0)<cp['step'] or
                                  (m.get('step')==cp['step'] and cp['phase']=='after_repair')) for m in trace.get('mutations',[])))
            axes[0].plot(x,repair,marker='o',label=label)
            axes[1].plot(x,[len(cp.get('unavailable_scopes',[])) for cp in checkpoints],marker='o',label=label)
            axes[2].plot(x,[len(cp.get('stale_scopes',[])) for cp in checkpoints],marker='o',label=label)
        checkpoints=h4[0].get('checkpoints',[])
        axes[2].set_xticks(range(len(checkpoints)),[str(cp['step'])+'\n'+cp['phase'].replace('_',' ') for cp in checkpoints],rotation=25,ha='right')
        for ax,title in zip(axes,['Cumulative repair\nfile mutations','Unavailable indexed\nseparator-rule scopes','Stale indexed\nseparator-rule scopes']):
            ax.set_ylabel(title);ax.grid(alpha=.18)
        axes[0].set_yticks(range(6))
        axes[1].set_yticks(range(3));axes[2].set_yticks(range(3))
        axes[0].legend(frameon=False);axes[2].set_xlabel('Observed replay checkpoint')
        finish(fig,figures,'11_h4_mutation_access_timeline','H4 prescribed replay · repair cost and indexed access',
               'Actual mutation/checkpoint logs. Indexed separator-rule access is narrower than complete governing-state accessibility; prescribed repairs do not measure LLM maintenance skill.')
    h6=[t for t in traces if t.get('hypothesis')=='H6']
    if h6:
        fig,axes=plt.subplots(4,1,figsize=(12,11),sharex=True)
        for ti,trace in enumerate(h6):
            cps=trace.get('checkpoints',[]);label=ARM_LABELS.get(trace.get('condition_id'),trace.get('condition_id','unknown'))
            x=[cp['step'] for cp in cps]
            for ax,key in zip(axes,['stale_field_count','dirty','cumulative_review_attempts','declares_clean_while_stale']):
                ax.step(x,[int(cp.get(key,0)) for cp in cps],where='post',marker=('o','s','^')[ti%3],
                        linestyle=('-','--',':')[ti%3],label=label)
        for ax,title in zip(axes,['Stale committed fields','View dirty flag','Cumulative review attempts','Declares clean while stale']):
            ax.set_ylabel(title);ax.grid(alpha=.18)
        axes[0].legend(frameon=False,ncols=3);axes[-1].set_xlabel('Observed event step')
        finish(fig,figures,'12_h6_stale_dirty_review_timeline','H6 capped replay · stale exposure and review state',
               'Observed committed-state logs, including interrupted reviews. Equal attempt caps expose different source versions: whole-policy mechanism trace, not a timing-only or LLM effect.')


def self_check():
    def demo(i,complete,critical,correct,regime='matched'):
        return {'trial_id':str(i),'case_id':'demo','hypothesis':'H1','condition':'demo_arm','regime':regime,
                'onboarding':'unbriefed','seconds':i,'actions':2,'returned_bytes':100,
                'calls':[{'usage':{'input_tokens':10,'output_tokens':5}}],
                'events':[{'seq':1,'executed':True,'action':{'tool':'write'}},
                          {'seq':2,'executed':True,'action':{'tool':'check'},'result':{'exit':0}}],
                'score':{'complete_task':complete,'critical_pass':critical,'semantic_artifact_correct':correct,
                         'artifact_written':True,'citation_complete':complete,'post_write_checks_pass':True,
                         'forbidden_attempts':0,'required_sources':2,'originals_read':1,'origin_read_complete':False}}
    data=[demo(1,True,True,True),demo(2,False,False,False),demo(3,False,True,True,'fidelity_first')]
    agg=aggregate(data)
    assert agg['n']==3 and agg['complete_task']==1 and agg['critical_gate_failed_trials']==1
    assert agg['semantic_correct']==2 and agg['failure_flag_counts']['citation_incomplete']==2
    assert agg['mean_authored_original_read_fraction']==.5 and agg['trace_totals']['executed_writes']==3
    assert agg['costs']['recorded_accepted_call_tokens']['sum']==45
    assert adapter_diagnostics({'calls':[],'infrastructure_error':'failed'})['failed_adapter_calls']==1
    convention=demo(4,False,False,False)
    convention['score'].update(wrong_fields={'status':{'expected':'ready','observed':'complete'}},
                               focused_question_pass=True,artifact={'evidence':[]})
    diagnostic=convention_diagnostics([convention])
    assert diagnostic['status_only_written_mismatch_count']==1
    assert diagnostic['status_only_observed_labels']=={'complete':1}
    assert not convention['score']['complete_task'], 'Diagnostic changed a frozen score'
    data[0]['events'].append({'seq':3,'executed':True,'action':{'tool':'write'}})
    assert trace_counts(data[0])['successful_checks_after_final_write']==0
    assert trace_counts({'events':[{'action':None},{'action':[]} ]})['executed_writes']==0
    assert token_usage({}) is None and token_usage({'input_tokens':10}) is None
    assert total_tokens({'calls':[{'usage':{'total_tokens':9}},{'usage':{}}]}) is None
    try: validate_trials({'trials':[data[0],data[0]]})
    except ValueError: pass
    else: raise AssertionError('Duplicate IDs were accepted')
    assert aggregate([])['complete_task_rate'] is None
    baseline=demo(5,True,True,True,'fidelity_first')
    other_arm=demo(6,True,True,True,'fidelity_first');other_arm['condition']='other_arm'
    no_entry=demo(7,True,True,True,'fidelity_first');no_entry['onboarding']='no_entry'
    block=[baseline,other_arm,no_entry]
    selected=onboarding_arms(block)
    assert len(onboarding_group(block,'demo',selected['demo'],'unbriefed'))==1, 'Onboarding pooled different arms'
    print('PASS: in-memory synthetic denominator, overlapping flags, token missingness, trace ordering and duplicate-ID checks; no outcomes or figures exported.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=HERE/'results.json')
    parser.add_argument('--maintenance',type=Path,default=HERE/'maintenance-results.json')
    parser.add_argument('--output',type=Path,default=HERE)
    parser.add_argument('--aborted',type=Path,action='append',help='Archived aborted batch; repeat for multiple histories.')
    parser.add_argument('--self-check',action='store_true')
    args=parser.parse_args()
    if args.self_check:
        self_check();return
    if not args.input.exists():
        parser.error('Observed results file is not present; no exports created.')
    data=read_json(args.input);trials=validate_trials(data)
    maintenance=read_json(args.maintenance) if args.maintenance.exists() else {}
    aborted_paths=args.aborted if args.aborted is not None else sorted(HERE.glob('attempt-*/aborted-results.json'))
    aborted=[(str(p.relative_to(HERE)) if p.is_relative_to(HERE) else p.name,file_hash(p),read_json(p)) for p in aborted_paths if p.exists()]
    plan=load_plan(HERE)
    provenance={'results_path':args.input.name,'results_sha256':file_hash(args.input),
                'reader_freeze_sha256':data.get('freeze_sha256'),
                'maintenance_sha256':file_hash(args.maintenance) if maintenance else None,
                'archived_aborted_batches':[{'path':p,'sha256':digest} for p,digest,batch in aborted],
                'analyzer_sha256':file_hash(Path(__file__))}
    summary=make_summary(trials,plan,maintenance,provenance,aborted)
    args.output.mkdir(parents=True,exist_ok=True)
    figures=args.output/'figures';figures.mkdir(exist_ok=True)
    setup_style()
    main_trials=[t for t in trials if t.get('onboarding','unbriefed')=='unbriefed']
    rate_panels(main_trials,plan,figures);rate_panels(main_trials,plan,figures,critical=True)
    heatmap(main_trials,plan,figures);failure_plot(main_trials,figures)
    cost_plot(main_trials,figures);origin_plot(main_trials,plan,figures)
    trace_plot(main_trials,figures);onboarding_plot(trials,figures)
    coverage_plot(trials,plan,maintenance,figures);critical_paths_plot(main_trials,figures)
    maintenance_plots(maintenance,figures)
    stems=['01_complete_task','02_critical_errors','03_case_arm_heatmap','04_overlapping_failure_flags',
           '05_costs_conditional_on_correctness','06_original_source_coverage_proxy','07_write_check_trace_counts',
           '08_onboarding_blocks','09_hypothesis_coverage','10_critical_assertion_paths']
    for hypothesis,stem in [('H4','11_h4_mutation_access_timeline'),('H6','12_h6_stale_dirty_review_timeline')]:
        if any(t.get('hypothesis')==hypothesis for t in maintenance.get('traces',[])): stems.append(stem)
    summary['figure_stems']=stems
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'recorded_trials':len(trials),'main_trials':len(main_trials),
                      'figures':len(summary['figure_stems']),'output':str(args.output)},indent=2))


if __name__=='__main__':
    main()
