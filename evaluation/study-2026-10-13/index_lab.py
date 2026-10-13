"""Gold-free, deterministic retrieval policies over fictional source records.

rank(docs, query, method) returns every document ID exactly once. Reuse
PreparedIndex for index/query timing; rank_with_receipt also records deterministic
provenance. This module performs no packing, summarization, file IO or inference.
See INDEX-RESEARCH.md for formulas, fixed choices and limitations.
"""
import argparse
from collections import Counter
from datetime import date
import hashlib
import json
import math
import re
import unicodedata


METHODS = (
    'body_bm25', 'search_bm25', 'word_tfidf', 'char_tfidf', 'field_bm25',
    'rrf_word_char', 'entity_rrf', 'clause_rrf', 'sentence_maxsim',
    'coverage_mmr', 'scope_temporal', 'graph_diffusion', 'pseudo_feedback',
)
VERSION = 'index-lab-2026-10-13-v1'
STOP = frozenset('a an and are as at be by can do for from how i in is it of on or '
                 'the this to was what when where which who why with would'.split())


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def sha(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def norm(text):
    return unicodedata.normalize('NFKC', text).casefold()


def tokens(text):
    return re.findall(r'[^\W_]+', norm(text), re.UNICODE)


def clauses_for(query):
    clauses = [c.strip() for c in re.split(r'[;?\n]|\b(?:and|also|plus)\b', query, flags=re.I)
               if tokens(c)] or [query]
    return clauses[:8], {'query_clauses': clauses[:8], 'clause_cap': 8,
                         'clauses_before_cap': len(clauses), 'clauses_omitted': max(0, len(clauses)-8)}


def grams(text):
    # Boundary-preserving word character grams avoid bridging unrelated words.
    # Memory is O(total unique document grams); use compressed postings at scale.
    result = Counter()
    for word in tokens(text):
        padded = ' ' + word + ' '
        for n in (3, 4, 5):
            result.update(padded[i:i+n] for i in range(max(0, len(padded)-n+1)))
    return result


def sorted_ids(ids, scores):
    if set(ids) != set(scores) or not all(math.isfinite(x) for x in scores.values()):
        raise ValueError('Scores must be finite and cover the collection')
    return sorted(ids, key=lambda i: (-scores[i], i))


def scale(scores):
    maximum = max(scores.values(), default=0.0)
    return {i: s / maximum if maximum > 0 else 0.0 for i, s in scores.items()}


def fuse(ids, rankings, k=60):
    result = {i: 0.0 for i in ids}
    for order in rankings:
        for position, i in enumerate(order, 1):
            result[i] += 1.0 / (k + position)
    return result


class Lexical:
    def __init__(self, bags):
        self.bags = bags
        self.lengths = {i: sum(b.values()) for i, b in bags.items()}
        self.average = sum(self.lengths.values()) / max(1, len(bags)) or 1.0
        self.df = Counter(t for b in bags.values() for t in b)
        self.idf = {t: math.log((1+len(bags))/(1+df))+1 for t, df in self.df.items()}
        self.vectors = {}
        for i, bag in bags.items():
            vector = {t: (1+math.log(count))*self.idf[t] for t, count in bag.items()}
            length = math.sqrt(sum(v*v for v in vector.values())) or 1.0
            self.vectors[i] = {t: value/length for t, value in vector.items()}

    def bm25(self, query):
        query = Counter(query)
        result = {}
        for i, bag in self.bags.items():
            score = 0.0
            for term, count in query.items():
                tf = bag[term]
                if tf:
                    idf = math.log(1+(len(self.bags)-self.df[term]+.5)/(self.df[term]+.5))
                    score += count*idf*tf*2.2/(tf+1.2*(.25+.75*self.lengths[i]/self.average))
            result[i] = score
        return result

    def cosine(self, query):
        query = Counter(query)
        # Corpus-unknown terms are omitted; a fully unknown query yields zeros.
        vector = {t: (1+math.log(c))*self.idf[t] for t, c in query.items() if t in self.idf}
        length = math.sqrt(sum(v*v for v in vector.values())) or 1.0
        vector = {t: v/length for t, v in vector.items()}
        return {i: sum(v*stored.get(t, 0) for t, v in vector.items())
                for i, stored in self.vectors.items()}


class PreparedIndex:
    """Immutable retained-field snapshot; unknown fields never enter retrieval.

    Eager word/sentence indexes and lazy character index allow callers to report
    both preparation time and first-query extra index work. No implicit disk cache.
    """
    def __init__(self, docs):
        if not isinstance(docs, dict):
            raise ValueError('docs must map IDs to record dictionaries')
        self.docs = {}
        for i in sorted(docs):
            d = docs[i]
            if not isinstance(i, str) or not i or not isinstance(d, dict):
                raise ValueError('Expected nonempty string IDs and record dictionaries')
            if d.get('id', i) != i or not isinstance(d.get('body'), str):
                raise ValueError('ID mismatch or missing body text')
            row = {'id': i, 'body': d['body']}
            revision = d.get('revision')
            if revision is not None and (isinstance(revision, bool) or not isinstance(revision, (str, int))):
                raise ValueError('Expected string/integer source revision')
            row['revision'] = revision
            for key in ('title', 'scope', 'effective_from', 'effective_to'):
                alias = {'effective_from': 'valid_from', 'effective_to': 'valid_to'}.get(key)
                if alias and d.get(key) and d.get(alias) and d[key] != d[alias]:
                    raise ValueError('Conflicting effective interval field names')
                value = d.get(key, d.get(alias, '') if alias else '')
                if value is None: value = ''
                if not isinstance(value, str): raise ValueError('Expected string '+key)
                row[key] = value
            for key in ('aliases', 'links', 'supersedes'):
                value = d.get(key, [])
                if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
                    raise ValueError('Expected string list '+key)
                row[key] = list(value)
            incorporated = d.get('incorporates', [])
            if not isinstance(incorporated, list) or any(
                    not isinstance(x, dict) or not isinstance(x.get('id'), str) for x in incorporated):
                raise ValueError('Expected incorporation ledger dictionaries with IDs')
            row['incorporates'] = [x['id'] for x in incorporated]
            for key in ('effective_from', 'effective_to'):
                if row[key]: date.fromisoformat(row[key])
            if row['effective_from'] and row['effective_to'] and row['effective_from'] > row['effective_to']:
                raise ValueError('Effective interval is inverted')
            self.docs[i] = row
        self.ids = tuple(self.docs)
        self.digest = sha(self.docs)
        self.body = Lexical({i: Counter(tokens(d['body'])) for i, d in self.docs.items()})
        self.search_text = {i: '\n'.join([d['title'], d['scope'], *d['aliases'], d['body']])
                            for i, d in self.docs.items()}
        self.search = Lexical({i: Counter(tokens(text)) for i, text in self.search_text.items()})
        self.title = Lexical({i: Counter(tokens(d['title'])) for i, d in self.docs.items()})
        self.cues = Lexical({i: Counter(tokens(' '.join([d['scope'], *d['aliases']])))
                             for i, d in self.docs.items()})
        self.parts = {}
        sentence_bags = {}
        for i, d in self.docs.items():
            pieces = [p for p in re.split(r'[\n.!?;]+', d['body']) if p.strip()]
            self.parts[i] = []
            for j, part in enumerate(pieces):
                key = (i, j)
                self.parts[i].append(key)
                sentence_bags[key] = Counter(tokens(part))
        self.sentences = Lexical(sentence_bags)
        self.characters = None
        self.graph = {i: set() for i in self.ids}
        self.missing = set()
        for i, d in self.docs.items():
            for other in d['links']+d['supersedes']+d['incorporates']:
                if other in self.graph:
                    if other != i:
                        self.graph[i].add(other)
                        self.graph[other].add(i)
                else:
                    self.missing.add((i, other))

    def prepare_characters(self):
        if self.characters is None:
            self.characters = Lexical({i: grams(text) for i, text in self.search_text.items()})

    def entity_scores(self, query):
        normalized = norm(query)
        result = {}
        for i, d in self.docs.items():
            score = 0.0
            if re.search(r'(?<!\w)'+re.escape(i)+r'(?!\w)', query): score += 10.0
            for alias in d['aliases']:
                alias = norm(alias).strip()
                if len(alias) >= 2 and re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)', normalized):
                    score = max(score, 1+len(tokens(alias)))
            result[i] = score
        return result

    def _rank(self, query, method):
        if method not in METHODS: raise ValueError('Unknown method: '+str(method))
        if not isinstance(query, str) or not query.strip(): raise ValueError('Expected nonempty query')
        qt = tokens(query)
        base = self.search.bm25(qt)
        base_order = sorted_ids(self.ids, base)
        metadata = {}
        if method == 'body_bm25': scores = self.body.bm25(qt)
        elif method == 'search_bm25': scores = base
        elif method == 'word_tfidf': scores = self.search.cosine(qt)
        elif method == 'char_tfidf':
            self.prepare_characters()
            scores = self.characters.cosine(grams(query))
        elif method == 'field_bm25':
            # Independent field-score combination, deliberately NOT BM25F.
            fields = (self.body.bm25(qt), self.title.bm25(qt), self.cues.bm25(qt))
            scores = {i: fields[0][i]+2*fields[1][i]+fields[2][i] for i in self.ids}
        elif method in ('rrf_word_char', 'entity_rrf'):
            self.prepare_characters()
            character = self.characters.cosine(grams(query))
            orders = [base_order, sorted_ids(self.ids, character)]
            entities = self.entity_scores(query) if method == 'entity_rrf' else {}
            # Non-matches contribute no entity rank; no arbitrary ID-tie votes.
            matches = [i for i in self.ids if entities.get(i, 0) > 0]
            if matches: orders.append(sorted(matches, key=lambda i: (-entities[i], i)))
            scores = fuse(self.ids, orders)
            metadata['exact_entity_matches'] = matches
            metadata['fusion_k'] = 60
            metadata['channel_rankings'] = orders
            metadata['uncertainty_note'] = 'Rank disagreement is inspectable; it is not calibrated confidence.'
        elif method == 'clause_rrf':
            clauses, metadata = clauses_for(query)
            scores = fuse(self.ids, [sorted_ids(self.ids, self.search.bm25(tokens(c))) for c in clauses])
        elif method == 'sentence_maxsim':
            clauses, metadata = clauses_for(query)
            similarities = [self.sentences.cosine(tokens(c)) for c in clauses]
            scores = {i: sum(max((s[k] for k in self.parts[i]), default=0.0)
                              for s in similarities)/len(similarities) for i in self.ids}
        elif method == 'coverage_mmr':
            # O(N^2) greedy ordering; use a bounded candidate pool for large vaults.
            # Every original remains eligible; novelty is not factual authority.
            relevant = scale(base)
            terms = set(qt)-STOP
            weights = {t: self.search.idf.get(t, 1.0) for t in terms}
            total = sum(weights.values()) or 1.0
            selected, covered, remaining = [], set(), set(self.ids)
            redundancies = {i: 0.0 for i in self.ids}
            trace = []
            while remaining:
                values = {}
                for i in remaining:
                    present = set(self.search.bags[i])
                    coverage = sum(weights[t] for t in (present & terms)-covered)/total
                    values[i] = .65*relevant[i]+.25*coverage-.10*redundancies[i]
                chosen = min(remaining, key=lambda i: (-values[i], i))
                trace.append({'id': chosen, 'greedy_score': values[chosen]})
                selected.append(chosen); remaining.remove(chosen)
                covered.update(set(self.search.bags[chosen]) & terms)
                for i in remaining:
                    similarity = sum(v*self.search.vectors[chosen].get(t, 0)
                                     for t, v in self.search.vectors[i].items())
                    redundancies[i] = max(redundancies[i], similarity)
            return selected, {'greedy_trace': trace, 'query_terms': sorted(terms)}
        elif method == 'scope_temporal':
            scores = scale(base)
            scopes = sorted({d['scope'] for d in self.docs.values() if d['scope'] and norm(d['scope']) != 'all'})
            matches = [s for s in scopes if re.search(r'(?<!\w)'+re.escape(norm(s))+r'(?!\w)', norm(query))]
            requested_scope = matches[0] if len(matches) == 1 else None
            date_match = re.search(r'\bas\s+of\s+(\d{4}-\d{2}-\d{2})\b', norm(query))
            requested_date = date.fromisoformat(date_match[1]).isoformat() if date_match else None
            states = {}
            for i, d in self.docs.items():
                state = {'scope': 'unknown', 'effective_interval': 'unknown'}
                if requested_scope and d['scope']:
                    state['scope'] = 'match' if norm(d['scope']) in (norm(requested_scope), 'all') else 'mismatch'
                    scores[i] += .20 if state['scope'] == 'match' else -.20
                if requested_date and (d['effective_from'] or d['effective_to']):
                    active = ((not d['effective_from'] or d['effective_from'] <= requested_date)
                              and (not d['effective_to'] or requested_date <= d['effective_to']))
                    state['effective_interval'] = 'match' if active else 'mismatch'
                    scores[i] += .20 if active else -.20
                states[i] = state
            metadata.update(requested_scope=requested_scope, requested_date=requested_date,
                            applicability_states=states, authored_time_used=False, hard_filter=False)
        elif method == 'graph_diffusion':
            total = sum(base.values())
            seed = {i: base[i]/total if total > 0 else 0.0 for i in self.ids}
            scores = seed.copy()
            for _ in range(4):
                propagated = {i: .65*seed[i] for i in self.ids}
                for i in self.ids:
                    if self.graph[i]:
                        for j in sorted(self.graph[i]): propagated[j] += .35*scores[i]/len(self.graph[i])
                    else: propagated[i] += .35*scores[i]
                scores = propagated
            metadata.update(iterations=4, propagation=.35, edge_direction='bidirectional',
                            missing_edges=[list(x) for x in sorted(self.missing)])
        elif method == 'pseudo_feedback':
            candidates = [i for i in base_order if base[i] > 0][:3]
            original = set(qt)
            feedback = Counter()
            for i in candidates:
                for term, count in self.body.bags[i].items():
                    if term not in original and term not in STOP and len(term) >= 3:
                        feedback[term] += min(count, 3)*self.body.idf[term]
            extra = sorted(feedback, key=lambda t: (-feedback[t], t))[:6]
            expanded = self.search.bm25(qt+extra)
            scaled_base, scaled_expanded = scale(base), scale(expanded)
            scores = {i: .75*scaled_base[i]+.25*scaled_expanded[i] for i in self.ids}
            metadata.update(feedback_source_ids=candidates, expansion_terms=extra,
                            interpretation='Unsupervised lexical feedback; not a relevance-model implementation')
        return sorted_ids(self.ids, scores), {'scores': scores, **metadata}

    def rank(self, query, method):
        return self._rank(query, method)[0]

    def rank_with_receipt(self, query, method):
        order, details = self._rank(query, method)
        receipt = {'schema_version': 1, 'implementation': VERSION, 'method': method,
                   'collection_sha256': self.digest, 'query_sha256': sha(query),
                   'documents': len(self.ids), 'ranked_ids': order,
                   'ranking_sha256': sha(order), 'gold_inputs_used': False,
                   'metadata_enters_returned_context': False,
                   'note': 'No context packet is created by this ranking interface.', **details}
        return order, receipt


def rank(docs, query, method):
    return PreparedIndex(docs).rank(query, method)


def rank_with_receipt(docs, query, method):
    return PreparedIndex(docs).rank_with_receipt(query, method)


def self_check():
    docs = {
        'N1': {'id': 'N1', 'title': 'Blue archive', 'aliases': ['Lighthouse'],
               'scope': 'north', 'body': 'Blue archive retention is eight days. Approved evidence is linked.',
               'links': ['N2', 'ABSENT'], 'effective_from': '2026-10-01', 'effective_to': '2026-10-31'},
        'N2': {'id': 'N2', 'title': 'Correction', 'scope': 'north',
               'body': 'The authorized exception changes retention to twelve days.', 'supersedes': ['N1']},
        'S1': {'id': 'S1', 'title': 'Blue archive', 'scope': 'south',
               'body': 'Blue archive retention is eight days.', 'effective_from': '2026-11-01'},
        'X1': {'id': 'X1', 'title': 'Recipe', 'body': 'The recipe uses apples and cinnamon.'},
    }
    index = PreparedIndex(docs)
    receipts = {}
    for method in METHODS:
        order, receipt = index.rank_with_receipt('Lighthouse blue archive retention north as of 2026-10-13', method)
        assert len(order) == 4 and set(order) == set(docs)
        assert (order, receipt) == index.rank_with_receipt('Lighthouse blue archive retention north as of 2026-10-13', method)
        assert all(math.isfinite(v) for v in receipt.get('scores', {}).values())
        receipts[method] = receipt
    assert index.rank('blue archive retention', 'body_bm25')[0] in ('N1', 'S1')
    assert index.entity_scores('Read N2 and Lighthouse')['N2'] == 10.0
    assert index.entity_scores('Read N21')['N2'] == 0.0
    assert receipts['scope_temporal']['applicability_states']['N1']['effective_interval'] == 'match'
    assert receipts['scope_temporal']['applicability_states']['S1']['effective_interval'] == 'mismatch'
    assert receipts['graph_diffusion']['missing_edges'] == [['N1', 'ABSENT']]
    assert rank({}, 'hello', 'search_bm25') == []
    contaminated = {i: {**d, 'expected': {'answer': 'DO NOT USE'}, 'evidence_sets': [['X1']]}
                    for i, d in docs.items()}
    assert PreparedIndex(contaminated).digest == index.digest
    original = index.rank('blue archive retention', 'search_bm25')
    docs['N1']['body'] = 'Mutated after snapshot'
    assert index.rank('blue archive retention', 'search_bm25') == original
    for invalid_docs in ({'bad': {'body': 3}}, {'bad': {'body': 'x', 'links': 'not a list'}},
                         {'bad': {'body': 'x', 'effective_from': '2026-99-10'}}):
        try: PreparedIndex(invalid_docs)
        except (ValueError, TypeError): pass
        else: raise AssertionError('Trust boundary did not reject invalid data')
    return {'state': 'passed', 'schema_version': 1, 'methods_checked': len(METHODS),
            'checks': ['complete permutation', 'deterministic receipt', 'finite scores', 'literal ID boundary',
                       'explicit time interval', 'missing edge retention', 'empty corpus',
                       'unknown/gold field exclusion', 'snapshot isolation', 'invalid-input rejection'],
            'fictional_smoke': receipts}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    if not args.self_check: parser.error('Use --self-check; ranking is available through the Python API')
    print(json.dumps(self_check(), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
