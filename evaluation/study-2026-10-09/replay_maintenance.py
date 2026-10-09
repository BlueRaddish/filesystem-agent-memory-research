"""Replay engineered fictional H4/H6 traces using real staged filesystem operations.

This script evaluates prescribed mechanics, not an LLM reader or maintainer.
Run: python evaluation/study-2026-10-09/replay_maintenance.py --self-check
"""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path, PurePosixPath


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


class Store:
    """A disposable, contained filesystem; no fallback outside its indexed paths."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        assert self.root.is_dir() and not any(self.root.iterdir())
        self.mutations = []
        self.reads = []
        self.last_reads = {}

    def path(self, relative):
        if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
            raise ValueError("path must be a nonempty portable relative path")
        pieces = PurePosixPath(relative)
        if pieces.is_absolute() or any(part in {"", ".", ".."} for part in pieces.parts):
            raise ValueError("path must remain within the trial root")
        target = self.root.joinpath(*pieces.parts)
        resolved = target.resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError("path escapes trial root")
        for parent in (target, *target.parents):
            if parent == self.root.parent:
                break
            if parent.is_symlink():
                raise ValueError("symlinks are not allowed in trial storage")
        return target

    def read_json(self, relative, category="state"):
        path = self.path(relative)
        if not path.is_file():
            self.reads.append({"path": relative, "category": category, "outcome": "missing", "bytes": 0})
            return None
        payload = path.read_bytes()
        receipt = {
            "path": relative, "category": category, "outcome": "read",
            "bytes": len(payload), "sha256": digest(payload),
        }
        self.reads.append(receipt)
        self.last_reads[relative] = receipt
        value = json.loads(payload.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("stored JSON record must be an object")
        return value

    def write(self, relative, text, step, phase, category):
        target = self.path(relative)
        before = digest(target.read_bytes()) if target.is_file() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = text.encode("utf-8")
        target.write_bytes(payload)
        assert target.read_bytes() == payload
        self.mutations.append({
            "step": step, "phase": phase, "category": category, "op": "write",
            "path": relative, "before_sha256": before,
            "after_sha256": digest(payload), "bytes": len(payload),
        })

    def rename(self, relative, new_relative, step, phase, category, overwrite=False):
        source, target = self.path(relative), self.path(new_relative)
        if not source.is_file() or (target.exists() and not overwrite):
            raise ValueError("rename requires an ordinary source and available target")
        payload = source.read_bytes()
        before = digest(target.read_bytes()) if target.is_file() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)
        assert not source.exists() and target.read_bytes() == payload
        self.mutations.append({
            "step": step, "phase": phase, "category": category,
            "op": "atomic_replace" if overwrite else "rename",
            "path": relative, "new_path": new_relative,
            "before_sha256": before, "source_sha256": digest(payload),
            "after_sha256": digest(payload), "bytes": len(payload),
        })

    def apply(self, operations, step, phase, category):
        for operation in operations:
            if operation["op"] == "write":
                self.write(operation["path"], operation["text"], step, phase, category)
            elif operation["op"] == "rename":
                self.rename(operation["path"], operation["new_path"], step, phase, category)
            else:
                raise ValueError("unsupported trace operation: " + operation["op"])

    def stage(self, files):
        for relative, text in files.items():
            self.write(relative, text, 0, "initial", "staging")

    def manifest(self):
        return {
            path.relative_to(self.root).as_posix(): {
                "sha256": digest(path.read_bytes()), "bytes": path.stat().st_size,
            }
            for path in sorted(self.root.rglob("*")) if path.is_file()
        }


def h4_state(store, storage_mode):
    def shared(project):
        index = store.read_json("projects/" + project + "/index.json")
        if index is None:
            return None
        if storage_mode == "stable_id_to_canonical_record":
            mapping = store.read_json("id-map.json")
            relative = (mapping or {}).get(index.get("shared_record_id"))
        elif storage_mode == "project_index_to_full_copy":
            relative = index.get("shared_copy_path")
        else:
            raise ValueError("unknown H4 storage mode")
        return store.read_json(relative) if relative is not None else None

    ash, birch = shared("ash"), shared("birch")
    local = store.read_json("projects/birch/local-exception.json")
    if local is not None:
        assert local["scope"] == "birch archived legacy-tile only"
        assert local["qualifies"] == "R401"
    current = {
        "ash_new": ash.get("separator") if ash else None,
        "birch_new": birch.get("separator") if birch else None,
        "birch_legacy": local.get("separator") if local else None,
        "external_release": None,
    }
    if ash is not None and birch is not None:
        assert ash["external_release"] == birch["external_release"]
        current["external_release"] = ash["external_release"]
    access = {key: current[key] is not None for key in ("ash_new", "birch_new", "birch_legacy")}
    return current, access


def replay_h4(case, condition, store):
    files = {**case["initial_files"], **condition["files"]}
    assert len(files) == len(case["initial_files"]) + len(condition["files"])
    store.stage(files)
    protected = {
        relative: digest(text.encode("utf-8")) for relative, text in files.items()
        if relative.startswith("authority/") or relative.startswith("records/versions/")
    }
    checkpoints = []
    expected = {(point["step"], point["phase"]): point for point in case["checkpoints"]}

    def capture(step, phase, authority):
        current, access = h4_state(store, condition["storage_mode"])
        point = expected.get((step, phase))
        if point is not None:
            assert point["expected_authority"] == authority
            if "expected_access" in point:
                assert access == point["expected_access"][condition["id"]], (step, phase, access)
            if "expected_current_by_condition" in point:
                assert current == point["expected_current_by_condition"][condition["id"]], (step, phase, current)
        stale = [
            key for key in ("ash_new", "birch_new", "birch_legacy")
            if access[key] and current[key] != authority[key]
        ]
        checkpoints.append({
            "step": step, "phase": phase, "authority": authority, "current": current,
            "indexed_separator_rule_access": access,
            "unavailable_scopes": [key for key, available in access.items() if not available],
            "stale_scopes": stale, "file_manifest": store.manifest(),
        })

    capture(0, "initial", expected[(0, "initial")]["expected_authority"])
    repair_count = 0
    for event in case["events"]:
        step = event["step"]
        store.apply(event["common_operations"], step, "event", "source_event")
        store.apply(event["operations_by_condition"][condition["id"]], step, "event", "injected_fault")
        capture(step, "before_repair", event["expected_authority"])
        repairs = event["repair_operations_by_condition"][condition["id"]]
        assert len(repairs) <= case["review_budget"]["max_file_mutations_per_event"]
        store.apply(repairs, step, "repair", "repair")
        repair_count += len(repairs)
        capture(step, "after_repair", event["expected_authority"])
    for relative, original_hash in protected.items():
        assert digest(store.path(relative).read_bytes()) == original_hash
    property_name = (
        "canonical_repair_file_mutations" if condition["id"] == "canonical"
        else "duplicated_repair_file_mutations"
    )
    assert repair_count == case["expected_properties"][property_name]
    final = checkpoints[-1]["current"]
    assert final["ash_new"] == final["birch_new"] == "|"
    assert final["birch_legacy"] == "::" and final["external_release"] is False
    return {
        "id": case["id"], "hypothesis": "H4", "condition_id": condition["id"],
        "passed": True, "kind": "prescribed_storage_repair",
        "access_scope": case["access_scope"],
        "summary": {
            "repair_file_mutations": repair_count,
            "indexed_access_failure_checkpoints": sum(bool(p["unavailable_scopes"]) for p in checkpoints),
            "stale_checkpoints": sum(bool(p["stale_scopes"]) for p in checkpoints),
            "original_versions_retained": True,
            "final_current": final,
        },
        "checkpoints": checkpoints, "mutations": store.mutations, "reads": store.reads, "reviews": [],
    }


def expected_h6_points(condition_id):
    """Independent fixed trace assertions: expose the missing-dependency checkpoint."""

    def state(separator, header, revision, dirty=False, gaps=()):
        return {
            "fields": {"separator": separator, "header": header, "external_release": False},
            "coverage": {"K601": revision, "K602": 2 if not header else 1},
            "dirty": dirty, "known_gaps": list(gaps),
        }

    pipe_old = state("|", True, 2)
    pipe_new = state("|", False, 2)
    colon = state(":", False, 3)
    triggered_gap = state("|", False, 2, True, ("K601",))
    initial_gap = state(",", True, 1, True, ("K601",))
    periodic_header_gap = state("|", True, 2, True, ("K602",))
    periodic_both = state("|", True, 2, True, ("K601", "K602"))
    return {
        "update_triggered": [pipe_old, pipe_old, pipe_old, pipe_new, triggered_gap, triggered_gap, triggered_gap, triggered_gap],
        "handoff_triggered": [initial_gap, initial_gap, initial_gap, pipe_new, triggered_gap, colon, colon, colon],
        "fixed_period": [initial_gap, pipe_old, pipe_old, periodic_header_gap, periodic_both, periodic_both, periodic_both, colon],
    }[condition_id]


def replay_h6(case, condition, store):
    store.stage(case["initial_files"])
    governing_ids = case["review_source_ids"]
    assert len(governing_ids) == len(set(governing_ids))
    cap = case["review_budget"]["max_source_records_per_review"]
    budget = case["review_budget"]["max_review_attempts"]
    scheduled = condition["review_at_steps"]
    assert len(scheduled) == len(set(scheduled)) == budget
    version_index_path = "source-version-index.json"
    source_versions = {}
    for source_id in governing_ids:
        source = store.read_json(case["source_paths"][source_id], category="ingest")
        assert source is not None and source["id"] == source_id
        source_versions[source_id] = source["revision"]
    store.write(version_index_path, encode({"versions": source_versions}), 0, "initial", "version_tracking")
    original_hashes = {
        relative: digest(text.encode("utf-8"))
        for relative, text in case["initial_files"].items()
        if relative.startswith("sources/versions/")
    }
    checkpoints, reviews = [], []
    attempts = inspections = 0
    expected_points = expected_h6_points(condition["id"])

    def versions():
        metadata = store.read_json(version_index_path, category="source_version_metadata")
        assert metadata is not None and set(metadata["versions"]) == set(governing_ids)
        return metadata["versions"]

    def mark_dirty(step, source_id=None, audit=False):
        view = store.read_json(case["view_path"])
        available = versions()
        gaps = set(view["known_gaps"])
        if audit:
            gaps.update(source_id for source_id, rev in available.items() if view["coverage"].get(source_id) != rev)
        elif source_id in available and view["coverage"].get(source_id) != available[source_id]:
            gaps.add(source_id)
        changed = bool(gaps) or view["dirty"]
        view["known_gaps"] = sorted(gaps)
        view["dirty"] = changed
        store.write(case["view_path"], encode(view), step, "audit" if audit else "notification", "coverage_warning")

    for event in case["events"]:
        step = event["step"]
        store.apply(event["operations"], step, "event", "source_event")
        metadata_changed = False
        for operation in event["operations"]:
            if operation["op"] != "write":
                continue
            for source_id, source_path in case["source_paths"].items():
                if operation["path"] == source_path:
                    committed = json.loads(operation["text"])
                    assert committed["id"] == source_id
                    source_versions[source_id] = committed["revision"]
                    metadata_changed = True
        if metadata_changed:
            store.write(version_index_path, encode({"versions": source_versions}), step, "event", "version_tracking")
        dependency_map = store.read_json("dependency-map.json")
        source_id = event.get("source_id")
        if source_id in dependency_map["current"]:
            mark_dirty(step, source_id=source_id)
        if event.get("audit_coverage"):
            mark_dirty(step, audit=True)
        inspected = []
        if step in scheduled:
            attempts += 1
            assert attempts <= budget
            assert len(governing_ids) <= cap
            prior = store.read_json(case["view_path"])
            prior_bytes = store.path(case["view_path"]).read_bytes()
            fields, coverage = {}, {}
            for inspected_id in governing_ids:
                relative = case["source_paths"][inspected_id]
                source = store.read_json(relative, category="review_source")
                assert source is not None
                overlap = set(fields).intersection(source["fields"])
                assert not overlap, "this prescribed trace has independent field owners"
                fields.update(source["fields"])
                coverage[inspected_id] = source["revision"]
                inspected.append({
                    "id": inspected_id, "revision": source["revision"],
                    "sha256": store.last_reads[relative]["sha256"],
                })
            inspections += len(inspected)
            gaps = sorted(set(governing_ids).difference(coverage))
            candidate = {"fields": fields, "coverage": coverage, "dirty": bool(gaps), "known_gaps": gaps}
            store.write("current.candidate.json", encode(candidate), step, "review", "candidate_write")
            interrupted = bool(event.get("interrupt_scheduled_review"))
            if interrupted:
                assert store.path(case["view_path"]).read_bytes() == prior_bytes
                assert store.read_json(case["view_path"]) == prior
                outcome = "interrupted"
            else:
                store.rename("current.candidate.json", case["view_path"], step, "review", "atomic_commit", overwrite=True)
                assert store.read_json(case["view_path"]) == candidate
                outcome = "committed"
            reviews.append({
                "step": step, "attempt": attempts, "outcome": outcome,
                "inspected": inspected,
                "coverage_before": prior["coverage"], "coverage_after": store.read_json(case["view_path"])["coverage"],
            })
        view = store.read_json(case["view_path"])
        assert view == expected_points[step - 1], (condition["id"], step, view)
        authority = event["expected_authority"]
        available_fields = {}
        available_revisions = {}
        for inspected_id in governing_ids:
            source = store.read_json(case["source_paths"][inspected_id], category="evaluator")
            available_fields.update(source["fields"])
            available_revisions[inspected_id] = source["revision"]
        assert available_fields == authority
        assert available_revisions == versions()
        stale = sorted(key for key, value in authority.items() if view["fields"].get(key) != value)
        declares_current = not view["dirty"] and not view["known_gaps"]
        checkpoints.append({
            "step": step, "phase": "after_event_and_scheduled_review",
            "authoritative_fields": authority, "committed_fields": view["fields"],
            "coverage": view["coverage"], "dirty": view["dirty"], "known_gaps": view["known_gaps"],
            "source_versions_available": versions(), "source_versions_inspected": inspected,
            "cumulative_review_attempts": attempts, "cumulative_source_inspections": inspections,
            "stale_fields": stale, "stale_field_count": len(stale),
            "view_declares_current": declares_current, "actually_current": not stale,
            "declares_clean_while_stale": declares_current and bool(stale),
            "file_manifest": store.manifest(),
        })
    final = store.read_json(case["view_path"])
    assert final == case["expected_final_by_condition"][condition["id"]]
    assert attempts == case["expected_properties"]["review_attempts_each"]
    assert inspections <= case["expected_properties"]["max_source_records_inspected_each"]
    assert sum(read["category"] == "review_source" for read in store.reads) == inspections
    interrupted_count = sum(review["outcome"] == "interrupted" for review in reviews)
    assert interrupted_count == case["expected_properties"]["interrupted_review_attempts"][condition["id"]]
    for relative, original_hash in original_hashes.items():
        assert digest(store.path(relative).read_bytes()) == original_hash
    assert store.read_json("sources/K699.json")["revision"] == 2
    assert not any("K699-v1" in path for path in store.manifest())
    return {
        "id": case["id"], "hypothesis": "H6", "condition_id": condition["id"],
        "passed": True, "kind": "capped_deterministic_maintenance",
        "summary": {
            "source_replay_steps": len(case["events"]), "review_attempts": attempts,
            "source_inspections": inspections, "interrupted_attempts": interrupted_count,
            "review_source_bytes": sum(read["bytes"] for read in store.reads if read["category"] == "review_source"),
            "source_version_metadata_reads": sum(read["category"] == "source_version_metadata" for read in store.reads),
            "source_version_metadata_bytes": sum(read["bytes"] for read in store.reads if read["category"] == "source_version_metadata"),
            "source_version_metadata_writes": sum(mutation["category"] == "version_tracking" for mutation in store.mutations),
            "evaluator_source_reads": sum(read["category"] == "evaluator" for read in store.reads),
            "stale_event_steps": sum(bool(point["stale_fields"]) for point in checkpoints),
            "stale_field_event_steps": sum(point["stale_field_count"] for point in checkpoints),
            "misleading_clean_checkpoints": [point["step"] for point in checkpoints if point["declares_clean_while_stale"]],
            "governing_original_versions_retained": True,
            "irrelevant_K699_original_retained": False, "final_view": final,
        },
        "checkpoints": checkpoints, "mutations": store.mutations, "reads": store.reads, "reviews": reviews,
    }


def self_check_paths():
    temporary = tempfile.TemporaryDirectory(prefix="filing-maintenance-path-check-")
    root = Path(temporary.name).resolve()
    assert root.parent == Path(tempfile.gettempdir()).resolve()
    try:
        store = Store(root)
        for bad in ("../escape.json", "/outside.json", "C:/outside.json", "a\\b.json", ""):
            try:
                store.path(bad)
            except ValueError:
                continue
            raise AssertionError("unsafe path accepted: " + bad)
        store.write("inside/value.json", encode({"safe": True}), 0, "self_check", "check")
        assert store.read_json("inside/value.json") == {"safe": True}
    finally:
        assert root.parent == Path(tempfile.gettempdir()).resolve() and not root.is_symlink()
        temporary.cleanup()


def run(fixture):
    payload = fixture.read_bytes()
    data = json.loads(payload.decode("utf-8"))
    cases = data["maintenance_cases"]
    assert {case["hypothesis"] for case in cases} == {"H4", "H6"}
    traces = []
    for case in cases:
        for condition in case["conditions"]:
            temporary = tempfile.TemporaryDirectory(prefix="filing-maintenance-trace-")
            root = Path(temporary.name).resolve()
            assert root.parent == Path(tempfile.gettempdir()).resolve()
            try:
                store = Store(root)
                replay = replay_h4 if case["hypothesis"] == "H4" else replay_h6
                traces.append(replay(case, condition, store))
                assert all(not path.is_symlink() for path in root.rglob("*"))
            finally:
                # Only this newly created synthetic trial is recursively removed.
                assert root.parent == Path(tempfile.gettempdir()).resolve() and not root.is_symlink()
                temporary.cleanup()
    return {
        "schema_version": 1,
        "status": "executed engineered deterministic replay; not LLM reader or maintainer benefit",
        "privacy": "Wholly fictional source data only; no private vault or session content.",
        "fixture_sha256": digest(payload), "traces": traces,
        "measurement_notes": {
            "review_budget": "Six governing-record body inspections per schedule, including interrupted reviews. Initial ingest, source-version metadata tracking and evaluator verification are separately logged.",
            "version_tracking": "Governing commits update an explicit staged source-version-index.json. Gap audits read this metadata, not governing source bodies.",
            "reads": "Explicit JSON reads are logged with category and bytes. Auxiliary SHA256 manifest/consistency reads are evaluator instrumentation and excluded from maintainer resource counts.",
        },
        "self_checks": [
            "Traversal and absolute paths rejected; all staged trial files verified ordinary and without symlinks.",
            "H4 prescribed checkpoints, repair budgets, access and final separators asserted.",
            "H6 every committed checkpoint, authority, budget, interrupted commit and final view asserted.",
            "Retained governing originals verified by SHA256; irrelevant K699 original explicitly not retained.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true", help="check containment and all prescribed replay assertions")
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("maintenance-results.json"))
    args = parser.parse_args()
    fixture = Path(__file__).with_name("secondary-cases.json")
    output = args.output.resolve()
    assert output.parent == fixture.parent.resolve(), "output must stay in the public study directory"
    assert output.name not in {"secondary-cases.json", "cases.json", "replay_maintenance.py"}, "refuse fixture/code overwrite"
    self_check_paths()
    result = run(fixture)
    candidate_output = output.with_name(output.name + ".candidate")
    candidate_output.write_text(encode(result), encoding="utf-8")
    assert json.loads(candidate_output.read_text(encoding="utf-8")) == result
    candidate_output.replace(output)
    print("PASS: 5 actual staged filesystem traces; all prescribed checkpoints and budgets verified.")
    print("H4 repair writes: canonical=4, duplicated_copies=5.")
    print("H6 attempts: 3 each; interrupted update/fixed=1; triggered final view remains dirty.")
    print("These are engineered mechanisms, not measured LLM benefits.")
    print("Output: " + output.name)


if __name__ == "__main__":
    main()
