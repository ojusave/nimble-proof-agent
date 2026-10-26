# System design

The user uploads or reuses a résumé, enters optional preferences, chooses a count (default five), and clicks Find jobs. No separate setup wizard.

FastAPI creates a run and returns its ID immediately. A background worker runs a LangGraph workflow. The browser subscribes to its SSE stream; ordered events are persisted in SQLite and replayed on reconnect. One search is active per local server.

## Workflow state

Profile, original preferences, explicit requirements, requested count, search round, seen URLs, candidates, accepted matches, unknowns, exclusions, warnings, and final shortlist.

The graph is prepare → plan → discover → screen → finish. After screening, a conditional edge returns to planning if fewer matches qualify and the round budget remains. Original requirements are retained verbatim during replanning.

## Replaceability

Business rules depend on SearchProvider, ExtractProvider, and Reasoner protocols. LangGraph is isolated in its runner. Composition wires the adapters; settings own keys and limits. The UI consumes domain events and job records, not provider SDK objects.

## Evidence and decision rules

A candidate must be an individual opening on an employer domain or recognized employer ATS. The model identifies the employer website; domain checks reject aggregators and mismatched hosts. This is evidence-based classification, not independent certification of domain ownership.

Application availability needs an exact quote. Every explicit requirement is met, conflicting, or unknown. Missing checks and unverified quotes become unknown. Conflicts are excluded. At least one professional strength must have an exact résumé quote and exact listing quote. Protected or sensitive traits must not be used for matching.

Matching is still model-based and can misinterpret text. Word matching does not prove entailment, current availability, or suitability. The UI exposes evidence and gaps for review. Unknown jobs are separate from qualifying matches.

## Real-time events

Events include type, stage, timestamp, tool, safe inputs, and actual output summaries. Events are emitted before and after calls; accepted/unknown/excluded records are emitted per candidate. Listing assessments run concurrently with at most two workers. IDs are assigned locally; requirement checks use fixed schema keys, so model-generated IDs cannot mix up listings. Providers may stream public progress; hidden reasoning is not requested or displayed.

The stream reads a run-state snapshot before fetching its remaining events, preventing a final event from being skipped when completion races with delivery. Last-Event-ID allows reconnect without replaying old events.

## Persistence and lifecycle

Files and extracted résumé text are local. Removal deletes both; derived evidence in search history remains. Files and the database use owner-only permissions. Events never contain full résumés or credentials.

The server runs independently of the browser. Local workflow execution is not checkpointed across server restarts; interrupted searches are marked accordingly. LangGraph checkpoint resumption, cancellation, authentication, and multi-user deployment are future work.
