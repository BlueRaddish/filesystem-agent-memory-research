"""Run disposable checks for the shared compressed-JSONL publication reader."""

import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import check_repository as gate


def main():
    passed = []
    with TemporaryDirectory(prefix="compressed-jsonl-fixture-") as directory:
        root = Path(directory)
        sequence = 0

        def write(payload, suffix=".jsonl.gz"):
            nonlocal sequence
            sequence += 1
            path = root / f"fixture-{sequence}{suffix}"
            path.write_bytes(gzip.compress(payload, mtime=0))
            return path

        def reject(name, path, errors=(ValueError,), **limits):
            try:
                list(gate.compressed_jsonl_lines(path, **limits))
            except errors:
                passed.append(name)
            else:
                raise AssertionError(f"Failed to reject {name}")

        records = [{"id": 1, "text": "caf\u00e9", "nested": [True, None, {"value": 1.25}]}, [1, 2]]
        lines = [json.dumps(row, ensure_ascii=False) + "\n" for row in records]
        payload = ("\n" + lines[0] + " \t\n" + lines[1]).encode("utf-8")
        path = write(payload)
        assert list(gate.compressed_jsonl_lines(path)) == list(zip(lines, records))
        assert list(gate.compressed_jsonl_lines(
            path, max_line_bytes=max(len(line.encode("utf-8")) for line in lines),
            max_total_bytes=len(payload))) == list(zip(lines, records))
        passed.extend(["valid Unicode nested roundtrip", "inclusive exact byte limits"])

        corrupt = root / "corrupt.jsonl.gz"
        raw = bytearray(gzip.compress(b'{"valid":true}\n', mtime=0))
        raw[-8] ^= 1
        corrupt.write_bytes(raw)
        reject("corrupt gzip checksum", corrupt, errors=(OSError, EOFError))
        truncated = root / "truncated.jsonl.gz"
        truncated.write_bytes(bytes(raw[:-9]))
        reject("truncated gzip trailer", truncated, errors=(OSError, EOFError))
        invalid_header = root / "header.jsonl.gz"
        invalid_header.write_bytes(b"not a gzip stream")
        reject("invalid gzip header", invalid_header, errors=(OSError, EOFError))
        reject("invalid JSON", write(b'{"value":}\n'))
        reject("invalid UTF-8", write(b'{"value":"\xff"}\n'), errors=(UnicodeError,))
        reject("duplicate object keys", write(b'{"key":1,"key":2}\n'))
        reject("nested duplicate object keys", write(b'{"outer":{"key":1,"key":2}}\n'))
        for token in ("NaN", "Infinity", "-Infinity", "1e999"):
            reject(f"nonfinite {token}", write(f'{{"number":{token}}}\n'.encode("ascii")))

        # Construct an entirely fictional path so the fixture source stays clean.
        fictional_path = chr(92).join(("Q:", "Users", "fictional-person", "fixture.txt"))
        escaped = json.dumps({"nested": [{"value": fictional_path}]}).encode("utf-8") + b"\n"
        assert not any(pattern.search(escaped.decode("utf-8")) for pattern in gate.LEAK_PATTERNS)
        reject("escaped nested private-path shape", write(escaped))
        reject("escaped private-path shape as object key",
               write((json.dumps({fictional_path: 1}) + "\n").encode("utf-8")))
        reject("overlong line", write(b'{"text":"abcdef"}\n'), max_line_bytes=8)
        reject("decoded total byte limit", write(b"1\n2\n3\n"), max_total_bytes=5)
        reject("blank lines count toward decoded total", write(b"\n" * 9), max_total_bytes=8)
        reject("wrong compressed extension", write(b"1\n", suffix=".gz"))
        reject("nonpositive line bound", path, max_line_bytes=0)
        reject("boolean total bound", path, max_total_bytes=True)

        # Exercise the real check_documents branch on a small isolated public tree.
        fixture_root = root / "public-tree"
        (fixture_root / "sources").mkdir(parents=True)
        (fixture_root / "README.md").write_text(
            "[AM01](https://example.org/source)\n", encoding="utf-8")
        ledger = [{"url": f"https://example.org/ledger/{i}", "source_id": "AM01",
                   "access_status": "primary_record_verified"} for i in range(47)]
        (fixture_root / "sources" / "earlier-links.json").write_text(
            json.dumps(ledger), encoding="utf-8")
        public_payload = fixture_root / "rows.jsonl.gz"
        public_payload.write_bytes(gzip.compress(b'{"ok":true}\n', mtime=0))
        previous_root = gate.ROOT
        try:
            gate.ROOT = fixture_root
            catalog = [{"id": "AM01", "url": "https://example.org/source"}]
            gate.check_documents(catalog)
            passed.append("real document gate accepts valid compressed JSONL")
            public_payload.write_bytes(gzip.compress(escaped, mtime=0))
            try:
                gate.check_documents(catalog)
            except ValueError:
                passed.append("real document gate rejects escaped sensitive shape")
            else:
                raise AssertionError("Document gate did not inspect compressed JSON strings")
            public_payload.write_bytes(gzip.compress(b'{"ok":true}\n', mtime=0))
            (fixture_root / "unsupported.gz").write_bytes(gzip.compress(b"1\n", mtime=0))
            try:
                gate.check_documents(catalog)
            except ValueError:
                passed.append("real document gate rejects unsupported gzip extension")
            else:
                raise AssertionError("Document gate accepted a non-JSONL gzip file")
        finally:
            gate.ROOT = previous_root

    result = {"state": "COMPRESSED_JSONL_FIXTURES_PASSED", "passed": len(passed),
              "checks": passed, "scope": "Disposable fixtures; no broad repository scan"}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
