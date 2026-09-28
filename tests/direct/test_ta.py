"""The lifecycle, the outcomes and the views a consumer reads.

Each test drives the contract the way the parties would - propose, accept,
deliver, assess, contest, finalise - and checks what the contract stored.
"""

from tests.direct import support as s

LATER = "2026-09-28T14:00:00Z"
NEXT_DAY = "2026-09-29T12:00:01Z"


def outcome(ta, agreement_id) -> tuple:
    o = ta.get_outcome(agreement_id)
    return (o["verdict"], o["reason_code"])


# -- the agreement -------------------------------------------------------------

def test_terms_are_proposed_with_their_hash(ta, direct_vm, direct_alice, direct_bob, mod):
    agreement_id = s.proposed(ta, direct_vm, direct_alice, direct_bob)
    info = ta.get_agreement(agreement_id)
    assert info["found"] and agreement_id == "TA-000001"
    assert info["requester"] == s.address(direct_alice)
    assert info["translator"] == s.address(direct_bob)
    assert info["status"] == "PROPOSED" and info["verdict"] == "PENDING"
    assert info["terms_hash"] == mod._sha256_hex(mod._canonical(info["terms"]))
    assert ta.get_terms_hash(agreement_id)["translator"] == s.address(direct_bob)


def test_only_the_named_translator_accepts_the_exact_terms(ta, direct_vm, direct_alice,
                                                          direct_bob, direct_charlie):
    agreement_id = s.proposed(ta, direct_vm, direct_alice, direct_bob)
    digest = ta.get_terms_hash(agreement_id)["terms_hash"]
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("only the named translator accepts"):
        ta.accept_agreement(agreement_id, digest)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("terms_hash does not match"):
        ta.accept_agreement(agreement_id, "00" * 32)
    assert ta.accept_agreement(agreement_id, digest) == "ACCEPTED"
    info = ta.get_agreement(agreement_id)
    assert info["delivery_due"] == "2026-09-29T12:00:00Z"


def test_the_translator_may_decline_and_the_requester_may_cancel(ta, direct_vm,
                                                                 direct_alice, direct_bob):
    first = s.proposed(ta, direct_vm, direct_alice, direct_bob)
    direct_vm.sender = direct_bob
    assert ta.decline_agreement(first) == "CANCELLED"
    assert ta.get_agreement(first)["ending"] == "DECLINED"
    assert ta.get_outcome(first)["verdict"] == "NONE"
    second = s.proposed(ta, direct_vm, direct_alice, direct_bob)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("only the requester cancels"):
        ta.cancel_agreement(second)
    direct_vm.sender = direct_alice
    assert ta.cancel_agreement(second) == "CANCELLED"
    assert ta.get_agreement(second)["ending"] == "CANCELLED"


def test_accepted_terms_can_no_longer_be_cancelled(ta, direct_vm, direct_alice, direct_bob):
    agreement_id = s.accepted(ta, direct_vm, direct_alice, direct_bob)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("only a PROPOSED agreement can be cancelled"):
        ta.cancel_agreement(agreement_id)


def test_a_delivery_binds_the_translation_to_its_bytes(ta, direct_vm, direct_alice,
                                                       direct_bob, mod):
    agreement_id = s.delivered(ta, direct_vm, direct_alice, direct_bob)
    info = ta.get_agreement(agreement_id)
    assert info["status"] == "DELIVERED"
    assert info["translation_url"] == s.TRANSLATION_URL
    assert info["translation_sha256"] == s.digest(s.FAITHFUL)
    assert info["commitment"] == mod._sha256_hex(mod._canonical({
        "agreement_id": agreement_id, "terms_hash": info["terms_hash"],
        "translation_url": s.TRANSLATION_URL,
        "translation_sha256": s.digest(s.FAITHFUL)}))
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("only an ACCEPTED agreement takes a delivery"):
        ta.deliver_translation(agreement_id, s.OTHER_URL, s.digest(s.FAITHFUL))


def test_a_delivery_after_the_deadline_is_refused_and_the_agreement_expires(
        ta, direct_vm, direct_alice, direct_bob, direct_charlie):
    agreement_id = s.accepted(ta, direct_vm, direct_alice, direct_bob)
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("the delivery window closes at"):
        ta.expire_agreement(agreement_id)
    direct_vm.warp(NEXT_DAY)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("the delivery window closed at"):
        ta.deliver_translation(agreement_id, s.TRANSLATION_URL, s.digest(s.FAITHFUL))
    direct_vm.sender = direct_charlie
    assert ta.expire_agreement(agreement_id) == "EXPIRED"
    assert ta.get_outcome(agreement_id)["ending"] == "EXPIRED"


def test_get_config_publishes_the_vocabulary(ta):
    config = ta.get_config()
    assert config["contract_version"] == "0.1.0" and config["payable"] is False
    assert config["verdicts"] == ["PENDING", "PRESERVED", "PARTIALLY_PRESERVED",
                                  "NOT_PRESERVED", "INSUFFICIENT_EVIDENCE", "NONE"]
    assert config["deviation_states"] == ["NONE", "MINOR", "MATERIAL", "UNCLEAR"]
    assert set(config["code_reasons"]) <= set(config["reason_codes"])


# -- the outcomes --------------------------------------------------------------

def test_a_faithful_translation_is_preserved(ta, direct_vm, direct_alice, direct_bob):
    agreement_id, resolution_id = s.assessed(ta, direct_vm, direct_alice, direct_bob)
    assert outcome(ta, agreement_id) == ("PRESERVED", "MEANING_PRESERVED")
    rec = s.record(ta, resolution_id)
    assert rec["checks"] == {"missing_numbers": [],
                             "terms": {"ingredient": "PRESENT", "tablet": "PRESENT"}}
    assert rec["deviations"] == {"ADDITION": "NONE", "DISTORTION": "NONE",
                                 "OMISSION": "NONE"}
    assert all(f["compared"] for f in rec["findings"])
    assert ta.get_stats()["preserved"] == 1


def test_a_minor_deviation_is_partially_preserved(ta, direct_vm, direct_alice, direct_bob):
    body = s.translation((s.T_DOSE, s.T_DOSE_NO_WATER))
    subjects = s.faithful_said(omission="MINOR",
                               quotes={"OMISSION": [("SOURCE", "with a glass of water")]})
    agreement_id, resolution_id = s.assessed(ta, direct_vm, direct_alice, direct_bob,
                                             subjects=subjects, body=body)
    assert outcome(ta, agreement_id) == ("PARTIALLY_PRESERVED", "MINOR_DEVIATIONS")
    compared = {f["id"]: f["compared"] for f in s.record(ta, resolution_id)["findings"]}
    assert compared == {"DISTORTION": False, "OMISSION": False, "ADDITION": False,
                        "TERM_INGREDIENT": True, "TERM_TABLET": True,
                        "REQ_FORMAL_ADDRESS": True}


def test_a_material_omission_is_not_preserved(ta, direct_vm, direct_alice, direct_bob):
    body = s.translation(drop=(s.T_ALCOHOL,))
    agreement_id, resolution_id = s.assessed(
        ta, direct_vm, direct_alice, direct_bob, body=body,
        subjects=s.faithful_said(omission="MATERIAL"))
    assert outcome(ta, agreement_id) == ("NOT_PRESERVED", "MATERIAL_OMISSION")
    omission = s.finding_in(s.record(ta, resolution_id), "OMISSION")
    assert omission["quotes"] == [{"evidence_id": "SOURCE", "text": s.S_ALCOHOL}]
    assert omission["compared"] is True


def test_a_material_distortion_is_not_preserved(ta, direct_vm, direct_alice, direct_bob):
    body = s.translation((s.T_PREGNANT, s.T_PREGNANT_DISTORTED))
    subjects = s.faithful_said(distortion="MATERIAL", quotes={
        "DISTORTION": [("TRANSLATION", s.T_PREGNANT_DISTORTED)]})
    agreement_id, _r = s.assessed(ta, direct_vm, direct_alice, direct_bob, body=body,
                                  subjects=subjects)
    assert outcome(ta, agreement_id) == ("NOT_PRESERVED", "MATERIAL_DISTORTION")


def test_a_material_addition_is_not_preserved(ta, direct_vm, direct_alice, direct_bob):
    body = s.translation(add=(s.T_ADDED,))
    agreement_id, _r = s.assessed(ta, direct_vm, direct_alice, direct_bob, body=body,
                                  subjects=s.faithful_said(addition="MATERIAL"))
    assert outcome(ta, agreement_id) == ("NOT_PRESERVED", "MATERIAL_ADDITION")


def test_a_misrendered_term_is_not_preserved(ta, direct_vm, direct_alice, direct_bob):
    agreement_id, _r = s.assessed(ta, direct_vm, direct_alice, direct_bob,
                                  subjects=s.faithful_said(tablet="INCORRECT"))
    assert outcome(ta, agreement_id) == ("NOT_PRESERVED", "TERM_MISRENDERED")


def test_a_requirement_not_met_is_not_preserved(ta, direct_vm, direct_alice, direct_bob):
    body = s.translation((s.T_DOSE, s.T_DOSE_INFORMAL))
    subjects = s.faithful_said(formal="NOT_MET", quotes={
        "REQ_FORMAL_ADDRESS": [("TRANSLATION", s.T_DOSE_INFORMAL)]})
    agreement_id, _r = s.assessed(ta, direct_vm, direct_alice, direct_bob, body=body,
                                  subjects=subjects)
    assert outcome(ta, agreement_id) == ("NOT_PRESERVED", "REQUIREMENT_NOT_MET")


def test_a_missing_critical_term_is_decided_in_code(ta, direct_vm, direct_alice,
                                                    direct_bob):
    body = s.translation((s.T_USE, s.T_USE_OTHER_NAME), title="Acetaminofén 500 mg - prospecto")
    agreement_id, resolution_id = s.assessed(ta, direct_vm, direct_alice, direct_bob,
                                             body=body)
    assert outcome(ta, agreement_id) == ("NOT_PRESERVED", "CRITICAL_TERM_MISSING")
    rec = s.record(ta, resolution_id)
    assert rec["panel_state"] == "SKIPPED"
    assert rec["checks"]["terms"] == {"ingredient": "MISSING", "tablet": "PRESENT"}


def test_a_changed_number_is_decided_in_code_even_when_it_still_appears(ta, direct_vm,
                                                                        direct_alice,
                                                                        direct_bob):
    """The source says 8 twice; the translation changes one to 4 and still says 8
    once. Counting, not presence, is what catches it."""
    body = s.translation((s.T_DOSE, s.T_DOSE_CHANGED))
    agreement_id, resolution_id = s.assessed(ta, direct_vm, direct_alice, direct_bob,
                                             body=body)
    assert outcome(ta, agreement_id) == ("NOT_PRESERVED", "NUMBER_NOT_PRESERVED")
    rec = s.record(ta, resolution_id)
    assert rec["checks"]["missing_numbers"] == ["8"] and rec["panel_state"] == "SKIPPED"


def test_numbers_are_not_checked_when_the_terms_do_not_ask(ta, direct_vm, direct_alice,
                                                           direct_bob):
    body = s.translation((s.T_DOSE, s.T_DOSE_CHANGED))
    agreement_id, resolution_id = s.assessed(
        ta, direct_vm, direct_alice, direct_bob, body=body, preserve_numbers=False,
        subjects=s.faithful_said(distortion="MATERIAL", quotes={
            "DISTORTION": [("TRANSLATION", s.T_DOSE_CHANGED)]}))
    assert outcome(ta, agreement_id) == ("NOT_PRESERVED", "MATERIAL_DISTORTION")
    assert s.record(ta, resolution_id)["checks"]["missing_numbers"] == []


def test_a_term_the_source_never_uses_asks_for_nothing(ta, direct_vm, direct_alice,
                                                       direct_bob):
    extra = s.terms("0x0")["critical_terms"] + [s.term("dosage", "dosage", ["posología"])]
    agreement_id, resolution_id = s.assessed(ta, direct_vm, direct_alice, direct_bob,
                                             critical_terms=extra,
                                             subjects=dict(s.faithful_said(),
                                                           TERM_DOSAGE=s.said("UNCLEAR")))
    assert outcome(ta, agreement_id) == ("PRESERVED", "MEANING_PRESERVED")
    rec = s.record(ta, resolution_id)
    assert rec["checks"]["terms"]["dosage"] == "NOT_IN_SOURCE"
    assert s.finding_in(rec, "TERM_DOSAGE")["compared"] is False


def test_an_unclear_reading_is_insufficient(ta, direct_vm, direct_alice, direct_bob):
    agreement_id, _r = s.assessed(ta, direct_vm, direct_alice, direct_bob,
                                  subjects=s.faithful_said(omission="UNCLEAR"))
    assert outcome(ta, agreement_id) == ("INSUFFICIENT_EVIDENCE", "READING_UNCLEAR")


def test_a_material_finding_outranks_an_unclear_one(ta, direct_vm, direct_alice, direct_bob):
    agreement_id, _r = s.assessed(ta, direct_vm, direct_alice, direct_bob,
                                  subjects=s.faithful_said(omission="MATERIAL",
                                                           distortion="UNCLEAR"))
    assert outcome(ta, agreement_id) == ("NOT_PRESERVED", "MATERIAL_OMISSION")


def test_an_unreadable_document_is_insufficient_not_a_verdict(ta, direct_vm, direct_alice,
                                                              direct_bob):
    agreement_id, resolution_id = s.assessed(ta, direct_vm, direct_alice, direct_bob,
                                             pages={s.TRANSLATION_URL: None})
    assert outcome(ta, agreement_id) == ("INSUFFICIENT_EVIDENCE", "DOCUMENT_UNREADABLE")
    rec = s.record(ta, resolution_id)
    assert s.source_in(rec, "TRANSLATION")["status"] == "NOT_FOUND"
    assert rec["checks"] == {"missing_numbers": [], "terms": {}}


def test_bytes_that_are_not_the_ones_delivered_are_insufficient(ta, direct_vm, direct_alice,
                                                                direct_bob):
    swapped = s.translation(drop=(s.T_ALCOHOL,))
    agreement_id, resolution_id = s.assessed(ta, direct_vm, direct_alice, direct_bob,
                                             pages={s.TRANSLATION_URL: swapped})
    assert outcome(ta, agreement_id) == ("INSUFFICIENT_EVIDENCE", "EVIDENCE_DIGEST_MISMATCH")
    assert s.source_in(s.record(ta, resolution_id), "TRANSLATION")["status"] \
        == "DIGEST_MISMATCH"


def test_a_source_that_changed_since_the_terms_is_insufficient(ta, direct_vm, direct_alice,
                                                               direct_bob):
    edited = s.page("Paracetamol 500 mg - patient leaflet", [s.S_USE, s.S_DOSE])
    agreement_id, resolution_id = s.assessed(ta, direct_vm, direct_alice, direct_bob,
                                             pages={s.SOURCE_URL: edited})
    assert outcome(ta, agreement_id) == ("INSUFFICIENT_EVIDENCE", "EVIDENCE_DIGEST_MISMATCH")
    assert s.source_in(s.record(ta, resolution_id), "SOURCE")["status"] == "DIGEST_MISMATCH"


def test_a_translation_addressing_the_assessor_stops_the_round(ta, direct_vm, direct_alice,
                                                               direct_bob):
    body = s.translation(add=(s.INJECTION,))
    agreement_id, resolution_id = s.assessed(ta, direct_vm, direct_alice, direct_bob,
                                             body=body)
    assert outcome(ta, agreement_id) == ("INSUFFICIENT_EVIDENCE",
                                         "DOCUMENT_ADDRESSES_ASSESSOR")
    assert s.record(ta, resolution_id)["markers"] == ["TRANSLATION:BODY"]


def test_a_translators_certification_is_not_an_injection(ta, direct_vm, direct_alice,
                                                         direct_bob):
    body = s.translation(add=(s.CERTIFICATION,))
    agreement_id, resolution_id = s.assessed(ta, direct_vm, direct_alice, direct_bob,
                                             body=body)
    assert outcome(ta, agreement_id) == ("PRESERVED", "MEANING_PRESERVED")
    assert s.record(ta, resolution_id)["markers"] == []


# -- windows, contest, finality ------------------------------------------------

def test_an_unassessed_delivery_lapses(ta, direct_vm, direct_alice, direct_bob,
                                       direct_charlie):
    agreement_id = s.delivered(ta, direct_vm, direct_alice, direct_bob)
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("the assess window closes at"):
        ta.lapse_agreement(agreement_id)
    direct_vm.warp(LATER)
    s.panel(direct_vm, s.faithful_said())
    with direct_vm.expect_revert("the assess window closed at"):
        ta.assess(agreement_id)
    assert ta.lapse_agreement(agreement_id) == "LAPSED"
    assert ta.get_outcome(agreement_id)["verdict"] == "NONE"


def test_a_contest_is_a_second_reading_of_the_same_bytes(ta, direct_vm, direct_alice,
                                                         direct_bob):
    agreement_id, first = s.assessed(ta, direct_vm, direct_alice, direct_bob,
                                     subjects=s.faithful_said(omission="UNCLEAR"))
    assert ta.get_outcome(agreement_id)["verdict"] == "INSUFFICIENT_EVIDENCE"
    s.panel(direct_vm, s.faithful_said())
    direct_vm.sender = direct_bob
    second = ta.contest(agreement_id)
    rec = s.record(ta, second)
    assert rec["mode"] == "CONTEST" and rec["round"] == 2 and rec["supersedes"] == first
    assert ta.get_outcome(agreement_id)["verdict"] == "PRESERVED"
    with direct_vm.expect_revert("contested once already"):
        ta.contest(agreement_id)
    assert [r["mode"] for r in ta.get_history(agreement_id)["rounds"]] == ["ASSESS",
                                                                          "CONTEST"]


def test_only_a_party_contests(ta, direct_vm, direct_alice, direct_bob, direct_charlie):
    agreement_id, _r = s.assessed(ta, direct_vm, direct_alice, direct_bob)
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("only the requester or the translator contests"):
        ta.contest(agreement_id)
    s.panel(direct_vm, s.faithful_said(omission="MATERIAL"))
    direct_vm.sender = direct_alice
    ta.contest(agreement_id)
    assert ta.get_outcome(agreement_id)["verdict"] == "NOT_PRESERVED"
    assert ta.get_stats()["preserved"] == 0


def test_the_outcome_is_final_only_after_the_contest_window(ta, direct_vm, direct_alice,
                                                            direct_bob):
    agreement_id, _r = s.assessed(ta, direct_vm, direct_alice, direct_bob)
    answer = ta.get_outcome(agreement_id)
    assert answer["verdict"] == "PRESERVED" and answer["preserved"] is False
    with direct_vm.expect_revert("the contest window closes at"):
        ta.finalize(agreement_id)
    direct_vm.warp(LATER)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("the contest window closed at"):
        ta.contest(agreement_id)
    assert ta.finalize(agreement_id) == "FINAL"
    answer = ta.get_outcome(agreement_id)
    assert answer["final"] is True and answer["preserved"] is True
    with direct_vm.expect_revert("only an ASSESSED agreement is finalized"):
        ta.finalize(agreement_id)


def test_a_partial_outcome_reads_as_such_once_final(ta, direct_vm, direct_alice, direct_bob):
    subjects = s.faithful_said(addition="MINOR", quotes={
        "ADDITION": [("TRANSLATION", s.T_CHILDREN)]})
    agreement_id, _r = s.assessed(ta, direct_vm, direct_alice, direct_bob, subjects=subjects)
    direct_vm.warp(LATER)
    ta.finalize(agreement_id)
    answer = ta.get_outcome(agreement_id)
    assert answer["preserved"] is False and answer["partially_preserved"] is True


def test_the_actions_view_follows_the_lifecycle(ta, direct_vm, direct_alice, direct_bob):
    agreement_id = s.proposed(ta, direct_vm, direct_alice, direct_bob)
    actions = ta.get_actions(agreement_id, s.NOW)
    assert actions["may_accept"] and actions["may_cancel"] and not actions["may_deliver"]
    direct_vm.sender = direct_bob
    ta.accept_agreement(agreement_id, ta.get_terms_hash(agreement_id)["terms_hash"])
    assert ta.get_actions(agreement_id, s.NOW)["may_deliver"] is True
    assert ta.get_actions(agreement_id, NEXT_DAY)["may_expire"] is True
    s.serve_all(direct_vm)
    ta.deliver_translation(agreement_id, s.TRANSLATION_URL, s.digest(s.FAITHFUL))
    assert ta.get_actions(agreement_id, s.NOW)["may_assess"] is True
    assert ta.get_actions(agreement_id, LATER)["may_lapse"] is True
    s.panel(direct_vm, s.faithful_said())
    ta.assess(agreement_id)
    assert ta.get_actions(agreement_id, s.NOW)["may_contest"] is True
    assert ta.get_actions(agreement_id, LATER)["may_finalize"] is True


def test_the_evidence_status_view(ta, direct_vm, direct_alice, direct_bob):
    agreement_id = s.delivered(ta, direct_vm, direct_alice, direct_bob)
    assert ta.get_evidence_status(agreement_id)["documents"] == []
    s.panel(direct_vm, s.faithful_said())
    ta.assess(agreement_id)
    status = ta.get_evidence_status(agreement_id)
    assert [d["status"] for d in status["documents"]] == ["RETRIEVED", "RETRIEVED"]
    assert status["documents"][1]["raw_sha256"] == s.digest(s.FAITHFUL)
    assert status["checks"]["terms"] == {"ingredient": "PRESENT", "tablet": "PRESENT"}
