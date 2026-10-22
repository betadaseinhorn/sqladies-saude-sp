---
name: DataCare_
description: Transformando dados em cuidado e decisão. Ask in Portuguese, get a dashboard of SUS hospitalizations in São Paulo state.
colors:
  violet: "#7e3ee0"
  violet-dark: "#8d4be8"
  violet-wordmark-dark: "#a77bf3"
  violet-ink: "#5f27b8"
  violet-wash: "#efe7fc"
  deep-purple: "#230e50"
  deep-purple-final-dark: "#2a1556"
  cream: "#fffef3"
  surface: "#fffef8"
  surface-2: "#f1ecf8"
  page: "#f4f1f9"
  tabbar: "#ebe5f5"
  text: "#1d1433"
  text-2: "#4e3d70"
  muted: "#6a5e82"
  grid: "#e7e1ef"
  axis: "#cbc1da"
  page-dark: "#120a22"
  surface-dark: "#1c1430"
  surface-2-dark: "#251a3d"
  text-dark: "#efeaf7"
  ok: "#0ca30c"
  warn: "#fab219"
  crit: "#d03b3b"
  ok-wash: "#e9f6e9"
  warn-wash: "#fef5e0"
  crit-wash: "#fbeaea"
  s1: "#7e3ee0"
  s2: "#eb6834"
  s3: "#0e9aa7"
  s4: "#d6336c"
  s5: "#c99a2e"
  s6: "#3b5bdb"
  s7: "#9c3f7a"
  s8: "#6b8e23"
typography:
  display:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "clamp(36px, 3.7vw, 54px)"
    fontWeight: 650
    lineHeight: 1.02
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "clamp(30px, 3.2vw, 44px)"
    fontWeight: 650
    lineHeight: 1.08
    letterSpacing: "-0.035em"
  title:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.35
  figure:
    fontFamily: "Geist Mono, ui-monospace, Cascadia Code, Consolas, monospace"
    fontSize: "40px"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.03em"
    fontFeature: "tnum"
  code:
    fontFamily: "Geist Mono, ui-monospace, Cascadia Code, Consolas, monospace"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.6
  wordmark:
    fontFamily: "DejaVu Sans, Verdana, system-ui, sans-serif"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.02em"
rounded:
  sm: "8px"
  md: "12px"
  lg: "16px"
  bubble: "18px 18px 4px 18px"
  composer: "22px"
  pill: "999px"
spacing:
  container: "1200px"
  dash: "1240px"
  gutter: "24px"
  section: "112px"
components:
  button-primary:
    backgroundColor: "{colors.violet}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "40px"
  button-on-purple:
    backgroundColor: "{colors.cream}"
    textColor: "{colors.deep-purple}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "44px"
  chip:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.pill}"
    padding: "6px 13px"
  chip-hover:
    backgroundColor: "{colors.violet-wash}"
  input-filter:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "6px 10px"
    height: "34px"
  composer:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.composer}"
    padding: "10px 10px 10px 20px"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.md}"
  question-bubble:
    backgroundColor: "{colors.violet}"
    textColor: "#ffffff"
    rounded: "{rounded.bubble}"
    padding: "9px 15px 10px"
---

# Design System: DataCare_

## Overview

**Creative North Star: "The Evidence Desk"**

DataCare_ is a data product built to the category standard at Vercel's level of craft. A question box comes first, then the real dashboard as proof, then the sources. The surfaces are quiet: a lilac-tinted page, cream panels, hairline borders, and deep-purple ink. Violet is spent on what the user can act on. The proof is real: live figures from the database, real screenshots in browser frames, and the Oracle SQL behind every answer. Nothing decorative stands in for evidence.

Two surfaces share one base layer (`static/css/base.css`): the landing at `/` persuades, and the app at `/app` answers. Both ship light and dark themes in deep purples. A theme toggle on each surface writes the shared localStorage key `tema`, and without a stored choice the theme follows `prefers-color-scheme`. A view transition carries the logo (`view-transition-name: marca-logo`) between the two surfaces. It is turned off under reduced motion.

**Key Characteristics:**
- Lilac-tinted page, cream surfaces, deep-purple ink, violet for actions.
- Geist for the interface and display type, Geist Mono for SQL and headline figures, all self-hosted with no CDN.
- Single panels split by hairline dividers rather than a card per item.
- Real screenshots in browser-frame windows, swapped for the theme.
- Status is always an icon plus a label on a tinted wash, never color alone.

## Colors

A restrained violet-and-purple brand on warm cream, plus a fixed status triad and a chart palette validated for color vision deficiency.

### Primary
- **Signal Violet** (violet; `violet-dark` in dark theme): primary buttons, the send button, focus rings, selection tint, caret, the active turn pill, and the user's question bubble. In dark theme, actions use `violet-dark`. The wordmark's "Data" and "_" use `violet-wordmark-dark`.
- **Violet Ink** (violet-ink): violet text on light grounds for hover text on links and chips, tags, and SQL keywords. In dark theme it becomes `#c4a6f7`.
- **Violet Wash** (violet-wash): selected and hover fills for chips, tags and the active turn pill, plus the landing's transparency note.

### Secondary
- **Deep Purple** (deep-purple): the brand ink. It colors "Care" in the wordmark, fills the landing's closing band, and sets the dark end of the sequential chart scale. Body text uses the near-relative `text`. In dark theme the closing band becomes `deep-purple-final-dark`.

### Tertiary
- **Cream** (cream): the brand's light color. It is used as text and button fill on the deep-purple band. Panel surfaces use the slightly cooler `surface`.
- **Lilac** (#BFAED8) and **Background Violet** (#8134EC) are approved brand colors that no shipped token carries yet. Lilac's role is taken by the tinted `page`, `surface-2` and `axis`.

### Neutral
- **Lilac Paper** (page; page-dark): the page background.
- **Cream Panel** (surface; surface-dark): panels, cards, inputs and chips.
- **Lilac Mist** (surface-2; surface-2-dark): table heads, SQL header bars, browser-frame bars and hover fills.
- **Ink ramp** (text, text-2, muted): primary text, secondary text, and hints or captions.
- **Hairline** (`rgba(35,14,80,.11)` light, `rgba(255,255,255,.10)` dark): every border and divider.
- **Grid / Axis** (grid, axis): chart gridlines and table row rules, and chart axes and scrollbars.

### Status and data
- **Status** (ok, warn, crit, plus their washes): fixed in both themes. Only the washes have dark variants (`#142614`, `#2b2410`, `#2d1616`).
- **Chart series** (s1–s3): brand colors only, violet, orange and lilac, with at most 3 series per chart. Validated with the dataviz skill; the 3rd series also has its own shape (dashed line, diamond marker). Dark-theme values live in base.css. The diverging scale runs violet to orange through a neutral mid (`--div-*`). The sequential scale runs from a lilac wash to deep purple (`--seq-*`). Plotly traces resolve these from CSS at draw time.

### Named Rules
**The Violet Means Act Rule.** Violet fills belong to things the user can press, focus or select, plus the user's own question bubble. Content, headings and decoration stay in the ink ramp.

**The Fixed Palette Rule.** The brand hexes, s1–s8 and ok/warn/crit are approved and pinned. Don't retune them for a new surface.

**The Never Color Alone Rule.** Every status shows a check, warning or alert SVG in a colored disc, followed by its label (Aceitável / Alerta / Crítico), on the matching wash.

## Typography

**Display Font:** Geist, variable 100–900, self-hosted (with system-ui fallback)
**Body Font:** Geist
**Label/Mono Font:** Geist Mono, variable, self-hosted (with ui-monospace, Cascadia Code and Consolas fallbacks)
**Wordmark Font:** DejaVu Sans / Verdana, bold. Used only for the wordmark.

**Character:** The display type is engineered and tightly tracked. The figures and SQL are monospaced and read as machine output.

### Hierarchy
- **Display** (display token): the landing hero headline, two lines, balanced wrap.
- **Headline** (headline token): landing section heads and the closing band (up to 48px).
- **Title** (title token): dashboard titles (22px) and the app home heading (clamp 22–30px). KPI values also use 22px/650 with tabular figures.
- **Body** (body token): 15px in the app, 16px on the landing, with secondary paragraphs at 17–18px. Measure is held at 46–66ch on the landing and 78ch for insights.
- **Label** (label token): chips, captions, and table text. Uses the `--fs-xs/sm/md` steps (12/13/14px); body text in the app uses `--fs-base` (15px). App sizes always come from the `--fs-*` scale.
- **Figure** (figure token): the landing's live figures (40px; 30px under 720px) and the team results (36–48px). Tabular numbers throughout.
- **Code** (code token): Oracle SQL blocks and the browser-frame address bar.

### Named Rules
**The Machine Figures Rule.** Headline figures and code are set in Geist Mono with tabular numbers. Every other number in a data context (KPIs, alert values, numeric table columns) uses `font-variant-numeric: tabular-nums`.

**The Wordmark Is Not A Font Rule.** DejaVu Sans/Verdana appears only in "DataCare_". Never set it in Geist or use it for anything else.

## Layout

The landing sits in a 1200px container (`min(1200px, 100% - 48px)`, with 32px of total inset under 720px). The hero splits into a text column of up to 640px and a screenshot column, 56px apart. The screenshot window bleeds off the right edge of the viewport. Sections are separated by 112px (80px on mobile). Section heads use a 5/7 grid, with the heading left and a paragraph aligned to its bottom. Content splits are 7/5. Everything collapses to one column at 1080px, and the nav becomes a horizontally scrolling row.

The app has a sticky tab bar (`--tabbar-h` 47px, 51px on mobile) and panels padded 24px (16px on mobile). Dashboards are capped at `--wide` (1600px). The app home centers the 820px question block. Charts sit in flex rows with 16px gaps that never leave a hole. Each card grows to fill its row, with 2 per row, or 3 at 1500px and up, balanced by count. Wide charts take a full row. A map is paired with the first chart at the same height and cropped to its municipalities. Charts, the "why it matters" panel and alerts go to one column at 960px. KPIs go to two columns at 640px. Touch targets grow to 44px at 640px (720px on the landing). Neither surface may scroll horizontally at 390px.

## Elevation & Depth

The system is mostly flat, built with tonal layers and hairline borders. Shadows are ambient and appear only in light theme. In dark theme `--shadow` is `none`, and depth comes from the surface steps.

### Shadow Vocabulary
- **Ambient** (`box-shadow: 0 1px 2px rgba(35,14,80,.05), 0 6px 24px rgba(35,14,80,.07)`): the question box, the composer and the question bubble.
- **Window lift** (`box-shadow: 0 1px 2px rgba(35,14,80,.06), 0 24px 64px -24px rgba(35,14,80,.28)`; dark `rgba(0,0,0,.4)` / `.7`): the browser frames that hold screenshots. This is the only deep shadow.
- **Focus halo** (`0 0 0 3px` violet at 22%): a field that holds focus, such as the landing question box.

### Named Rules
**The Dividers Not Cards Rule.** A set of peers (KPIs, alerts, the "why it matters" blocks, the problem chain, figures, results) lives in one bordered panel split by 1px hairlines. Separate cards are for charts and for the landing's three step demos.

## Shapes

Corners come from a small radius family: `--r-sm` 8px for buttons, inputs and inner visuals; `--r-md` 12px for panels, windows, tables and the SQL box; `--r-lg` 16px for the closing band. Chips, tags, status badges and turn pills are full pills. The composer is softer (24px = the send button's 14px + 10px padding, so the corners are concentric; 18px on mobile). The question bubble has one tight corner (18 18 4 18) pointing to its sender. Borders are always 1px hairlines. The turn separator is the one dashed line. The problem chain links its cells with small rotated-square chevrons drawn from the same hairline.

## Components

### Buttons
Compact and quiet. Violet appears only where an action happens.
- **Shape:** gently rounded (8px), 40px tall (44px in the hero, the closing band and on mobile), weight 550, 14px.
- **Primary:** violet fill with white text. Hover mixes in 14% black (`color-mix(in srgb, var(--accent) 86%, #000)`).
- **On deep purple:** a cream-filled button, and an outline button with a 35% cream border that becomes solid on hover.
- **Utility (CSV, print, copy, clear filters, SQL tabs):** a hairline border on the surface with `text-2` text. Hover turns the border violet.
- **Feedback:** every button scales to 0.98 when pressed, with transitions at `--dur` 160ms and `--ease` `cubic-bezier(.2,.8,.2,1)`. Focus shows a 2px violet outline offset by 2px.

### Chips
- **Style:** pill, hairline border, surface fill. 13px in the app, 13.5px on the landing.
- **State:** on hover the border turns violet over a violet-wash fill (in the app) or the text turns violet ink (on the landing). The active turn pill uses violet-wash with violet-ink text and a numbered disc filled violet.

### Cards / Containers
- **Corner Style:** 12px.
- **Background:** surface, inner bars in surface-2.
- **Shadow Strategy:** none at rest (see Elevation).
- **Border:** 1px hairline.
- **Internal Padding:** 14–18px in the app, 22–28px on the landing.

### Inputs / Fields
- **Style:** surface fill, hairline border, 8px radius, 34px minimum height (44px on mobile, with 16px text to prevent iOS zoom).
- **Focus:** 2px violet outline. Hover tints the border violet at 45%. The composer and question box move the ring to the whole container.
- **Error:** an invalid field gets a `crit` border.

### Navigation
- **Landing top bar:** sticky, 64px, page color at 82% with `blur(10px)` and a hairline bottom border. Links are 14px `text-2` and gain a surface-2 fill on hover.
- **App tab bar:** folder tabs, following the user's reference image. A 56px rail (`--tabbar-h`), 5% darker than the page, holds the logo, a hairline divider, the tabs, a chevron menu and the theme button. Inactive tabs are transparent, 15px, 500 weight, `--text-2`, with 16px top corners and a light page-tint pill on hover. The active tab is page-colored, 650 weight, with no outline, and merges into the content below; concave 16px radial-gradient flares at its base join it to the panel. A short, thick (3px, rounded) underline in `currentColor` sits under its label. Status icons, the faint close X and the overflow edge fades stay. The chevron opens "Abas abertas": a floating card (18px radius, soft wide shadow) with one row per tab, divided by hairlines. Each row has a 40px round icon holding the status icon, the question in bold, "Situação: …" in muted text and the question count on the right. The "Perguntas 1 · 2" strip below is page-colored, so the active tab flows into it.
- **Turn nav:** sticky under the tab bar, translucent page color with blur, and numbered pills.

### Status Badge (signature)
A pill on the status wash: an 18px colored disc holding a white SVG glyph (dark glyph on warn), followed by the label. It shrinks inside tables and legends. On the landing's step demo, labelled washes with a status-tinted inset ring carry the same meaning.

### Browser Window (signature)
A hairline 12px frame with a 34px surface-2 bar holding three axis-colored dots and a mono address. It holds a real screenshot (`.webp`) in matching light and dark versions, and shows the matching one through `.so-claro` / `.so-escuro`.

### Skeleton
Loading draws the shape of the dashboard: a bubble, a title, KPIs and a chart. A 1.2s shimmer runs from surface-2 to surface. The skeleton replaces the spinner and stops under reduced motion.

### Logo
The logo is the wordmark alone: "DataCare_" with "Data" and "_" in violet and "Care" in deep purple (light in dark theme), 18px in the app and 20px on the landing. The user asked to drop the brain-circuit icon from the logo. It survives only as the favicon (`static/marca/favicon.svg`). A soft brand glow sits behind both pages as a fixed `body::before` layer, so it stays visible while scrolling: on the whole landing and in every app tab (Início and dashboards). It is four radial gradients: violet at the top center, top left and bottom right, and a touch of orange at the top right. It comes from `--brilho-violeta` and `--brilho-laranja`, which are stronger in dark theme. In the app it starts at the page color right under the tab bar, so the active folder tab stays seamless. On the landing, the `.numeros` and `.banda` stripes are 62% surface so the glow shows through. **Meshes:** plexus-style `<canvas class="malha">` layers in the landing's hero and in the closing band, after the user's reference image. They are brand violet and lilac dots joined by fading lines, with some glowing dots, drifting slowly. They are drawn by `landing.js` (`malha()`), masked away under the text, pause offscreen or when the tab is hidden, stay static under reduced motion, and redraw on theme change.

## Do's and Don'ts

### Do:
- **Do** take every color from the `:root` tokens in base.css, and give each new token a dark-theme override.
- **Do** keep violet for actions, focus and selection.
- **Do** group peer items in one panel with 1px hairline dividers.
- **Do** pair every status color with its SVG icon and its Aceitável / Alerta / Crítico label.
- **Do** show proof with real screenshots in the browser-window frame, in matching light and dark captures.
- **Do** set headline figures and SQL in Geist Mono with tabular numbers.
- **Do** attribute team-reported results to the SQLadies team, stating that this demonstration did not measure them.
- **Do** use prefixed class names (`tab-home`, `n-alerta`, `relev-*`, `aba-*`, `turno-*`).
- **Do** use skeletons shaped like the coming content for loading.
- **Do** share the theme through localStorage key `tema`, and respect `prefers-reduced-motion`.

### Don't:
- **Don't** put colored side stripes on cards or alerts.
- **Don't** use violet for decorative fills, headings or icons that aren't actions.
- **Don't** retune s1–s8, ok/warn/crit or the brand hexes.
- **Don't** show status by color alone.
- **Don't** load fonts, scripts or map data from a CDN; everything ships under `static/vendor`.
- **Don't** use generic class names such as `.home` or `.alerta` for new components.
- **Don't** put staged or edited images in a browser window. The window holds only real captures of the running app.
