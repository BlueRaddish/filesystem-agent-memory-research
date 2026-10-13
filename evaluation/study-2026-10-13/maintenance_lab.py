"""Prescribed cache/retention traces, not LLM extraction or maintenance accuracy.

No personal vault is touched. The fixture supplies the true dependency graph;
missing-edge and false-current cases explicitly test the limit of that premise.
"""
import argparse
from collections import deque
import json
from pathlib import Path
import random
import tempfile

from study_common import digest, save

POLICIES = ('no_invalidation', 'ttl_5', 'global', 'direct_dependencies', 'transitive_dependencies')


class Materialized:
    def __init__(self, policy, missing_edge=False):
        if policy not in POLICIES:
            raise ValueError('Unknown invalidation policy')
        self.policy = policy
        self.sources = {'S1': 'amber', 'S2': 'blue', 'U': 'unrelated'}
        self.dependencies = {'V1': ['S1', 'S2'] if not missing_edge else ['S1'], 'V2': ['V1']}
        self.dirty = {'V1', 'V2'}
        self.cache, self.built_at, self.rebuilds, self.originals = {}, {}, 0, []
        self.record_sources()

    def record_sources(self):
        for identifier, text in self.sources.items():
            blob = {'id': identifier, 'body': text, 'sha256': digest(text)}
            if blob not in self.originals:
                self.originals.append(blob)

    def update(self, source, value, step):
        changed = self.sources[source] != value
        self.sources[source] = value
        self.record_sources()
        if not changed:
            return []
        affected = set()
        if self.policy == 'global':
            affected = set(self.dependencies)
        elif self.policy in ('direct_dependencies', 'transitive_dependencies'):
            queue, seen = deque([source]), set()
            while queue:
                item = queue.popleft()
                if item in seen:
                    continue
                seen.add(item)
                parents = {v for v, deps in self.dependencies.items() if item in deps}
                affected.update(parents)
                if self.policy == 'transitive_dependencies':
                    queue.extend(sorted(parents))
        self.dirty.update(affected)
        return sorted(affected)

    def read(self, identifier, step):
        if identifier in self.sources:
            return self.sources[identifier]
        stale_by_time = self.policy == 'ttl_5' and step - self.built_at.get(identifier, -5) >= 5
        if identifier in self.dirty or identifier not in self.cache or stale_by_time:
            # V1's semantic formatter requires both sources even when its declared
            # dependency ledger omits S2. That deliberate mismatch exposes the
            # ceiling of ledger-only invalidation rather than pretending to infer it.
            value = self.sources['S1'] + '|' + self.sources['S2'] if identifier == 'V1' else self.read('V1', step)
            self.cache[identifier] = value
            self.built_at[identifier] = step
            self.dirty.discard(identifier)
            self.rebuilds += 1
        return self.cache[identifier]

    def truth(self):
        return self.sources['S1'] + '|' + self.sources['S2']


def traces(seeds=64, events=20):
    rows = []
    for seed in range(seeds):
        rng = random.Random(1300 + seed)
        actions = []
        state = {'S1': 'amber', 'S2': 'blue', 'U': 'unrelated'}
        for step in range(1, events + 1):
            source = rng.choice(['S1', 'S2', 'U', 'U'])
            value = state[source] if step % 5 == 0 else source.lower() + '-revision-' + str(step)
            state[source] = value
            actions.append((source, value))
        for missing in (False, True):
            for policy in POLICIES:
                cache = Materialized(policy, missing)
                assert cache.read('V2', 0) == cache.truth()
                previous_truth = cache.truth()
                for step, (source, value) in enumerate(actions, 1):
                    before_rebuilds = cache.rebuilds
                    invalidated = cache.update(source, value, step)
                    observed, expected = cache.read('V2', step), cache.truth()
                    rows.append({'seed': seed, 'missing_declared_edge': missing, 'policy': policy,
                        'step': step, 'changed_source': source, 'invalidated': invalidated,
                        'stale_reuse': observed != expected,
                        'rebuilds': cache.rebuilds - before_rebuilds,
                        'truth_changed': expected != previous_truth,
                        'unnecessary_rebuild': expected == previous_truth and cache.rebuilds > before_rebuilds,
                        'retained_original_versions': len(cache.originals)})
                    previous_truth = expected
                assert all(digest(blob['body']) == blob['sha256'] for blob in cache.originals)
    summary = []
    for missing in (False, True):
        for policy in POLICIES:
            selected = [r for r in rows if r['missing_declared_edge'] == missing and r['policy'] == policy]
            summary.append({'policy': policy, 'missing_declared_edge': missing,
                'queries': len(selected), 'stale_reuses': sum(r['stale_reuse'] for r in selected),
                'rebuilds': sum(r['rebuilds'] for r in selected),
                'unnecessary_rebuild_queries': sum(r['unnecessary_rebuild'] for r in selected)})
    return {'state': 'complete_engineered_replay', 'seeds': seeds, 'events_per_seed': events,
            'scope': 'Prescribed dependencies/semantic truth, not LLM maintenance or distributed concurrency',
            'summary': summary, 'rows': rows}


def optimistic_write(path, expected_hash, value):
    current = path.read_bytes() if path.exists() else b''
    if digest(current) != expected_hash:
        return {'committed': False, 'reason': 'stale_baseline'}
    save(path, value)
    return {'committed': True, 'sha256': digest(path.read_bytes())}


def commit_checks(directory):
    """Actual local file checks; no guarantee of multi-host atomic CAS follows."""
    directory.mkdir(parents=True, exist_ok=True)
    pointer = directory / 'current.json'
    save(pointer, {'version': 1, 'sources': ['S1']})
    original = pointer.read_bytes()
    candidate = directory / 'pending.json'
    save(candidate, {'version': 2, 'sources': ['S1', 'S2']})
    # Simulated interruption happens before publication. An uncommitted candidate
    # remains recoverable while the active pointer retains its old complete bytes.
    assert pointer.read_bytes() == original
    candidate_hash = digest(candidate.read_bytes())
    accepted = optimistic_write(pointer, digest(original), json.loads(candidate.read_text(encoding='utf8')))
    rejected = optimistic_write(pointer, digest(original), {'version': 2, 'sources': ['S3']})
    assert accepted['committed'] and not rejected['committed']
    assert json.loads(pointer.read_text(encoding='utf8'))['sources'] == ['S1', 'S2']
    assert candidate_hash == digest(candidate.read_bytes())
    corrupt = candidate.read_bytes()[:-2] + b'xx'
    assert digest(corrupt) != candidate_hash
    return {'actual_disk_write_and_readback': True, 'old_pointer_retained_before_commit': True,
            'stale_writer_rejected': True, 'candidate_source_retained': True,
            'tamper_detected': True, 'multi_host_atomicity_tested': False}


def semantic_ledger_counterexample():
    sources = {'S1': 'Approved interval:13days.', 'S2': 'Scope:amberlane.'}
    projection = 'The approved amberlane interval is99days.'
    ledger = {key: digest(text) for key, text in sources.items()}
    retained_view_hash = digest(projection)
    # A source-version ledger and fixity checksum can both be correct for a
    # faithfully retained but semantically wrong generated view. Known fixture
    # truth, not a hash predicate, supplies the comparison to13days.
    return {'ledger_matches_current_originals': ledger == {key: digest(text) for key, text in sources.items()},
            'view_fixity_passes': retained_view_hash == digest(projection),
            'fixture_view_fact_correct': '13days' in projection,
            'source_text_retained': True,
            'scope': 'Engineered counterexample; no model truth evaluator executed'}


def self_check():
    result = traces(seeds=3, events=10)
    full = {(s['policy'], s['missing_declared_edge']): s for s in result['summary']}
    assert full['transitive_dependencies', False]['stale_reuses'] == 0
    assert full['global', False]['stale_reuses'] == 0
    assert full['direct_dependencies', False]['stale_reuses'] > 0
    assert full['transitive_dependencies', True]['stale_reuses'] > 0
    assert full['global', False]['unnecessary_rebuild_queries'] > 0
    with tempfile.TemporaryDirectory() as folder:
        assert commit_checks(Path(folder))['stale_writer_rejected']
    counterexample = semantic_ledger_counterexample()
    assert counterexample['ledger_matches_current_originals'] and counterexample['view_fixity_passes'] and not counterexample['fixture_view_fact_correct']
    print('maintenance_lab self-check passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--work', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.self_check:
        self_check()
    elif args.run and args.work and args.output:
        result = traces()
        result['commit_checks'] = commit_checks(args.work)
        result['semantic_ledger_counterexample'] = semantic_ledger_counterexample()
        save(args.output, result)
        print(json.dumps({'state': result['state'], 'rows': len(result['rows']), 'summary': result['summary']}))
    else:
        parser.error('Use --self-check, or --run --work PRIVATE_DIRECTORY --output RESULT_JSON')
