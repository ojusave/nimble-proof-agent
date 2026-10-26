# Design

Nimble Agent API handles research and reasoning. Python manages the run, checks evidence, and saves it to SQLite. JavaScript displays progress and results. No separate model API key is needed.

## Evidence

The agent returns up to five findings with quotes and source URLs. URLs must appear in its source report. Proof then calls Nimble Extract on each cited page and checks the quoted text. Rejected findings appear under gaps. If no finding passes, the run fails. For partial results, a factual status line replaces the generated summary.

This checks text provenance, not truth or logical entailment. Dynamic pages, extraction differences, and page changes can cause valid quotes to fail. Source text is rendered as plain text.

## Remote lifecycle

Create a low-effort run, poll its state, then fetch the structured output. The create request has no automatic retries: a lost response could still have created a paid job. Read requests retry transient HTTP errors twice.

The client waits for up to five minutes between requests. Individual HTTP requests can take 90 seconds, and extraction adds time. If waiting stops, the remote run may continue. Its IDs remain in the activity log; the app does not cancel it or start a replacement automatically.

The local server accepts one run at a time. Runs do not resume automatically after restart. The remote research agent's internal search count and monetary cost are controlled by Nimble, not the old local demo tool budget.

## Demo

The offline demo retains a small scripted tool loop to exercise the ledger and UI without credentials. It is labelled synthetic and does not call the hosted agent.
