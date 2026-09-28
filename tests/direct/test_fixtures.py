"""The live-run fixtures, checked against the deployed code.

The panel's readings cannot be checked here - that is what the live run is for -
but everything around them can: the terms parse, every delivered digest is the
digest of the document that will be served, the injected document trips the
marker scan and no honest one does, and the two code-decided cases decide in
code while every other case clears the code checks and reaches the panel.
"""

import hashlib
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"

TERMS = json.loads((FIXTURES / "terms.json").read_text(encoding="utf-8"))
CASES = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
SOURCE = CASES["source"]
UNPUBLISHED = "evidence/leaflet-es-unpublished.html"
INJECTED = "evidence/leaflet-es-annotated.html"
BASE = "https://raw.githubusercontent.com/example/translationagreement/0000000/fixtures/"
TRANSLATOR = "0x" + "ab" * 20
REQUESTER = "0x" + "cd" * 20


def filled(**overrides) -> str:
    spec = dict(TERMS["leaflet"], translator=TRANSLATOR, source_url=BASE + SOURCE)
    spec.update(overrides)
    return json.dumps(spec)


def text_of(mod, path: str) -> str:
    return mod._normalize((FIXTURES / path).read_text(encoding="utf-8"), True)[:mod.TEXT_CAP]


def test_the_terms_parse(mod):
    error, spec = mod._parse_terms(filled(), REQUESTER)
    assert error == ""
    assert sorted(spec["evidence_domains"]) == sorted(CASES["origins"])
    assert spec["source_sha256"] == hashlib.sha256(
        (FIXTURES / SOURCE).read_bytes()).hexdigest()


def test_every_case_override_still_parses(mod):
    for case in CASES["cases"]:
        error, _spec = mod._parse_terms(filled(**case["terms"]), REQUESTER)
        assert error == "", case["case"]


def test_the_catalogue_is_coherent(mod):
    for case in CASES["cases"]:
        assert case["expect_verdict"] in mod.VERDICTS, case["case"]
        assert case["expect_reason"] in mod.REASON_CODES + mod.ENDINGS, case["case"]
    assert CASES["contest_case"] in [c["case"] for c in CASES["cases"]]
    assert len({c["wallet"] for c in CASES["cases"]}) == len(CASES["cases"])


def test_every_verdict_and_every_code_reason_is_exercised(mod):
    verdicts = {c["expect_verdict"] for c in CASES["cases"]}
    assert verdicts == {"PRESERVED", "PARTIALLY_PRESERVED", "NOT_PRESERVED",
                        "INSUFFICIENT_EVIDENCE", "NONE"}
    reasons = {c["expect_reason"] for c in CASES["cases"]}
    assert set(mod.CODE_REASONS) <= reasons
    for reason in ("MEANING_PRESERVED", "MINOR_DEVIATIONS", "MATERIAL_OMISSION",
                   "MATERIAL_DISTORTION", "MATERIAL_ADDITION", "REQUIREMENT_NOT_MET",
                   "EXPIRED", "LAPSED", "DECLINED", "CANCELLED"):
        assert reason in reasons, reason


def test_only_the_added_claim_case_tolerates_a_second_reason():
    tolerant = [c for c in CASES["cases"] if c.get("expect_reason_any")]
    assert [c["case"] for c in tolerant] == ["TA05"]
    assert tolerant[0]["expect_verdict"] == "NOT_PRESERVED"
    assert set(tolerant[0]["expect_reason_any"]) == {"MATERIAL_ADDITION",
                                                     "MATERIAL_DISTORTION"}


def test_every_delivered_digest_is_the_digest_of_the_document_that_is_served():
    for case in CASES["cases"]:
        if case["translation"] == UNPUBLISHED \
                or case["expect_reason"] == "EVIDENCE_DIGEST_MISMATCH":
            continue
        served = hashlib.sha256((FIXTURES / case["translation"]).read_bytes()).hexdigest()
        assert case["translation_sha256"] == served, case["case"]


def test_the_mismatch_case_names_a_published_document_with_a_wrong_digest():
    case = [c for c in CASES["cases"] if c["expect_reason"] == "EVIDENCE_DIGEST_MISMATCH"][0]
    path = FIXTURES / case["translation"]
    assert path.exists()
    assert case["translation_sha256"] != hashlib.sha256(path.read_bytes()).hexdigest()


def test_only_the_unreadable_case_names_a_document_that_does_not_exist():
    for case in CASES["cases"]:
        exists = (FIXTURES / case["translation"]).exists()
        assert exists != (case["translation"] == UNPUBLISHED), case["case"]


def test_no_document_is_unreferenced():
    served = {"evidence/" + p.name for p in (FIXTURES / "evidence").iterdir()}
    referenced = {c["translation"] for c in CASES["cases"]} | {SOURCE}
    assert served - referenced == set()


def test_every_document_says_it_is_a_fixture_where_the_panel_cannot_read_it(mod):
    for path in (FIXTURES / "evidence").iterdir():
        raw = path.read_text(encoding="utf-8")
        assert "TEST / DEMONSTRATION ONLY" in raw and "NOT FOR PRODUCTION" in raw, path.name
        assert "TEST / DEMONSTRATION ONLY" not in mod._normalize(raw, True), path.name


@pytest.mark.parametrize("path", sorted("evidence/" + p.name
                                        for p in (FIXTURES / "evidence").iterdir()))
def test_the_marker_scan_agrees_with_what_each_document_is(mod, path):
    raw = (FIXTURES / path).read_text(encoding="utf-8")
    source = {"status": "RETRIEVED", "title": mod._title_of(raw, True)}
    found = mod._markers(source, mod._normalize(raw, True), raw)
    assert bool(found) == (path == INJECTED), (path, found)


def test_the_code_checks_decide_exactly_the_code_cases(mod):
    """TA07 fails the term check, TA08 the number check, and every document the
    panel is meant to read clears both - so each panel case isolates the one
    reading it is about."""
    _e, terms = mod._parse_terms(filled(), REQUESTER)
    source = text_of(mod, SOURCE)
    for case in CASES["cases"]:
        if case["translation"] == UNPUBLISHED:
            continue
        checks = mod._checks(terms, {"SOURCE": source,
                                     "TRANSLATION": text_of(mod, case["translation"])})
        missing_term = "MISSING" in checks["terms"].values()
        if case["expect_reason"] == "CRITICAL_TERM_MISSING":
            assert checks["terms"]["ingredient"] == "MISSING", case["case"]
        elif case["expect_reason"] == "NUMBER_NOT_PRESERVED":
            assert not missing_term and checks["missing_numbers"] == ["8"], case["case"]
        else:
            assert not missing_term and checks["missing_numbers"] == [], case["case"]
            assert checks["terms"] == {"ingredient": "PRESENT", "tablet": "PRESENT"}
