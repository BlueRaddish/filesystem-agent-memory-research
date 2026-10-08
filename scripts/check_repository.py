"""Check public catalog/link consistency and the fictional fixture, using stdlib."""

import argparse
from collections import Counter
from datetime import date
import importlib.util
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CATALOGS = (
    "agent-memory.json",
    "retrieval-context.json",
    "organization-retention.json",
    "recent-evidence.json",
)
REQUIRED = (
    "id", "title", "year", "url", "kind", "venue_or_status", "topics",
    "evidence_note", "limitation", "review_level", "accessed",
)
CITATION = re.compile(r"\[((?:AM|RC|OR|RE)\d{2})\]\((https://[^\s)]+)\)")
LINK = re.compile(r"\[[^\]\n]*\]\(([^\s)]+)\)")
# These catch common leak shapes only; narrative and history review is still required.
LEAK_PATTERNS = (
    re.compile(r"[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]", re.I),
    re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+/"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def https_url(value):
    parts = urlsplit(value)
    return parts.scheme == "https" and bool(parts.netloc) and not parts.username and not parts.password


def records():
    result = []
    for name in CATALOGS:
        rows = json.loads((ROOT / "sources" / name).read_text(encoding="utf-8"))
        require(isinstance(rows, list) and rows, f"Empty or invalid catalog: {name}")
        for row in rows:
            require(isinstance(row, dict) and all(field in row for field in REQUIRED),
                    f"Missing record fields in {name}")
            require(re.fullmatch(r"(?:AM|RC|OR|RE)\d{2}", row["id"]) is not None,
                    f"Invalid ID in {name}")
            require(all(isinstance(row[field], str) and row[field].strip()
                        for field in REQUIRED if field not in {"year", "topics"}),
                    f"Empty or non-string metadata: {row['id']}")
            require(type(row["year"]) is int and 1900 <= row["year"] <= 2026,
                    f"Invalid year: {row['id']}")
            require(https_url(row["url"]), f"Invalid primary URL: {row['id']}")
            require(isinstance(row["topics"], list) and row["topics"]
                    and all(isinstance(topic, str) and topic for topic in row["topics"]),
                    f"Invalid topics: {row['id']}")
            require(date.fromisoformat(row["accessed"]) <= date(2026, 10, 8),
                    f"Access date after this review cutoff: {row['id']}")
        result.extend(rows)
    require(len({row["id"] for row in result}) == len(result), "Duplicate source IDs")
    require(len({row["url"] for row in result}) == len(result), "Duplicate primary URLs")
    return result


def bibliography(rows):
    lines = [
        "# Annotated bibliography", "",
        "Generated from the four JSON catalogs by `python scripts/check_repository.py --write-bibliography`.", "",
        f"**{len(rows)} cataloged primary works/pages; cutoff 2026-10-08 UTC.** URL aliases are not extra studies. "
        "An interface document, creator account, or preservation standard is not an empirical agent result.", "",
        "Review depth and status belong to each record. Full-text review means selected relevant sections, "
        "not reproduction. See [methodology](../research/methodology.md).", "",
        "[Earlier public link ledger](earlier-links.json) retains prior URLs, aliases, and access-blocked records.", "",
    ]
    for name in CATALOGS:
        group = json.loads((ROOT / "sources" / name).read_text(encoding="utf-8"))
        lines += [f"## {name.removesuffix('.json').replace('-', ' ').title()}", ""]
        for row in group:
            lines += [
                f"### {row['id']} — {row['title']}", "",
                f"[{row['year']} · Primary source]({row['url']}) — {row['venue_or_status']}", "",
                f"**Kind:** {row['kind']}. **Reviewed:** {row['review_level']}. **Accessed:** {row['accessed']}.", "",
                f"**Evidence:** {row['evidence_note']}", "",
                f"**Limit:** {row['limitation']}", "",
            ]
    return "\n".join(lines)


def check_documents(rows):
    catalog = {row["id"]: row for row in rows}
    cited = set()
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        require(not path.is_symlink(), f"Symlink in public tree: {path.relative_to(ROOT)}")
        require(path.suffix in {".md", ".json", ".py", ""}
                or path.name in {".gitignore", ".gitattributes"},
                f"Unexpected public file type: {path.relative_to(ROOT)}")
        text = path.read_text(encoding="utf-8")
        require(not any(pattern.search(text) for pattern in LEAK_PATTERNS),
                f"Potential sensitive pattern: {path.relative_to(ROOT)}")
        if path.suffix != ".md":
            continue
        for identifier, url in CITATION.findall(text):
            require(identifier in catalog and catalog[identifier]["url"] == url,
                    f"Citation/catalog mismatch: {path.relative_to(ROOT)} {identifier}")
            cited.add(identifier)
        for raw in LINK.findall(text):
            if urlsplit(raw).scheme or raw.startswith("#"):
                continue
            target = (path.parent / unquote(raw.split("#", 1)[0])).resolve()
            require(target.is_relative_to(ROOT) and target.exists(),
                    f"Missing or escaping local link: {path.relative_to(ROOT)} -> {raw}")
    require(cited == set(catalog), f"Sources without an ID citation: {sorted(set(catalog) - cited)}")
    ledger = json.loads((ROOT / "sources" / "earlier-links.json").read_text(encoding="utf-8"))
    require(isinstance(ledger, list) and len(ledger) == 47, "Earlier link ledger must retain 47 URLs")
    require(len({row["url"] for row in ledger}) == len(ledger), "Duplicate earlier link")
    for row in ledger:
        require(https_url(row["url"]) and row["source_id"] in catalog, "Invalid ledger source mapping")
        require(row["access_status"] in {"primary_record_verified", "access_blocked"},
                "Ledger must state verification/access status")


def check_fixture():
    spec = importlib.util.spec_from_file_location("fixture_builder", ROOT / "scripts" / "make_fixture.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    source_files = {path.relative_to(builder.FIXTURE).as_posix()
                    for path in builder.FIXTURE.rglob("*") if path.is_file()}
    require(source_files == set(builder.AGENT_FILES), "Fixture subtree differs from agent-file allowlist")
    gold = json.loads((ROOT / "evaluation" / "fixture-gold.json").read_text(encoding="utf-8"))
    require(len({task["id"] for task in gold["tasks"]}) == 3, "Fixture must define three tasks")
    joined = "\n".join(path.read_text(encoding="utf-8") for path in builder.FIXTURE.rglob("*.md"))
    for task in gold["tasks"]:
        sets = task["minimal_sufficient_evidence_sets"]
        require(sets and all(evidence_set for evidence_set in sets), "Missing sufficient evidence sets")
        evidence = set(task["supporting_context"]).union(*map(set, sets))
        for identifier in evidence:
            require(identifier in joined, f"Gold evidence missing from fixture: {identifier}")
    expected = gold["tasks"][0]["expected_text"]
    require(expected.splitlines() == ["amber|2", "cobalt|5", "silver|1"] and expected.endswith("\n"),
            "Fixture artifact key changed; review its semantics")
    # This checks staging/isolation boundaries, not model retrieval quality.
    with TemporaryDirectory(prefix="memory-fixture-check-") as temporary:
        target = Path(temporary) / "trial"
        staged = builder.stage(target)
        require(set(staged) == set(builder.AGENT_FILES), "Incorrect staged file set")
        require(not (target / "evaluation").exists(), "Evaluator materials leaked into stage")
        require(all((target / relative).read_bytes() == (builder.FIXTURE / relative).read_bytes()
                    for relative in staged), "Staged bytes differ")
        try:
            builder.stage(target)
        except ValueError:
            pass
        else:
            raise ValueError("Staging must reject a nonempty workspace")
        existing = target / "TASKS.md"
        require(existing.read_bytes() == (builder.FIXTURE / "TASKS.md").read_bytes(),
                "Rejected staging changed existing data")
    try:
        builder.stage(ROOT / "trial-must-not-exist")
    except ValueError:
        pass
    else:
        raise ValueError("Staging must reject a workspace inside the original repository")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-bibliography", action="store_true")
    args = parser.parse_args()
    rows = records()
    generated = bibliography(rows)
    path = ROOT / "sources" / "README.md"
    if args.write_bibliography:
        path.write_text(generated, encoding="utf-8", newline="\n")
    require(path.read_text(encoding="utf-8") == generated, "Bibliography needs regeneration")
    check_documents(rows)
    check_fixture()
    counts = Counter(row["kind"] for row in rows)
    print(f"PASS: {len(rows)} source records, citations, local links, hygiene patterns, and fixture staging.")
    print("Kinds: " + ", ".join(f"{kind}={count}" for kind, count in sorted(counts.items())))
    print("These checks do not reproduce studies, grade models, or prove publication privacy.")
