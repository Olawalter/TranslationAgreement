# Submission - TranslationAgreement

Copy-ready for the portal's Builder > Intelligent Contracts form. No addresses,
hashes or shell commands appear in the free-text fields: the contract goes only
in the evidence row the portal recognises as a GenLayer Explorer contract.

## Title

TranslationAgreement - does a translation preserve what both parties agreed

## One-line thesis

A reusable GenLayer Intelligent Contract that decides whether a translation
preserves what its requester and translator agreed before it existed, and
records a typed outcome a payment system reads in one call.

<!-- PORTAL:START -->
## Portal description (956 characters, limit 1000)

Two parties agree what a translation must preserve before it exists: the source bound to its hash, critical terms and their accepted renderings, requirements such as formal address, and whether numbers must survive. The translator delivers a translation bound to its own hash. Validators retrieve both documents and read them for distortion, omission and addition, each graded none, minor or material and quoted from the document it concerns, plus term meaning and requirements. The model is never asked whether meaning is preserved: code derives PRESERVED, PARTIALLY_PRESERVED, NOT_PRESERVED or INSUFFICIENT_EVIDENCE. Two rules are exact and never reach the model: agreed term renderings, and every number counted, so a dose changed from every 8 hours to every 4 is caught. Verified with 114 Direct Mode tests, an 80-mutation sweep, GenVM lint, live integration tests, and 19 of 19 live outcomes on a StudioNet deployment byte-identical to the repository.
<!-- PORTAL:END -->

## Evidence rows

| Type | What |
|---|---|
| GitHub Repository | https://github.com/Olawalter/TranslationAgreement |
| GenLayer Explorer Contract | https://explorer-studio.genlayer.com/address/0xB4162264cB70FdC774951a236ED3d18a32ccb680 |

## Reviewer fast path

1. `DECISION.md` - the specification written before the contract, and what the
   diagnostic passes changed.
2. `docs/CONSENSUS.md` - which document each reading may quote, what validators
   compare, and the live findings.
3. `contracts/translation_agreement.py` - `_verdict_for`, `_checks`, `_quotable`.
4. `docs/DEPLOYMENT.md` - every transaction of the run of record, and the four
   passes before it.
5. `tests/direct/test_ta_adversarial.py` - forged readings, quotes from the wrong
   document, injections and their evasions.
