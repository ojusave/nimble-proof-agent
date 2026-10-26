# Demo walkthrough

1. Upload a résumé or select the saved fictional sample.
2. Enter explicit preferences and request five jobs.
3. Open the activity feed: show generated queries, Search results, Extract output, and Agent task status.
4. Open a match card and compare its résumé quote with its job quote.
5. Open Needs review. Explain why an unknown location or salary does not count as a match.
6. Show one excluded listing and its conflicting requirement.
7. Show the final ranking or shortfall prompt. Requirements never broaden silently.
8. Export the shortlist.

Use real employer listings for the conference demo. Record a successful live run as backup. The sample search is fictional and labelled accordingly.

## 20-minute talk

- 0–3: Résumé search finds plausible jobs; a usable shortlist needs actual requirements and current listing evidence.
- 3–6: Walk through the user flow and modular LangGraph architecture.
- 6–12: Run the agent, inspect a match, and explain an exclusion.
- 12–16: Show strict/unknown criteria, quote checks, provider delays, and failure handling.
- 16–20: Explain Nimble's three roles, the open-source components, tradeoffs, and how to replace a provider.

Do not present quote matching as proof that a vacancy is open or a recommendation is correct. Do not claim superiority over other search providers without a measured comparison.

## Live verification

Search and Extract found a real SerpApi Python Developer Advocate listing. A Nimble Agent research run returned a structured assessment. Local validation found shared Python evidence, but marked the listing for review because requirement/application quotations could not be verified verbatim. This is a provider integration check, not a guarantee of current vacancy availability.
