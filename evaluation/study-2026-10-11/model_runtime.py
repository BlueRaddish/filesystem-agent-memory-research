"""Pinned local ONNX relevance scorers; model files remain outside the repository.

Requires already installed numpy, onnxruntime and tokenizers. No remote Python
code, deserialized Python objects or authenticated model service is used.
"""
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import tempfile
import time
import urllib.request

HERE = Path(__file__).resolve().parent
MODELS = {
    'minilm': {
        'repo':'cross-encoder/ms-marco-MiniLM-L6-v2',
        'revision':'233902d25c440f23af6f7d6e94d2946bac0bee0a',
        'weight':'onnx/model_quint8_avx2.onnx',
        'bytes':23200716,
        'sha256':'c80a8b34256ea453093d612e3ac48d3d965a0c0a48c7906709af8b8e28461bf9',
    },
    'mixedbread': {
        'repo':'mixedbread-ai/mxbai-rerank-xsmall-v1',
        'revision':'b5c6e9da73abc3711f593f705371cdbe9e0fe422',
        'weight':'onnx/model_quantized.onnx',
        'bytes':87245802,
        'sha256':'15ef19a6de90be7d52b627f2c784107bd806e64826450f41fb75fa4f0179ab30',
    },
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def acquire(cache, name):
    spec = MODELS[name]
    target = Path(cache).resolve()/name
    if target.is_relative_to(HERE.parents[1]):
        raise ValueError('Model cache must be outside the public repository')
    target.mkdir(parents=True,exist_ok=True)
    files = ('config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json',spec['weight'])
    manifest = {'name':name,'spec':spec,'files':{}}
    for rel in files:
        destination = target/rel
        destination.parent.mkdir(parents=True,exist_ok=True)
        if not destination.exists():
            url = f"https://huggingface.co/{spec['repo']}/resolve/{spec['revision']}/{rel}"
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=destination.parent,delete=False) as stream:
                    temporary = Path(stream.name)
                    with urllib.request.urlopen(url,timeout=60) as response:
                        while chunk := response.read(1024*1024):
                            stream.write(chunk)
                if rel==spec['weight']:
                    assert temporary.stat().st_size==spec['bytes'] and digest(temporary)==spec['sha256'], 'Publisher weight digest mismatch'
                temporary.replace(destination)
            finally:
                if temporary is not None and temporary.exists():
                    temporary.unlink()
        if rel==spec['weight']:
            assert destination.stat().st_size==spec['bytes'] and digest(destination)==spec['sha256']
        manifest['files'][rel]={'sha256':digest(destination),'bytes':destination.stat().st_size}
    config = json.loads((target/'config.json').read_text(encoding='utf8'))
    assert not config.get('auto_map'), 'Unexpected custom-code configuration'
    return target,manifest


class Scorer:
    def __init__(self, cache, name, threads=2, batch_size=12):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        if name not in MODELS or not 1<=threads<=4 or not 1<=batch_size<=64:
            raise ValueError('Invalid model or bounded CPU configuration')
        started = time.perf_counter()
        path,self.manifest = acquire(cache,name)
        acquired = time.perf_counter()
        self.tokenizer = Tokenizer.from_file(str(path/'tokenizer.json'))
        config = json.loads((path/'config.json').read_text(encoding='utf8'))
        self.tokenizer.enable_truncation(max_length=512,strategy='longest_first')
        pad_id = config.get('pad_token_id',0)
        self.tokenizer.enable_padding(pad_id=pad_id,pad_token=self.tokenizer.id_to_token(pad_id))
        options = ort.SessionOptions()
        options.intra_op_num_threads=threads
        options.inter_op_num_threads=1
        options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(str(path/MODELS[name]['weight']),sess_options=options,providers=['CPUExecutionProvider'])
        self.inputs = {x.name:x.type for x in self.session.get_inputs()}
        assert set(self.inputs).issubset({'input_ids','attention_mask','token_type_ids'})
        assert all(v=='tensor(int64)' for v in self.inputs.values())
        assert len(self.session.get_outputs())==1
        self.batch_size=batch_size
        self.manifest.update(acquire_or_checksum_seconds=acquired-started,
            load_seconds=time.perf_counter()-acquired,threads=threads,batch_size=batch_size,
            providers=self.session.get_providers(),inputs=self.inputs,
            packages={p:importlib.metadata.version(p) for p in ('numpy','onnxruntime','tokenizers')})

    def score(self,query,texts):
        import numpy as np
        if not isinstance(query,str) or not query or any(not isinstance(t,str) for t in texts):
            raise ValueError('Expected query and text strings')
        started = time.perf_counter()
        scores=[]
        tokens=truncated=0
        for offset in range(0,len(texts),self.batch_size):
            encodings = self.tokenizer.encode_batch([(query,t) for t in texts[offset:offset+self.batch_size]])
            tokens += sum(sum(e.attention_mask) for e in encodings)
            truncated += sum(bool(e.overflowing) for e in encodings)
            arrays = {'input_ids':[e.ids for e in encodings],
                      'attention_mask':[e.attention_mask for e in encodings],
                      'token_type_ids':[e.type_ids for e in encodings]}
            feed = {name:np.asarray(arrays[name],dtype=np.int64) for name in self.inputs}
            output = self.session.run(None,feed)[0]
            assert output.shape in ((len(encodings),1),(len(encodings),)), output.shape
            scores.extend(float(v) for v in output.reshape(-1))
        assert len(scores)==len(texts) and all(math.isfinite(v) for v in scores)
        return scores,{'seconds':time.perf_counter()-started,'pairs':len(texts),
                       'input_pair_tokens':tokens,'truncated_pairs':truncated}


def smoke(cache):
    receipts=[]
    for name in MODELS:
        scorer=Scorer(cache,name)
        scores,usage=scorer.score('Which record specifies the final blue archive retention period?',[
            'The blue archive final approved retention period is eight days.',
            'The recipe calls for green apples and one cup of cinnamon.',
            '青灯 archive: the final approved retention period is eight days.'])
        assert scores[0]>scores[1], 'Basic positive/negative ranking failed'
        assert usage['truncated_pairs']==0
        # Rankings over Unicode are observed, not assumed equivalent to English.
        receipts.append({'model':scorer.manifest,'smoke_scores':scores,'smoke_usage':usage})
    return receipts


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    if not args.smoke: parser.error('Use --smoke to acquire and test both pinned scorers')
    print(json.dumps(smoke(args.cache),indent=2,allow_nan=False))
