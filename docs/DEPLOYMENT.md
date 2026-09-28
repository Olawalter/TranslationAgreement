# Deployment

The canonical StudioNet deployment, how to reproduce it, the diagnostic passes
that shaped it, and the live run of record. Every value below is read from
`deploy/deployment.json` and `deploy/live_run_transcript.json`.

## Environment

| | |
|---|---|
| Network | GenLayer StudioNet, chain id 61999, `https://studio.genlayer.com/api` |
| Explorer | `https://explorer-studio.genlayer.com` |
| Wallets | the deployer key in `.data/deployer.json`; the demo wallets' keys in `.data/demo_wallets.json` (`scripts/make_wallets.py`), public addresses in `fixtures/wallets.json`; `.data/` is gitignored and no key is ever printed |
| Toolchain | Python 3.12, genlayer-test 0.29.2, genlayer-py 0.16.3, genvm-linter 0.11.0 with GenVM bundle v0.3.0-rc7 |
| Runner | `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6` |

The linter picks the newest GenVM bundle in its cache; pin the one the suite was
verified against:

```bash
GENVM_VERSION=v0.3.0-rc7 genvm-lint check contracts/translation_agreement.py --json
```

## Reproduce

```bash
pip install -r requirements-test.txt
python scripts/fetch_genvm_bundle.py
python -m pytest tests/direct -q
python scripts/deploy_studionet.py
python scripts/deploy_studionet.py --verify
python scripts/make_wallets.py
python scripts/live_run.py <address> --raw-base https://raw.githubusercontent.com/<owner>/<repo>/<commit>/fixtures/ --phase full
python -m pytest tests/integration -q
```

## Canonical deployment

| | |
|---|---|
| Contract | [`0xB4162264cB70FdC774951a236ED3d18a32ccb680`](https://explorer-studio.genlayer.com/address/0xB4162264cB70FdC774951a236ED3d18a32ccb680) |
| Deployment transaction | [`0xbddf808e0d4ede93187f5e0ec961f87652730b6126e9980c4fe69dedcd0ad6d3`](https://explorer-studio.genlayer.com/tx/0xbddf808e0d4ede93187f5e0ec961f87652730b6126e9980c4fe69dedcd0ad6d3) |
| Status | FINALIZED, leader execution SUCCESS, votes AGREE x5 |
| Source commit | `20b76b243730006cc848562f22bc37dabac09442` |
| Contract blob | `9b8f46fa17ca02f6159156a935150aa386f9e40f` |
| Source | byte-identical to the repository (sha256 in `deploy/deployment.json`) |
| Schema | 21 methods (11 view, 10 write), read from the chain |

## How the live evidence was reached

Four passes ran before the run of record, and each changed something. All are
kept under `deploy/diagnostics/`.

| Pass | Deployment | What it found | What changed |
|---|---|---|---|
| `pass0_ambiguous_fixture_*` | first, `0x711DD6ED` | the faithful translation read `MATERIAL_DISTORTION`: its "Mantengase fuera del alcance de los ninos" is reflexive and can mean *keep yourself* out of children's reach | the fixture, which now names the medicine - the panel was right |
| `pass1_0x711dd6ed` | first | the faithful translation split the round: the leader offered the single word "tome" as proof of formal address, one word grounds nothing, the leader downgraded MET to UNCLEAR, and three validators disagreed. Material omission and distortion held | **the contract**: a requirement met throughout needs no quote, as NONE and CORRECT already did; redeployed, the first deployment moved to `deploy/superseded/0x711dd6ed/` |
| `pass2_0xb4162264` | canonical | the faithful translation read `PARTIALLY_PRESERVED`: naming the medicine supplied an object the English "Keep out of the reach of children" left implicit | the fixture source now states every object ("Keep this medicine...", "before using it") |
| `pass3_0xb4162264` | canonical | 72 transactions, 19 of 19 held, 11 of 11 refused | nothing |

Two lessons are in those rows. A fixture in two languages has to be unambiguous
in both, and a source that leaves something implicit forces every faithful
translation to make a choice a careful panel will notice. And a quote rule that
suits a finding does not suit its absence: "met throughout" is proven by no one
passage.

## Live run of record

`python scripts/live_run.py` against the canonical deployment, 2026-09-28
16:59:40Z to 17:54:43Z, documents at commit `3a25be4`: the source from
`raw.githubusercontent.com`, the translations from the jsDelivr mirror of the
same commit.

**72 transactions, 19 of 19 outcomes held, 11 of 11 refusals refused.** Every
verdict and every reason the catalogue names was reached on chain: a faithful
translation `PRESERVED`, and upheld by the requester's contest; "out of the
reach *and sight* of children" `PARTIALLY_PRESERVED`; a dropped alcohol warning,
a reversed pregnancy warning and an invented claim of safety for all ages each
`NOT_PRESERVED` on the dimension they break; informal address against an agreed
requirement; a synonym that is not the agreed rendering, and a dose changed from
every 8 hours to every 4, both decided in code; an injection, a wrong digest and
an unpublished translation each `INSUFFICIENT_EVIDENCE`; then a decline, a
cancellation, an expiry, a lapse, three outcomes read back through `get_outcome`,
and eleven refusals, each for the reason it was sent to test.

| Step | Transaction | Recorded | |
|---|---|---|---|
| `propose:TA12` | [`0x5d28dd07...`](https://explorer-studio.genlayer.com/tx/0x5d28dd07e7052b9257de8d69bd0728f0bd073741a7d557ac30b986bdb0a4a071) | propose_agreement FINALIZED/SUCCESS |  |
| `accept:TA12` | [`0xe246bd1d...`](https://explorer-studio.genlayer.com/tx/0xe246bd1de32390c4730543de34a0ee7f91b30400047c6a4bd5519487ed60e350) | accept_agreement FINALIZED/SUCCESS |  |
| `propose:TA13` | [`0x156019f8...`](https://explorer-studio.genlayer.com/tx/0x156019f806d54267a376bc44ed848b236684693588f0fd8f2e9e03a078e2f57c) | propose_agreement FINALIZED/SUCCESS |  |
| `accept:TA13` | [`0x5cd22b29...`](https://explorer-studio.genlayer.com/tx/0x5cd22b299e37d80a9b1dd24cb7de1e264e26d7fa7a930caf7c195c16198cb04d) | accept_agreement FINALIZED/SUCCESS |  |
| `deliver:TA13` | [`0xcf11f60d...`](https://explorer-studio.genlayer.com/tx/0xcf11f60d10c51f2f9ad2d4bd96fc141a5400a83d1b75e1dc84c34a63761afff7) | deliver_translation FINALIZED/SUCCESS |  |
| `propose:TA01` | [`0x5beadd70...`](https://explorer-studio.genlayer.com/tx/0x5beadd70b7fb7d254557b10a6af60b71315d3b49f0b4e4ecf97bfc3d7cbfad28) | propose_agreement FINALIZED/SUCCESS |  |
| `accept:TA01` | [`0xfb4d8615...`](https://explorer-studio.genlayer.com/tx/0xfb4d861557bdf0af1f0d381a6a00704238edbcc261e1319d9d741ce80b4058d6) | accept_agreement FINALIZED/SUCCESS |  |
| `deliver:TA01` | [`0x8c103085...`](https://explorer-studio.genlayer.com/tx/0x8c1030850e4efed9fe9d1f36025867fbda24dce8458a9c3c6fd80fede1543261) | deliver_translation FINALIZED/SUCCESS |  |
| `assess:TA01` | [`0x2c446174...`](https://explorer-studio.genlayer.com/tx/0x2c446174dbab50ec7a8c6496744133f700d31efebd860eb06db45c15673defd6) | PRESERVED / MEANING_PRESERVED | held |
| `contest:TA01` | [`0x2583c626...`](https://explorer-studio.genlayer.com/tx/0x2583c62652f69078a99304e2077522c5d119ba9ec977fa7c73a1134f8de054b1) | PRESERVED / MEANING_PRESERVED | held |
| `propose:TA02` | [`0x6aa4b9cf...`](https://explorer-studio.genlayer.com/tx/0x6aa4b9cf1968778ba5a1a0a39e08f7c48b6d2a15c6dc291886e7f568c71fa1f0) | propose_agreement FINALIZED/SUCCESS |  |
| `accept:TA02` | [`0x43592fb5...`](https://explorer-studio.genlayer.com/tx/0x43592fb5d37680fec0363d6284dcf7493dc6b96c385ec0f8a8c8681c4ea048f7) | accept_agreement FINALIZED/SUCCESS |  |
| `deliver:TA02` | [`0x067703e1...`](https://explorer-studio.genlayer.com/tx/0x067703e1bb3f9ae91e7e7c5fde54162ad3b5e874e633b668c480c4ffdf9c3465) | deliver_translation FINALIZED/SUCCESS |  |
| `assess:TA02` | [`0xfc0793d5...`](https://explorer-studio.genlayer.com/tx/0xfc0793d51b95240cbc1f1ec35ccedd465760e5348824e4555e7b3b3c082d0ce8) | PARTIALLY_PRESERVED / MINOR_DEVIATIONS | held |
| `propose:TA03` | [`0x1f446e3b...`](https://explorer-studio.genlayer.com/tx/0x1f446e3b259aeadce2079600580cae104a76556b358cf9d7c98c4c50d4460703) | propose_agreement FINALIZED/SUCCESS |  |
| `accept:TA03` | [`0x2bba788b...`](https://explorer-studio.genlayer.com/tx/0x2bba788b2b0a0b06f9780f91c1de37f1c6e9a8195f30ca65934517d9d8748146) | accept_agreement FINALIZED/SUCCESS |  |
| `deliver:TA03` | [`0xc481be05...`](https://explorer-studio.genlayer.com/tx/0xc481be0593dee2d5483010bc3fc698580fe5f6f9115c8e34f552c283ea8db6da) | deliver_translation FINALIZED/SUCCESS |  |
| `assess:TA03` | [`0x95118dcc...`](https://explorer-studio.genlayer.com/tx/0x95118dccbde3f8c74bb0c8bbc466ef0a5a02b6558bdc8f754acb68f0fb753820) | NOT_PRESERVED / MATERIAL_OMISSION | held |
| `propose:TA04` | [`0x5ea65d74...`](https://explorer-studio.genlayer.com/tx/0x5ea65d74958692c8ee4ff6a43713f314c5639c1cba8f2a8db4563a798a9da8f6) | propose_agreement FINALIZED/SUCCESS |  |
| `accept:TA04` | [`0x7708bb6d...`](https://explorer-studio.genlayer.com/tx/0x7708bb6dd654e12415ed2d7161e48202874259f73d5ac7ed851f5b6e9ee54ab9) | accept_agreement FINALIZED/SUCCESS |  |
| `deliver:TA04` | [`0x7c71a1ff...`](https://explorer-studio.genlayer.com/tx/0x7c71a1ff499138bdc59c26a6520b4fb445ccb1a414faf7c71612a2858c1b7ed9) | deliver_translation FINALIZED/SUCCESS |  |
| `assess:TA04` | [`0x59252fea...`](https://explorer-studio.genlayer.com/tx/0x59252feafa26495a669d6cbe4454c41d6bf4565c18a9ee28d8dd9e76caa6eadb) | NOT_PRESERVED / MATERIAL_DISTORTION | held |
| `propose:TA05` | [`0x5c510238...`](https://explorer-studio.genlayer.com/tx/0x5c510238c774782cd505b2108c8295f7aa20c5a4c7e296d239b947bef7b2c438) | propose_agreement FINALIZED/SUCCESS |  |
| `accept:TA05` | [`0xf1108eba...`](https://explorer-studio.genlayer.com/tx/0xf1108eba80ed7792acf8ed28271673fbe1069843b1edd9479e7dfda03064d188) | accept_agreement FINALIZED/SUCCESS |  |
| `deliver:TA05` | [`0x75280fcd...`](https://explorer-studio.genlayer.com/tx/0x75280fcdfb4c1f332f4f5208afaf868e4fb56a511a596262fe516192599d0b6e) | deliver_translation FINALIZED/SUCCESS |  |
| `assess:TA05` | [`0xc111e408...`](https://explorer-studio.genlayer.com/tx/0xc111e40802832d975b11153d23ee7960fc13a3152337ce1ce11a62b597ff8d04) | NOT_PRESERVED / MATERIAL_ADDITION | held |
| `propose:TA06` | [`0xe2c1b37c...`](https://explorer-studio.genlayer.com/tx/0xe2c1b37cdd6bc718659a8accb37b3643f6141c85c2b1fd1b52942903478214f0) | propose_agreement FINALIZED/SUCCESS |  |
| `accept:TA06` | [`0x4452c8e1...`](https://explorer-studio.genlayer.com/tx/0x4452c8e1f726061aac6b499cf736910a47db79a30e85d556d359a625b20488ad) | accept_agreement FINALIZED/SUCCESS |  |
| `deliver:TA06` | [`0x65e34d3f...`](https://explorer-studio.genlayer.com/tx/0x65e34d3f899d66ece0f2f1fcc97d32a6dc08c86c5c1b5274cf814197d3cba55e) | deliver_translation FINALIZED/SUCCESS |  |
| `assess:TA06` | [`0x864d8fc2...`](https://explorer-studio.genlayer.com/tx/0x864d8fc22f80365cdb3a708a5992107eb47569fd4edd5abb2c46d40c5dbeb57d) | NOT_PRESERVED / REQUIREMENT_NOT_MET | held |
| `propose:TA07` | [`0xcc2d1850...`](https://explorer-studio.genlayer.com/tx/0xcc2d18505212c93d0e107f88a1a2acedf7fb34da86d367c722c112c33b0087d3) | propose_agreement FINALIZED/SUCCESS |  |
| `accept:TA07` | [`0x5b72031f...`](https://explorer-studio.genlayer.com/tx/0x5b72031f794c8539522984a50403aa5e07441a33b254fd902970d3a454679f5d) | accept_agreement FINALIZED/SUCCESS |  |
| `deliver:TA07` | [`0xd308ce33...`](https://explorer-studio.genlayer.com/tx/0xd308ce33da544b183b577cad704d797fa767f45d021384480e85485861a61b5d) | deliver_translation FINALIZED/SUCCESS |  |
| `assess:TA07` | [`0x8c9bba99...`](https://explorer-studio.genlayer.com/tx/0x8c9bba996e5820150dcd86b18a697d4ba3d0c6a2d4802575fe482f88aed56732) | NOT_PRESERVED / CRITICAL_TERM_MISSING | held |
| `propose:TA08` | [`0xd722ce26...`](https://explorer-studio.genlayer.com/tx/0xd722ce2655940a0c8aeb917a8c13472ee4d922bc536d33e757642d59b53978ca) | propose_agreement FINALIZED/SUCCESS |  |
| `accept:TA08` | [`0xe85dc6cd...`](https://explorer-studio.genlayer.com/tx/0xe85dc6cd7b9e527975e277260306eaa0f4edf6d867580948579436f4d3f4c948) | accept_agreement FINALIZED/SUCCESS |  |
| `deliver:TA08` | [`0xc3189359...`](https://explorer-studio.genlayer.com/tx/0xc3189359cc0dbf5a07993776a62c217bcb143cbe32aba21edd2ac7b30fdd9f8c) | deliver_translation FINALIZED/SUCCESS |  |
| `assess:TA08` | [`0xfbc8aaf1...`](https://explorer-studio.genlayer.com/tx/0xfbc8aaf15210dda3efb877d96cea7b9a60ed11372e6068497c51bfdd4bc2b056) | NOT_PRESERVED / NUMBER_NOT_PRESERVED | held |
| `propose:TA09` | [`0xa836e452...`](https://explorer-studio.genlayer.com/tx/0xa836e452dd8051b0f9c949405d2272bd1e3240aa36cfe1b182fb2ba66b8005ea) | propose_agreement FINALIZED/SUCCESS |  |
| `accept:TA09` | [`0xc4aad9ad...`](https://explorer-studio.genlayer.com/tx/0xc4aad9ad2f51420343449b3ab5f1f69d249190eb8aae795a5e272eb89b65ba0c) | accept_agreement FINALIZED/SUCCESS |  |
| `deliver:TA09` | [`0xea988ee9...`](https://explorer-studio.genlayer.com/tx/0xea988ee9dcf9adb43bc49d9a2fb6d9a4d51a9db79f54b4ccbf048c0d32878c72) | deliver_translation FINALIZED/SUCCESS |  |
| `assess:TA09` | [`0x28df448c...`](https://explorer-studio.genlayer.com/tx/0x28df448cc12980d83a7ecb1649d3f460324c759ad2c8bc4aad5991f65da93dd4) | INSUFFICIENT_EVIDENCE / DOCUMENT_ADDRESSES_ASSESSOR | held |
| `propose:TA10` | [`0x6a654363...`](https://explorer-studio.genlayer.com/tx/0x6a654363b6b4a9968af08f53501faf96b75a5c58b110620ea349366213a16591) | propose_agreement FINALIZED/SUCCESS |  |
| `accept:TA10` | [`0x3af07fe6...`](https://explorer-studio.genlayer.com/tx/0x3af07fe6b5845abab6ad28a5788ad3f4701742b06934430c9bc022ad9ba83afd) | accept_agreement FINALIZED/SUCCESS |  |
| `deliver:TA10` | [`0x91d5d7b7...`](https://explorer-studio.genlayer.com/tx/0x91d5d7b7fc679fd22e618b5919c6da39a7ca6c83c3621455c68a16ddda808516) | deliver_translation FINALIZED/SUCCESS |  |
| `assess:TA10` | [`0x68240a45...`](https://explorer-studio.genlayer.com/tx/0x68240a4558c423465ce81f8180074de10db1b29dfd609230a770732bdaadc2e2) | INSUFFICIENT_EVIDENCE / EVIDENCE_DIGEST_MISMATCH | held |
| `propose:TA11` | [`0x806a6fb1...`](https://explorer-studio.genlayer.com/tx/0x806a6fb14f85973dba197819bb9e5bdc9ec175249aecdd07f30d344ea55d9b98) | propose_agreement FINALIZED/SUCCESS |  |
| `accept:TA11` | [`0x29c49377...`](https://explorer-studio.genlayer.com/tx/0x29c4937747caa76f48f3b3bee0d4dffe659d6cad2336a9754412a9d5f636103f) | accept_agreement FINALIZED/SUCCESS |  |
| `deliver:TA11` | [`0x460d15b2...`](https://explorer-studio.genlayer.com/tx/0x460d15b2ecb7220280f106ed3d237d4aa54a4f5ef0e913a73fc73c073f5e49c1) | deliver_translation FINALIZED/SUCCESS |  |
| `assess:TA11` | [`0x9d51bbd2...`](https://explorer-studio.genlayer.com/tx/0x9d51bbd268393e57253128d53e3a453b1bf0935bb0c8070689edcd899709ebea) | INSUFFICIENT_EVIDENCE / DOCUMENT_UNREADABLE | held |
| `propose:TA14` | [`0x8af6efdd...`](https://explorer-studio.genlayer.com/tx/0x8af6efddbb340b572980460ba45d5859f993a79655148a1b6a45b5ba49c37f02) | propose_agreement FINALIZED/SUCCESS |  |
| `decline:TA14` | [`0xa52e12cb...`](https://explorer-studio.genlayer.com/tx/0xa52e12cb2dfcaeab3f9edbd600ca1b7f66a4d57d01794f2ed12729481c3dc604) | NONE / DECLINED | held |
| `propose:TA15` | [`0x2a8f8b77...`](https://explorer-studio.genlayer.com/tx/0x2a8f8b7759e35c24909ae45e862e4d1a73da55a61f9bdc6d393dadf68f841a20) | propose_agreement FINALIZED/SUCCESS |  |
| `cancel:TA15` | [`0x4c060e60...`](https://explorer-studio.genlayer.com/tx/0x4c060e60aba8d051210877d79f2d0a266c041ad704375114ff8d264277c2c519) | NONE / CANCELLED | held |
| `finalize:TA01` | [`0x9ed3ef12...`](https://explorer-studio.genlayer.com/tx/0x9ed3ef1210c8fead7cb691f2ae5c17b8bd329f0f04a21d11429852cddc704a15) | FINAL; get_outcome preserved=true, partially_preserved=false | held |
| `finalize:TA02` | [`0xaef7f2fe...`](https://explorer-studio.genlayer.com/tx/0xaef7f2feaa8142d44fa4f74858ca837b033edfd8b74d63b88b67f23246b4480c) | FINAL; get_outcome preserved=false, partially_preserved=true | held |
| `finalize:TA03` | [`0xd9727614...`](https://explorer-studio.genlayer.com/tx/0xd972761417f005589c26d730844dffbffc6ca70ccb4cbc1b7d7c0a433ca895a4) | FINAL; get_outcome preserved=false, partially_preserved=false | held |
| `expire:TA12` | [`0x5e417bfa...`](https://explorer-studio.genlayer.com/tx/0x5e417bfa93024d58361d4a1db4db3cdcd02e29058455a79888f947717811fd15) | NONE / EXPIRED | held |
| `lapse:TA13` | [`0x6a835722...`](https://explorer-studio.genlayer.com/tx/0x6a83572232d3c1dc4d425453151bfcc9ff550ac0b7ec4b66fa70a337f5b774aa) | NONE / LAPSED | held |
| `refuse:self_as_translator` | [`0x1cb8f734...`](https://explorer-studio.genlayer.com/tx/0x1cb8f7341c57ef143c0641faf5cc9f6794f83b1ab03820302fe416774c3ea4c4) | refused: the translator must be another account than the requester | held |
| `refuse:same_language` | [`0x5af7cbce...`](https://explorer-studio.genlayer.com/tx/0x5af7cbce6b265b1e25219a5c52a88c09bbf689c8ebc257bf9017c7a4d4fff042) | refused: source_language and target_language must differ | held |
| `propose:REFUSALS` | [`0xdabca65c...`](https://explorer-studio.genlayer.com/tx/0xdabca65c5dcc9c66235bb006af9cdbcf195a07cbea0971d89a2678f798c7e436) | propose_agreement FINALIZED/SUCCESS |  |
| `refuse:stranger_accepts` | [`0x7f055a91...`](https://explorer-studio.genlayer.com/tx/0x7f055a917bb427091ecf2c84f19c13f90a404ac6e4a44877e3fc5f7dd677daf8) | refused: only the named translator accepts | held |
| `refuse:wrong_terms_hash` | [`0x1d30c8d7...`](https://explorer-studio.genlayer.com/tx/0x1d30c8d7a6a2e18f6c7e3b7251bac9c439e71d812a0c72f2c260c8cd4dbe59af) | refused: terms_hash does not match the agreement | held |
| `accept:REFUSALS` | [`0x04f09557...`](https://explorer-studio.genlayer.com/tx/0x04f0955771c7bef5a489bb3f4ab6decf930e3b9f14990636ceba61156168a92f) | accept_agreement FINALIZED/SUCCESS |  |
| `refuse:outside_domains` | [`0x81fa00bf...`](https://explorer-studio.genlayer.com/tx/0x81fa00bfb4de1fcb978bdb0dd63bf955c8d767ad70eb7e70c887133e1cf98d57) | refused: translation_url is outside the agreement's evidence domains | held |
| `refuse:source_as_translation` | [`0xf6dfb2a4...`](https://explorer-studio.genlayer.com/tx/0xf6dfb2a43f51af8595aca1fe4b81d199d010cbea9cf55dc016608a09b019790a) | refused: the translation's bytes are the source's bytes | held |
| `refuse:stranger_delivers` | [`0x1d997f05...`](https://explorer-studio.genlayer.com/tx/0x1d997f05136dea4723fdf2c0c381bad2c7074ba432d8e99593ff0ba6a44150d3) | refused: only the named translator delivers | held |
| `refuse:accepted_cancel` | [`0x0d060f1a...`](https://explorer-studio.genlayer.com/tx/0x0d060f1a2f9c92111ec9861de0ab7704e5ad1645990e53b55d0dfa213ab85683) | refused: only a PROPOSED agreement can be cancelled | held |
| `refuse:double_assessment` | [`0x9547c82a...`](https://explorer-studio.genlayer.com/tx/0x9547c82a895212134f75383f3e077768139cd6c59d7d15762efd892e42023839) | refused: only a DELIVERED agreement is assessed | held |
| `refuse:stranger_contest` | [`0xff71d004...`](https://explorer-studio.genlayer.com/tx/0xff71d004167a7b572c397d59e4b456be3ec4f127cf89b5db131abb671415782b) | refused: only the requester or the translator contests an outcome | held |
| `refuse:final_contest` | [`0x46a77838...`](https://explorer-studio.genlayer.com/tx/0x46a77838e5acdbc33e41e6502f69bc419957ff9963276f25c914679c602ef3c4) | refused: only an ASSESSED agreement is contested | held |

## Mutation sweeps

| Sweep | Result |
|---|---|
| `deploy/mutation_sweep_first.txt` - the first sweep, on the first contract and suite | 79 mutations, 67 killed, 12 survived |
| `deploy/mutation_sweep.txt` - the sweep of record, on the canonical contract and the final suite | 80 mutations, **80 killed, 0 survived** |

Every survivor of the first sweep was a gap in the tests, and each now has the
test that kills it - fetch statuses, a title injection, an oversized document,
the which-document rule forged directly into a payload, a misrendered term
asserted without a quote, an optional requirement, a stranger declining, the
gate's own check of the code checks, and a deterministic failure offered to a
transient one. One mutation is documented as equivalent rather than counted: the
code checks are compared twice - in the retrieval comparison and inside the
consequence - and are pure functions of the bound bytes, so removing either
comparison alone changes nothing; a test forging the checks with nothing else
changed pins the pair.
