"""Fixed neural relevance decisions; original model pins are reused unchanged."""
import importlib.util
import math
from pathlib import Path
import time

from index_lab import PreparedIndex
from study_common import digest

HERE = Path(__file__).resolve().parent


def runtime():
    path = HERE.parent / 'study-2026-10-11/model_runtime.py'
    spec = importlib.util.spec_from_file_location('oct11_pinned_scorer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PairDecisions:
    def __init__(self, cache, names=('minilm', 'mixedbread'), threads=2):
        module = runtime()
        self.scorers = {name: module.Scorer(cache, name, threads=threads, batch_size=12) for name in names}
        self.scores = {}
        self.calls = []

    def get(self, name, query, texts, cached=True):
        keys = [(name, digest(query), digest(text)) for text in texts]
        text_by_key = dict(zip(keys, texts))
        missing = list(dict.fromkeys(key for key in keys if not cached or key not in self.scores))
        receipt = {'pairs_requested': len(keys), 'unique_pairs_requested': len(set(keys)),
                   'pair_cache_enabled': cached, 'pairs_computed': len(missing)}
        if missing:
            values, measured = self.scorers[name].score(query, [text_by_key[key] for key in missing])
            self.scores.update(zip(missing, values))
            receipt.update(measured)
            self.calls.append({'model': name, **receipt})
        else:
            receipt.update(seconds=0.0, input_pair_tokens=0, truncated_pairs=0)
        return [self.scores[key] for key in keys], receipt

    def rank(self, docs, query, method, lexical=None, cached=True):
        from packing_lab import source_windows
        if method not in ('minilm_body', 'mixedbread_body', 'minilm_passages'):
            raise ValueError('Unknown neural ranker')
        started = time.perf_counter()
        lexical = lexical or PreparedIndex(docs)
        base = lexical.rank(query, 'body_bm25')
        candidates = base[:32]
        texts, owners = [], []
        for identifier in candidates:
            pieces = source_windows(docs[identifier], query) if method == 'minilm_passages' else [{'text': docs[identifier]['body']}]
            for piece in pieces:
                texts.append(piece['text'])
                owners.append(identifier)
        name = 'mixedbread' if method == 'mixedbread_body' else 'minilm'
        values, receipt = self.get(name, query, texts, cached=cached)
        scores = {i: -math.inf for i in candidates}
        for identifier, value in zip(owners, values):
            scores[identifier] = max(scores[identifier], value)
        order = sorted(candidates, key=lambda i: (-scores[i], i)) + base[32:]
        assert len(order) == len(set(order)) == len(docs)
        receipt.update(method=method, lexical_candidates=32, candidate_count=len(candidates),
            candidate_scores=scores, combined_query_document_token_limit=512,
            passage_heuristic='two highest-overlap sentence anchors with immediate neighbors',
            query_rank_seconds=time.perf_counter() - started,
            query_sha256=digest(query), ranking_sha256=digest('\n'.join(order)))
        return order, receipt


def self_check():
    # No model load needed to test exact duplicate cache semantics.
    class Fake:
        def score(self, query, texts):
            return [float(len(text)) for text in texts], {'seconds': 0.0, 'pairs': len(texts), 'input_pair_tokens': len(texts), 'truncated_pairs': 0}
    instance = PairDecisions.__new__(PairDecisions)
    instance.scorers, instance.scores, instance.calls = {'minilm': Fake()}, {}, []
    values, receipt = instance.get('minilm', '青灯', ['aa', 'aa', 'b'])
    assert values == [2.0, 2.0, 1.0] and receipt['pairs_computed'] == 2
    assert instance.get('minilm', '青灯', ['aa'])[1]['pairs_computed'] == 0
    assert instance.get('minilm', '青灯', ['aa'], cached=False)[1]['pairs_computed'] == 1
    print('neural_ranker self-check passed')


if __name__ == '__main__':
    self_check()
