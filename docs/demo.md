# Demo

1. Set `NIMBLE_API_KEY` in `.env` and start `python3 app.py serve`.
2. Ask a narrow comparison question using first-party documentation.
3. Show the remote run status, then the local source reads and quote checks.
4. Open a cited page and compare its text with the finding.
5. Export the brief. Explain any gaps.

Record a successful live run as a backup. The offline demo uses fictional data; do not present it as a live result.

## Talk outline — 20 minutes

- **0–3:** Why a source link alone is not enough to trust an answer.
- **3–6:** Nimble researches; the app checks quoted evidence.
- **6–12:** Run the demo and inspect a source.
- **12–16:** Show a rejected quote and explain the limits of text matching.
- **16–20:** Walk through the code, tradeoffs, and next steps.

## Q&A

- **Where is the reasoning?** Nimble's hosted Agent API.
- **Why Extract too?** An independent retrieval checks the quote against current page text.
- **What does the app prove?** That the returned quote was retrieved, not that its claim is true.
- **What happens on timeout?** The local client stops waiting; the remote run may continue. Inspect its saved IDs before resubmitting.
- **What needs more work?** Resuming remote runs, cancellation, cost reporting, and measured evaluations.
