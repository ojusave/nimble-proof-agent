# Open-source components

The application code is MIT licensed. Dependencies retain their own licenses:

- LangGraph: MIT — https://github.com/langchain-ai/langgraph
- FastAPI: MIT — https://github.com/fastapi/fastapi
- Uvicorn: BSD-3-Clause — https://github.com/encode/uvicorn
- HTTPX: BSD-3-Clause — https://github.com/encode/httpx
- pypdf: BSD-3-Clause — https://github.com/py-pdf/pypdf
- SQLite: public domain — https://www.sqlite.org/copyright.html
- React and Next.js: MIT — https://github.com/facebook/react, https://github.com/vercel/next.js
- CopilotKit: MIT (installed core packages; optional paid services have separate terms) — https://github.com/CopilotKit/CopilotKit
- AG-UI: MIT — https://github.com/ag-ui-protocol/ag-ui
- TanStack Query: MIT — https://github.com/TanStack/query
- Lucide: ISC — https://github.com/lucide-icons/lucide
- Playwright and Vitest (development): Apache-2.0 and MIT — https://github.com/microsoft/playwright, https://github.com/vitest-dev/vitest

Dependency notices are included with installed distributions. `requirements.lock` and `package-lock.json` record tested versions. Nimble's hosted APIs are proprietary services, billed under your Nimble account.

The search → enrichment → ranking pattern was informed by Nimble's public lead-generation cookbook: https://github.com/Nimbleway/cookbook-langchain-lead-gen. This project uses its own implementation; no cookbook source code is copied.
