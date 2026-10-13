"""A shallow, development-only classifier exported as ordinary JSON rules.

This scores authored evidence relevance, not factual authority or probability of
correct action. Query/document features omit answers, family IDs and split labels.
"""
from collections import Counter
import importlib.metadata
import math
import re
import time
import unicodedata

FEATURES = ('body_query_fraction', 'title_query_fraction', 'alias_query_fraction',
            'scope_query_fraction', 'query_id_hit', 'source_kind',
            'body_log_length', 'outgoing_edges', 'incoming_supersession',
            'has_incorporation_ledger')


def tokens(value):
    return set(re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', value).casefold()))


def features(docs, query):
    wanted = tokens(query)
    denominator = max(1, len(wanted))
    incoming = Counter(old for d in docs.values() for old in d['supersedes'])
    output = {}
    for identifier, doc in docs.items():
        overlap = lambda text: len(tokens(text) & wanted) / denominator
        output[identifier] = [overlap(doc['body']), overlap(doc['title']),
            overlap(' '.join(doc.get('aliases', []))), overlap(doc['scope']),
            float(bool(re.search(r'(?<!\w)' + re.escape(identifier.casefold()) + r'(?!\w)', query.casefold()))), float(doc['kind'] == 'source'),
            math.log1p(len(doc['body'])), min(16, len(doc['links']) + len(doc['supersedes'])),
            min(16, incoming[identifier]), float(bool(doc['incorporates']))]
    return output


def train(rows, training_identity):
    """rows: (numeric feature vector, 0/1 label), from development only."""
    from sklearn.tree import DecisionTreeClassifier
    started = time.perf_counter()
    x, y = zip(*rows)
    assert set(y) == {0, 1} and all(len(value) == len(FEATURES) for value in x)
    estimator = DecisionTreeClassifier(max_depth=3, min_samples_leaf=16,
        class_weight='balanced', random_state=13)
    estimator.fit(x, y)
    tree = estimator.tree_
    positive = list(estimator.classes_).index(1)
    nodes = []
    for n in range(tree.node_count):
        values = tree.value[n][0]
        nodes.append({'feature': int(tree.feature[n]), 'threshold': float(tree.threshold[n]),
            'left': int(tree.children_left[n]), 'right': int(tree.children_right[n]),
            'positive_score': float(values[positive] / sum(values)),
            'samples': int(tree.n_node_samples[n])})
    exported = {'features': list(FEATURES), 'nodes': nodes,
        'training_identity': training_identity, 'training_rows': len(rows),
        'positive_rows': sum(y), 'depth_limit': 3, 'minimum_leaf_rows': 16,
        'class_weight': 'balanced', 'random_state': 13,
        'training_seconds': time.perf_counter() - started,
        'sklearn_version': importlib.metadata.version('scikit-learn'),
        'interpretation': 'Uncalibrated development-evidence classifier score; not authority.'}
    # sklearn uses float32 inputs. Preserve that rounding during rule traversal.
    import numpy as np
    expected = estimator.predict_proba(x)[:, positive]
    actual = [score(exported, [float(v) for v in np.asarray(value, dtype=np.float32)]) for value in x]
    assert max(abs(a - b) for a, b in zip(actual, expected)) < 1e-12
    return exported


def score(model, vector):
    assert len(vector) == len(FEATURES) and all(math.isfinite(v) for v in vector)
    n = 0
    while model['nodes'][n]['left'] != -1:
        node = model['nodes'][n]
        n = node['left'] if vector[node['feature']] <= node['threshold'] else node['right']
    return model['nodes'][n]['positive_score']


def rank(docs, query, model):
    import numpy as np
    vectors = features(docs, query)
    values = {i: score(model, [float(v) for v in np.asarray(row, dtype=np.float32)]) for i, row in vectors.items()}
    return sorted(values, key=lambda i: (-values[i], i))


def self_check():
    rows = [([float(n > 31)] + [0.0] * 9, int(n > 31)) for n in range(64)]
    model = train(rows, {'development_only': True, 'synthetic_boundary_check': True})
    assert len(model['nodes']) == 3 and score(model, rows[0][0]) < score(model, rows[-1][0])
    assert model['depth_limit'] == 3
    docs = {'D1': {'id': 'D1', 'body': 'rule', 'title': 'rule', 'scope': 'all',
                  'kind': 'source', 'links': [], 'supersedes': [], 'incorporates': []}}
    assert features(docs, 'read D10')['D1'][4] == 0
    assert features(docs, 'read D1.')['D1'][4] == 1
    print('decision_ranker self-check passed')


if __name__ == '__main__':
    self_check()
