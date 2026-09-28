# Security

The threat model, what each boundary holds, and what this contract does not
defend against.

## Assets

| Asset | Why it is worth attacking |
|---|---|
| a **PRESERVED** outcome | a payment or acceptance process releases on it; a false one ships an unfaithful translation of a document someone will act on |
| a **NOT_PRESERVED** outcome | a false one withholds payment from a faithful translator |
| the **terms** | if they could change after the translation existed, the requirements could be rewritten around it |
| the **documents** | the outcome is only about the bytes both parties agreed on |

No funds. No method is payable.

## Actors

| Actor | Can | Cannot |
|---|---|---|
| **requester** | propose terms naming one translator; cancel them before acceptance; contest an outcome once | change the terms, the source or its digest once proposed; cancel after acceptance; assess, or influence a reading |
| **translator** (named in the terms) | accept the exact terms by hash; decline; deliver once, before the deadline; contest once | deliver after the deadline, deliver twice, deliver the source itself, or swap the translation after delivery |
| **keeper** (anyone) | assess, finalise, expire, lapse | change any outcome |
| **validators** | reproduce the round and refuse the leader | write an outcome; code derives it |
| **consumer** | read outcomes and finality | write anything |

## Trust assumptions

- The hosts the terms name are trusted only to serve bytes. Both documents are
  trusted only to the extent they hash to what was declared.
- The model is fallible and possibly adversarially prompted. It is never asked
  whether meaning is preserved, and every finding that bears on the outcome
  must quote the document it is about.
- A translator's own certification that the work is accurate is a claim. It is
  not a marker (certified translations carry one routinely) and the panel is
  told to read past it.
- Both parties are self-interested. That is why the terms are fixed before the
  translation, accepted by hash, and why either party - and only a party - may
  contest.

## Input attacks

**Changing a number.** A dose changed from every 8 hours to every 4 is decided
in code when the terms ask numbers to survive. The check counts: a leaflet that
says 8 twice must say it twice, so changing one occurrence is caught even though
another 8 remains.

**A synonym for an agreed term.** Parties who agree a rendering get it: a
correct synonym that is not an accepted rendering is `CRITICAL_TERM_MISSING`.
That is the rule both accepted; it is decided in code.

**Prompt injection.** Both documents are data. `_markers` scans each in code -
visible text, markup and attributes, title - undoing soft hyphens, zero-width
characters, byte order marks, numeric entities and tag or comment splits. A
document carrying text addressed to the assessor decides the round as
`DOCUMENT_ADDRESSES_ASSESSOR`. The terms' own fields are screened the same way.

**Swapping a document.** Each document's sha256 is fixed before it is read -
the source's in the terms, the translation's at delivery - and checked on every
retrieval, in every round. Different bytes are `EVIDENCE_DIGEST_MISMATCH`, never
a verdict, and a contest cannot be judged on a better translation.

**Quoting the wrong document.** An omission must quote the source; a
distortion, an addition or a misrendered term must quote the translation. A
finding that cannot be checked against the document it is about is downgraded.

**Fabricated or spliced support.** A quote grounds only as a contiguous run of
words in this node's own retrieval; an ellipsis splice is refused.

**Malformed model output.** Types are checked, not coerced; unknown states,
missing subjects and extra fields fail closed.

**Griefing by volume.** At most ten open agreements per requester, four terms,
four renderings each, four requirements, 200 KB per document, 9,000 normalised
characters shown to the panel.

## Fail-closed policy

Nothing unreadable becomes a verdict and nothing unclear becomes `PRESERVED`:
a mismatch, an unreadable document, an injection, an unusable answer, or an
unclear reading with nothing material found are all `INSUFFICIENT_EVIDENCE`.

A **material** finding outranks an unclear one, deliberately: if the panel
agrees the alcohol warning is missing, the translation is not preserved whether
or not another dimension was clear. The finding still has to quote the source
passage that went missing, in every validator's own bytes.

## Limitations

- **The outcome is about meaning, not quality.** Fluency, style and register
  are graded NONE unless the parties write them in as requirements.
- **Absence cannot be proven in code across languages.** An omission quote
  proves the passage exists in the source, not that it is missing from the
  translation; that is a reading, which is why independent readers must agree
  on it.
- The MINOR / MATERIAL line is a judgement. The contract defines it (would a
  reader act differently?), and where honest models place it differently the
  round reaches no majority and stores nothing.
- Term and number checks are string rules. They catch what they are written to
  catch and nothing else; a term used with the wrong meaning is the panel's
  `TERM_<id>` reading.
- Documents up to 9,000 normalised characters are read in full; a longer one is
  read to that point and recorded `PARTIAL`.
- One contest per agreement, for whichever party uses it first; the second
  reading is of the same bound bytes.
- The demonstration leaflet is a fixture. It describes no real product and is
  not medical advice.
