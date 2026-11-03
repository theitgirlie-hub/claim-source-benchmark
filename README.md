# Claim-Source Benchmark (pilot, v0.1)

A small, tool-independent format for recording how well a cited source supports a claim, plus a validator that checks records for structural and rubric-consistency errors.

It does not depend on any particular platform. Anyone comparing human and AI claim verification can use it.

> **Status:** early pilot. The schema and rubric thresholds are provisional. The examples are illustrative, not reference annotations.

<!-- TODO (write in your own words): two or three sentences on why this exists.
     What problem did the pilot expose? (verdict thresholds applied inconsistently) -->

## What a record contains

One record is one claim, judged by one annotator (human or AI) against one or more cited sources.

| Part | What it holds |
|---|---|
| `claim` | The claim verbatim, optional context, the article, and the claim split into elements |
| `sources` | Each cited source: citation, URL, type, date, access |
| `annotator` | Who or what labeled it. AI annotators must record the model and whether it had web access |
| `assessments` | One per source: gate results, element findings, scores, caps, verdict, evidence note, flags |
| `overall` | The overall verdict and whether the claim is true by other sources, kept separate from the verdict |

The full definition is in [`schema/annotation.schema.json`](schema/annotation.schema.json).

## The rubric

See [`docs/rubric.md`](docs/rubric.md). In short: split the claim into elements, pass the source through four gates (readable, on topic, timing, conflict), score coverage, explicitness and scope, and derive the verdict from the total and caps.

## Quick start

```bash
pip install -r requirements.txt
python validator/validate.py examples/valid/*.json      # should print OK
python validator/validate.py examples/invalid/*.json    # should print FAIL
```

## What the validator checks

1. **Structure:** the record matches the schema (required fields, allowed values).
2. **Scores follow from findings:** coverage and explicitness are recomputed from the element findings, and the total must equal the sum of the axes.
3. **Verdict follows from gates, scores and caps:** the verdict is recomputed from the rubric and must match.
4. **Flags:** warns if a borderline total, undated source or possible conflict lacks its flag.
5. **Qualifiers:** warns when an element text contains a qualifier word (heuristic only).

## Known limitations

- Scope fidelity is a judgment call, so the validator takes it as given.
- With several sources, the pooled overall verdict is not checked automatically. Only the case of a single source and the rule that any Contradicted source makes the overall verdict Contradicted are checked.
- Whether an element counts as "stated" or "implied" is also a judgment. The validator only checks that the scores agree with whatever was recorded.
- Tested on a handful of examples only.

## Open questions

<!-- TODO: list the choices you want feedback on, for example:
     one record per annotator vs one record per claim with several annotations;
     pinning Wikipedia revision IDs; the license for claim text; the schema version policy. -->

## License

<!-- TODO: choose before publishing. Code and data may need different licenses.
     Claim text copied from Wikipedia is CC BY-SA 4.0, so dataset files may need
     attribution and share-alike. Ask the mentors if unsure. -->

## Note on AI assistance

<!-- TODO: state plainly how AI was used in building this repo. -->
