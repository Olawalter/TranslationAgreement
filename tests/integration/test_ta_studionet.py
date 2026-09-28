"""Reads against the canonical StudioNet deployment.

These tests do not re-run consensus: they check that the contract on chain is the
contract in this repository, that it answers, and that every outcome the live run
recorded is what the chain still holds - including through the view a payment
system would use. One write is opt-in (`TA_LIVE_WRITES=1`), because it sends a
real transaction.

Each test is independently runnable:

    python -m pytest tests/integration -q
    python -m pytest tests/integration -q -k source_is_this_repository
"""

import base64
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

RECORD = ROOT / "deploy" / "deployment.json"
TRANSCRIPT = ROOT / "deploy" / "live_run_transcript.json"
CONTRACT = ROOT / "contracts" / "translation_agreement.py"
RPC = "https://studio.genlayer.com/api"

pytestmark = pytest.mark.skipif(not RECORD.exists(),
                                reason="no canonical deployment recorded yet")


def rpc(method: str, params: list):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    request = urllib.request.Request(RPC, data=body, headers={
        "Content-Type": "application/json", "User-Agent": "ta-integration"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                answer = json.loads(response.read().decode())
            if "error" in answer and "-32029" in json.dumps(answer["error"]):
                raise RuntimeError("rate limited")
            return answer
        except Exception:
            if attempt == 5:
                raise
            time.sleep(5 * (attempt + 1))


@pytest.fixture(scope="module")
def record():
    return json.loads(RECORD.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def client():
    """A read-only client with a throwaway account: nothing under .data/ is needed."""
    import studionet_transport  # noqa: F401 - retries RPC transport failures
    from genlayer_py import create_account, create_client
    from genlayer_py.chains import studionet
    return create_client(chain=studionet, account=create_account(), endpoint=RPC)


def read(client, record, method, args=None):
    return client.read_contract(address=record["contract_address"],
                                function_name=method, args=args or [])


def steps() -> dict:
    return json.loads(TRANSCRIPT.read_text(encoding="utf-8"))["steps"]


def test_the_deployed_source_is_this_repository(record):
    raw = rpc("gen_getContractCode", [record["contract_address"]]).get("result")
    deployed = str(raw).encode()
    if hashlib.sha256(deployed).hexdigest() != record["source_sha256"]:
        deployed = base64.b64decode(raw)
    assert hashlib.sha256(deployed).hexdigest() == record["source_sha256"]
    assert record["source_sha256"] == hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
    assert record["byte_identical"] is True


def test_the_schema_is_the_whole_surface(record):
    schema = rpc("gen_getContractSchema", [record["contract_address"]]).get("result") or {}
    methods = schema.get("methods") or {}
    assert len(methods) == 21
    for name in ("propose_agreement", "accept_agreement", "deliver_translation", "assess",
                 "contest", "finalize", "expire_agreement", "lapse_agreement",
                 "get_outcome", "get_evidence_status", "get_terms_hash"):
        assert name in methods, name


def test_the_config_on_chain_matches_the_contract(client, record):
    config = read(client, record, "get_config")
    assert config["contract_version"] == "0.1.0" and config["payable"] is False
    assert config["verdicts"] == ["PENDING", "PRESERVED", "PARTIALLY_PRESERVED",
                                  "NOT_PRESERVED", "INSUFFICIENT_EVIDENCE", "NONE"]


@pytest.mark.skipif(not TRANSCRIPT.exists(), reason="no live run recorded yet")
def test_every_outcome_the_run_recorded_is_still_on_chain(client, record):
    checked = 0
    for name, entry in sorted(steps().items()):
        if not name.startswith(("assess:", "contest:")) or "resolution_id" not in entry:
            continue
        resolution = read(client, record, "get_resolution", [entry["resolution_id"]])
        assert resolution["found"], name
        assert resolution["resolution"]["verdict"] == entry["observed_verdict"], name
        assert resolution["resolution"]["reason_code"] == entry["observed_reason"], name
        checked += 1
    assert checked > 0


@pytest.mark.skipif(not TRANSCRIPT.exists(), reason="no live run recorded yet")
def test_the_consumer_view_agrees_with_the_records(client, record):
    checked = 0
    for name, entry in sorted(steps().items()):
        if not name.startswith("finalize:") or "consumer_view" not in entry:
            continue
        seen = entry["consumer_view"]
        answer = read(client, record, "get_outcome", [seen["agreement_id"]])
        assert answer["final"] is True, name
        assert answer["verdict"] == seen["verdict"], name
        assert answer["preserved"] == (answer["verdict"] == "PRESERVED"), name
        assert answer["partially_preserved"] == (answer["verdict"] == "PARTIALLY_PRESERVED")
        checked += 1
    assert checked > 0


@pytest.mark.skipif(not TRANSCRIPT.exists(), reason="no live run recorded yet")
def test_the_code_decided_outcomes_never_convened_a_panel(client, record):
    decided = 0
    for name, entry in steps().items():
        if name.startswith("assess:") and entry.get("observed_reason") in (
                "CRITICAL_TERM_MISSING", "NUMBER_NOT_PRESERVED", "DOCUMENT_UNREADABLE",
                "EVIDENCE_DIGEST_MISMATCH", "DOCUMENT_ADDRESSES_ASSESSOR"):
            resolution = read(client, record, "get_resolution",
                              [entry["resolution_id"]])["resolution"]
            assert resolution["panel_state"] == "SKIPPED", name
            assert all(f["by"] == "CODE" for f in resolution["findings"]), name
            decided += 1
    assert decided > 0


@pytest.mark.skipif(not TRANSCRIPT.exists(), reason="no live run recorded yet")
def test_a_material_finding_quotes_the_document_it_is_about(client, record):
    for name, entry in steps().items():
        if not name.startswith("assess:") or entry.get("panel_state") != "ASSESSED":
            continue
        resolution = read(client, record, "get_resolution",
                          [entry["resolution_id"]])["resolution"]
        for finding in resolution["findings"]:
            if finding["id"] == "OMISSION" and finding["state"] in ("MINOR", "MATERIAL"):
                assert {q["evidence_id"] for q in finding["quotes"]} == {"SOURCE"}, name
            if finding["id"] in ("DISTORTION", "ADDITION") \
                    and finding["state"] in ("MINOR", "MATERIAL"):
                assert {q["evidence_id"] for q in finding["quotes"]} == {"TRANSLATION"}, name


@pytest.mark.skipif(os.environ.get("TA_LIVE_WRITES") != "1",
                    reason="set TA_LIVE_WRITES=1 to send one transaction")
def test_an_agreement_can_still_be_proposed(record):
    import studionet_transport  # noqa: F401
    from genlayer_py import create_account, create_client
    from genlayer_py.chains import studionet
    from genlayer_py.types import TransactionStatus
    keys = json.loads((ROOT / ".data" / "demo_wallets.json").read_text(encoding="utf-8"))
    writer = create_client(chain=studionet, account=create_account(
        account_private_key=keys["keeper"]), endpoint=RPC)
    spec = json.loads((ROOT / "fixtures" / "terms.json").read_text(encoding="utf-8"))["leaflet"]
    wallets = json.loads((ROOT / "fixtures" / "wallets.json").read_text(encoding="utf-8"))
    run = json.loads(TRANSCRIPT.read_text(encoding="utf-8"))
    spec = dict(spec, translator=wallets["translator"],
                source_url=run["raw_base"] + "evidence/leaflet-en.html")
    before = read(writer, record, "get_stats")["agreements"]
    tx = writer.write_contract(address=record["contract_address"],
                               function_name="propose_agreement",
                               args=[json.dumps(spec, sort_keys=True, ensure_ascii=False)])
    writer.wait_for_transaction_receipt(transaction_hash=tx,
                                        status=TransactionStatus.FINALIZED,
                                        interval=5000, retries=240)
    assert read(writer, record, "get_stats")["agreements"] == before + 1
