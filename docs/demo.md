# Demo walkthrough

## Before presenting

1. Add real API keys to the local `.env`, restart the server, and run a narrow live question.
2. Verify the resulting findings against their quoted sources. Check Nimble quota and Anthropic model access.
3. Save the Markdown output. Record a successful live run as a network-failure backup; a synthetic demo is not a recording of live research.
4. Keep keys, account screens, and `.env` out of screen recordings.

## A 20-minute talk

**0–3 minutes — The problem.** Put a polished answer next to a primary source that contradicts it. Ask: “What would you need to inspect before trusting this?” Explain why current platform features and plan restrictions require live documentation.

**3–6 — The architecture.** Show the README diagram. Explain the separation between deciding what to investigate, retrieving web evidence, and checking whether a quotation was actually retrieved.

**6–12 — Live run.** Compare two developer platforms on one concrete capability. Start research, narrate the search/read trail, inspect a finding, open its source, and export the brief. Call out one unresolved question. Use real API output; do not pass off synthetic fixtures as a live run.

**12–16 — The failure case.** Show `test_rejects_fabricated_quotes` and `test_recovers_after_bad_quote`. Explain why a readable page or an HTTP 200 is not the same as a supported answer. Distinguish a matching quote from proof that a claim is true.

**16–18 — Nimble’s role.** Show discovery with Search and page reading with Extract. Discuss what you would measure to compare providers: successful extractions, answerable questions, latency, and cost. Do not claim benchmark results that have not been measured.

**18–20 — Lessons.** Give the audience three patterns they can reuse: bounded tools, a source ledger, and explicit gaps. Close with the repository and one command to run the demo.

## Q&A preparation

- Why is it an agent? The model chooses and revises searches and reads based on tool feedback.
- What stops invented citations? Sources must exist in the ledger, be read, and contain the quoted text.
- What is still unsolved? Source trust, entailment, freshness, prompt injection, and cost predictability.
- What happens without API keys? The synthetic demo works; live mode fails with a clear configuration error.
- Why SQLite? Easy local setup and inspectable run history. It is not an enterprise multi-user data layer.
- Next steps? Measured live evaluations, resumable jobs, semantic entailment checks, and a human review stage.
