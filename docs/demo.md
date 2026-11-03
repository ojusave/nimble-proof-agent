# Demo and talk notes

The talk's question is **how much research an application should own and how much it should delegate**. Proof is a small case study that makes the boundaries visible. The audience should leave able to choose a discovery call, a page read, or a research task—and explain what they still need to validate themselves.

## A short demo, not the whole talk

Allow two to three minutes. Prepare a completed live run and keep the labelled fictional sample available for the UI walkthrough. A research task can take minutes; do not make the talk wait for it.

1. Show the résumé, explicit preferences, and requested result count.
2. Open one result. Compare its résumé quotation with its captured listing quotation.
3. Open Needs review. Show why missing region or salary evidence cannot count as a confirmed preference.
4. Open research sources. Separate the provider's citations/confidence from the app's local quote check.
5. Show one excluded listing or a shortfall. Requirements never broaden silently.
6. Use **Follow this opening in the activity trace**. Expand the recorded retrieval and research outcomes, then the separate local decision. Show original timestamps on replay and download the recorded trace if someone wants to inspect the calls.

The learning point is the decision boundary: finding a plausible URL, reading a page, and deciding what to accept are different operations.

## Source walkthrough

Keep these tabs ready, in this order:

| File | Point to show |
| --- | --- |
| [`search.py`](../adapters/nimble/search.py) | Discovery returns candidates; the request is small and explicit. |
| [`extract.py`](../adapters/nimble/extract.py) | A known URL becomes retrieved text. |
| [`prompts.py`](../workflows/prompts.py) | The scope, constraints, and evidence budget are visible instructions. |
| [`agent.py`](../adapters/nimble/agent.py) | Create once, observe status, retrieve structured content and trust. |
| [`job_matcher.py`](../workflows/job_matcher.py) | `validate` owns the final decision; unknowns do not become matches. |
| [`composition.py`](../composition.py) | Each API is a separate adapter; workflow rules remain independent. |
| [`ui/core/ports.ts`](../ui/core/ports.ts), [`ui/composition.tsx`](../ui/composition.tsx) | The same trace view works through CopilotKit/AG-UI or native SSE. |

Avoid opening `.env`, real uploaded résumés, or private search history on stage. Use the fictional résumé with live employer data for a reproducible integration example.

## 20-minute shape

| Time | Topic | Audience takeaway |
| --- | --- | --- |
| 0–3 | A plausible result can still be unusable | Define what a valid answer must establish before choosing tools. |
| 3–6 | Discovery, retrieval, and investigation | Choose the smallest useful unit of work; use local code for routine planning. |
| 6–9 | Short Proof demo | Watch a missing fact change the outcome, with evidence visible. |
| 9–13 | Source walkthrough | Separate API transport, task instructions, evidence, and application policy. |
| 13–17 | Failure cases | Handle truncated pages, uncited claims, paid-run retries, delays, and unknowns. |
| 17–20 | Transfer the pattern | Apply the same boundaries to supplier checks, research tools, or support assistants. |

Do not describe quote matching as proof of truth, confidence as a probability of correctness, or this project as a benchmark against other providers. The three APIs illustrate the design choices; using every API is not a goal in itself.

## Optional research beyond the résumé

The expanded flow adds a second Nimble research branch for public professional work, then lets the user select one role for a Nimble follow-up. Show one requirement → artifact quote → proposed bullet connection, with a gap that remains unresolved. The applicant confirms attribution and wording before downloading a separate draft; no perfect-fit score or invented experience is produced.

For a code walkthrough, add `runners/resume_ingestion.py`, `adapters/llamaindex/parser.py`, and `workflows/applicant_research.py`, and `workflows/resume_tailoring.py`. Explain why the job-search subgraph runs alongside applicant research rather than waiting at the first planning-node barrier. Prepare completed research beforehand; early candidate cards show responsiveness without claiming the underlying investigation is instant.
