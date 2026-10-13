"""Validate the public fictional bank, without consulting any retrieval method.

Usage: python bank_check.py [challenge-bank.json] [--self-check]
Structural/provenance checks do not replace the source support audit in BANK.md.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

RECORD_FIELDS = {"id", "kind", "revision", "authored_at", "title", "scope", "body", "links", "supersedes", "incorporates"}
TASK_FIELDS = {"id", "query", "answer_keys", "critical_keys", "answer_contract", "expected", "evidence_sets", "evidence_spans", "gold_rationale"}
TYPES = {"string", "integer", "number", "boolean", "array", "null"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_strings(value, where, nonempty=True):
    require(isinstance(value, list), f"{where}: expected list")
    require(all(isinstance(x, str) and x for x in value), f"{where}: expected nonempty strings")
    require(len(value) == len(set(value)), f"{where}: duplicates")
    require(bool(value) or not nonempty, f"{where}: empty")


def matches(value, typ):
    return {"null": value is None, "boolean": type(value) is bool,
            "integer": type(value) is int, "number": type(value) in (int, float),
            "string": isinstance(value, str), "array": isinstance(value, list)}[typ]


def validate(bank):
    families = bank["families"]
    require(isinstance(families, list) and len(families) >= 72, "need at least 72 families")
    require("LLM" in bank["authored_origin"]["method"], "origin must disclose LLM authorship")
    require("not" in bank["authored_origin"]["limits"], "origin must limit generalization")
    strata = {s["id"] for s in bank["strata"]}
    require(len(strata) >= 12 and len(strata) == len(bank["strata"]), "need at least 12 unique strata")
    require(all(s.get("disjoint_rule") for s in bank["strata"]), "strata need disjoint rule")
    all_ids = set()
    all_records = {}
    templates = {}
    lengths, support_offsets = [], []
    source_count = derived_count = task_count = 0
    declared_missing_ids = set()
    unresolved_modes = Counter()
    field_type_counts = Counter()
    status_counts = Counter()
    role_counts = Counter()
    for family in families:
        fid = family["id"]
        require(re.fullmatch(r"N\d{3}", fid), f"bad family ID: {fid}")
        require(fid not in all_ids, f"duplicate ID: {fid}")
        all_ids.add(fid)
        require(isinstance(family["name"], str) and family["name"], f"{fid}: empty name")
        unique_strings(family["aliases"], f"{fid} aliases")
        require(family["stratum"] in strata, f"{fid}: undeclared stratum")
        require(family["template_family"], f"{fid}: template provenance absent")
        templates.setdefault(family["template_family"], []).append(family)
        require(7 <= len(family["records"]) <= 18, f"{fid}: records outside 7–18")
        require(len(family["tasks"]) == 3, f"{fid}: need three tasks")
        require({t.get("audit_role") for t in family["tasks"]} == {"historical", "current", "followup"}, f"{fid}: missing audit-only roles")
        local = {}
        for record in family["records"]:
            rid = record["id"]
            require(RECORD_FIELDS <= record.keys(), f"{rid}: missing record fields")
            require(rid not in all_ids and rid.startswith(fid + "-R"), f"{rid}: duplicate or alien ID")
            all_ids.add(rid)
            local[rid] = record
            all_records[rid] = record
            require(record["kind"] in {"source", "derived"}, f"{rid}: invalid kind")
            require(type(record["revision"]) is int and record["revision"] > 0, f"{rid}: invalid revision")
            dt = datetime.fromisoformat(record["authored_at"].replace("Z", "+00:00"))
            require(dt.tzinfo is not None, f"{rid}: authored_at needs timezone")
            for key in ("title", "scope", "body"):
                require(isinstance(record[key], str) and record[key], f"{rid}: empty {key}")
            for key in ("links", "supersedes"):
                unique_strings(record[key], f"{rid} {key}", nonempty=False)
            require(isinstance(record["incorporates"], list), f"{rid}: incorporates not list")
            require(not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|[A-Za-z]:[\\/]", record["body"]), f"{rid}: personal-looking email or absolute path")
            for key in ("valid_from", "valid_to"):
                if key in record:
                    date.fromisoformat(record[key])
                    require(record[key] in record["body"], f"{rid}: {key} not literally grounded in prose")
            if "valid_from" in record and "valid_to" in record:
                require(record["valid_from"] <= record["valid_to"], f"{rid}: reversed validity")
            if "path" in record:
                require(not Path(record["path"]).is_absolute() and ":" not in record["path"], f"{rid}: path must be fictional relative category path")
            lengths.append(len(record["body"].split()))
            source_count += record["kind"] == "source"
            derived_count += record["kind"] == "derived"
        for record in family["records"]:
            rid = record["id"]
            missing = record.get("declared_missing_links", [])
            require(isinstance(missing, list), f"{rid}: missing-link markers not list")
            missing_ids = set()
            for marker in missing:
                require(set(marker) == {"id", "reason"} and isinstance(marker["reason"], str) and marker["reason"], f"{rid}: malformed missing-link declaration")
                ref = marker["id"]
                require(ref not in local and ref in record["links"] and re.fullmatch(fid + r"-X\d{3}", ref), f"{rid}: missing declaration must name an absent linked ID")
                require(ref not in declared_missing_ids, f"{rid}: duplicate missing declaration")
                missing_ids.add(ref)
                declared_missing_ids.add(ref)
            for ref in record["links"] + record["supersedes"]:
                require(ref in local or (ref in record["links"] and ref in missing_ids), f"{rid}: unmarked missing corpus ID {ref}")
            for ref in record["supersedes"]:
                require(record["kind"] == local[ref]["kind"] == "source", f"{rid}: supersession must name original authority")
            for inc in record["incorporates"]:
                require(set(inc) == {"id", "revision"} and inc["id"] in local, f"{rid}: malformed incorporation")
                require(type(inc["revision"]) is int and inc["revision"] == local[inc["id"]]["revision"], f"{rid}: incorporation revision absent")
            require(record["kind"] != "derived" or record["incorporates"], f"{rid}: derived record lacks provenance")
        for task in family["tasks"]:
            tid = task["id"]
            require(TASK_FIELDS <= task.keys(), f"{tid}: missing task fields")
            require(tid not in all_ids and tid.startswith(fid + "-T"), f"{tid}: duplicate or alien ID")
            all_ids.add(tid)
            task_count += 1
            require(isinstance(task["query"], str) and task["query"], f"{tid}: empty query")
            unique_strings(task["answer_keys"], f"{tid} answer_keys")
            unique_strings(task["critical_keys"], f"{tid} critical_keys")
            require(set(task["critical_keys"]) <= set(task["answer_keys"]), f"{tid}: unknown critical key")
            expected = task["expected"]
            require(set(expected) == {"status", "answer"} and expected["status"] in {"ready", "hold"}, f"{tid}: bad expected status")
            require(set(expected["answer"]) == set(task["answer_keys"]), f"{tid}: answer-key mismatch")
            status_counts[expected["status"]] += 1
            role_counts[(task["audit_role"], expected["status"])] += 1
            contract = task["answer_contract"]
            fields = contract["fields"]
            require(set(fields) == set(task["answer_keys"]), f"{tid}: contract-key mismatch")
            policy = contract["unresolved_policy"]
            require(policy.get("allow_null_when_status_hold") is True and policy.get("reason_required") is True and policy.get("null_meaning"), f"{tid}: honest partial-evidence hold contract absent")
            for key, spec in fields.items():
                declared = spec["type"] if isinstance(spec["type"], list) else [spec["type"]]
                require(set(declared) <= TYPES and declared, f"{tid}.{key}: bad type")
                value = expected["answer"][key]
                require(any(matches(value, typ) for typ in declared), f"{tid}.{key}: expected violates contract")
                require(isinstance(spec["description"], str) and spec["description"], f"{tid}.{key}: field description absent")
                field_type_counts.update(declared)
                if "null" in declared:
                    require(spec.get("null_meaning"), f"{tid}.{key}: null needs meaning")
                if "array" in declared:
                    require(spec.get("items") == {"type": "string"}, f"{tid}.{key}: bad item contract")
                    require(spec.get("comparison") in {"ordered_exact", "unordered_unique"}, f"{tid}.{key}: missing list ordering")
                    if value is not None:
                        require(all(isinstance(item, str) for item in value), f"{tid}.{key}: bad item type")
                        if spec["comparison"] == "unordered_unique":
                            require(len(value) == len(set(value)), f"{tid}.{key}: set answer duplicates")
                if "enum" in spec:
                    require(value is None or value in spec["enum"], f"{tid}.{key}: value outside enum")
            if expected["status"] == "hold":
                require(any(x is None for x in expected["answer"].values()), f"{tid}: hold has no unresolved field")
                require(isinstance(expected["answer"].get("hold_reason"), str) and expected["answer"]["hold_reason"], f"{tid}: hold reason absent")
                unresolved_modes[expected["answer"]["hold_reason"]] += 1
            else:
                require(all(value is not None or key == "hold_reason" for key, value in expected["answer"].items()), f"{tid}: ready factual field is unresolved")
                if "hold_reason" in expected["answer"]:
                    require(expected["answer"]["hold_reason"] is None, f"{tid}: ready should have null reason")
            require(isinstance(task["gold_rationale"], str) and len(task["gold_rationale"]) >= 80, f"{tid}: support rationale absent")
            evidence = task["evidence_sets"]
            require(evidence and len(evidence) == len(task["evidence_spans"]), f"{tid}: missing or unaligned alternatives")
            require(len({tuple(sorted(group)) for group in evidence}) == len(evidence), f"{tid}: duplicate evidence alternatives")
            for group, spans in zip(evidence, task["evidence_spans"]):
                unique_strings(group, f"{tid} evidence alternative")
                require(all(rid in local and local[rid]["kind"] == "source" for rid in group), f"{tid}: evidence must be local originals")
                require(isinstance(spans, list) and spans, f"{tid}: empty spans")
                require({s["id"] for s in spans} == set(group), f"{tid}: spans do not cover alternative")
                for span in spans:
                    require(set(span) == {"id", "start", "end"}, f"{tid}: malformed span")
                    require(type(span["start"]) is type(span["end"]) is int, f"{tid}: offsets must be integers")
                    body = local[span["id"]]["body"]
                    require(0 <= span["start"] < span["end"] <= len(body), f"{tid}: out-of-range span")
                    require(body[span["start"]:span["end"]].strip(), f"{tid}: empty support text")
                    require(span["id"] in task["gold_rationale"], f"{tid}: rationale omits support ID")
                    support_offsets.append(span["start"])
    declared_templates = {s["template_family"] for s in bank["strata"]}
    require(not declared_missing_ids.intersection(all_records), "declared missing ID is actually present")
    require(set(unresolved_modes) == {"required_source_missing", "scope_not_established", "conflicting_authority"}, "need distinct evidence insufficiency modes")
    require(declared_templates == set(templates), "template/stratum declaration mismatch")
    recipe = bank["split_recipe"]
    order = sorted(templates, key=lambda t: hashlib.sha256((t + ":" + recipe["salt"]).encode()).hexdigest())
    require(recipe["unit"] == "whole template_family group", "split must hold out whole templates")
    require(recipe["development_template_families"] == order[:4] and recipe["confirmation_template_families"] == order[4:], "split hash mismatch")
    for template, members in templates.items():
        wanted = "development" if template in order[:4] else "confirmation"
        require(len(members) == 6 and all(f["split"] == wanted for f in members), f"{template}: variants leak across split")
    split_counts = Counter(f["split"] for f in families)
    require(split_counts == {"development": 24, "confirmation": 72}, "wrong split sizes")
    return {"families": len(families), "templates": len(templates), "strata": len(strata), "records": len(all_records),
            "source_records": source_count, "derived_records": derived_count, "tasks": task_count,
            "record_count_distribution": dict(Counter(len(f["records"]) for f in families)),
            "declared_missing_edges": len(declared_missing_ids), "unresolved_reason_distribution": dict(unresolved_modes),
            "expected_status_distribution": dict(status_counts),
            "audit_role_status_distribution": {f"{role}:{status}": count for (role, status), count in role_counts.items()},
            "split_families": dict(split_counts), "field_type_occurrences": dict(field_type_counts),
            "body_words_min": min(lengths), "body_words_max": max(lengths), "body_words_over_500": sum(x > 500 for x in lengths),
            "operative_spans_at_nonzero_offset": sum(x > 0 for x in support_offsets),
            "structural_and_original_provenance_checks": "passed",
            "semantic_support_limit": "Typed/offset/reference validation is not semantic proof; BANK.md records a separate source audit."}


def self_check(bank):
    """Four deliberate corruptions show checks can fail for relevant mistakes."""
    def derived_only(b):
        family = b["families"][0]
        derived = next(r for r in family["records"] if r["kind"] == "derived")
        task = family["tasks"][0]
        task["evidence_sets"] = [[derived["id"]]]
        task["evidence_spans"] = [[{"id": derived["id"], "start": 0, "end": len(derived["body"])}]]
    def unmarked_missing(b):
        record = next(r for f in b["families"] for r in f["records"] if r.get("declared_missing_links"))
        record.pop("declared_missing_links")
    mutations = [
        lambda b: b["families"][0]["tasks"][0]["expected"]["answer"].update({b["families"][0]["tasks"][0]["answer_keys"][0]: {}}),
        lambda b: b["families"][0]["tasks"][0]["evidence_spans"][0][0].update(end=10**9),
        derived_only,
        unmarked_missing,
    ]
    for mutate in mutations:
        broken = copy.deepcopy(bank)
        mutate(broken)
        try:
            validate(broken)
        except ValueError:
            pass
        else:
            raise AssertionError("checker accepted a deliberate corruption")
    return "four negative checks passed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bank", type=Path, nargs="?", default=Path(__file__).with_name("challenge-bank.json"))
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    raw = args.bank.read_bytes()
    bank = json.loads(raw)
    report = validate(bank)
    report["sha256"] = hashlib.sha256(raw).hexdigest()
    if args.self_check:
        report["checker_self_check"] = self_check(bank)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
