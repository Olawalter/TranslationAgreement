#!/usr/bin/env python3
"""Drive the deployed contract through the whole agreement lifecycle with real
transactions, and record what the chain answered.

    python scripts/live_run.py <address> --raw-base <pinned raw url> --phase full

Phases run in order and can be run one at a time: cases, settle, refusals. Every step is recorded in deploy/live_run_transcript.json under a
unique name; re-running skips steps already recorded, so a transport failure or a
rate limit never repeats work and never loses an id. A step whose write reverted
is retried on a resume, and no id is ever guessed for a write that did not
execute.

The documents are served at a pinned commit: the source leaflet from
raw.githubusercontent.com, the translations from the jsDelivr mirror of the same
commit. Both return identical bytes, which is what the declared digests are
taken over.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import studionet_transport  # noqa: E402,F401 - retries RPC transport failures
from genlayer_py import create_account, create_client  # noqa: E402
from genlayer_py.chains import studionet  # noqa: E402
from genlayer_py.types import TransactionStatus  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
KEYS = ROOT / ".data" / "demo_wallets.json"
TRANSCRIPT = ROOT / "deploy" / "live_run_transcript.json"
LOG = ROOT / "deploy" / "live_run.log"
RPC = "https://studio.genlayer.com/api"
WAIT = dict(interval=5000, retries=300)
PHASES = ("cases", "settle", "refusals")


def log(text: str):
    line = time.strftime("%H:%M:%S") + " " + text
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def now_iso(offset: int = 0) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + offset))


# -- the transcript ------------------------------------------------------------

class Transcript:
    def __init__(self, address: str, raw_base: str, path=None):
        self.path = path or TRANSCRIPT
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {"address": address, "raw_base": raw_base,
                         "started_at": now_iso(), "steps": {}, "order": []}
        if self.data["address"] != address:
            sys.exit("the transcript records a different contract; move it aside first")
        self.data["raw_base"] = raw_base

    def has(self, step: str) -> bool:
        return step in self.data["steps"]

    def get(self, step: str) -> dict:
        return self.data["steps"][step]

    def put(self, step: str, entry: dict):
        entry["at"] = now_iso()
        if step not in self.data["steps"]:
            self.data["order"].append(step)
        self.data["steps"][step] = entry
        self.save()

    def save(self):
        self.data["finished_at"] = now_iso()
        self.data["summary"] = self.summary()
        self.path.write_text(json.dumps(self.data, indent=1, sort_keys=True) + "\n",
                             encoding="utf-8")

    def summary(self) -> dict:
        steps = self.data["steps"].values()
        checks = [s for s in steps if "held" in s and s.get("kind") != "refusal"]
        refusals = [s for s in steps if s.get("kind") == "refusal"]
        return {
            "steps": len(self.data["order"]),
            "transactions": len([s for s in steps if s.get("tx")]),
            "outcomes_checked": len(checks),
            "outcomes_held": len([s for s in checks if s["held"]]),
            "missed": sorted(s["step"] for s in checks if not s["held"]),
            "refusals": len(refusals),
            "refusals_held": len([s for s in refusals if s.get("held")]),
        }


# -- the chain -----------------------------------------------------------------

class Chain:
    def __init__(self, address: str, transcript: Transcript):
        self.address = address
        self.transcript = transcript
        keys = json.loads(KEYS.read_text(encoding="utf-8"))
        self.accounts = {name: create_account(account_private_key=key)
                         for name, key in keys.items()}
        self.clients = {name: create_client(chain=studionet, account=account,
                                            endpoint=RPC)
                        for name, account in self.accounts.items()}
        self.reader = self.clients[sorted(self.clients)[0]]

    def address_of(self, wallet: str) -> str:
        return str(self.accounts[wallet].address).lower()

    def read(self, method: str, args=None):
        return self.reader.read_contract(address=self.address, function_name=method,
                                         args=args or [])

    def send(self, step: str, wallet: str, method: str, args=None) -> dict:
        if self.transcript.has(step):
            entry = self.transcript.get(step)
            if entry.get("leader_execution") == "SUCCESS":
                log("  skip " + step + " (recorded " + entry.get("status", "?") + ")")
                return entry
            log("  retry " + step + " (recorded " + str(entry.get("error"))[:80] + ")")
        client = self.clients[wallet]
        log("  " + step + ": " + method + " as " + wallet)
        tx = client.write_contract(address=self.address, function_name=method,
                                   args=args or [])
        receipt = client.wait_for_transaction_receipt(
            transaction_hash=tx, status=TransactionStatus.FINALIZED, **WAIT)
        entry = {"step": step, "kind": "write", "method": method, "wallet": wallet,
                 "args": _plain(args or []), "tx": _hex(tx), "status": _status(receipt),
                 "leader_execution": _execution(receipt), "votes": _votes(receipt),
                 "rounds": _rounds(receipt)}
        if entry["leader_execution"] != "SUCCESS":
            entry["error"] = _revert(receipt)
        self.transcript.put(step, entry)
        log("    " + entry["status"] + "/" + entry["leader_execution"] + " votes "
            + ",".join(entry["votes"]))
        return entry

    def created(self, entry: dict, step: str, method: str, args) -> dict:
        """Read back the id a successful write created. A write that reverted has
        created nothing, so the phase stops rather than guessing."""
        if entry.get("leader_execution") != "SUCCESS":
            raise SystemExit("  " + step + " did not execute: " + str(entry.get("error")))
        page = self.read(method, args)
        if not page["ids"]:
            raise SystemExit("  " + step + " executed but created nothing")
        return page

    def refuse(self, step: str, wallet: str, method: str, args=None,
               because: str = "") -> dict:
        if self.transcript.has(step):
            log("  skip " + step + " (recorded)")
            return self.transcript.get(step)
        client = self.clients[wallet]
        log("  " + step + ": expecting a refusal of " + method)
        entry = {"step": step, "kind": "refusal", "method": method, "wallet": wallet,
                 "args": _plain(args or []), "because": because}
        try:
            tx = client.write_contract(address=self.address, function_name=method,
                                       args=args or [])
            receipt = client.wait_for_transaction_receipt(
                transaction_hash=tx, status=TransactionStatus.FINALIZED, **WAIT)
            entry["tx"] = _hex(tx)
            entry["status"] = _status(receipt)
            entry["leader_execution"] = _execution(receipt)
            entry["error"] = _revert(receipt)
            entry["held"] = entry["leader_execution"] != "SUCCESS"
        except Exception as err:                       # a client-side rejection counts
            entry["error"] = str(err)[:400]
            entry["held"] = True
        self.transcript.put(step, entry)
        log("    refused" if entry["held"] else "    NOT REFUSED - recorded as a miss")
        return entry


def _hex(value) -> str:
    return value if isinstance(value, str) else "0x" + bytes(value).hex()


def _plain(args) -> list:
    out = []
    for value in args:
        text = value if isinstance(value, (str, int, bool)) else str(value)
        if isinstance(text, str) and len(text) > 200:
            text = text[:200] + "... (" + str(len(text)) + " characters)"
        out.append(text)
    return out


def _status(receipt) -> str:
    for key in ("status", "statusName", "status_name"):
        value = receipt.get(key)
        if isinstance(value, str):
            return value
        if value is not None and hasattr(value, "name"):
            return value.name
    return "UNKNOWN"


def _leader(receipt) -> dict:
    data = receipt.get("consensus_data") or {}
    leader = data.get("leader_receipt") or {}
    if isinstance(leader, list):
        leader = leader[0] if leader else {}
    return leader


def _execution(receipt) -> str:
    value = _leader(receipt).get("execution_result")
    return value if isinstance(value, str) else str(value)


def _revert(receipt) -> str:
    result = _leader(receipt).get("result") or {}
    return json.dumps(result)[:400] if not isinstance(result, str) else result[:400]


def _votes(receipt) -> list:
    last = receipt.get("last_round") or {}
    votes = last.get("votes") or (receipt.get("consensus_data") or {}).get("votes") or {}
    if isinstance(votes, dict):
        return [str(v) for v in votes.values()]
    return [str(v) for v in votes]


def _rounds(receipt) -> int:
    data = receipt.get("consensus_data") or {}
    rounds = data.get("rounds") or receipt.get("rounds")
    return len(rounds) if isinstance(rounds, list) else 1


# -- the catalogue -------------------------------------------------------------

def origins(raw_base: str) -> dict:
    prefix = "https://raw.githubusercontent.com/"
    if not raw_base.startswith(prefix):
        sys.exit("--raw-base must be a commit-pinned raw.githubusercontent.com URL")
    owner, repo, commit, rest = raw_base[len(prefix):].split("/", 3)
    return {"base": raw_base,
            "mirror": "https://cdn.jsdelivr.net/gh/" + owner + "/" + repo + "@" + commit
                      + "/" + rest}


def terms_json(template: dict, case: dict, translator: str, hosts: dict, source: str) -> str:
    spec = dict(template, translator=translator, source_url=hosts["base"] + source)
    spec.update(case["terms"])
    return json.dumps(spec, sort_keys=True, ensure_ascii=False)


# -- the phases ----------------------------------------------------------------

def propose(chain: Chain, case: dict, template: dict, hosts: dict, source: str) -> str:
    step = "propose:" + case["case"]
    entry = chain.send(step, case["wallet"], "propose_agreement",
                       [terms_json(template, case, chain.address_of("translator"), hosts,
                                   source)])
    if "agreement_id" not in entry:
        if entry.get("leader_execution") != "SUCCESS":
            raise SystemExit("  " + step + " did not execute: " + str(entry.get("error")))
        total = chain.read("get_stats")["agreements"]
        page = chain.read("list_agreements", [total - 1, 1])
        agreement = chain.read("get_agreement", [page["ids"][0]])
        if agreement["requester"] != chain.address_of(case["wallet"]):
            raise SystemExit("  " + step + ": the newest agreement is not this case's")
        entry["agreement_id"] = page["ids"][0]
        chain.transcript.put(step, entry)
    return entry["agreement_id"]


def accept(chain: Chain, case: dict, agreement_id: str):
    terms_hash = chain.read("get_terms_hash", [agreement_id])["terms_hash"]
    chain.send("accept:" + case["case"], "translator", "accept_agreement",
               [agreement_id, terms_hash])


def deliver(chain: Chain, case: dict, agreement_id: str, hosts: dict):
    chain.send("deliver:" + case["case"], "translator", "deliver_translation",
               [agreement_id, hosts["mirror"] + case["translation"],
                case["translation_sha256"]])


def phase_cases(chain: Chain, cases: dict, template: dict, hosts: dict):
    source = cases["source"]
    # the agreements that must run out of time start first
    for case in cases["cases"]:
        kind = case.get("lifecycle")
        if kind not in ("expire", "lapse"):
            continue
        agreement_id = propose(chain, case, template, hosts, source)
        accept(chain, case, agreement_id)
        if kind == "lapse":
            deliver(chain, case, agreement_id, hosts)
    for case in cases["cases"]:
        kind = case.get("lifecycle")
        if kind in ("expire", "lapse"):
            continue
        name = case["case"]
        agreement_id = propose(chain, case, template, hosts, source)
        if kind == "cancel":
            chain.send("cancel:" + name, case["wallet"], "cancel_agreement", [agreement_id])
            ending(chain, "cancel:" + name, case, agreement_id)
            continue
        if kind == "decline":
            chain.send("decline:" + name, "translator", "decline_agreement", [agreement_id])
            ending(chain, "decline:" + name, case, agreement_id)
            continue
        accept(chain, case, agreement_id)
        deliver(chain, case, agreement_id, hosts)
        step = "assess:" + name
        if chain.transcript.has(step) \
                and chain.transcript.get(step).get("leader_execution") == "SUCCESS":
            log("  skip " + step + " (recorded)")
        else:
            chain.send(step, "keeper", "assess", [agreement_id])
            record(chain, step, name, agreement_id, case)
        # a contest lives inside a window measured from the assessment it contests
        if name == cases["contest_case"]:
            contest_step = "contest:" + name
            if not chain.transcript.has(contest_step):
                chain.send(contest_step, case["wallet"], "contest", [agreement_id])
                record(chain, contest_step, name + ":contest", agreement_id, case,
                       round_two=True)


def ending(chain: Chain, step: str, case: dict, agreement_id: str):
    entry = chain.transcript.get(step)
    answer = chain.read("get_outcome", [agreement_id])
    entry["agreement_id"] = agreement_id
    entry["observed_verdict"] = answer["verdict"]
    entry["observed_reason"] = answer["ending"]
    entry["expected_verdict"] = case["expect_verdict"]
    entry["expected_reason"] = case["expect_reason"]
    entry["held"] = answer["verdict"] == case["expect_verdict"] \
        and answer["ending"] == case["expect_reason"]
    entry["note"] = case["note"]
    chain.transcript.put(step, entry)
    log("    " + case["case"] + ": " + answer["verdict"] + "/" + answer["ending"]
        + (" HELD" if entry["held"] else " MISSED"))


def record(chain: Chain, step: str, label: str, agreement_id: str, case: dict,
           round_two: bool = False):
    entry = chain.transcript.get(step)
    entry["agreement_id"] = agreement_id
    answer = chain.read("get_latest_resolution", [agreement_id])
    if answer.get("found"):
        resolution = answer["resolution"]
        entry["resolution_id"] = resolution["resolution_id"]
        entry["observed_verdict"] = resolution["verdict"]
        entry["observed_reason"] = resolution["reason_code"]
        entry["panel_state"] = resolution["panel_state"]
        entry["markers"] = resolution["markers"]
        entry["checks"] = resolution["checks"]
        entry["deviations"] = resolution["deviations"]
        entry["round"] = resolution["round"]
        entry["supersedes"] = resolution["supersedes"]
        entry["readings"] = {f["id"]: f["state"] for f in resolution["findings"]}
        allowed = case.get("expect_reason_any") or [case["expect_reason"]]
        entry["expected_verdict"] = case["expect_verdict"]
        entry["expected_reason"] = case["expect_reason"] if len(allowed) == 1 \
            else "one of: " + ", ".join(allowed)
        held = resolution["verdict"] == case["expect_verdict"] \
            and resolution["reason_code"] in allowed
        if round_two:
            held = resolution["round"] == 2 and resolution["supersedes"] != ""
            entry["expected_verdict"] = "a second reading, superseding the first"
        entry["held"] = held
        entry["note"] = case["note"]
    else:
        entry["held"] = False
        entry["observed_reason"] = "no resolution stored"
    chain.transcript.put(step, entry)
    log("    " + label + ": " + str(entry.get("observed_verdict")) + "/"
        + str(entry.get("observed_reason")) + (" HELD" if entry["held"] else " MISSED"))


def wait_until(iso: str, what: str):
    target = time.mktime(time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
    while True:
        left = target - time.time()
        if left <= 5:
            return
        log("  waiting " + str(int(left) + 5) + "s for " + what)
        time.sleep(min(left + 5, 120))


def phase_settle(chain: Chain, cases: dict):
    """Finalise the outcomes a consumer should see, read them back through the
    consumer's view, and expire and lapse the agreements that ran out of time."""
    for case in cases["cases"]:
        if not case.get("settle") or not chain.transcript.has("propose:" + case["case"]):
            continue
        agreement_id = chain.transcript.get("propose:" + case["case"])["agreement_id"]
        step = "finalize:" + case["case"]
        state = chain.read("get_agreement", [agreement_id])
        if state["status"] == "ASSESSED" and not chain.transcript.has(step):
            wait_until(state["window_ends"], "the contest window of " + agreement_id)
            chain.send(step, "keeper", "finalize", [agreement_id])
        if not chain.transcript.has(step):
            continue
        entry = chain.transcript.get(step)
        answer = chain.read("get_outcome", [agreement_id])
        entry["consumer_view"] = answer
        entry["held"] = (answer["final"] is True
                         and answer["verdict"] == case["expect_verdict"]
                         and answer["preserved"] == (case["expect_verdict"] == "PRESERVED")
                         and answer["partially_preserved"]
                         == (case["expect_verdict"] == "PARTIALLY_PRESERVED"))
        chain.transcript.put(step, entry)
        log("    " + case["case"] + " consumer view: preserved=" + str(answer["preserved"])
            + " partial=" + str(answer["partially_preserved"])
            + (" HELD" if entry["held"] else " MISSED"))

    for case in cases["cases"]:
        kind = case.get("lifecycle")
        if kind not in ("expire", "lapse") \
                or not chain.transcript.has("propose:" + case["case"]):
            continue
        agreement_id = chain.transcript.get("propose:" + case["case"])["agreement_id"]
        step = kind + ":" + case["case"]
        state = chain.read("get_agreement", [agreement_id])
        if kind == "expire" and state["status"] == "ACCEPTED":
            wait_until(state["delivery_due"], "the delivery window of " + agreement_id)
            chain.send(step, "keeper", "expire_agreement", [agreement_id])
        if kind == "lapse" and state["status"] == "DELIVERED":
            wait_until(state["window_ends"], "the assess window of " + agreement_id)
            chain.send(step, "keeper", "lapse_agreement", [agreement_id])
        if chain.transcript.has(step):
            ending(chain, step, case, agreement_id)

    chain.transcript.data["stats"] = chain.read("get_stats")
    chain.transcript.save()
    log("  stats: " + json.dumps(chain.transcript.data["stats"]))


def phase_refusals(chain: Chain, cases: dict, template: dict, hosts: dict):
    by_code = {c["case"]: c for c in cases["cases"]}
    first = by_code["TA01"]
    faithful = chain.transcript.get("propose:TA01")["agreement_id"]
    informal = chain.transcript.get("propose:TA06")["agreement_id"]
    source = cases["source"]
    me = dict(first, terms={})
    as_self = json.loads(terms_json(template, me, chain.address_of("stranger"), hosts, source))
    same_language = dict(json.loads(terms_json(template, me, chain.address_of("translator"),
                                               hosts, source)), target_language="English")

    chain.refuse("refuse:self_as_translator", "stranger", "propose_agreement",
                 [json.dumps(as_self, sort_keys=True, ensure_ascii=False)],
                 because="the translator must be another account than the requester")
    chain.refuse("refuse:same_language", "stranger", "propose_agreement",
                 [json.dumps(same_language, sort_keys=True, ensure_ascii=False)],
                 because="a translation needs two languages")
    fresh = propose(chain, dict(first, case="REFUSALS", wallet="stranger"), template, hosts,
                    source)
    chain.refuse("refuse:stranger_accepts", "keeper", "accept_agreement",
                 [fresh, chain.read("get_terms_hash", [fresh])["terms_hash"]],
                 because="only the named translator accepts")
    chain.refuse("refuse:wrong_terms_hash", "translator", "accept_agreement",
                 [fresh, "00" * 32], because="the translator accepts the exact terms")
    accept(chain, dict(first, case="REFUSALS"), fresh)
    chain.refuse("refuse:outside_domains", "translator", "deliver_translation",
                 [fresh, "https://translator-own-site.example.com/es.html", "aa" * 32],
                 because="the translation must come from a host the agreement names")
    chain.refuse("refuse:source_as_translation", "translator", "deliver_translation",
                 [fresh, hosts["mirror"] + source, template["source_sha256"]],
                 because="the source's own bytes are not a translation")
    chain.refuse("refuse:stranger_delivers", "stranger", "deliver_translation",
                 [fresh, hosts["mirror"] + first["translation"], first["translation_sha256"]],
                 because="only the named translator delivers")
    chain.refuse("refuse:accepted_cancel", "stranger", "cancel_agreement", [fresh],
                 because="accepted terms can no longer be withdrawn")
    chain.refuse("refuse:double_assessment", "keeper", "assess", [informal],
                 because="an agreement is assessed once, then only contested")
    chain.refuse("refuse:stranger_contest", "stranger", "contest", [informal],
                 because="only the requester or the translator contests")
    chain.refuse("refuse:final_contest", "r01", "contest", [faithful],
                 because="a final outcome is not contested")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("address")
    parser.add_argument("--raw-base", required=True,
                        help="commit-pinned base URL for fixtures/, ending in a slash")
    parser.add_argument("--phase", default="full", choices=("full",) + PHASES)
    parser.add_argument("--transcript", default=None)
    args = parser.parse_args()
    if not args.raw_base.endswith("/"):
        sys.exit("--raw-base must end with a slash")

    hosts = origins(args.raw_base)
    path = pathlib.Path(args.transcript) if args.transcript else None
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        globals()["LOG"] = path.with_suffix(".log")
    transcript = Transcript(args.address, args.raw_base, path)
    template = json.loads((FIXTURES / "terms.json").read_text(encoding="utf-8"))["leaflet"]
    cases = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
    chain = Chain(args.address, transcript)
    log("contract " + args.address + " phase " + args.phase)

    phases = PHASES if args.phase == "full" else (args.phase,)
    for phase in phases:
        log("phase " + phase)
        if phase == "cases":
            phase_cases(chain, cases, template, hosts)
        elif phase == "settle":
            phase_settle(chain, cases)
        elif phase == "refusals":
            phase_refusals(chain, cases, template, hosts)
    log("summary " + json.dumps(transcript.summary()))


if __name__ == "__main__":
    main()
