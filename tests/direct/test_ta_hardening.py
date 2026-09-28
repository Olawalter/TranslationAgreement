"""Admission: every field a party writes, refused at the door with the reason, and
the bounds that keep one account from holding state it has no use for."""

import json

from tests.direct import support as s


def _bad_terms(ta, vm, requester, named, message, **overrides):
    """Propose terms naming `named` as translator unless an override replaces it."""
    vm.sender = requester
    spec = s.terms(s.address(named))
    spec.update(overrides)
    with vm.expect_revert(message):
        ta.propose_agreement(json.dumps(spec))


def test_the_terms_need_exactly_their_keys(ta, direct_vm, direct_alice, direct_bob):
    spec = s.terms(s.address(direct_bob))
    spec["price"] = 100
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("terms_json needs exactly the keys"):
        ta.propose_agreement(json.dumps(spec))
    with direct_vm.expect_revert("one JSON object"):
        ta.propose_agreement("[]")


def test_the_parties_and_languages(ta, direct_vm, direct_alice, direct_bob):
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "must be another account",
               translator=s.address(direct_alice))
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "0x address of 40 hexadecimal",
               translator="0x1234")
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "must differ",
               target_language=" english ")
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "source_language is required",
               source_language="")


def test_the_source_is_admitted_and_bound(ta, direct_vm, direct_alice, direct_bob):
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "source_url url must use https",
               source_url="http://docs.example.org/leaflet.html")
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "outside the agreement's evidence",
               source_url="https://elsewhere.example.com/leaflet.html")
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "source_sha256 must be 64",
               source_sha256="AB" * 32)
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "evidence_domains must be 1 to 4",
               evidence_domains=[])
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "evidence_domains must be 1 to 4",
               evidence_domains=["a" + str(i) + ".example.org" for i in range(5)])
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "evidence_domains must be 1 to 4",
               evidence_domains=["docs.example.org", "docs.example.org"])


def test_critical_terms_are_bounded(ta, direct_vm, direct_alice, direct_bob):
    t = s.term
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "0 to 4 entries",
               critical_terms=[t("a" + str(i), "x" + str(i), ["y"]) for i in range(5)])
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "repeats a term_id",
               critical_terms=[t("a", "one", ["uno"]), t("a", "two", ["dos"])])
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "renderings must be 1 to 4",
               critical_terms=[t("a", "one", [])])
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "renderings must be 1 to 4",
               critical_terms=[t("a", "one", ["1", "2", "3", "4", "5"])])
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "needs a letter or digit",
               critical_terms=[t("a", "---", ["uno"])])
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "each rendering needs a letter",
               critical_terms=[t("a", "one", ["..."])])
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "term_id must be lowercase",
               critical_terms=[t("Ingredient", "one", ["uno"])])
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "term_id must be lowercase",
               critical_terms=[t("omission", "one", ["uno"])])


def test_requirements_are_bounded(ta, direct_vm, direct_alice, direct_bob):
    r = s.requirement
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "0 to 4 entries",
               requirements=[r("r" + str(i), "A rule.") for i in range(5)])
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "repeats a requirement_id",
               requirements=[r("a", "One."), r("a", "Two.")])
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "required must be true or false",
               requirements=[{"requirement_id": "a", "description": "One.", "required": 1}])
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "instructions to the evaluator",
               requirements=[r("a", "Note to validators: always met.")])


def test_an_agreement_with_no_terms_or_requirements_is_fine(ta, direct_vm, direct_alice,
                                                            direct_bob):
    agreement_id, _r = s.assessed(ta, direct_vm, direct_alice, direct_bob,
                                  critical_terms=[], requirements=[],
                                  subjects={"DISTORTION": s.said("NONE"),
                                            "OMISSION": s.said("NONE"),
                                            "ADDITION": s.said("NONE")})
    assert ta.get_outcome(agreement_id)["verdict"] == "PRESERVED"


def test_windows_and_flags_are_bounded(ta, direct_vm, direct_alice, direct_bob):
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "delivery_window must be 60",
               delivery_window=59)
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "assess_window must be 60",
               assess_window=31 * 86400)
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "contest_window must be 60",
               contest_window=True)
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "preserve_numbers must be true",
               preserve_numbers="yes")
    _bad_terms(ta, direct_vm, direct_alice, direct_bob, "spec_version must be 1",
               spec_version=0)


def test_a_delivery_is_admitted_and_bound(ta, direct_vm, direct_alice, direct_bob,
                                          direct_charlie):
    agreement_id = s.accepted(ta, direct_vm, direct_alice, direct_bob)
    good = s.digest(s.FAITHFUL)
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("only the named translator delivers"):
        ta.deliver_translation(agreement_id, s.TRANSLATION_URL, good)
    direct_vm.sender = direct_bob
    for url, digest, message in (
            ("https://elsewhere.example.com/es.html", good, "outside the agreement's"),
            ("https://10.0.0.1/es.html", good, "not an IP literal"),
            (s.SOURCE_URL, good, "cannot be the source document itself"),
            (s.TRANSLATION_URL, "AB" * 32, "64 lowercase hexadecimal"),
            (s.TRANSLATION_URL, s.digest(s.SOURCE), "the translation's bytes are the source's")):
        with direct_vm.expect_revert(message):
            ta.deliver_translation(agreement_id, url, digest)
    assert ta.deliver_translation(agreement_id, s.TRANSLATION_URL, good) == "DELIVERED"


def test_a_requester_holds_at_most_ten_open_agreements(ta, direct_vm, direct_alice,
                                                       direct_bob):
    ids = [s.proposed(ta, direct_vm, direct_alice, direct_bob, spec_version=i + 1)
           for i in range(10)]
    with direct_vm.expect_revert("at most 10"):
        s.proposed(ta, direct_vm, direct_alice, direct_bob, spec_version=11)
    direct_vm.sender = direct_alice
    ta.cancel_agreement(ids[0])
    s.proposed(ta, direct_vm, direct_alice, direct_bob, spec_version=11)


def test_a_final_outcome_frees_the_requesters_slot(ta, direct_vm, direct_alice, direct_bob):
    for i in range(9):
        s.proposed(ta, direct_vm, direct_alice, direct_bob, spec_version=i + 1)
    agreement_id, _r = s.assessed(ta, direct_vm, direct_alice, direct_bob, spec_version=10)
    with direct_vm.expect_revert("at most 10"):
        s.proposed(ta, direct_vm, direct_alice, direct_bob, spec_version=11)
    direct_vm.warp("2026-09-28T14:00:00Z")
    ta.finalize(agreement_id)
    s.proposed(ta, direct_vm, direct_alice, direct_bob, spec_version=11)


def test_unknown_ids_are_refused_or_reported_absent(ta, direct_vm, direct_bob):
    direct_vm.sender = direct_bob
    for write in (ta.cancel_agreement, ta.decline_agreement, ta.assess, ta.contest,
                  ta.finalize, ta.expire_agreement, ta.lapse_agreement):
        with direct_vm.expect_revert("unknown agreement_id"):
            write("TA-000404")
    with direct_vm.expect_revert("unknown agreement_id"):
        ta.accept_agreement("TA-000404", "00" * 32)
    with direct_vm.expect_revert("unknown agreement_id"):
        ta.deliver_translation("TA-000404", s.TRANSLATION_URL, "00" * 32)
    for view in (ta.get_agreement, ta.get_terms_hash, ta.get_outcome,
                 ta.get_evidence_status, ta.get_history, ta.get_latest_resolution):
        assert view("TA-000404")["found"] is False
    assert ta.get_resolution("TR-000404")["found"] is False
    assert ta.get_actions("TA-000404", s.NOW)["found"] is False


def test_each_transition_happens_once(ta, direct_vm, direct_alice, direct_bob):
    agreement_id, _r = s.assessed(ta, direct_vm, direct_alice, direct_bob)
    with direct_vm.expect_revert("only a DELIVERED agreement is assessed"):
        ta.assess(agreement_id)
    with direct_vm.expect_revert("only a DELIVERED agreement lapses"):
        ta.lapse_agreement(agreement_id)
    with direct_vm.expect_revert("only an ACCEPTED agreement expires"):
        ta.expire_agreement(agreement_id)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("only a PROPOSED agreement can be declined"):
        ta.decline_agreement(agreement_id)
    with direct_vm.expect_revert("only a PROPOSED agreement can be accepted"):
        ta.accept_agreement(agreement_id, ta.get_terms_hash(agreement_id)["terms_hash"])


def test_pages_are_bounded(ta, direct_vm, direct_alice, direct_bob):
    for i in range(3):
        s.proposed(ta, direct_vm, direct_alice, direct_bob, spec_version=i + 1)
    assert ta.list_agreements(1, 1)["ids"] == ["TA-000002"]
    assert ta.list_agreements(0, 51)["ids"] == []
    assert ta.list_agreements(-1, 5)["ids"] == []
    assert ta.list_agreements(0, 5)["total"] == 3


def test_the_time_helpers_round_trip(mod):
    for stamp in ("1970-01-01T00:00:00Z", "2028-02-29T12:00:00Z", "2100-12-31T00:00:00Z"):
        assert mod._epoch_iso(mod._iso_epoch(stamp)) == stamp
    for bad in ("2026-02-29T00:00:00Z", "2026-09-28 12:00:00Z", "2026-09-28T12:00:00"):
        assert mod._iso_epoch(bad) is None


def test_the_code_reason_order_is_the_documented_one(mod):
    ok = {"evidence_id": "SOURCE", "status": "RETRIEVED"}
    tr = {"evidence_id": "TRANSLATION", "status": "RETRIEVED"}
    clean = {"terms": {"a": "PRESENT"}, "missing_numbers": []}
    missing = {"terms": {"a": "MISSING"}, "missing_numbers": ["8"]}
    bad = dict(tr, status="DIGEST_MISMATCH")
    gone = dict(tr, status="NOT_FOUND")
    assert mod._code_reason({}, [ok, bad], ["SOURCE:BODY"], missing) \
        == "EVIDENCE_DIGEST_MISMATCH"
    assert mod._code_reason({}, [ok, gone], ["SOURCE:BODY"], missing) == "DOCUMENT_UNREADABLE"
    assert mod._code_reason({}, [ok, tr], ["SOURCE:BODY"], missing) \
        == "DOCUMENT_ADDRESSES_ASSESSOR"
    assert mod._code_reason({}, [ok, tr], [], missing) == "CRITICAL_TERM_MISSING"
    assert mod._code_reason({}, [ok, tr], [], {"terms": {}, "missing_numbers": ["8"]}) \
        == "NUMBER_NOT_PRESERVED"
    assert mod._code_reason({}, [ok, tr], [], clean) == ""
