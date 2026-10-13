"""Pinned, cached dense retrieval with one public ONNX sentence encoder.

No pickle, remote code, authenticated service or torch is used. Weights and
representations belong in a private cache outside the public repository. Whole
record and overlapping token-window variants share the same pinned encoder.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import tempfile
import time
import urllib.request

from index_lab import PreparedIndex, fuse, sha, sorted_ids, tokens


HERE = Path(__file__).resolve().parent
SPEC = {
    'repository': 'sentence-transformers/all-MiniLM-L6-v2',
    'revision': '1110a243fdf4706b3f48f1d95db1a4f5529b4d41',
    'weight': 'onnx/model_quint8_avx2.onnx',
    'bytes': 23046789,
    'sha256': 'b941bf19f1f1283680f449fa6a7336bb5600bdcd5f84d10ddc5cd72218a0fd21',
    'license': 'Apache-2.0', 'dimensions': 384, 'max_tokens': 256,
    'pooling': 'attention-mask weighted token mean, then L2 normalization',
}
FILES = ('config.json', 'tokenizer.json', 'tokenizer_config.json',
         'special_tokens_map.json', 'sentence_bert_config.json', '1_Pooling/config.json', SPEC['weight'])
FILE_SHA256 = {
    'config.json': '953f9c0d463486b10a6871cc2fd59f223b2c70184f49815e7efbcab5d8908b41',
    'tokenizer.json': 'be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037',
    'tokenizer_config.json': 'acb92769e8195aabd29b7b2137a9e6d6e25c476a4f15aa4355c233426c61576b',
    'special_tokens_map.json': '303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3',
    'sentence_bert_config.json': 'fc1993fde0a95c24ec6c022539d41cf6e2f7c9721e5415d6fb6897472a9cd4b7',
    '1_Pooling/config.json': '4be450dde3b0273bb9787637cfbd28fe04a7ba6ab9d36ac48e92b11e350ffc23',
    SPEC['weight']: SPEC['sha256'],
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                              allow_nan=False)+'\n', encoding='utf-8', newline='\n')
    tmp.replace(path)


def acquire(cache):
    cache = Path(cache).resolve()
    if cache.is_relative_to(HERE.parents[1]):
        raise ValueError('Dense cache must remain outside the public repository')
    target = cache/'dense-minilm'
    target.mkdir(parents=True, exist_ok=True)
    manifest = {'model': SPEC, 'files': {}}
    for rel in FILES:
        destination = target/rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    url = f"https://huggingface.co/{SPEC['repository']}/resolve/{SPEC['revision']}/{rel}"
                    with urllib.request.urlopen(url, timeout=60) as response:
                        while chunk := response.read(1024*1024): stream.write(chunk)
                if digest(temporary) != FILE_SHA256[rel]:
                    raise ValueError('Pinned model-file digest mismatch')
                if rel == SPEC['weight'] and temporary.stat().st_size != SPEC['bytes']:
                    raise ValueError('Publisher weight size mismatch')
                temporary.replace(destination)
            finally:
                if temporary is not None and temporary.exists(): temporary.unlink()
        if digest(destination) != FILE_SHA256[rel]:
            raise ValueError('Pinned model-file digest mismatch')
        if rel == SPEC['weight'] and destination.stat().st_size != SPEC['bytes']:
            raise ValueError('Pinned weight size mismatch')
        manifest['files'][rel] = {'sha256': digest(destination), 'bytes': destination.stat().st_size}
    config = json.loads((target/'config.json').read_text(encoding='utf-8'))
    pooling = json.loads((target/'1_Pooling/config.json').read_text(encoding='utf-8'))
    limits = json.loads((target/'sentence_bert_config.json').read_text(encoding='utf-8'))
    if config.get('auto_map') or config.get('model_type') != 'bert':
        raise ValueError('Unexpected architecture or custom-code mapping')
    if limits.get('max_seq_length') != 256 or not pooling.get('pooling_mode_mean_tokens'):
        raise ValueError('Publisher pooling/token configuration changed')
    return target, manifest


class Encoder:
    def __init__(self, cache, threads=2, batch_size=12):
        if threads not in (1, 2) or not 1 <= batch_size <= 24:
            raise ValueError('Bounded CPU configuration required')
        import onnxruntime as ort
        from tokenizers import Tokenizer
        started = time.perf_counter()
        path, self.manifest = acquire(cache)
        acquired = time.perf_counter()
        self.tokenizer = Tokenizer.from_file(str(path/'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=256)
        self.tokenizer.enable_padding(pad_id=0, pad_token='[PAD]')
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(str(path/SPEC['weight']), sess_options=options,
                                             providers=['CPUExecutionProvider'])
        self.inputs = {x.name: x.type for x in self.session.get_inputs()}
        if set(self.inputs) != {'input_ids', 'attention_mask', 'token_type_ids'}:
            raise ValueError('Unexpected model input interface')
        if any(t != 'tensor(int64)' for t in self.inputs.values()):
            raise ValueError('Unexpected input tensor type')
        if len(self.session.get_outputs()) != 1:
            raise ValueError('Expected token embeddings only')
        self.batch_size = batch_size
        self.cache = Path(cache).resolve()
        self.manifest.update(acquire_or_verify_seconds=acquired-started,
                             model_load_seconds=time.perf_counter()-acquired,
                             threads=threads, batch_size=batch_size, providers=self.session.get_providers(),
                             packages={p: importlib.metadata.version(p) for p in ('numpy', 'onnxruntime', 'tokenizers')})

    def encode(self, texts):
        import numpy as np
        if not isinstance(texts, list) or any(not isinstance(t, str) for t in texts):
            raise ValueError('Expected a list of text strings')
        started = time.perf_counter()
        vectors, records = [], []
        for offset in range(0, len(texts), self.batch_size):
            encodings = self.tokenizer.encode_batch(texts[offset:offset+self.batch_size])
            arrays = {'input_ids': [e.ids for e in encodings],
                      'attention_mask': [e.attention_mask for e in encodings],
                      'token_type_ids': [e.type_ids for e in encodings]}
            feed = {name: np.asarray(arrays[name], dtype=np.int64) for name in self.inputs}
            output = self.session.run(None, feed)[0]
            if output.shape != (len(encodings), len(encodings[0].ids), 384):
                raise ValueError('Unexpected token embedding output shape')
            mask = feed['attention_mask'].astype(np.float32)[..., None]
            pooled = (output.astype(np.float32)*mask).sum(axis=1)/np.maximum(mask.sum(axis=1), 1e-9)
            pooled /= np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9)
            if not np.isfinite(pooled).all(): raise ValueError('Non-finite dense vectors')
            vectors.extend(pooled)
            records.extend({'tokens': int(sum(e.attention_mask)), 'truncated': bool(e.overflowing)} for e in encodings)
        matrix = np.asarray(vectors, dtype=np.float32).reshape((-1, 384))
        return matrix, {'seconds': time.perf_counter()-started, 'texts': len(texts),
                        'input_tokens': sum(r['tokens'] for r in records),
                        'truncated_texts': sum(r['truncated'] for r in records), 'records': records}

    def windows(self, text, width=192, overlap=32):
        # Use original Unicode offsets, retaining provenance. This local tokenizer
        # clone avoids changing query/whole-document truncation state.
        from tokenizers import Tokenizer
        tokenizer = Tokenizer.from_str(self.tokenizer.to_str())
        tokenizer.no_truncation(); tokenizer.no_padding()
        encoded = tokenizer.encode(text, add_special_tokens=False)
        offsets = encoded.offsets
        if not offsets: return [{'start': 0, 'end': len(text), 'text': text}]
        pieces = []
        for position in range(0, len(offsets), width-overlap):
            selected = offsets[position:position+width]
            start, end = selected[0][0], selected[-1][1]
            pieces.append({'start': start, 'end': end, 'text': text[start:end]})
            if position+width >= len(offsets): break
        return pieces


class DensePreparedIndex:
    def __init__(self, docs, encoder, text_mode='body', windows=False):
        import numpy as np
        if text_mode not in ('body', 'search') or not isinstance(windows, bool):
            raise ValueError('Expected body/search text representation and bool windows')
        started = time.perf_counter()
        self.lexical = PreparedIndex(docs)
        self.ids = self.lexical.ids
        self.encoder = encoder
        self.text_mode, self.windows_enabled = text_mode, windows
        texts = {i: self.lexical.docs[i]['body'] if text_mode == 'body' else self.lexical.search_text[i]
                 for i in self.ids}
        self.mapping = []
        representations = []
        for i, text in texts.items():
            chunks = encoder.windows(text) if windows else [{'start': 0, 'end': len(text), 'text': text}]
            for j, chunk in enumerate(chunks):
                self.mapping.append({'id': i, 'chunk': j, 'start': chunk['start'], 'end': chunk['end'],
                                     'text_sha256': hashlib.sha256(chunk['text'].encode('utf-8')).hexdigest()})
                representations.append(chunk['text'])
        self.key = sha({'implementation': 'dense-lab-2026-10-13-v1', 'model': SPEC,
                        'files': encoder.manifest['files'], 'collection': self.lexical.digest,
                        'text_mode': text_mode, 'windows': windows, 'window_tokens': 192,
                        'overlap_tokens': 32, 'mapping': self.mapping})
        folder = encoder.cache/'dense-indexes'/self.key
        folder.mkdir(parents=True, exist_ok=True)
        meta_path, matrix_path = folder/'manifest.json', folder/'vectors.npy'
        hit = meta_path.exists() and matrix_path.exists()
        if hit:
            saved = json.loads(meta_path.read_text(encoding='utf-8'))
            if saved['key'] != self.key or saved['mapping'] != self.mapping or saved['vector_sha256'] != digest(matrix_path):
                raise ValueError('Dense cache provenance/integrity mismatch')
            self.vectors = np.load(matrix_path, allow_pickle=False)
            self.index_usage = saved['index_usage']
        else:
            self.vectors, self.index_usage = encoder.encode(representations)
            temporary = matrix_path.with_suffix('.npy.tmp')
            with temporary.open('wb') as stream: np.save(stream, self.vectors, allow_pickle=False)
            temporary.replace(matrix_path)
            write_json(meta_path, {'key': self.key, 'mapping': self.mapping,
                                  'vector_sha256': digest(matrix_path), 'index_usage': self.index_usage})
        if self.vectors.shape != (len(self.mapping), 384) or self.vectors.dtype != np.float32:
            raise ValueError('Cached vector shape/type mismatch')
        if not np.isfinite(self.vectors).all(): raise ValueError('Cached vectors are non-finite')
        lengths = np.linalg.norm(self.vectors, axis=1)
        if not np.allclose(lengths, 1, atol=1e-4): raise ValueError('Cached vectors are not normalized')
        self.build_receipt = {'schema_version': 1, 'model': SPEC, 'collection_sha256': self.lexical.digest,
                              'index_key': self.key, 'text_mode': text_mode, 'windows': windows,
                              'vector_sha256': digest(matrix_path), 'index_manifest_sha256': digest(meta_path),
                              'index_cache_hit': hit, 'build_or_cache_load_seconds': time.perf_counter()-started,
                              'index_usage': self.index_usage, 'vectors': len(self.mapping),
                              'vector_storage_bytes': self.vectors.nbytes, 'mapping': self.mapping}

    def rank_with_receipt(self, query, method='dense'):
        import numpy as np
        if method not in ('dense', 'dense_rrf'): raise ValueError('Expected dense or dense_rrf')
        if not isinstance(query, str) or not query.strip(): raise ValueError('Expected nonempty query')
        started = time.perf_counter()
        query_vector, usage = self.encoder.encode([query])
        values = self.vectors @ query_vector[0]
        scores = {i: -1.0 for i in self.ids}
        for row, value in zip(self.mapping, values): scores[row['id']] = max(scores[row['id']], float(value))
        dense_order = sorted_ids(self.ids, scores)
        if method == 'dense_rrf':
            lexical = self.lexical.body if self.text_mode == 'body' else self.lexical.search
            lexical_order = sorted_ids(self.ids, lexical.bm25(tokens(query)))
            order = sorted_ids(self.ids, fuse(self.ids, [dense_order, lexical_order]))
        else: order = dense_order
        receipt = {'schema_version': 1, 'method': method, 'index_key': self.key,
                   'collection_sha256': self.lexical.digest, 'query_sha256': sha(query),
                   'ranked_ids': order, 'ranking_sha256': sha(order), 'dense_scores': scores,
                   'query_encode_usage': usage, 'query_and_search_seconds': time.perf_counter()-started,
                   'document_vectors_computed_at_query': 0, 'gold_inputs_used': False,
                   'returned_context_created': False}
        return order, receipt

    def rank(self, query, method='dense'):
        return self.rank_with_receipt(query, method)[0]


def smoke(cache):
    import numpy as np
    encoder = Encoder(cache)
    vectors, encoding_usage = encoder.encode([
        'The archive retention period is twelve days.', 'The retention rule keeps records for twelve days.',
        'The recipe uses apples and cinnamon.', 'archive ' * 600,
    ])
    if float(vectors[0]@vectors[1]) <= float(vectors[0]@vectors[2]):
        raise AssertionError('Basic semantic positive/negative check failed')
    if encoding_usage['truncated_texts'] != 1: raise AssertionError('Truncation receipt failed')
    docs = {'D1': {'body': 'The archive retention period is twelve days.'},
            'D2': {'body': 'The recipe uses apples and cinnamon.'},
            'D3': {'body': 'noise ' * 300 + 'The archive retention period is twelve days.'}}
    indexes = []
    for windows in (False, True):
        index = DensePreparedIndex(docs, encoder, windows=windows)
        order, query_usage = index.rank_with_receipt('How long are archive records retained?')
        assert order[0] in ('D1', 'D3') and set(order) == set(docs)
        second = DensePreparedIndex(docs, encoder, windows=windows)
        assert second.build_receipt['index_cache_hit']
        assert np.array_equal(index.vectors, second.vectors)
        assert second.rank('How long are archive records retained?') == order
        if windows: assert index.index_usage['truncated_texts'] == 0 and len(index.mapping) > len(docs)
        indexes.append({'build': index.build_receipt, 'query': query_usage,
                        'cache_reload': second.build_receipt, 'dense_rrf_order': index.rank('archive retention', 'dense_rrf')})
    return {'state': 'passed', 'model_manifest': encoder.manifest,
            'encoding_usage': encoding_usage, 'semantic_smoke_cosines': [float(vectors[0]@v) for v in vectors[:3]],
            'indexes': indexes, 'scope': 'Fictional smoke checks, not benchmark accuracy or latency claims'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    if not args.smoke: parser.error('Use --smoke; reusable classes are the study interface')
    result = smoke(args.cache)
    if args.receipt: write_json(args.receipt, result)
    else: print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
