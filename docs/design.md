# Design notes

## Keep the boundaries visible

Claude chooses actions. Nimble retrieves public web evidence. Python owns the source IDs and validates quotations. SQLite retains traces. The browser displays the result without trusting source HTML.

The model has no tool to execute code, send email, modify files, or request arbitrary local URLs. Source IDs prevent a final answer from introducing a never-retrieved citation.

## Why two web tools?

Search is for discovery. Extract is for inspection. A search snippet can omit the plan restriction that changes an answer. The validator therefore requires a successful read, even when Search already returns a plausible snippet.

## Why no framework?

The tool loop is small enough to read in one sitting. Framework abstraction would obscure the exact place where evidence is accepted or rejected. HTTP adapters use the Python standard library, making the offline demo runnable without package installation.

## Why not claim fact checking?

Substring matching can prove that text is present, not that it supports a claim. A second semantic judge could help, but would add another fallible model and more cost. The UI and exports expose quotes and gaps for human review.

## Budgets and failure

A live run allows 12 tool calls and 10 model turns, and each request has a 90-second timeout. Transient HTTP failures retry at most twice. These bounds limit work but do not constitute a guaranteed monetary ceiling. Provider errors are returned to the model for recovery; an exhausted run is explicitly failed.

The prototype accepts one running job. SQLite uses parameterized SQL and short-lived connections. Runs execute in a background thread; closing the app interrupts outstanding work. Resuming interrupted runs and cancellation are future work.

## Live evaluation plan

Use a versioned set of technical questions with human-checked sources. Record answer coverage, unsupported claims, quote acceptance/rejection, extraction failures, provider usage, and latency. Run the same set against alternative retrieval adapters. Report results only after collecting real data; synthetic fixtures cannot measure live quality.
