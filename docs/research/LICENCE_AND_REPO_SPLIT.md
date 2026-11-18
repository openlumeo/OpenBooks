# Licence and public/private repository split

Status: **recommendations and tooling. No licence file has been added, no repository has been made public, no names have been
claimed.** Date: 2026-11-18. Facts marked **[V]** were checked in this session; **[U]** is unverified; **[R]** is a recommendation.
This is engineering analysis, not legal advice: have counsel review the licence choice and the PyMuPDF question before publishing.

---

## 1. Where things stand

- The repository `Sagexd08/OpenBooks` is **private** and has **no licence** [V]. With no licence, all rights are reserved: nobody may
  use, copy or modify the code, so publishing packages without one would make them unusable and legally ambiguous.
- It holds both what is meant to be open (schema, parsers, validators, grader, benchmark) and what is meant to stay closed
  (matching, training recipe, task factory, the hosted web app and API), plus their history [V: your pipeline diagram, `docs/PACKAGES.md`].
- The code is already separated by folder: five public Python packages plus the `openbooks` meta package, the `packages/js`
  workspace, and a private `packages/py/openbooks-lab`.

## 2. Dependency licences (what a licence for our code has to live with)

| Dependency | Reaches users via | Licence [V: from the installed package metadata] |
|---|---|---|
| jsonschema, openpyxl, referencing, rpds-py, attrs | core, every provider | MIT |
| **PyMuPDF** | `statements[pdf]`, `[scan]`, and therefore the `openbooks` meta package | **"Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License"** |
| EasyOCR | `statements[scan]` | Apache-2.0 |
| python-bidi (pulled in by EasyOCR) | `statements[scan]` | **LGPL** |
| PyTorch, torchvision, NumPy, SciPy, Pillow | `statements[scan]` | BSD / MIT-style |
| FastAPI, uvicorn, python-multipart | the hosted server only | MIT / BSD / Apache-2.0 |
| npm: Ajv, Commander and everything the packages ship with | JS packages | MIT, BSD-3, ISC, Apache-2.0 (dev tooling also includes one Python-2.0 package) |

Nothing except **PyMuPDF** forces a choice. python-bidi's LGPL permits ordinary use as an installed library; mention it in the notices.
The shipped model weights were trained from scratch on synthetic data we generate (`models/roles_manifest.json`, kept private, says so
and lists the datasets that were excluded). That makes them ours to license, but a model needs its own explicit licence statement.

## 3. The PyMuPDF problem (the one that actually matters)

**What it is.** Artifex offers PyMuPDF under AGPL-3.0 or a paid commercial licence. Artifex's published guidance is that software
delivered over a network (SaaS) that uses it under the AGPL must make its own source available to its users, and that the
commercial licence is the alternative (searched; Artifex does not publish prices) [U: confirm with Artifex and counsel].

**Why it bites here.** Lumeo's hosted engine runs `openbooks-statements[pdf]` in-process, next to **closed** matching and task code. If
the AGPL applied to that combined service, the closed parts would be at risk. Separately, anyone installing our `openbooks` meta
package gets PyMuPDF, so our "permissive" open core would carry AGPL obligations for their users in practice.

**How much code depends on it [V].** Only `openbooks_statements/pdf_front.py` and `frontend.py` use it in the public path, for six
things: open a document, check the password flag, count pages, read page size, extract text as characters/words with boxes
(`get_text("rawdict")`), and render a page to an image for OCR. The private lab also uses it to generate synthetic PDFs (offline
training; and the hosted sample catalogue, which imports those builders at runtime and should switch to committed fixtures).

**Options.**

| | A. Buy the Artifex commercial licence | B. Replace it with permissive libraries | C. Accept AGPL for the open packages |
|---|---|---|---|
| Open core licence story | still AGPL for anyone using `[pdf]` unless they also buy | clean: everything Apache/MIT/BSD | AGPL packages, or Apache code with an AGPL dependency |
| Hosted Lumeo | covered | covered (no PyMuPDF at all) | closed code at risk; not viable |
| Cost | licence fee, unknown (not published) | engineering, once | none now |
| Risk | vendor dependency and renewal | behaviour change: word boundaries differ, so heads and baselines must be re-validated | the closed/open split collapses |
| Effort | procurement | moderate, contained to ~4 places | none |

**[R] B for the open core, A (or B) for the hosted service while B is built.** Candidates [U: verify APIs before committing]: **pypdfium2**
(Apache-2.0; rendering and character boxes; word grouping is ours to write), **pdfminer.six** or **pdfplumber** (MIT; character and
word boxes). Plan: introduce a small `PdfBackend` interface (pages, words with boxes, render at DPI) in `openbooks-statements`, keep
PyMuPDF as an optional `[pymupdf]` backend, add the permissive backend, and make it the default for `[pdf]`.

**The safety net already exists.** The 88-result PDF baseline (recorded on the pre-refactor engine) and the 69-case OCR golden set
already run in CI. A new backend must reproduce the baseline's released/refused decisions with zero false accepts; any word-boundary
difference that changes a hash needs a reviewed re-record. Expect the typed heads to need re-checking too: they were trained on
tokens produced by PyMuPDF's word splitting. They can only add refusals, so the failure mode is more `LOW_CONFIDENCE`, not wrong
releases, but measure it.

## 4. Licence choice for our own code

| | Apache-2.0 | MIT | AGPL-3.0 (+ commercial dual licence) | Source-available (BSL, etc.) |
|---|---|---|---|---|
| Patent grant | yes | no | yes | varies |
| Adoption by finance/enterprise users | high | high | low (many ban AGPL) | low, and not open source |
| Stops a competitor hosting it | no | no | yes | yes (time-limited) |
| Fits "open parsers, closed matching/hosted" | yes | yes | works but heavy | muddies the "open" message |

**[R] Apache-2.0** for all six Python packages and all six npm packages. Reasons: the moat is not the parsers (it is matching, hosted
service, data and models, all of which stay closed), so copyleft protection buys little; the patent grant matters in financial
infrastructure; and adoption is the goal of publishing. Pair it with a `NOTICE` file, a **trademark policy** for "Open Books" and
"Lumeo" (Apache-2.0 grants no trademark rights, but say so explicitly), and **DCO sign-off** for contributions (a CLA only if you
later want to relicense; DCO is lighter and already in the draft `CONTRIBUTING.md`).

**Model weights.** Decide separately whether `roles_head.pt` is Apache-2.0 too or under a model licence. [R] Apache-2.0 with the
model card stating synthetic-only training; it is a cross-check that can only add refusals, so there is little to protect.

## 5. The repository split

### 5.1 What goes where

| Public repository (new, fresh history) | Private repository (this one, becomes the platform) |
|---|---|
| `packages/py/openbooks-{core,gateways,tax,statements,doctor}`, `packages/py/openbooks` | `server/`, `web/` (hosted product, LLM prompts) |
| `packages/js/*` | `packages/py/openbooks-lab` (synthetic data, golden builders, calibration fitting, matching) |
| `models/roles_head.pt`, `roles_calibration.json`, `roles_model_card.json` | `scripts/` (training, promotion gate, evaluation), `models/roles_manifest.json` and any other model artefacts |
| `tests/packaging`, `tests/test_cli_machine.py`, `tests/test_model_card.py`, each package's own tests | `tests/` (golden-set, characterisation, PDF and OCR suites that need the lab package) |
| public `README`, `CONTRIBUTING`, `SECURITY`, `THIRD_PARTY`, `LICENSE`, public CI | `docs/` (HANDOFF, evidence, format catalogue, datasets, pipeline diagram, research), `PRODUCT.md` |

This is exactly what `scripts/export_public.py` implements: an **allow-list** (nothing is public by default), then a scan that fails the
export on private strings, private paths, personal or machine details, or unexpected binary files.

### 5.2 Verified [V]
- A real export (128 files, 19.4 MB) into an empty directory, then a **fresh virtual environment** installing only that tree: 196 tests
  passed, 14 packaging tests passed (every wheel built, file lists exact, no private names in any wheel). The lab package was not installed.
- The scan caught real leaks in files I had assumed were public (a comment naming the internal pretrained encoder, a constant naming
  the private training manifest, a doc pointing at private evidence, a dataset name in a docstring, a test naming the private package).
  All are fixed at the source and guarded by `tests/test_export_public.py`.
- The weights file itself contains only tensors and references to `torch` and `OrderedDict`: no paths, names or machine details.

### 5.3 History
**Do not make this repository public and do not push its history.** It contains the training recipe, evidence, the hosted product and
the lineage of the weights. Rewriting history afterwards does not remove forks, clones or caches. Start the public repo from the export
with one fresh commit.

### 5.4 Source of truth after the split
- **[R] Public repo is the source of truth for the open packages; the private repo consumes it** (git submodule at `vendor/openbooks`, or a
  pinned git dependency), and the private tests that need the lab package run against it. This is what lets outside contributions land
  without manual back-porting.
- Alternative: keep this repo as the source of truth and re-export periodically. Simpler for the first months, but every outside
  contribution then needs hand-porting and the two histories drift. Use it only until the public repo has real contributors.
- Either way keep `scripts/export_public.py` (or the equivalent check) in CI as a guard.

### 5.5 Weights in git
19 MB per retrain is acceptable once but bloats history. [R] Keep the current weights in the public repo for the first release (the
wheel needs them), and move later versions to GitHub release assets plus the wheel, so the repository history stays small.

### 5.6 Housekeeping in the new repo
Branch protection on `main`; required CI; private vulnerability reporting enabled (the draft `SECURITY.md` assumes this); a
DCO check; `CODEOWNERS`; Dependabot; secret scanning. Public CI must not receive any credential for the private repo or private index.

## 6. Names [V]
All six PyPI names (`openbooks`, `-core`, `-statements`, `-gateways`, `-tax`, `-doctor`) and all six npm names (`openbooks`, `@openbooks/{core,statements,gateways,tax,doctor}`)
currently return 404, i.e. unclaimed packages. **A 404 on a scoped package does not prove the `@openbooks` scope is free**, and a name
can be taken between now and publishing. Create the npm organisation and a PyPI project (or pending trusted publisher) for each name
**first**; that is an account action only you can take. The private package is named `lumeo-openbooks-lab` and must never be uploaded
(it carries the `Private :: Do Not Upload` classifier, so PyPI would refuse it).

## 7. Decisions needed from you

1. **Licence** for code (Apache-2.0 recommended) and for the weights.
2. **PyMuPDF**: B (replace) for the open core, and for the hosted service either buy A in the meantime or accept holding off hosted PDF until B lands. Ask Artifex for a quote in parallel; it costs nothing to ask.
3. **Source of truth** after the split (public + submodule recommended).
4. **Owner of the new public repository** (organisation or user), its name, and the contact for the trademark policy and security reports.
5. Whether the public README may state the validation status as written (synthetic fixtures only, experimental layouts).

## 8. Runbook once you decide (nothing below has been done)

1. Counsel reviews the licence and the PyMuPDF position. Request the Artifex quote.
2. Put the chosen licence text in a file and run: `python scripts/export_public.py ../openbooks-public --licence-file LICENSE.txt` (fails on any private material).
3. In `../openbooks-public`: `git init`, one commit, create the empty public repo under the chosen owner, push. Enable branch protection, private vulnerability reporting, secret scanning.
4. Confirm the public CI is green on its own (it never sees the lab package).
5. In this repo: add the public repo as a submodule, point the private tests at it, and drop the duplicated paths.
6. Reserve the PyPI and npm names; set up trusted publishing from the public repo (see `OPENBOOKS_PACKAGING_RESEARCH.md` section 11).
7. Build the permissive PDF backend (section 3) before any public release that includes `[pdf]`.
8. Only then: TestPyPI and an npm dry run, then release candidates.

## 9. Risks
- **Publishing before the PyMuPDF decision** would tie the open core to AGPL by default through the meta package. Gate the first release on section 3.
- **A leak through a path the scanner does not know about.** The scanner is an allow-list plus pattern checks, not a guarantee; review the export diff by eye the first time and keep the guard test.
- **Behaviour drift when swapping the PDF backend.** Mitigated by the two baselines and the OCR golden set, but treat any change in a recorded hash as a decision, not a formality.
- **Weights lineage claim.** "Trained from scratch on synthetic data" rests on `models/roles_manifest.json`; keep that file and the training scripts private but preserved as the evidence.

## Sources
- PyMuPDF licensing and Artifex's AGPL/SaaS guidance (searched): https://pymupdf.readthedocs.io/en/latest/about.html , https://artifex.com/blog/pymupdf-acquired-by-artifex
- PDF library alternatives, third-party comparison (searched; verify before relying): https://github.com/datalab-to/pdftext
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0 ; Developer Certificate of Origin: https://developercertificate.org/
- GitHub private vulnerability reporting: https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability
