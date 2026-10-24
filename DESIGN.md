# Design system: Savepoint console

Operate + Read surface with one Experience page (Try it). White theme, restrained colour, left navigation. Static HTML/CSS/JS, no build step. Source of truth: `console/public/style.css` (tokens at the top).

## Colour roles (all text pairs meet WCAG AA)

| Token | Hex | Role |
|---|---|---|
| `--bg` / `--panel` | #FFFFFF | Page and panels |
| `--side` | #F9FAFB | Navigation rail, table headers, code blocks (second neutral layer) |
| `--sunken` | #F2F4F7 | Segmented-control track, hover on rail |
| `--ink` / `--ink-2` | #101828 / #344054 | Headings and body |
| `--muted` / `--subtle` | #475467 / #667085 | Secondary text (7.7:1 / 5.0:1 on white) |
| `--line` / `--line-2` | #E4E7EC / #D0D5DD | Hairlines / control borders |
| `--brand` (+ hover, tint, line) | #1D4ED8 (#1E40AF, #EFF4FF, #B2CCFF) | **Savepoint acted**: primary actions, selection, checkpoints, restores, safe-fail outcome |
| `--ok` (+ tint, line) | #067647 (#ECFDF3, #ABEFC6) | Correct result, passed check |
| `--bad` (+ tint, line) | #B42318 (#FEF3F2, #FECDCA) | Wrong result, failed check, mess left |
| `--warn` (+ tint, line) | #B54708 (#FFFAEB, #FEDF89) | Caution and honesty notes |

Outcome encoding (always icon + word, never colour alone): Correct (check, green tint), Safe fail (undo arrow, blue tint), False done (alert circle, red tint), Mess left (x, solid red), Restore failed (alert, hatched red).

## Type

Inter variable, self-hosted (`fonts/inter-latin-wght.woff2`), tabular numerals. Scale: 28/36 page title (650), 20/28 section (620), 16/24 card title (600), 15/24 body, 14/20 table and controls, 13/20 labels and hints, 12.5 mono for code. Body measure capped at 78ch. Chosen as a workhorse UI face for an Operate surface; the detector's "overused font" note is accepted.

## Layout

Left rail 264px (sticky, 100vh, never scrolls on its own), content max 1120px, 28/40px page padding. At 1000px the rail becomes a Menu button and drawer; tables below 700px stack into labelled rows. One page scroll only; no nested scroll areas. Spacing rhythm: 8, 12, 16, 20, 36 (more space above a heading than below).

## Components

Buttons 40px (32px small): primary (brand fill), secondary (white, line-2 border), ghost. Segmented control (track + raised white selected state) for filters and choices. Panels (1px line, 12px radius, no shadow), callouts (info / warning / danger with icon, tinted background, no side stripe), disclosures, definition lists, stacked-on-mobile tables, breadcrumbs, timeline with icon dots, before/after slider. Focus ring 2px brand with 2px offset. Motion: 150ms colour transitions and one 1.2s change flash in Try it; all disabled under `prefers-reduced-motion`.

## Pages and routes

`#/` Overview, `#/try?fault=&prot=` Try it, `#/results`, `#/run/<id>`, `#/benchmark`, `#/tasks`, `#/how`, `#/glossary`. Every route is linkable from a portfolio.

## Rules for new work

Plain words first, technical term one click away; failures get the same weight as successes; every number comes from `data/bundle.js`; never claim the agent is a model; keep the scripted-agent notice in the rail and footer.
