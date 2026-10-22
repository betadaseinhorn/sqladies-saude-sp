---
version: 1
slug: "static-landing-html"
primary_target: "static/landing.html"
related_targets: []
---

# Landing do DataCare_ (`/`)

Mode: Persuade.

Audience: people from many companies, general visitors and recruiters seeing the project.

Job: understand within seconds what DataCare_ is, why it matters and that it works, then try it in `/app`.

Proof available:
- the working app and its real data (5.7 million hospitalizations, 645 municipalities, 2024–2025);
- the Oracle SQL behind every answer;
- the slides' content;
- the results reported by the team, always attributed.

Constraints:
- the approved colors and logo stay;
- offline, with no CDN;
- no team names or student IDs;
- the delivered product (Select AI, APEX, Power BI, OES) is kept separate from this demonstration.

## Direction contract
THESIS: the category standard for a data product (headline, working question box, the real dashboard as proof, then sources) at Vercel's level of craft. It refuses decoration that stands in for evidence.

OWN-WORLD:
- light page on lilac-tinted white `#f4f1f9`, with cream `#fffef8` surfaces;
- deep purple `#230e50` ink and violet `#7e3ee0` for actions only;
- dark theme in deep purples;
- Geist for UI and display, Geist Mono for SQL and figures;
- hairline borders, an 8px radius family and real screenshots in browser frames;
- the brain-circuit icon and the "DataCare_" wordmark.

STORY:
1. The data exists but decisions arrive late.
2. Ask in Portuguese and get a dashboard with alerts, reasons and actions.
3. It is real (live numbers, real screens, the SQL shown).
4. Open the app.

FIRST VIEWPORT:
- Navigation bar: logo on the left; anchors in the middle; "Abrir o DataCare" on the right.
- Left 45%: a two-line Geist headline (about 64px), one line of subcopy, a working question box that opens `/app#pergunta=`, and three example chips.
- Right 55%: the real dashboard screenshot in a browser frame, in a light or dark version to match the theme.
- Below it: a strip of four live figures.

FORM: canon (category standard), chosen by the user; seed: a7300240ebaf6239. Signature interaction: the question box placeholder cycles through real catalog questions, and Enter opens that dashboard. Motion: a view transition between the landing and the app.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
