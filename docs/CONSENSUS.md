# Consensus

How one reading of a source and its translation becomes one outcome, and what
validators may and may not differ on.

## Why byte equality is useless here

Two faithful translations of one sentence share almost no bytes; an unfaithful
one can differ from a faithful one by a single word. The contract therefore
never compares translations to anything byte by byte. What it binds by bytes is
the *documents* - each one's sha256 is declared before it is read and checked on
every retrieval - and what validators agree on is what those documents *mean*.

## The exact nondeterministic calls

Two, and no others:

| Call | Where | What it does |
|---|---|---|
| `gl.nondet.web.get(url)` | `_fetch_source`, once for the source and once for the translation | retrieves the bytes, derives a status from the HTTP answer and the content type, normalises the text a reader sees, takes the sha256 of the raw bytes and of the normalised text, extracts the title |
| `gl.nondet.exec_prompt(..., response_format="json")` | `_node_round`, once per round | asks the panel for readings, and only readings |

Both sit inside one `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)` per
assessment.

## What every node does

`_node_round(ctx)`, on the leader and on every validator:

1. retrieves both documents and checks each against its declared sha256 - the
   source's in the terms, the translation's at delivery (`_retrieve`);
2. scans both, in code, for text addressed to the assessor (`_markers`);
3. runs the two exact checks (`_checks`): whether each critical term the source
   uses has an accepted rendering in the translation, and which of the source's
   numbers the translation has fewer of - counted, not merely present;
4. derives the code reason (`_code_reason`): a digest mismatch, an unreadable
   document, a document addressing the assessor, a missing term or a missing
   number decides the round **without the panel**;
5. otherwise convenes the panel once and reduces each subject's answer to a
   finding, re-grounding every quote in this node's own text, in the document
   the reading is allowed to cite.

The payload holds the two source records, the markers, the checks, the code
reason, the panel state and one finding per subject. **It contains no verdict
and no reason code** - those are code's.

## Which document a reading may quote

| Reading | May quote |
|---|---|
| `OMISSION` `MINOR` / `MATERIAL` | the **source** only - what went missing has no words in the translation |
| `DISTORTION` / `ADDITION` `MINOR` / `MATERIAL` | the **translation** only - the changed or invented passage |
| `TERM_<id>` `INCORRECT` | the **translation** only |
| `REQ_<id>` `NOT_MET` | either - the passage that breaks it |

A reading that finds no problem (`NONE`, `CORRECT`, `MET`) needs no quote: "formal
throughout" is not proven by any one passage. The first diagnostic pass showed
why - a leader offered the single word "tome" as proof of formal address, one
word grounds nothing, and the round split.

A quote naming the wrong document is re-attributed only if its words occur in
the document the reading may cite; otherwise it is dropped, and a reading that
needs a quote and has none is downgraded to `UNCLEAR` (`_quotable`, `_quoted`).

## What the validator does

`_validator_decision` reproduces the round from its own retrieval and its own
model call, runs the strict gate on the leader's payload **with its own texts**,
compares what was retrieved and checked (`_evidence_difference`), derives its
own outcome and compares the consequence (`_consequence_difference`), and
prints the reason for every refusal.

## Decision-critical fields

**What was retrieved and checked:** the panel state and code reason, the
markers, the checks, and for both documents every field - status, HTTP answer,
truncation, byte count, both digests, title and content type. Both documents are
bound to their bytes, so nothing about either may differ between nodes.

**What it leads to:**

| Field | Compared |
|---|---|
| `verdict` | every round |
| `reason_code` | every round |
| `statuses`, `digests` | every round |
| `checks` | every round |

## Equivalence: what may differ

Notes, which passage was quoted, and readings no rule reached. The comparison
carries values, not implications: a reason names the rule that decided, and a
rule fixes the reading it names. `MEANING_PRESERVED` fixes every reading;
`MINOR_DEVIATIONS` fixes every term and required requirement; a material reason
fixes the dimension it names. Each stored finding says whether its state was
fixed that way (`compared`). Under a material omission, for instance, whether a
validator also saw a minor addition changes nothing that was compared - and is
not.

## Forged-leader defence

| Forgery | What stops it |
|---|---|
| a clean reading of a translation that omits a warning | the consequence comparison: each validator derives its own outcome |
| an omission quoted from the translation | `_quotable`, in the gate |
| a term check that says PRESENT when the rendering is absent, to reach the panel | the checks are compared, and the reason is recomputed from them |
| a missing-numbers list that is invented, or not numbers | the gate and the comparison |
| a quote that is in neither document | grounding, in each validator's own bytes |
| a spliced quote | `_spliced` refuses an ellipsis |
| a digest or status that was not what was fetched | the evidence comparison |
| a payload about another agreement, round or moment | the identity fields |
| malformed JSON, extra fields, wrong types | the gate |

## Failure semantics

| Situation | Result |
|---|---|
| a document's bytes are not the ones declared | `INSUFFICIENT_EVIDENCE` / `EVIDENCE_DIGEST_MISMATCH`, in code |
| a document cannot be read | `INSUFFICIENT_EVIDENCE` / `DOCUMENT_UNREADABLE`, in code |
| a document addresses the assessor | `INSUFFICIENT_EVIDENCE` / `DOCUMENT_ADDRESSES_ASSESSOR`, in code |
| a critical term has no accepted rendering | `NOT_PRESERVED` / `CRITICAL_TERM_MISSING`, in code |
| a number is missing (when required) | `NOT_PRESERVED` / `NUMBER_NOT_PRESERVED`, in code |
| the model's answer is unusable | `INSUFFICIENT_EVIDENCE` / `PANEL_UNUSABLE` |
| a reading is unclear, or asserted without a quote, and nothing material was found | `INSUFFICIENT_EVIDENCE` / `READING_UNCLEAR` |
| the model call fails on a node | `[TRANSIENT]`, ratified only by another transient failure |
| validators disagree | no majority, nothing stored, the agreement stays `DELIVERED` until its window passes |

A document nobody could read is never a verdict about the translation, and
nothing unclear becomes `PRESERVED`.

<!-- LIVE:START -->
## Live findings

The run of record held 19 of 19 outcomes; the passes before it are where the
design met real panels, and they are worth reading
([`DEPLOYMENT.md`](DEPLOYMENT.md#how-the-live-evidence-was-reached)).

**The panel reads both languages closely - closer than the fixtures were
written.** It flagged a reflexive Spanish construction that could mean "keep
yourself away from children", and then a named object ("this medicine") the
English source had left implicit. Both times it was right, and both times the
fix was the fixture: a source that leaves something implicit forces every
faithful translation to choose, and a careful reader notices the choice.

**A quote rule that suits a finding does not suit its absence.** The first
contract asked a requirement read as MET to quote a passage. A leader offered
the single word "tome" as proof of formal address, one word grounds nothing, the
reading fell to UNCLEAR, and the round split against three validators who read
MET. The contract now asks for a quote only where a reading finds a problem.
The failure itself was the designed one: no majority, nothing stored.

**What the panel found, with the passage it rests on.** The dropped alcohol
warning was quoted from the source; the reversed pregnancy warning and the
invented all-ages claim from the translation; informal address with the
sentence that breaks it. The all-ages line - which both adds a claim and
contradicts the source - was read as an addition, the reason the catalogue named
first; the tolerance for reading it as a distortion was declared and not used.

**What code decided.** A correct synonym that is not the agreed rendering, and a
dose changed from every 8 hours to every 4 while another 8 stayed on the page,
never reached the panel.
<!-- LIVE:END -->
