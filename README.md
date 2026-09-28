<p align="center">
  <img src="docs/assets/ta-mark.svg" width="84" height="84" alt="TranslationAgreement">
</p>

<h1 align="center">TranslationAgreement</h1>

## Thesis

**TranslationAgreement is a reusable GenLayer Intelligent Contract that decides
whether a translation preserves what its requester and translator agreed, before
the translation existed, that it must - nothing material distorted, omitted or
added, every critical term rendered as agreed, every requirement met - and
records a typed outcome a payment system reads in one call.**

<!-- DEPLOYMENT:START -->
## Canonical deployment

[`0xB4162264cB70FdC774951a236ED3d18a32ccb680`](https://explorer-studio.genlayer.com/address/0xB4162264cB70FdC774951a236ED3d18a32ccb680)
on GenLayer StudioNet (chain id 61999), from commit `20b76b2`, deployed source
read back with `gen_getContractCode` and **byte-identical** to this repository.
Deployment transaction
[`0xbddf808e0d4ede93187f5e0ec961f87652730b6126e9980c4fe69dedcd0ad6d3`](https://explorer-studio.genlayer.com/tx/0xbddf808e0d4ede93187f5e0ec961f87652730b6126e9980c4fe69dedcd0ad6d3),
FINALIZED, leader execution SUCCESS, votes AGREE x5. It supersedes a first
deployment (`deploy/superseded/0x711dd6ed/`) that asked a requirement read as
met for a quote - see [`DECISION.md`](DECISION.md#the-panels-subjects).
<!-- DEPLOYMENT:END -->

## The problem

A requester commissions a translation of a document someone will act on - a
medicine leaflet, a contract clause, a safety notice - and both sides agree what
it must preserve. When the translation arrives, one party says it is faithful.
Today that is settled by the translator's word, the requester's word, or one
reviewer in private.

Byte equality cannot settle it by construction. Two faithful translations of one
sentence share almost no bytes; an unfaithful one can differ by a single word -
"every 8 hours" becoming "every 4". Meaning has to be read, in two languages, by
several independent readers who must agree on what they found.

## Why GenLayer

- the question is semantic, across two languages;
- the parties have opposite interests in the answer;
- a leader's proposed reading must be refusable on substance by validators who
  read both documents themselves;
- a payment system needs a record it can act on without trusting either party.

## Delete GenLayer: what breaks?

One of the parties - or one reviewer - decides whether their own agreement was
met. A string diff says every faithful translation is wrong; a single model call
is one private opinion.

## The model is never asked the question

It is never asked whether meaning is preserved - that question is the verdict.
It reports what it finds, dimension by dimension, and must quote the document
each finding is about:

| Reading | States | Must quote |
|---|---|---|
| `DISTORTION` | NONE, MINOR, MATERIAL | the translation |
| `OMISSION` | NONE, MINOR, MATERIAL | the **source** - what went missing |
| `ADDITION` | NONE, MINOR, MATERIAL | the translation |
| `TERM_<id>` | CORRECT, INCORRECT | the translation, if incorrect |
| `REQ_<id>` | MET, NOT_MET | the breaking passage, if not met |

MATERIAL means a reader would act differently. Code derives the outcome.

## Two rules code decides exactly

| Rule | Reason |
|---|---|
| each critical term the source uses must appear as one of its agreed renderings | `CRITICAL_TERM_MISSING` |
| every number in the source must survive - **counted**, so a leaflet that says 8 twice must say 8 twice | `NUMBER_NOT_PRESERVED` |

Neither reaches the panel. A dose changed from every 8 hours to every 4 is caught
by counting even though another 8 remains on the page.

## Outcomes

| Verdict | Means |
|---|---|
| `PRESERVED` | no deviation, every term correct, every required requirement met |
| `PARTIALLY_PRESERVED` | only MINOR deviations |
| `NOT_PRESERVED` | a material distortion, omission or addition, a misrendered or missing term, a changed number, or an unmet requirement |
| `INSUFFICIENT_EVIDENCE` | a document could not be read, was not the one agreed, addressed the assessor, or a reading was unclear - never a verdict about the translation |

## Lifecycle

```
propose ─► PROPOSED ─accept─► ACCEPTED ─deliver─► DELIVERED ─assess─► ASSESSED ─finalize─► FINAL
              │                   │                    │                  │
      cancel / decline            └─ expire            └─ lapse           └─ contest (either party, once)
```

## Contract surface

| Writes | |
|---|---|
| `propose_agreement`, `cancel_agreement`, `decline_agreement`, `accept_agreement` | fixing the terms, bound by hash |
| `deliver_translation` | once, by the named translator, bound to its sha256 |
| `assess`, `contest` | one consensus round each |
| `finalize`, `expire_agreement`, `lapse_agreement` | permissionless exits after the relevant window |

| Views | |
|---|---|
| `get_outcome` | the consumer's one call: verdict, reason, final, preserved |
| `get_agreement`, `get_terms_hash` | the terms, the parties, the delivery |
| `get_evidence_status` | both documents, the markers, the code checks |
| `get_resolution`, `get_latest_resolution`, `get_history` | every reading and the passage it quotes |
| `get_actions`, `list_agreements`, `get_stats`, `get_config` | what may happen next, paging, counts, vocabulary |

21 methods: 11 views, 10 writes, none payable.

## Equivalence / validator design

Validators reproduce the round from their own retrieval and their own model
call, then compare what was retrieved and checked - both documents in full, the
markers, the term and number checks - and the consequence: the verdict and the
reason. Not compared: notes, which passage was quoted, readings no rule reached.
[`docs/CONSENSUS.md`](docs/CONSENSUS.md).

## Reuse surface

```python
answer = ITranslationAgreement(TA).view().get_outcome(agreement_id)
if not answer["preserved"]:
    raise gl.vm.UserError("[EXPECTED] no final PRESERVED outcome for that agreement")
```

Three consumers: a payment or escrow system releasing on `preserved`, a
regulator or auditor reading every quoted passage behind a safety document's
translation, and a translation marketplace reading a translator's outcomes.
[`docs/INTEGRATION.md`](docs/INTEGRATION.md).

## Limitations

- **Meaning, not quality.** Style and fluency are NONE unless written in as
  requirements.
- **Absence is a reading.** An omission quote proves the passage is in the
  source, not that it is missing from the translation; independent readers must
  agree on that.
- The MINOR / MATERIAL line is a judgement, defined (would a reader act
  differently?) and compared; where honest models split, nothing is stored.
- Term and number checks are string rules and catch exactly what they say.
- One contest per agreement, for whichever party uses it first.
- The leaflet in the demonstration is a fixture; it describes no real product and
  is not medical advice.

## Verification

<!-- VERIFIED:START -->
| Check | Result |
|---|---|
| `python -m pytest tests/direct -q` | 114 passed |
| pickling of the nondeterministic closures | checked (`direct_vm.check_pickling = True`) |
| `genvm-lint check contracts/translation_agreement.py --json` (`GENVM_VERSION=v0.3.0-rc7`) | lint ok (3 checks), validation ok, 21 methods (11 view, 10 write), exit 0 |
| `ruff check .` | clean |
| `python scripts/generate_fixtures.py --check` | 12 fixture files regenerate byte for byte |
| `python scripts/mutation_check.py` | 80 mutations, **80 killed, 0 survived** |
| `python scripts/deploy_studionet.py --verify` | deployed and repository sha256 equal, 21 schema methods |
| `python -m pytest tests/integration -q` | 7 passed, 1 skipped (the opt-in live write) |
| live run of record | 72 transactions, **19 of 19 outcomes held**, 11 of 11 refusals refused |

Every outcome was reached by real transactions against the canonical
deployment: a faithful translation preserved and upheld on contest, a minor
addition partially preserved, a dropped warning, a reversed warning and an
invented safety claim each not preserved on the dimension they break, informal
address against an agreed requirement, a synonym and a changed dose decided in
code, and an injection, a wrong digest and an unpublished translation each
insufficient - never a verdict. Four diagnostic passes came first and each
changed something, including the contract itself:
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md#how-the-live-evidence-was-reached).
<!-- VERIFIED:END -->

## Reviewer fast path

1. [`DECISION.md`](DECISION.md) - the specification, written before the
   contract, and what changed after the diagnostic passes and why.
2. [`docs/CONSENSUS.md`](docs/CONSENSUS.md) - the calls, which document a
   reading may quote, what validators compare.
3. `contracts/translation_agreement.py` - `_verdict_for` is the derivation;
   `_checks` holds the two exact rules; `_quotable` the which-document rule.
4. [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) - every transaction of the run of
   record, and the diagnostic passes that shaped the fixtures.
5. `tests/direct/test_ta_adversarial.py` - forged readings, quotes from the wrong
   document, injections and their evasions.

## Licence

MIT. See [`LICENSE`](LICENSE).
