#!/usr/bin/env python3
"""Mutation kill check: prove the Direct Mode suite pins each load-bearing
guard, not merely that the code passes today.

For each mutation the repository is copied to a scratch directory with ONE
guard in the contract mechanically broken, and the whole Direct Mode suite
runs against the copy. A mutation is KILLED when the suite fails and SURVIVED
when it passes (an unpinned guard). The run starts with an accept-control:
the unmodified copy must pass, or every kill would be vacuous.

Anchors are code TEXT, never line numbers. An anchor that is not found
exactly once is reported as ANCHOR MISSING - the guard moved or was deleted,
which is its own finding.

Run:  python scripts/mutation_check.py              (full sweep)
      python scripts/mutation_check.py --anchors    (anchor check only)
      python scripts/mutation_check.py --only gate  (names containing "gate";
                                                     separate several with |)
      python scripts/mutation_check.py --jobs 3     (three scratch copies)
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = "contracts/translation_agreement.py"


def off(condition: str) -> tuple:
    """(anchor, replacement) turning one `if` line into `if False:`."""
    head = condition[:len(condition) - len(condition.lstrip())]
    keyword = condition.lstrip().split(" ", 1)[0]
    return (condition + "\n", head + keyword + " False:\n")


def m(name: str, anchor: str, replacement: str = None) -> tuple:
    if replacement is None:
        anchor, replacement = off(anchor)
    return (name, anchor, replacement)


MUTATIONS = [
    # -- retrieval ------------------------------------------------------------------------
    m("a redirect is read as a retrieved document", "    if 300 <= code < 400:"),
    m("a 404 is a generic failure", "    if code in (404, 410):"),
    m("a binary content type is read",
      '    if content_type != "" and not any(t in content_type for t in TEXT_TYPES):'),
    m("an oversized document is not marked partial",
      "    truncated = len(body) > BODY_BYTES_CAP or len(normalized) > TEXT_CAP\n",
      "    truncated = False\n"),
    # -- document integrity ---------------------------------------------------------------
    m("a document's bytes are not checked against its declared digest",
      '        if source["status"] in READABLE and source["raw_sha256"] != item["sha256"]:'),
    m("a digest mismatch is judged by the panel anyway",
      '    if any(s["status"] == DIGEST_MISMATCH for s in sources):'),
    m("an unreadable document is judged anyway",
      '    if not all(s["status"] in READABLE for s in sources):\n'
      '        return "DOCUMENT_UNREADABLE"',
      '    if False:\n        return "DOCUMENT_UNREADABLE"'),
    m("the checks of an unreadable round may be anything",
      '    if not all(s["status"] in READABLE for s in sources):\n'
      '        return terms == {} and missing == []',
      '    if False:\n        return terms == {} and missing == []'),
    m("a document addressing the assessor is judged anyway",
      "    if len(markers) > 0:\n        return \"DOCUMENT_ADDRESSES_ASSESSOR\"\n",
      "    if False:\n        return \"DOCUMENT_ADDRESSES_ASSESSOR\"\n"),
    m("text in the visible body is not scanned", "    if body_hit:"),
    m("markup and attributes are not scanned",
      "    if not body_hit and _evaluator_hits(_scan_form(raw_text)):"),
    m("the title is not scanned", '    if _evaluator_hits(_scan_form(source["title"])):'),
    # -- the exact checks -----------------------------------------------------------------
    m("a missing critical term reaches the panel",
      '    if any(v == TERM_MISSING for v in checks["terms"].values()):'),
    m("a missing number reaches the panel", '    if len(checks["missing_numbers"]) > 0:'),
    m("a term the source never uses is still required",
      '        if not _has_phrase(source_words, entry["source_term"]):'),
    m("the first accepted rendering is the only one",
      '        elif any(_has_phrase(translation_words, r) for r in entry["renderings"]):',
      '        elif _has_phrase(translation_words, entry["renderings"][0]):'),
    m("numbers are checked by presence, not by count",
      "    return [run for run in order if have.get(run, 0) < need[run]]\n",
      "    return [run for run in order if have.get(run, 0) < 1]\n"),
    m("numbers are checked even when the terms do not ask",
      '    if terms["preserve_numbers"]:\n', "    if True:\n"),
    m("a term check matches part of a word",
      "    return len(words) > 0 and _find_run(haystack, words, 0) >= 0\n",
      "    return len(words) > 0 and \" \".join(words) in \" \".join(haystack)\n"),
    # -- what a reading must show ----------------------------------------------------------
    m("a deviation needs no quote",
      "        return state in (MINOR, MATERIAL)\n", "        return False\n"),
    m("a misrendered term needs no quote", "        return state == INCORRECT\n",
      "        return False\n"),
    m("an unmet requirement needs no quote", "    return state == NOT_MET\n",
      "    return False\n"),
    m("a met requirement needs a quote again", "    return state == NOT_MET\n",
      "    return state in (MET, NOT_MET)\n"),
    m("an omission may be quoted from the translation",
      "    if subject_id == SUBJECT_OMISSION and state in (MINOR, MATERIAL):"),
    m("a distortion or an addition may be quoted from the source",
      "    if subject_id in (SUBJECT_DISTORTION, SUBJECT_ADDITION) and state in (MINOR, "
      "MATERIAL):"),
    m("a spliced quote is accepted when the panel answers",
      '        if _spliced(rq["text"]):\n            continue\n', ""),
    m("a spliced quote passes the gate",
      '        if q in seen or _spliced(q["text"]) or not _quote_grounded(q, quotable, texts):',
      "        if q in seen or not _quote_grounded(q, quotable, texts):"),
    m("a quote need not ground in the text this node retrieved",
      "    return _grounds_in_order(_word_tokens(source), quote[\"text\"])\n",
      "    return True\n"),
    m("the gate lets a reading quote either document",
      '    quotable = _quotable(subject_id, f["state"], eligible)\n', "    quotable = eligible\n"),
    # -- the outcome -----------------------------------------------------------------------
    m("a code decision about a term or a number is not a verdict",
      '    if reason in ("CRITICAL_TERM_MISSING", "NUMBER_NOT_PRESERVED"):\n'
      "        return (NOT_PRESERVED, reason)\n",
      '    if False:\n        return (NOT_PRESERVED, reason)\n'),
    m("a code reason is overridden by the panel's reading",
      '    if reason != "":\n        return (INSUFFICIENT_EVIDENCE, reason)\n',
      '    if False:\n        return (INSUFFICIENT_EVIDENCE, reason)\n'),
    m("an unusable panel answer reaches a verdict",
      '    if payload["panel_state"] != PANEL_ASSESSED:\n'
      '        return (INSUFFICIENT_EVIDENCE, "PANEL_UNUSABLE")',
      '    if False:\n        return (INSUFFICIENT_EVIDENCE, "PANEL_UNUSABLE")'),
    m("a material deviation is not a failure",
      "        if _state_of(payload, subject_id) == MATERIAL:"),
    m("a misrendered term is not a failure", "    if INCORRECT in terms:"),
    m("an unmet requirement is not a failure", "    if NOT_MET in requirements:"),
    m("an optional requirement decides the outcome",
      '            for r in ctx["terms"]["requirements"] if r["required"]]\n',
      '            for r in ctx["terms"]["requirements"]]\n'),
    m("a term the source never uses is judged anyway",
      '        if payload["checks"]["terms"].get(t["term_id"]) == TERM_NOT_IN_SOURCE:'),
    m("an unclear reading is preserved",
      "    if any(state == UNCLEAR for _s, state in deviations) or UNCLEAR in terms \\\n",
      "    if False \\\n"),
    m("a minor deviation is preserved", "    if any(state == MINOR for _s, state in deviations):"),
    # -- what validators compare -----------------------------------------------------------
    m("the consequence is not compared",
      "    for key in sorted(mine.keys()):\n        if mine[key] != theirs[key]:\n",
      "    for key in sorted(mine.keys()):\n        if False:\n"),
    # Equivalent by construction, and left out rather than counted as a false kill:
    # the code checks are compared twice, in _evidence_difference and inside the
    # consequence, and either alone catches every difference the other would - they
    # are pure functions of the bound bytes, so they cannot differ without the
    # consequence differing. test_a_forged_check_that_changes_no_reason_is_still_refused
    # pins the pair together.
    m("the code checks are not gated",
      "    if sorted(terms.keys()) != ids or not all(v in TERM_CHECKS for v in terms.values()):"),
    m("a missing number need not be a number",
      "    return all(isinstance(n, str) and n != \"\" and n.isdigit() and n.isascii()\n"
      "               for n in missing)\n",
      "    return True\n"),
    m("the leader's payload is gated against its own text, not this node's",
      "        parsed = _parse_payload(leader_res.calldata, ctx, own_texts)\n",
      "        parsed = _parse_payload(leader_res.calldata, ctx, None)\n"),
    m("a transient failure ratifies a different failure",
      "        if leader_text.startswith(ERROR_TRANSIENT):\n"
      "            return own_text.startswith(ERROR_TRANSIENT)\n"
      "        return own_text == leader_text\n",
      "        return True\n"),
    m("a payload about another agreement is accepted",
      '            or p["agreement_id"] != ctx["agreement_id"] or not _is_int(p["round"]) \\\n',
      '            or not _is_int(p["round"]) \\\n'),
    # -- the terms -------------------------------------------------------------------------
    m("the translator may be the requester", '    if spec["translator"] == requester:'),
    m("the languages may be the same",
      '    if _norm_ws(spec["source_language"]) == _norm_ws(spec["target_language"]):'),
    m("the source may come from any host",
      '    if not _domain_allowed(_host_of(canonical), domains):\n'
      '        return ("source_url is outside',
      '    if False:\n        return ("source_url is outside'),
    m("the source need not be bound to a digest", '    if not _is_hex(spec["source_sha256"], 64):'),
    m("the windows are unbounded",
      "        if not _int_in(spec[field], MIN_WINDOW, MAX_WINDOW):"),
    m("preserve_numbers may be anything", '    if not isinstance(spec["preserve_numbers"], bool):'),
    m("a term id may shadow a built-in subject", "    if text.upper() in BUILT_IN_SUBJECTS:"),
    m("a term may have no accepted rendering",
      "        if not isinstance(renderings, list) or len(renderings) < 1 \\\n",
      "        if not isinstance(renderings, list) \\\n"),
    m("the terms' text may address the assessor",
      "    if _evaluator_hits(value) or _hidden_hits(value):"),
    m("an IP literal is a host", "    if all_numeric or labels[-1].isdigit():"),
    # -- the delivery ----------------------------------------------------------------------
    m("a stranger may deliver",
      '        if self._sender_hex() != str(agreement.translator):\n'
      '            self._fail("only the named translator delivers")',
      '        if False:\n            self._fail("only the named translator delivers")'),
    m("a delivery may come after its deadline",
      '        if _iso_epoch(now) > _iso_epoch(str(agreement.delivery_due)):\n'
      '            self._fail("the delivery window closed at "',
      '        if False:\n            self._fail("the delivery window closed at "'),
    m("a translation may come from any host",
      '        if not _domain_allowed(_host_of(canonical), terms["evidence_domains"]):'),
    m("the source may be delivered as the translation",
      '        if canonical == terms["source_url"]:'),
    m("the source's bytes may be delivered as the translation",
      '        if translation_sha256 == terms["source_sha256"]:'),
    m("a translation need not be bound to a digest",
      "        if not _is_hex(translation_sha256, 64):"),
    # -- the state machine -----------------------------------------------------------------
    m("a stranger may accept",
      '        if self._sender_hex() != str(agreement.translator):\n'
      '            self._fail("only the named translator accepts")',
      '        if False:\n            self._fail("only the named translator accepts")'),
    m("the accepted terms are not checked",
      "        if terms_hash != str(agreement.definition_hash):"),
    m("accepted terms may be accepted again",
      '        if str(agreement.status) != AG_PROPOSED:\n'
      '            self._fail("only a PROPOSED agreement can be accepted")',
      '        if False:\n            self._fail("only a PROPOSED agreement can be accepted")'),
    m("a stranger may cancel", '        if self._sender_hex() != str(agreement.requester):'),
    m("accepted terms may be cancelled",
      '        if str(agreement.status) != AG_PROPOSED:\n'
      '            self._fail("only a PROPOSED agreement can be cancelled")',
      '        if False:\n            self._fail("only a PROPOSED agreement can be cancelled")'),
    m("a stranger may decline",
      '        if self._sender_hex() != str(agreement.translator):\n'
      '            self._fail("only the named translator declines")',
      '        if False:\n            self._fail("only the named translator declines")'),
    m("an agreement may be assessed twice",
      '        if str(agreement.status) != AG_DELIVERED:\n'
      '            self._fail("only a DELIVERED agreement is assessed")',
      '        if False:\n            self._fail("only a DELIVERED agreement is assessed")'),
    m("a delivery may be assessed after its window",
      '        if _iso_epoch(now) > _iso_epoch(str(agreement.window_ends)):\n'
      '            self._fail("the assess window closed at "',
      '        if False:\n            self._fail("the assess window closed at "'),
    m("an outcome may be contested twice", "        if bool(agreement.contested):"),
    m("a stranger may contest",
      "        if self._sender_hex() not in (str(agreement.requester), "
      "str(agreement.translator)):"),
    m("an outcome may be contested after its window",
      '        if _iso_epoch(now) > _iso_epoch(str(agreement.window_ends)):\n'
      '            self._fail("the contest window closed at "',
      '        if False:\n            self._fail("the contest window closed at "'),
    m("an outcome may be made final inside its contest window",
      '        if _iso_epoch(now) <= _iso_epoch(str(agreement.window_ends)):\n'
      '            self._fail("the contest window closes at "',
      '        if False:\n            self._fail("the contest window closes at "'),
    m("an agreement may expire before its delivery deadline",
      '        if _iso_epoch(now) <= _iso_epoch(str(agreement.delivery_due)):\n'
      '            self._fail("the delivery window closes at "',
      '        if False:\n            self._fail("the delivery window closes at "'),
    m("a delivery may lapse while its window is open",
      '        if _iso_epoch(now) <= _iso_epoch(str(agreement.window_ends)):\n'
      '            self._fail("the assess window closes at "',
      '        if False:\n            self._fail("the assess window closes at "'),
    m("the open-agreement cap does not hold",
      "        if self._counter_value(requester) >= MAX_OPEN_PER_WALLET:"),
    m("a final outcome keeps the requester's slot",
      "        agreement.finalized_at = now\n        self._count(str(agreement.requester), -1)\n"
      "        return AG_FINAL\n",
      "        agreement.finalized_at = now\n        return AG_FINAL\n"),
    m("an outcome is final before it is final",
      "        final = str(agreement.status) == AG_FINAL\n        verdict = str(agreement.verdict)\n",
      "        final = True\n        verdict = str(agreement.verdict)\n"),
    m("every reading is marked compared",
      '            entry["compared"] = self._compared(ctx, payload, outcome["reason_code"], '
      "finding)\n",
      '            entry["compared"] = True\n'),
    m("the preserved count is not corrected when a contest overturns",
      "        if was and not is_now:\n"
      "            self.preserved_counter = u32(int(self.preserved_counter) - 1)\n", ""),
]


def run_suite(workdir: pathlib.Path) -> bool:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/direct", "-q", "-x", "-p", "no:cacheprovider",
         "--no-header"], cwd=workdir, capture_output=True, text=True)
    return completed.returncode == 0


def check_anchors(source: str) -> int:
    missing = 0
    for name, old, _new in MUTATIONS:
        hits = source.count(old)
        if hits != 1:
            print(f"ANCHOR MISSING ({hits} hits): {name}")
            missing += 1
    return missing


def copy_repo(scratch: pathlib.Path, index: int) -> pathlib.Path:
    work = scratch / ("repo%d" % index)
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", ".pytest_cache", "deploy", "artifacts", ".data", "docs"))
    return work


def main() -> None:
    source = (ROOT / CONTRACT).read_text(encoding="utf-8")
    missing = check_anchors(source)
    print(f"{len(MUTATIONS)} mutations, {missing} anchor problems")
    if "--anchors" in sys.argv:
        sys.exit(0 if missing == 0 else 1)
    only = ""
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1].casefold()
    jobs = 1
    if "--jobs" in sys.argv:
        jobs = max(1, int(sys.argv[sys.argv.index("--jobs") + 1]))
    todo = [x for x in MUTATIONS if source.count(x[1]) == 1
            and (not only or any(part in x[0].casefold() for part in only.split("|")))]
    jobs = min(jobs, max(1, len(todo)))
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="ta-mut-"))
    copies = [copy_repo(scratch, i) for i in range(jobs)]
    print("accept-control: unmodified copy must pass ...", flush=True)
    if not run_suite(copies[0]):
        print("CONTROL FAILED: the unmodified suite does not pass; aborting")
        shutil.rmtree(scratch, ignore_errors=True)
        sys.exit(1)
    print(f"control green; {len(todo)} mutations over {jobs} job(s)\n", flush=True)
    results = [None] * len(todo)
    cursor = [0]
    done = [0]
    lock = threading.Lock()

    def worker(work: pathlib.Path) -> None:
        target = work / CONTRACT
        while True:
            with lock:
                i = cursor[0]
                if i >= len(todo):
                    return
                cursor[0] = i + 1
            name, old, new = todo[i]
            target.write_text(source.replace(old, new), encoding="utf-8", newline="\n")
            passed = run_suite(work)
            target.write_text(source, encoding="utf-8", newline="\n")
            with lock:
                results[i] = passed
                done[0] += 1
                print(f"  [{done[0]}/{len(todo)}] {'SURVIVED' if passed else 'killed  '}: "
                      f"{name}", flush=True)

    threads = [threading.Thread(target=worker, args=(w,)) for w in copies]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    shutil.rmtree(scratch, ignore_errors=True)
    print()
    killed = survived = 0
    for (name, _old, _new), passed in zip(todo, results):
        print(("SURVIVED: " if passed else "killed:   ") + name)
        survived += 1 if passed else 0
        killed += 0 if passed else 1
    print(f"\nmutations: {killed} killed, {survived} survived, {missing} anchor missing")
    sys.exit(0 if survived == 0 and missing == 0 else 1)


if __name__ == "__main__":
    main()
