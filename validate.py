#!/usr/bin/env python3
"""Validate claim-source annotation records.

Two layers of checking:
  1. Structure: the record must match schema/annotation.schema.json.
  2. Consistency: scores must follow from the element findings, and the
     verdict must follow from the gates, scores and caps (rubric v0.3).

Usage:
    python validator/validate.py examples/valid/*.json

Exit code is 0 if there are no errors and 1 otherwise. Warnings never fail a run.
"""
import glob
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "annotation.schema.json"

SUPPORTED = "Supported"
PARTLY = "Partly supported"
COMPAT = "Compatible but not confirmed"
SILENT = "Not supported (on topic but silent)"
OFFTOPIC = "Not supported (off-topic)"
PREDATES = "Not supported (source predates event)"
CONTRADICTED = "Contradicted"
CANT_CHECK = "Can't check"

BORDERLINE_TOTALS = {2, 3, 5}

# Heuristic only: qualifiers should modify an element, not be one.
QUALIFIER_WORDS = ["first", "full", "all", "thousands", "nationwide", "only"]


def expected_outcome(assessment, n_elements):
    """Work out what the rubric says this assessment should produce.

    Returns a dict that may contain: verdict, coverage, explicitness, total, caps.
    Gate failures stop scoring, so they return only a verdict.
    """
    gates = assessment["gates"]
    if gates["G1"] == "fail":
        return {"verdict": CANT_CHECK}
    if gates["G2"] == "fail":
        return {"verdict": OFFTOPIC}
    if gates["G3"] == "fail":
        return {"verdict": PREDATES}
    if gates["G4"] == "fail":
        return {"verdict": CONTRADICTED}

    addressed = [f for f in assessment["element_findings"] if f["addressed"]]
    n_addressed = len(addressed)

    if n_addressed == n_elements:
        coverage = 2
    elif n_addressed > 0:
        coverage = 1
    else:
        coverage = 0
    if coverage == 0:
        return {"verdict": SILENT, "coverage": 0}

    n_stated = sum(1 for f in addressed if f["stated_or_implied"] == "stated")
    if n_stated == n_addressed:
        explicitness = 2
    elif n_stated > 0:
        explicitness = 1
    else:
        explicitness = 0

    scope = assessment["scores"]["scope"]  # a judgment call, so it is taken as given
    result = {"coverage": coverage, "explicitness": explicitness}
    if scope is None:
        return result

    total = coverage + explicitness + scope
    if total == 6:
        verdict = SUPPORTED
    elif total >= 3:
        verdict = PARTLY
    else:
        verdict = COMPAT

    caps = []
    if explicitness == 0:
        caps.append("explicitness_zero")
    if scope == 0:
        caps.append("scope_zero")
    if n_addressed * 2 < n_elements:
        caps.append("fewer_than_half_addressed")
    if caps and verdict in (SUPPORTED, PARTLY):
        verdict = COMPAT

    result.update({"total": total, "verdict": verdict, "caps": caps})
    return result


def check_record(record):
    """Return (errors, warnings) for one schema-valid record."""
    errors, warnings = [], []

    elements = record["claim"]["elements"]
    element_ids = [e["id"] for e in elements]
    n_elements = len(elements)

    if len(set(element_ids)) != n_elements:
        errors.append("claim.elements: element ids are not unique")

    for e in elements:
        for word in QUALIFIER_WORDS:
            if re.search(rf"\b{word}\b", e["text"], flags=re.IGNORECASE):
                warnings.append(
                    f"element {e['id']} contains the qualifier '{word}'. "
                    "Qualifiers should be scored under Scope, not written into an element."
                )

    source_ids = {s["source_id"] for s in record["sources"]}
    assessed_ids = [a["source_id"] for a in record["assessments"]]
    for sid in assessed_ids:
        if sid not in source_ids:
            errors.append(f"assessment refers to unknown source_id '{sid}'")
    for sid in source_ids - set(assessed_ids):
        warnings.append(f"source '{sid}' has no assessment")

    for a in record["assessments"]:
        label = f"assessment[{a['source_id']}]"
        scores = a["scores"]
        exp = expected_outcome(a, n_elements)
        scored = a["gates"]["G1"] == "pass" and a["gates"]["G2"] == "pass" \
            and a["gates"]["G3"] != "fail" and a["gates"]["G4"] != "fail"

        if scored:
            finding_ids = [f["element_id"] for f in a["element_findings"]]
            if sorted(finding_ids) != sorted(element_ids):
                errors.append(f"{label}: element_findings must cover every claim element exactly once")
            for f in a["element_findings"]:
                if f["addressed"] and f["stated_or_implied"] == "n/a":
                    errors.append(f"{label}: element {f['element_id']} is addressed, so it must be 'stated' or 'implied'")
                if not f["addressed"] and f["stated_or_implied"] != "n/a":
                    errors.append(f"{label}: element {f['element_id']} is not addressed, so stated_or_implied must be 'n/a'")

            if "coverage" in exp and scores["coverage"] != exp["coverage"]:
                errors.append(f"{label}: coverage is {scores['coverage']} but the element findings give {exp['coverage']}")
            if "explicitness" in exp and exp.get("coverage", 0) > 0 and scores["explicitness"] != exp["explicitness"]:
                errors.append(f"{label}: explicitness is {scores['explicitness']} but the element findings give {exp['explicitness']}")
            if exp.get("coverage") == 0:
                if scores["explicitness"] not in (None, 0) or scores["scope"] not in (None, 0):
                    warnings.append(f"{label}: coverage is 0, so explicitness and scope should be left null")
            elif scores["scope"] is None:
                errors.append(f"{label}: scope must be scored when a source is on topic and addresses at least one element")

            if "total" in exp:
                given = [scores["coverage"], scores["explicitness"], scores["scope"]]
                if None not in given and scores["total"] != sum(given):
                    errors.append(f"{label}: total is {scores['total']} but the axes add up to {sum(given)}")
                if set(a["caps_triggered"]) != set(exp["caps"]):
                    errors.append(f"{label}: caps_triggered is {sorted(a['caps_triggered'])} but the rubric gives {sorted(exp['caps'])}")
                is_borderline = exp["total"] in BORDERLINE_TOTALS
                has_flag = "borderline" in a["flags"]
                if is_borderline and not has_flag:
                    warnings.append(f"{label}: total {exp['total']} is borderline but the flag is missing")
                if has_flag and not is_borderline:
                    warnings.append(f"{label}: 'borderline' flag set but total {exp['total']} is not 2, 3 or 5")
        else:
            if a["element_findings"]:
                warnings.append(f"{label}: a gate stopped scoring, so element_findings is normally empty")

        if "verdict" in exp and exp["verdict"] is not None and a["verdict"] != exp["verdict"]:
            errors.append(f"{label}: verdict is '{a['verdict']}' but the rubric gives '{exp['verdict']}'")

        if a["gates"]["G3"] == "undated" and "undated source" not in a["flags"]:
            warnings.append(f"{label}: G3 is 'undated' but the 'undated source' flag is missing")
        if a["gates"]["G4"] == "possible" and "possible conflict" not in a["flags"]:
            warnings.append(f"{label}: G4 is 'possible' but the 'possible conflict' flag is missing")

    verdicts = [a["verdict"] for a in record["assessments"]]
    overall = record["overall"]["verdict"]
    if len(verdicts) == 1:
        if overall != verdicts[0]:
            errors.append(f"overall verdict '{overall}' differs from the only assessment's verdict '{verdicts[0]}'")
    else:
        if CONTRADICTED in verdicts and overall != CONTRADICTED:
            errors.append("a source is Contradicted, so the overall verdict must be Contradicted")
        warnings.append("several sources: pooled overall verdict is not checked automatically")

    return errors, warnings


def expand_paths(args):
    """Expand wildcards ourselves, because Windows shells do not."""
    paths = []
    for arg in args:
        matches = sorted(glob.glob(arg))
        paths.extend(matches if matches else [arg])
    return paths


def main(paths):
    paths = expand_paths(paths)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    any_errors = False
    for path in paths:
        try:
            record = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"{path}: cannot read ({exc})")
            any_errors = True
            continue

        schema_errors = sorted(validator.iter_errors(record), key=lambda e: list(e.path))
        if schema_errors:
            any_errors = True
            print(f"{path}: SCHEMA ERRORS")
            for err in schema_errors:
                where = "/".join(str(p) for p in err.path) or "(top level)"
                print(f"  ERROR {where}: {err.message}")
            continue

        errors, warnings = check_record(record)
        if errors:
            any_errors = True
        status = "FAIL" if errors else "OK"
        print(f"{path}: {status}")
        for msg in errors:
            print(f"  ERROR {msg}")
        for msg in warnings:
            print(f"  WARN  {msg}")

    return 1 if any_errors else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
