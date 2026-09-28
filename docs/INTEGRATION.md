# Integration

How a payment system, an escrow or another Intelligent Contract reads a
translation outcome without reinterpreting storage.

## The consumer's interface

```python
@gl.contract_interface
class ITranslationAgreement:
    class View:
        def get_outcome(self, agreement_id: str) -> dict: ...
        def get_terms_hash(self, agreement_id: str) -> dict: ...

    class Write:
        pass
```

Releasing payment on a faithful translation, inside another contract:

```python
TA = Address("0x...")                   # the canonical deployment

answer = ITranslationAgreement(TA).view().get_outcome(agreement_id)
if not answer["preserved"]:
    raise gl.vm.UserError("[EXPECTED] no final PRESERVED outcome for that agreement")
# from here the consumer's own rules apply
```

`preserved` is already the conjunction a consumer wants: the outcome is
`PRESERVED` and final. `partially_preserved` is the same for
`PARTIALLY_PRESERVED`. No web access, no prompt, no equivalence principle, no
parsing of the documents.

A consumer that pays against specific terms should also check
`answer["terms_hash"]` against the hash it expects, so it is paying for the
agreement it thinks it is.

## What each view answers

| Method | Returns |
|---|---|
| `get_outcome(agreement_id)` | `verdict`, `reason_code`, `final`, `preserved`, `partially_preserved`, `status`, `ending`, the `terms_hash`, the latest `resolution_id`, `rounds` |
| `get_agreement(agreement_id)` | the terms as proposed, both parties, every timestamp, the delivered translation's URL and sha256, the commitment |
| `get_terms_hash(agreement_id)` | what the translator must accept, and who the translator is |
| `get_evidence_status(agreement_id)` | both documents' statuses and digests, the markers, and the code checks |
| `get_resolution` / `get_latest_resolution` | one full record: every reading with the passage it quotes and its `compared` flag |
| `get_history(agreement_id)` | one line per round |
| `get_actions(agreement_id, as_of)` | what can happen next, and who may do it |
| `list_agreements` / `get_stats` / `get_config` | paging, counts and the vocabulary |

## Reading an outcome correctly

1. **Only a final outcome is an outcome.** Inside its contest window it can be
   read again once.
2. **`INSUFFICIENT_EVIDENCE` is not `NOT_PRESERVED`.** The first means a
   document could not be read or judged; the second is a finding about the
   translation.
3. **`NONE` means no assessment ever happened** - the agreement was cancelled,
   declined, expired or lapsed; `ending` says which.
4. **The reason says which rule decided.** `CRITICAL_TERM_MISSING` and
   `NUMBER_NOT_PRESERVED` were decided in code, exactly; the material reasons
   by the panel, with the quoted passage in the resolution.

## Writing, for the parties who do

| Method | Who |
|---|---|
| `propose_agreement(terms_json)` | the requester; fields in [`../DECISION.md`](../DECISION.md#the-terms-immutable-hashed) |
| `cancel_agreement(agreement_id)` | the requester, before acceptance |
| `decline_agreement(agreement_id)` | the named translator, before acceptance |
| `accept_agreement(agreement_id, terms_hash)` | the named translator |
| `deliver_translation(agreement_id, translation_url, translation_sha256)` | the named translator, once, before the delivery deadline |
| `assess(agreement_id)` | anyone, inside the assess window |
| `contest(agreement_id)` | either party, once, inside the contest window |
| `finalize(agreement_id)` | anyone, after the contest window |
| `expire_agreement(agreement_id)` | anyone, after the delivery deadline with no delivery |
| `lapse_agreement(agreement_id)` | anyone, after the assess window with no assessment |

## Failures a client should expect

| Symptom | Meaning |
|---|---|
| leader execution `ERROR` with `[EXPECTED] ...` | the contract refused; the message says why |
| leader execution `ERROR` with `[TRANSIENT] ...` | the model call or the clock failed on that node; send it again |
| the transaction finalises but nothing changed | the round reached no majority; the agreement is still `DELIVERED` |
