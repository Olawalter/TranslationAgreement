# Decision record - TranslationAgreement

Written before the contract. It fixes what the contract decides, what it refuses
to decide, and why each boundary sits where it does.

## The trust question

A requester commissions a translation of a document that matters - a medicine
leaflet, a contract clause, a safety notice. Requester and translator agree up
front what the translation must preserve. When the translation arrives, one of
them says "it is faithful" and the other may not agree. The question:

> Given the source document, the translation, and requirements both parties
> agreed before the translation existed, does the translation preserve the
> source's meaning - with nothing material distorted, omitted or added, every
> critical term rendered as agreed, and every requirement met?

The output is `PRESERVED`, `PARTIALLY_PRESERVED` or `NOT_PRESERVED` - and a
fourth, `INSUFFICIENT_EVIDENCE`, because a document nobody could read is neither
preserved nor not preserved. Failing closed means never guessing between them.

## The delete-GenLayer test

Delete GenLayer and one of the parties decides whether their own agreement was
met - the translator that the work is faithful, or the requester that it is
not - or a single reviewer, in private, with nothing either party can check.
Byte equality is useless here by construction: two faithful translations of one
sentence share almost no bytes, and an unfaithful one can change a single word.
Meaning has to be read, in two languages, by several independent readers who
must agree on what they found.

## One primitive

An **agreement** fixes, before any translation exists: the source document
(bound to its sha256), the two languages, the critical terms and their accepted
renderings, the requirements, whether numbers must survive verbatim, the hosts
documents may come from, and the windows. The named translator **accepts** it,
committing to those exact terms by their hash. The translator **delivers** a
translation bound to its own sha256. One consensus round produces the outcome.

## Collision audit (the owner's own portfolio, 52 repositories)

Nothing in it compares two documents across languages. The nearest are
evidence-judging agreements - Verity (agent work against a spec), WITNESS
(did an obligation happen), STATELOCK (did a world condition hold), AgentSLA
(were requirements met) - which read evidence *about* an event. This reads two
texts *against each other*, which is a different question with a different
failure mode: the risk is not missing evidence but a confident reading of a
subtle change in meaning. (Tradera, on the other account, checks trade documents
against letter-of-credit terms in one language; it is not this.)

## Responsibility split

**Deterministic code owns:** identity (requester and translator are signers,
and only the named translator may accept and deliver); the immutable terms and
their hash, which acceptance commits to; every field limit; URL admission and
the permitted hosts; document integrity (both documents' declared sha256
verified against the bytes fetched, every round); which documents are readable,
mismatched or addressed to the assessor; **whether each critical term's
source form appears in the source and an accepted rendering in the
translation**; **whether every number in the source survives in the
translation**, when the terms ask for it; the verdict and its reason; windows;
every transition.

**GenLayer consensus owns meaning:** whether the translation changes what the
source says (distortion), leaves out what the source says (omission), says what
the source does not (addition) - each graded NONE, MINOR or MATERIAL - whether
each critical term is rendered with the right meaning in context, and whether
each requirement is met.

**The model is never asked whether meaning is preserved.** That question is the
verdict. It reads the dimensions; code derives the verdict.

## The terms (immutable, hashed)

```json
{
  "title": "Patient leaflet - Paracetamol 500 mg tablets",
  "translator": "0x...",
  "source_url": "https://raw.githubusercontent.com/.../leaflet-en.html",
  "source_sha256": "<64 hex>",
  "source_language": "English",
  "target_language": "Spanish",
  "critical_terms": [
    {"term_id": "ingredient", "source_term": "paracetamol", "renderings": ["paracetamol"]}
  ],
  "requirements": [
    {"requirement_id": "formal_address", "description": "...", "required": true}
  ],
  "preserve_numbers": true,
  "evidence_domains": ["raw.githubusercontent.com", "cdn.jsdelivr.net"],
  "delivery_window": 86400,
  "assess_window": 1800,
  "contest_window": 900,
  "spec_version": 1
}
```

## State machine

```text
propose ─► PROPOSED ─accept─► ACCEPTED ─deliver─► DELIVERED ─assess─► ASSESSED ─finalize─► FINAL
              │                  │                    │                  │
              ├─ cancel (requester)                   │                  └─ contest (either party, once)
              └─ decline (translator)                 │
                                 └─ expire (anyone, no delivery in time) ─► EXPIRED
                                                      └─ lapse (anyone, not assessed in time) ─► LAPSED
```

## The panel's subjects

| Subject | States | Quote required, and from which document |
|---|---|---|
| `DISTORTION` | `NONE`, `MINOR`, `MATERIAL`, `UNCLEAR` | `MINOR`/`MATERIAL`: from the translation |
| `OMISSION` | `NONE`, `MINOR`, `MATERIAL`, `UNCLEAR` | `MINOR`/`MATERIAL`: from the **source** - what went missing |
| `ADDITION` | `NONE`, `MINOR`, `MATERIAL`, `UNCLEAR` | `MINOR`/`MATERIAL`: from the translation - what was added |
| `TERM_<id>` | `CORRECT`, `INCORRECT`, `UNCLEAR` | `INCORRECT`: from the translation |
| `REQ_<id>` | `MET`, `NOT_MET`, `UNCLEAR` | `NOT_MET`: either document - the passage that breaks it |

MATERIAL means a reader would act differently: an obligation, a quantity, a
date, a party, a condition, a warning, a prohibition. MINOR means a real change
in meaning that no reader would act on. Style, word order and register are
NONE.

Every quote is re-grounded by every validator in the bytes it fetched, and in
the document its subject allows.

A reading that finds a problem points at it; a reading that finds none has
nothing to point at. (Changed after the first diagnostic pass: the draft asked
`MET` for a quote too, a leader quoted the single word "tome" as proof of formal
address, one word grounds nothing, and the round split. "Formal throughout" is a
universal claim that no one passage proves.)

## The derivation (code, in this order)

1. a document's bytes differ from its declared sha256 -> `INSUFFICIENT_EVIDENCE / EVIDENCE_DIGEST_MISMATCH`
2. a document cannot be read -> `INSUFFICIENT_EVIDENCE / DOCUMENT_UNREADABLE`
3. a document addresses the assessor -> `INSUFFICIENT_EVIDENCE / DOCUMENT_ADDRESSES_ASSESSOR`
4. a critical term in the source has no accepted rendering in the translation -> `NOT_PRESERVED / CRITICAL_TERM_MISSING`
5. a number in the source is missing from the translation (when required) -> `NOT_PRESERVED / NUMBER_NOT_PRESERVED`
6. (1-5 skip the panel.) The panel's answer is unusable -> `INSUFFICIENT_EVIDENCE / PANEL_UNUSABLE`
7. a MATERIAL distortion, omission or addition -> `NOT_PRESERVED / MATERIAL_DISTORTION`, `MATERIAL_OMISSION`, `MATERIAL_ADDITION` (in that order)
8. a critical term rendered with the wrong meaning -> `NOT_PRESERVED / TERM_MISRENDERED`
9. a required requirement not met -> `NOT_PRESERVED / REQUIREMENT_NOT_MET`
10. any of those readings unclear -> `INSUFFICIENT_EVIDENCE / READING_UNCLEAR`
11. any MINOR distortion, omission or addition -> `PARTIALLY_PRESERVED / MINOR_DEVIATIONS`
12. otherwise -> `PRESERVED / MEANING_PRESERVED`

A material finding outranks an unclear one: if one validator's reading shows a
material omission, the translation is not preserved whether or not another
dimension was clear. An unclear reading outranks a clean or minor one: nothing
unclear becomes `PRESERVED`.

## What validators compare

Retrieval: panel state and code reason, the markers, each document's status,
HTTP answer, truncation, bytes, digests, title and content type, and the code
checks (term presence, missing numbers). Consequence: `verdict`, `reason_code`,
the statuses and the digests. Values, not implications: the reason names the
rule that decided, so the readings behind it are not compared again.

## Why non-payable

The outcome is a signal both parties agreed to be bound by. A payment system,
an escrow or a dispute process reads it; the contract holds no funds and has no
reason to prefer an answer.

## Three consumers

| Consumer | Reads |
|---|---|
| the requester's payment or escrow system | `get_outcome`: preserved, final |
| a regulator or auditor of translated safety material | the full resolution: every reading with the passage it quotes, the code checks |
| a translation marketplace | a translator's history of final outcomes, one agreement at a time |

## Deliberately left out

- **Revisions inside one agreement.** A revision is a new agreement; the old
  outcome stays on the record.
- **Scoring translation quality.** Fluency and style are not meaning; the
  contract grades fidelity only.
- **Machine translation inside the contract.** The panel reads both texts; it
  never produces its own translation to compare against.
- **Funds.** See above.
