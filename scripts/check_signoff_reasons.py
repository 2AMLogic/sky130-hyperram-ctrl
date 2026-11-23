#!/usr/bin/env python3
"""Assert no signoff-record item is graded `reason: "stale_evidence"`.

Why this exists (issue #212). `klt signoff` legitimately exits 3 whenever any
T1 item is unmet, so the `klt signoff record is fresh` gate in check_ci.sh
accepts rc 0 or 3 and gates on bytes alone: a fresh render equal to the
committed record passes. But a stale
manifest pin -- an attested inventory or envelope regenerated without
copying the new `provenance.input.content_hash` into the item's
`evidence."N".content_hash` pin -- downgrades a previously-met T1 item to
`unmet`/`stale_evidence`, and once that downgraded record is committed, the
byte-compare compares the render to itself and CI stays green: a met T1 item
silently dropped (`t1_met_count` 7 -> 6) with no failing check anywhere.

The reason token is the discriminator. klt 0.9.2 documents thirty unmet
reasons (`no_evidence`, `check_failed`, `tier_not_supported`, `wrong_kind`,
...) and the vocabulary grows release by release, so this check reject-lists
exactly one token -- an allow-list would break CI on every new legitimate
klt reason (issue #212 curation). `"stale_evidence"` is klt's "the check
passed, but its provenance.input.content_hash does not match the manifest's
pinned content_hash": the pin and the cited evidence disagree, which is
never a legitimate resting state -- it is always a pin that must be
refreshed (or an envelope that must be re-produced) before the record may
be committed.

  scripts/check_signoff_reasons.py RECORD [RECORD ...]   check record(s) (the
  `klt signoff record is fresh` gate in check_ci.sh)
  scripts/check_signoff_reasons.py --self-test           check this checker, on fixtures

The self-test is here because this file is now the only thing standing
between a stale-pin downgrade and a green CI, so "it catches the hole" is a
claim that needs its own testbench (the step 3c/3d/4c/6b/6c pattern). It
drives the grading functions over fixture records inside a temporary
directory; it touches nothing in the repo and needs no klt, no manifest and
no PDK.

A record whose `items` is missing or not a list fails closed -- a schema
rename must not silently pass -- while an item with a null or absent
`reason` (every met item) passes. Exit 0 when no checked item carries
`stale_evidence`, 1 otherwise.
"""

import contextlib
import io
import json
import pathlib
import sys
import tempfile

REASON_STALE = "stale_evidence"
REFRESH = (
    "the cited evidence no longer matches the manifest's pinned"
    " content_hash: re-run that item's attestation, copy the new"
    " provenance.input.content_hash into its evidence.\"N\".content_hash pin"
    " in the block manifest, then re-render the record (order per"
    " manifests/README.md)"
)


def stale_items(record):
    """The `items` entries of `record` graded `stale_evidence`, in order.

    Raises ValueError when `items` is missing or not a list, so a schema
    rename fails closed instead of passing vacuously. An entry without a
    `reason` key, or with `reason: null` (every met item), is not stale.
    """
    items = record.get("items") if isinstance(record, dict) else None
    if not isinstance(items, list):
        raise ValueError("record has no items[] array (schema change?)")
    return [it for it in items if isinstance(it, dict) and it.get("reason") == REASON_STALE]


def name_item(item):
    """A human name for a record entry: `item 9 (title)` or the bare title."""
    title = item.get("title")
    if item.get("id") is None:
        return str(title)
    return f"item {item.get('id')} ({title})"


def run_check(paths):
    """Check each record in `paths`; print the report; return the exit code."""
    failed = False
    for path in paths:
        record = json.loads(pathlib.Path(path).read_text())
        try:
            stale = stale_items(record)
        except ValueError as exc:
            print(f"::error file={path}::{exc}; cannot grade reasons")
            failed = True
            continue
        if not stale:
            met = sum(1 for it in record["items"]
                      if isinstance(it, dict) and it.get("status") == "met")
            print(f"ok {path}: no item carries reason {REASON_STALE}"
                  f" ({met} met of {len(record['items'])} items)")
            continue
        failed = True
        print(
            f"::error file={path}::{len(stale)} item(s) were downgraded to"
            f" unmet/{REASON_STALE} -- a met T1 item silently dropped:"
        )
        for it in stale:
            print(f"  {name_item(it)}")
        print(f"Fix: {REFRESH}")
    return 1 if failed else 0


def main(argv):
    if argv == ["--self-test"]:
        return self_test()
    if not argv:
        print("usage: check_signoff_reasons.py RECORD [RECORD ...] | --self-test",
              file=sys.stderr)
        return 2
    return run_check(argv)


# --- self-test ------------------------------------------------------------

failures = []


def record(ok, name, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f"\n       {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def item(id_, title, status, reason):
    """A minimal record entry; `reason` omitted entirely when None."""
    it = {"tier": "T1", "id": id_, "title": title, "status": status}
    if reason is not None:
        it["reason"] = reason
    return it


#: The committed record's shape as of issue #212: met items carry no reason,
#: the legitimately-unmet ones carry no_evidence / check_failed /
#: tier_not_supported, and the T2-T4 ladder rows have no id.
MAIN_SHAPED = [
    item(1, "Design sources", "met", None),
    item(4, "Something checked", "met", None),
    item(5, "Full corner verification", "unmet", "no_evidence"),
    item(7, "Timing margin", "unmet", "check_failed"),
    item(None, "T2 — signoff-validated", "unmet", "tier_not_supported"),
]

#: One fixture entry per documented unmet reason that can legitimately rest
#: in a committed record -- every token klt 0.9.2 emits except
#: stale_evidence. Pins the reject-list: a token klt adds later must pass
#: here without an edit, which an allow-list would not.
LEGITIMATE_REASONS = [
    "no_evidence", "evidence_not_klt_native", "invalid_evidence",
    "unreadable_evidence", "unrecognized_envelope", "envelope_version_skew",
    "invalid_pointer", "command_timeout", "command_failed", "check_errored",
    "check_failed", "unverifiable_provenance", "nothing_checked",
    "no_limits_checked", "undersized_sample", "wrong_kind", "wrong_item",
    "unanchored_evidence", "stale_artifact", "timing_margin_missing",
    "ungradeable_by_build", "not_post_layout", "tier_not_supported",
    "not_applicable_wrong_partition", "not_applicable_spec_unratified",
    "not_applicable_statistical_row", "not_applicable_statement_incomplete",
    "negative_control_not_detected", "partial_coverage",
]


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)

        def write(name, items):
            path = tmp / name
            path.write_text(json.dumps({"items": items}))
            return path

        # 1. The committed-record shape passes: met items (reason absent or
        #    null) and the expected unmet reasons are not stale_evidence.
        got = stale_items({"items": MAIN_SHAPED})
        record(got == [], "a main-shaped record reports nothing", f"got {got}")

        # 2. The hole this check exists to close (the issue #212 repro): a
        #    previously-met item downgraded to unmet/stale_evidence.
        downgraded = MAIN_SHAPED[:1] + [
            item(9, "Testbenches shipped", "unmet", "stale_evidence")
        ] + MAIN_SHAPED[1:]
        got = stale_items({"items": downgraded})
        record(len(got) == 1 and got[0].get("id") == 9,
               "a downgraded item is reported and named by id", f"got {got}")

        # 2b. Pins case 2 to the reason comparison: the same record with the
        #     item back to met (no reason key) reports nothing.
        fixed = MAIN_SHAPED[:1] + [item(9, "Testbenches shipped", "met", None)] + MAIN_SHAPED[1:]
        got = stale_items({"items": fixed})
        record(got == [], "...and the same record passes once the pin is refreshed",
               f"got {got}")

        # 3. Every other documented unmet reason passes: the reject-list is
        #    stale_evidence alone, so a new klt token cannot break CI here.
        others = [item(i + 100, f"reason probe {i}", "unmet", r)
                  for i, r in enumerate(LEGITIMATE_REASONS)]
        got = stale_items({"items": others})
        record(got == [],
               f"all {len(LEGITIMATE_REASONS)} other documented unmet reasons pass",
               f"got {got}")

        # 4. An id-less entry (a T2-T4 ladder row) is still caught, and the
        #    report names it by title rather than crashing on the id.
        tier_row = {"tier": "T3", "id": None, "title": "T3 — partial",
                    "status": "unmet", "reason": "stale_evidence"}
        got = stale_items({"items": [tier_row]})
        record(len(got) == 1 and name_item(got[0]) == "T3 — partial",
               "an id-less stale entry is caught and named by title",
               f"got {[name_item(x) for x in got]}")

        # 5. Multiple stale items are all reported, in record order.
        two = [item(2, "Layout stream", "unmet", "stale_evidence"),
               item(3, "DRC", "unmet", "stale_evidence")]
        got = stale_items({"items": two})
        record([x.get("id") for x in got] == [2, 3],
               "multiple stale items are all reported, in order", f"got {got}")

        # 6. A record with no items[] at all fails closed, not vacuously --
        #    the run_check path turns the ValueError into a ::error and a
        #    nonzero exit, and stale_items never crashes on one.
        path = tmp / "no-items.json"
        path.write_text(json.dumps({"t1_met_count": 7}))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = run_check([path])
        try:
            stale_items({"schema_version": 2})
            raised = False
        except ValueError:
            raised = True
        record(raised and code == 1 and "::error" in buf.getvalue(),
               "a record with no items[] fails closed with a ::error",
               f"raised={raised} exit={code} out={buf.getvalue().strip()}")

        # 7. A non-list items value fails closed the same way (an objects-
        #    keyed schema change is not silently iterable).
        try:
            stale_items({"items": {"1": item(1, "x", "met", None)}})
            raised = False
        except ValueError:
            raised = True
        record(raised, "a non-list items value fails closed", f"raised={raised}")

        # 8. A stale record on disk fails run_check with the item named and
        #    the refresh hint; a clean sibling passes in the same run.
        bad = write("bad.json", downgraded)
        good = write("good.json", MAIN_SHAPED)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = run_check([bad, good])
        out = buf.getvalue()
        record(code == 1 and "item 9 (Testbenches shipped)" in out
               and "content_hash" in out and f"ok {good}" in out,
               "run_check names the stale item, prints the hint, passes the clean record",
               f"exit {code}, out: {out.strip()}")

    print(f"\n{'FAIL: ' + str(len(failures)) if failures else 'all ok'}"
          f" — check_signoff_reasons self-test")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
