# Verification — November 2, 2026

These are local results for the provider split, evidence handling, and React/Next.js/CopilotKit migration. They are not a provider benchmark or evidence of job-market coverage.

## Automated checks

- 43 Python tests passed, including the full offline workflow, HTTP upload/start/result/SSE/export path, port binding, separate adapter composition, Agent lifecycle, trust retention, passage selection, malformed output isolation, fixed requirement IDs, rejection of fabricated evidence, AG-UI replay, failed runs, and concurrent tool identity.
- 13 JavaScript activity checks passed, including local-planner labels and retention of research provenance for excluded candidates.
- 15 Vitest checks passed for event deduplication, run state, requirement labels, operation outcomes, the loopback boundary, hosted password/origin checks, bounded request bodies, session expiry/tampering, and safe return paths. TypeScript checking passed.
- Next.js production compilation, type checking, and static page generation passed.
- 8 Chrome browser checks passed across desktop and mobile with CopilotKit: sample flow, evidence, exports, saved replay, interrupted connection recovery without creating a search, upload errors, incremental result delivery with evidence kept open, and failed-run presentation.
- The native SSE replacement passed the same 6 applicable browser checks; the 2 tests that deliberately interrupt a CopilotKit request were skipped for that transport. This verifies the replacement with the same components and workflow, rather than only asserting an interface.
- The offline CLI demo returned four matches, one opening needing review, and one exclusion for the fictional résumé and listings.

Browser checks used the isolated `work/review-data` database. The incremental/failed-run fixtures are explicitly controlled test records; they do not call Nimble. To include these tests locally, set `PROOF_TEST_DB` to that isolated server's `jobs.db`. CI uses `.test-data/jobs.db` and a blank Nimble key.

## Live Nimble flow

Executed `python scripts/verify_nimble.py --live` with the fictional résumé, preference **“Python developer advocate”**, one requested match, one search round, and at most two candidate assessments. The run began November 2 at 4:00 p.m. Pacific (November 3 at 00:00 UTC).

| Stage | Observed result |
| --- | --- |
| Upload and start | Fictional TXT résumé accepted; asynchronous search ID returned |
| Search | Two discovery searches returned six unique candidate URLs |
| Extract | Both selected URLs returned readable Markdown |
| Agent | Two remote runs were created once, observed, and completed; both returned structured content and trust |
| Application decision | Zero confirmed matches; one needs review; one excluded |
| Persistence and delivery | Ordered events and terminal SSE replay returned; Markdown export succeeded |

The [PyCon sponsor job listings page](https://us.pycon.org/2026/sponsorship/job-listings) was excluded because it contains multiple listings rather than a single employer opening.

The [SerpApi Python Developer Advocate page](https://serpapi.com/careers/python-developer-advocate) produced an assessment, one cited source, and 22 claim-level trust entries. Its provider-reported overall confidence was `medium`. Some citation excerpts were null, and résumé quotations were omitted; the app used its explicitly labelled shared-skill fallback where exact evidence existed.

The provider returned explanatory prose for the requirement and application-evidence fields, despite the prompt asking for exact quotations. Those whole strings were not in the captured passages, so local validation marked the checks unknown. The opening therefore remained in **Needs review**. A cited or high-confidence field did not bypass the app's quote check.

This verifies the real API wiring and conservative handling of imperfect output. **It does not demonstrate a confirmed live match.** Improving the provider's adherence to quote fields, or adding a separately evaluated evidence-repair step, remains future work; the app does not silently reinterpret prose as a verified quotation.

The full report, selected passages, trust objects, and fetched provider results are saved locally under the Git-ignored `work/nimble-verification-20261103T000051Z/`. Re-running verification uses paid API calls and may produce different listings and outcomes.

## Browser review

Chrome was checked against an isolated local database. The fictional sample exercised result cards, paired evidence, the review tab, local-planner activity, export, and saved-history replay. The completed live report was then replayed through the browser without new provider calls: source links, all 22 claim entries, confidence labels, the unknown decision, and exported run provenance were checked. Desktop and 390-pixel mobile layouts were checked for horizontal overflow, with no JavaScript page errors.

The same saved live report was replayed through the new CopilotKit/AG-UI route. It still showed zero confirmed matches and one opening needing review with 22 provider claim entries. This migration check did not make fresh paid Nimble calls. Reconnection tests observed multiple observer attempts with zero additional search-creation requests.

The README screenshot shows fictional sample data and is labelled as such in the app.

## Dependency limits

Compatible dependency updates were applied, including Next.js and Hono patches. The remaining npm audit advisories are transitive framework dependencies, including Zod 3 and KaTeX. A forced fix would replace major framework dependencies or change their expected schema APIs; it was not applied. Passing local tests does not establish that these advisories are harmless. Hosted mode now adds password and origin checks plus bounded API payloads. It remains a single shared demo workspace, not a multi-tenant product or a completed security review. The final audit is retained locally in `work/npm-audit-final.json`.

## Progressive activity and Stop

A controlled, key-free provider was exercised through the browser: while Search was waiting, only two real stages appeared, with no result cards, tabs, or zero counters. Releasing Search revealed retrieval activity. Clicking Stop showed Stopping until the in-flight extraction returned, then Stopped, without starting Agent research. New search cleared the résumé, preferences, results, and trace. Python tests cover idempotent stop, partial results, queued call prevention, and Agent observation termination.

## November 2 update: parsing, parallel research, and progressive results

The earlier measurements above describe the previous implementation. The current changes have passed **59 Python tests, 18 Vitest tests, and 13 activity checks**, including actual nested-node span identity, upload event streaming, saved parser provenance, location precedence, parallel job/applicant execution, native Nimble follow-up requests, quotation rejection, and reviewed draft export. A passing mock test establishes request handling, not a live provider result.

Live observations using isolated, ignored test artifacts:

- A generated one-page fictional PDF was parsed by LlamaParse’s agentic tier in about five seconds. Its `San Francisco, CA` header location was recovered. No personal résumé was used for this parser test.
- A location-aware Nimble Search/Extract/Agent flow found two stale employer URLs. One redirected to an index; the other was closed. Neither was presented as a fit rejection.
- A separate known-opening check for SerpApi’s Python Developer Advocate returned a confirmed match for the fictional résumé, with paired quotes passing local validation. This is a single observed match, not a coverage benchmark.
- Nimble applicant research against the owner’s public GitHub identity returned ten findings whose source/identity quotations passed recapture checks. A separate role-connection task returned six source-linked draft suggestions. Attribution and wording still require the applicant’s confirmation; no résumé was overwritten or published.
- The completed applicant run exposes native continuation context. The adapter reuses that context for on-demand role tailoring instead of creating a new applicant identity.

UI fixtures are labelled fictional and use isolated storage. The current interface shows discovered candidates before assessments, separates retrieval failures from exclusions even on older saved runs, and streams actual graph-node and parser events. Tailoring is now requested for a selected role; the search does not automatically create tailoring tasks for every result.

The on-demand role endpoint was also exercised through the production UI against Nimble’s native continuation API. It completed with seven reviewable additions, retained the original match and résumé, and emitted 26 recorded events including the `connect_role` span. The result is retained privately in ignored test storage.

README images were recaptured from the updated local production build. The shortlist, evidence, and execution trace use the no-API fictional sample; the résumé-suggestion image uses a labelled controlled fixture. Older duplicate images were removed.

A second generated-PDF upload through the production UI completed LlamaParse in 2.13 seconds and displayed parser job provenance, actual parse/profile node spans, and the inferred San Francisco location. Its screenshot is included in the README.

The feature commit `954c7b6` passed all 14 desktop/mobile browser checks in [GitHub Actions](https://github.com/ojusave/nimble-proof-agent/actions/runs/41580234181) and was deployed to the existing paid Render service. Hosted checks verified authentication, preserved data, the four-match sample, exports, SSE, and CopilotKit replay without creating another search. A generated fictional PDF produced its first streamed event in 0.11 seconds; a subsequent sample search reused the saved LlamaParse job and emitted no new parser submission.
