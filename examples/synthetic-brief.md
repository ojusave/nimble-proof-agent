# Two platforms. Four claims. Every claim has a receipt.

> Mode: synthetic offline demo

In this synthetic scenario, Atlas exports daily and offers private networking on Enterprise; Beacon exports weekly and does not offer private networking.

## Findings

- Atlas supports daily CSV exports.
  - Evidence: “Scheduled CSV exports run every day.”
  - [S1](https://atlas.example.com/docs/exports)

- Atlas limits private networking to Enterprise.
  - Evidence: “Private networking is available on the Enterprise plan.”
  - [S1](https://atlas.example.com/docs/exports)

- Beacon supports weekly CSV exports.
  - Evidence: “Scheduled CSV exports run every week.”
  - [S2](https://beacon.example.com/docs/exports)

- Beacon does not currently offer private networking.
  - Evidence: “Private networking is not currently available.”
  - [S2](https://beacon.example.com/docs/exports)

## Gaps and limitations

- All companies and source text in this demo are fictional. No live Nimble or Anthropic requests were made.
- The scripted model demonstrates orchestration and validation; it does not test autonomous model reasoning.

Quote matching verifies provenance, not whether a source is true or a claim follows from it.
