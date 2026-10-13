"""Read-only, stdlib audit of privately downloaded external benchmark artifacts.

Prints only hashes, schemas, and counts. Never ranks, answers, fetches, or writes.
The input projections deliberately exclude construction labels and evaluator gold.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def jsonl_prefix(path, partial=False):
    data = path.read_bytes()
    lines = data.splitlines(keepends=True)
    if partial and lines and not lines[-1].endswith(b'\n'):
        lines.pop()  # A partial final record is not an observed complete trajectory.
    return [json.loads(line) for line in lines if line.strip()]


def array_prefix(path):
    # Only complete objects count. A bounded byte prefix may cut its last UTF-8
    # character/object; full-file parsing and publisher verification precede scoring.
    text = path.read_bytes().decode('utf-8', errors='ignore')
    assert text.lstrip().startswith('[')
    decoder, rows, cursor = json.JSONDecoder(), [], text.index('[') + 1
    while cursor < len(text):
        while cursor < len(text) and (text[cursor].isspace() or text[cursor] == ','):
            cursor += 1
        if cursor == len(text) or text[cursor] == ']':
            break
        try:
            row, cursor = decoder.raw_decode(text, cursor)
        except json.JSONDecodeError:
            break
        assert isinstance(row, dict)
        rows.append(row)
    return rows


def keys(value):
    if isinstance(value, dict):
        return set(value).union(*(keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(keys(v) for v in value))
    return set()


def v1_separate(row):
    query = {k: row[k] for k in ('question_id', 'question', 'question_date')}
    assert len(row['haystack_sessions']) == len(row['haystack_session_ids']) == len(row['haystack_dates'])
    corpus = [{'id': sid, 'date': date,
               'turns': [{k: turn[k] for k in ('role', 'content')} for turn in session]}
              for sid, date, session in zip(row['haystack_session_ids'], row['haystack_dates'], row['haystack_sessions'])]
    gold = {'answer': row['answer'], 'answer_session_ids': row['answer_session_ids'],
            'turn_support': [[bool(t.get('has_answer', False)) for t in s]
                             for s in row['haystack_sessions']]}
    assert not {'answer', 'answer_session_ids', 'has_answer', 'question_type'} & keys([query, corpus])
    assert set(gold['answer_session_ids']) <= set(row['haystack_session_ids'])
    return query, corpus, gold


def v2_separate(question, trajectories):
    query = {k: question[k] for k in ('id', 'question')}
    corpus = [{'id': t['id'], 'goal': t['goal'],
               'states': [{k: s[k] for k in ('state_index', 'step', 'url', 'action', 'accessibility_tree')}
                          for s in t['states']]} for t in trajectories]
    gold = {k: question[k] for k in ('answer', 'eval_function')}
    assert not {'answer', 'eval_function', 'question_type', 'thought', 'screenshot'} & keys([query, corpus])
    return query, corpus, gold


def support_ids(value):
    if isinstance(value, dict):
        return set().union(*(support_ids(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(support_ids(v) for v in value))
    assert isinstance(value, int) and not isinstance(value, bool), 'Unexpected support-id shape'
    return {str(value)}


def beam_separate(question, chat):
    corpus = [{'id': str(t['id']), 'role': t['role'], 'content': t['content'],
               'time_anchor': t.get('time_anchor', b['time_anchor'])}
              for b in chat for group in b['turns'] for t in group]
    query = {'question': question['question']}
    gold = {k: v for k, v in question.items() if k != 'question'}
    assert keys([query, corpus]) <= {'question', 'id', 'role', 'content', 'time_anchor'}
    supports = support_ids(gold.get('source_chat_ids', []))
    assert supports <= {r['id'] for r in corpus}, 'Unresolved original support id'
    return query, corpus, gold, supports


def mem2act_separate(row):
    query = {'query': row['query'], 'target_tool_schema': row['target_tool_schema']}
    gold = {k: v for k, v in row.items() if k not in query}
    # target_tool_schema is a task affordance; its validity/defaults still require
    # review before action scoring. No tool is invoked by this audit.
    assert not {'tool_call', 'grounding_info', 'evolution_chain', 'source_conversation_ids', 'complexity_metadata'} & keys(query)
    return query, gold


def self_check():
    row = {'question_id': 'q', 'question': 'query', 'question_date': 'date',
           'question_type': 'withheld', 'answer': 'gold sentinel', 'answer_session_ids': ['s'],
           'haystack_session_ids': ['s'], 'haystack_dates': ['date'],
           'haystack_sessions': [[{'role': 'user', 'content': 'source', 'has_answer': True}]]}
    query, corpus, gold = v1_separate(row)
    assert 'gold sentinel' not in json.dumps([query, corpus])
    assert gold['turn_support'] == [[True]]
    assert support_ids({'first': [1], 'second': [1, 2]}) == {'1', '2'}
    try:
        support_ids(['ambiguous textual label'])
    except AssertionError:
        pass
    else:
        raise AssertionError('Malformed support ids were accepted')
    return {'self_check': 'passed', 'no_network_no_writes_no_scores': True}


def audit(root):
    manifest = json.loads(Path(__file__).with_name('external-transfer-sources.json').read_text(encoding='utf-8'))
    verified = []
    for f in manifest['downloaded_files']:
        path = root / f['local_relative']
        data = path.read_bytes()
        assert len(data) == f['bytes'] and hashlib.sha256(data).hexdigest() == f['sha256'], f['local_relative']
        verified.append({'file': f['local_relative'], 'bytes': len(data), 'sha256': f['sha256'], 'prefix_only': f['prefix_only']})
    qs = jsonl_prefix(root / 'lme2/questions.jsonl')
    hay = json.loads((root / 'lme2/haystacks/lme_v2_small.json').read_bytes())
    trajectories = jsonl_prefix(root / 'lme2/trajectories.prefix', partial=True)
    assert len({q['id'] for q in qs}) == len(qs) and set(hay) == {q['id'] for q in qs}
    assert all(len(ids) == 100 for ids in hay.values())
    v2 = [v2_separate(q, trajectories) for q in qs if q['image'] is None]
    oracle = json.loads((root / 'lme1/longmemeval_oracle.json').read_bytes())
    small_prefix = array_prefix(root / 'lme1/longmemeval_s_cleaned.prefix')
    v1 = [v1_separate(row) for row in oracle + small_prefix]
    chat = json.loads((root / 'beam/chat.json').read_bytes())
    bq = json.loads((root / 'beam/probing_questions.json').read_bytes())
    beam = [beam_separate(q, chat) for group in bq.values() for q in group]
    mqs = jsonl_prefix(root / 'mem2act/qa_dataset.jsonl')
    mem = [mem2act_separate(q) for q in mqs]
    mrows = jsonl_prefix(root / 'mem2act/toolmem_conversation.prefix', partial=True)
    return {'audit_kind': 'schema_and_label_boundary_only', 'files_verified': verified,
            'counts': {'lme2_questions': len(qs), 'lme2_text_only': len(v2),
                       'lme2_question_types': dict(Counter(q['question_type'] for q in qs)),
                       'lme2_unique_small_haystacks': len({tuple(v) for v in hay.values()}),
                       'lme2_unique_small_trajectory_ids': len(set().union(*(set(v) for v in hay.values()))),
                       'lme2_complete_prefix_trajectories': len(trajectories),
                       'lme1_oracle_questions': len(oracle), 'lme1_abstentions': sum(q['question_id'].endswith('_abs') for q in oracle),
                       'lme1_complete_small_prefix_records': len(small_prefix),
                       'lme1_small_prefix_types': dict(Counter(q['question_type'] for q in small_prefix)),
                       'beam_queries': len(beam), 'beam_source_labeled_queries': sum(bool(q[3]) for q in beam),
                       'beam_messages': len(beam[0][1]), 'beam_unique_message_ids': len({x['id'] for x in beam[0][1]}),
                       'mem2act_questions': len(mqs), 'mem2act_complete_prefix_sessions': len(mrows),
                       'mem2act_levels': dict(Counter(q['complexity_metadata']['level'] for q in mqs))},
            'schemas': {'lme2_question': sorted(qs[0]), 'lme2_trajectory': sorted(trajectories[0]),
                        'lme2_state': sorted(trajectories[0]['states'][0]), 'lme1_question': sorted(oracle[0]),
                        'mem2act_question': sorted(mqs[0]), 'beam_query_categories': sorted(bq)},
            'separation': {'all_projection_assertions_passed': True,
                           'projection_pair_counts': {'v1': len(v1), 'v2': len(v2), 'beam': len(beam), 'mem2act': len(mem)},
                           'v1_source_projection_digest': digest([v[0:2] for v in v1]),
                           'beam_source_projection_digest': digest([v[0:2] for v in beam]),
                           'gold_never_emitted': True, 'support_semantics_validated': False,
                           'v2_original_support_labels_available': False},
            'benchmark_or_retrieval_scores_computed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-root', type=Path)
    args = parser.parse_args()
    result = self_check()
    if args.private_root:
        result['artifact_audit'] = audit(args.private_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
