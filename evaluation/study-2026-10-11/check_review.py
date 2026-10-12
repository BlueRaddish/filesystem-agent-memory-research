"""Validate the supplemental review census and recompute descriptive intersections.

This is a data/provenance check, not a semantic judge. It never changes primary
reader outcomes, loads weights, calls a model or accesses a personal filesystem.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABELS = {'supported', 'contradicted', 'not_established', 'not_auditable'}


def read(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def validate():
    review = read('semantic-review.json')
    reader_path = HERE / 'reader-results.json'
    assert hashlib.sha256(reader_path.read_bytes()).hexdigest() == review['input_sha256']['reader-results.json']
    trials = {t['trial_id']: t for t in read('reader-results.json')['trials']}
    assert len(trials) == 144 and len(review['cases']) == 123
    assert len({c['case_id'] for c in review['cases']}) == 123
    assert {c['trial_id'] for c in review['cases']} == {t['trial_id'] for t in trials.values() if t['artifact_written']}
    counts = Counter()
    by_arm = {}
    for case in review['cases']:
        trial = trials[case['trial_id']]
        packet, judgments = case['packet'], case['review']
        assert case['case_id'] == packet['case_id'] == judgments['case_id']
        assert case['block'] == trial['block'] and case['arm'] == trial['arm']
        assert packet['artifact']['status'] == trial['artifact']['status']
        assert packet['artifact']['evidence'] == trial['artifact']['evidence']
        assert packet['artifact']['answer'] == {k: trial['artifact']['answer'].get(k) for k in packet['required_answer_keys']}
        assert set(judgments['answer_judgments']) == set(packet['required_answer_keys'])
        value_status = list(judgments['answer_judgments'].values()) + [judgments['status_judgment']]
        source_ids = {s['source_id'] for s in packet['supplied_sources']}
        for item in value_status + [judgments['citation_judgment'], judgments['full_query_judgment']]:
            assert item['label'] in LABELS and isinstance(item['rationale'], str)
            assert set(item['citations']) <= source_ids
        supported = all(item['label'] == 'supported' for item in value_status)
        flags = dict(value_status_supported=supported,
                     value_status_contradicted=any(item['label'] == 'contradicted' for item in value_status),
                     full_query_supported=judgments['full_query_judgment']['label'] == 'supported',
                     citation_entailment_supported=judgments['citation_judgment']['label'] == 'supported',
                     source_supported_exact_answer_mismatch=supported and not trial['score']['factual_correct'],
                     primary_complete_task=trial['complete_task'])
        assert flags == case['descriptive_flags']
        assert case['frozen_field_errors'] == trial['score']['field_errors']
        arm = by_arm.setdefault(trial['block'] + '/' + trial['arm'], Counter())
        counts['reviewed_artifacts'] += 1
        arm['reviewed_artifacts'] += 1
        for flag, value in flags.items():
            counts[flag] += int(value)
            arm[flag] += int(value)
    for trial in trials.values():
        arm = by_arm.setdefault(trial['block'] + '/' + trial['arm'], Counter())
        arm['scheduled_trials'] += 1
        arm['no_artifact_trials'] += int(not trial['artifact_written'])
    counts['scheduled_trials'] = len(trials)
    counts['no_artifact_trials'] = sum(not t['artifact_written'] for t in trials.values())
    # Counters equate absent and explicit-zero categories without hiding unknowns.
    assert counts == Counter(review['summary'])
    assert set(by_arm) == set(review['by_arm'])
    assert all(c == Counter(review['by_arm'][arm]) for arm, c in by_arm.items())
    return {'state': 'passed', 'reviewed_artifacts': 123, 'scheduled_trials': 144,
            'no_artifact_trials_retained': 21, 'primary_scores_changed': 0,
            'semantic_claims_adjudicated_by_this_check': 0, 'model_calls': 0}


if __name__ == '__main__':
    print(json.dumps(validate(), sort_keys=True))
