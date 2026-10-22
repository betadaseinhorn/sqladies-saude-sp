# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
- **Landing page (`/`):** people from many companies, general visitors and recruiters who come to see the project. They want to understand quickly what was built, why it matters and whether it works, and then try it. Confirmed by the team on 2026-10-22.
- **Application (`/app`):** in the product's own story (presentation slides), the user is a manager in Brazilian public health: a state or municipal health secretariat, a regional health department (DRS) or a public hospital. Their job is to understand demand, capacity and seasonality without writing SQL.

## Product Purpose
DataCare_ ("Transformando dados em cuidado e decisão") is a conversational platform that supports public hospital management. The user asks a question in Portuguese and gets back a dashboard built from public data:
- SIH/SUS hospitalizations;
- the CNES registry of facilities and beds;
- IBGE population.

The problem it addresses comes from the slides. The data exists, but it is fragmented, decentralized and depends on manual treatment. Management therefore stays reactive and cannot see its own operation, which leads to bottlenecks and overcrowding, wasted public money and wasted human effort.

Success means three things: a question answered in time to act, no dependence on technical staff, and insights a manager can act on.

## Positioning
- Natural language replaces SQL, so access to information is democratized.
- The public databases are unified.
- Every answer comes with alerts (Aceitável / Alerta / Crítico), why the question matters, suggested actions, and the Oracle SQL behind it.
- Ethics and LGPD are built into the design.

This repository is a **demonstrative, offline adaptation** of the work the SQLadies team delivered to Oracle in the Challenge Oracle + FIAP.

## Operating Context
**The product delivered to Oracle (from the slides):**
- Oracle Autonomous Database, Select AI (natural language to SQL), OML4Py (K-means), APEX (interface), Oracle Ethics Shield and Power BI.

**This demonstration:**
- FastAPI, plain HTML/CSS/JS and SQLite;
- no LLM: questions are matched to a catalog of 18 analyses;
- it runs fully offline.

## Capabilities and Constraints
**What the demonstration does:**
- natural-language questions mapped to 18 analyses in 5 categories: overview, seasonality, rankings and comparisons, capacity, and patterns and factors;
- per-tab conversation turns with follow-up suggestions;
- editable filters;
- alerts, "Por que essa pergunta importa", Plotly charts and municipal maps;
- sortable tables with CSV export, print/PDF, and the Oracle SQL behind each answer.

**Data:** the 645 municipalities of São Paulo state, 2024–2025. K-means groups **municipalities** into 3 profiles.

**Do not claim** that this demonstration runs Select AI, an LLM, Power BI, APEX or real-time data. Those belong to the delivered product.

## Brand Commitments
- **Name:** DataCare_, with the trailing underscore. The group is SQLadies; the context line is "Challenge Oracle + FIAP".
- **Tagline:** "Transformando dados em cuidado e decisão".
- **Colors, approved and fixed:**

  | Role | Hex |
  |---|---|
  | Violet | `#7E3EE0` |
  | Background violet | `#8134EC` |
  | Deep purple | `#230E50` |
  | Lilac | `#BFAED8` |
  | Cream | `#FFFEF3` |

  The chart palette and the status colors (green, yellow, red) are approved.
- **Logo:** the wordmark "DataCare_" ("Data" and "_" violet, "Care" deep purple) and the brain-circuit line icon are approved. An earlier "D_" monogram was rejected.
- **Assets:** the cover art is `static/marca/capa-topo.webp`, cropped above the members' names.
- **Team:** shown only as the group name SQLadies. No member names or student IDs (RMs) in public material.
- **Framing:** commits, README and footer must say this is a "demonstrative adaptation of the project delivered to Oracle".
- **Standing preference:** the landing follows the category standard for a data product (headline, real product view, sources), executed at **Vercel's** level of craft. The team chose this on 2026-10-22 over bolder directions.

## Evidence on Hand
- **Real database:** about 5.7 million hospitalizations, 645 municipalities, 2024–2025, reachable through the API.
- **Team presentation:** 15 slides in `Downloads/Apresentacao_Banca_SQLadies/`. They are not in the repository.
- **Results reported by the team** for the delivered product: −85% in decision time during crises and −70% in dependence on IT for reports. They must always be attributed to the team, never presented as measured by this demonstration.
- **Pitch video:** https://www.youtube.com/watch?v=zK9VKLOwr8s (external).
- **Absent, and not to be fabricated:** testimonials, customer logos, adoption figures, pricing.

## Product Principles
1. Show the real thing: the working app and its real data are the proof, not claims.
2. Be honest about scope: always separate the delivered Oracle product from this offline demonstration.
3. A question goes straight to action: every answer explains why it matters and what to do.
4. Work without technical help: no SQL, no setup for the visitor, and offline by default.

## Accessibility & Inclusion
WCAG 2.2 AA:
- light and dark themes, 390px mobile, keyboard navigation, reduced motion;
- status is never shown by color alone;
- the content is in Brazilian Portuguese.
