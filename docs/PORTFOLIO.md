# Putting Savepoint in your portfolio

Savepoint is already a finished, hosted app. You do **not** need to rebuild anything in the portfolio. The portfolio
only needs a card and a short case-study page that send people to the live app, where the "Try it" tab lets them
experience the idea in about 60 seconds. The test results are in the same app, on the other tabs.

## 1. The links

| What | Link |
|---|---|
| **Live app (opens on the Overview page)** | https://savepoint-demo.ksvhari007.workers.dev |
| **Deep link straight into the experience** | https://savepoint-demo.ksvhari007.workers.dev/#/try |
| Deep link to the 600 test runs | https://savepoint-demo.ksvhari007.workers.dev/#/results |
| Deep link to the benchmark | https://savepoint-demo.ksvhari007.workers.dev/#/benchmark |
| Same app on Hugging Face (static Space mirror) | https://huggingface.co/spaces/SrihariV/savepoint |
| Code (GitHub, MIT licence, tag v1.0.0) | https://github.com/MayaDispeler/savepoint |

Use the Cloudflare link as the main "Live demo" button, the GitHub link as "Code", and the Hugging Face link as "Space".

### What visitors see in the app

The app has a left navigation with seven pages, written in plain language (technical terms are one click away).

- **Overview**: the problem in two sentences, the save / check / undo flow, and a table of what the tests show.
- **Try it**: pick what goes wrong with an AI agent (it stops, types a wrong value, skips the last save, says
  "done" too early), switch Savepoint on or off, press Play, and watch the record, the checkpoints, the failing check and
  the rollback. Every replay is a real recorded run, not an animation made up for the page.
- **Test results**: all 600 runs as a grid, one tile each, with filters by app, protection level and wrong results only. Click a tile to see its steps, checks and the before/after screen.
- **Benchmark**: how often a run ended clean, reliability over repeated attempts (pass^k), outcome counts, per app.
- **Tasks and rules**: the 30 tasks and the written rules each one is checked against.
- **How it works** and **Glossary and limits**: the explanation for engineers and the honest limits.

## 2. Recommended way to show it

1. **Project card** on the projects page: title, one line, 3 tags, image `2-try-without-savepoint.png` or the video, and a
   "Try it live" button to the Cloudflare link.
2. **Case-study page** (`/projects/savepoint`, same pattern as your other project pages) with the text blocks in section 3,
   the images in section 5, and the same buttons.
3. **Do not iframe the whole app inside the page.** The app is a full page of its own, so an iframe gives a scroll box
   inside a scroll page. Open it as its own page (new tab). If you still want an embed, give the frame a fixed height
   of about 900 px and a clear "Open full page" link next to it:

```html
<iframe src="https://savepoint-demo.ksvhari007.workers.dev/" title="Savepoint: try it" loading="lazy"
        style="width:100%;height:900px;border:1px solid #DCE0E6;border-radius:8px"></iframe>
<a href="https://savepoint-demo.ksvhari007.workers.dev/" target="_blank" rel="noopener">Open the full page</a>
```

4. **Optional nicer address** (so the link lives on your own domain): in the Cloudflare dashboard open
   Workers & Pages, then `savepoint-demo`, then Settings, then Domains & Routes, and add a **custom domain** such as
   `savepoint.iamsrihari.com`. Use a subdomain, not `iamsrihari.com/projects/savepoint/demo`: the app loads its files
   with relative paths and a path prefix would not be stripped. After that, replace the `workers.dev` link everywhere.

## 3. Copy you can paste (all numbers come from `docs/results.md` and `docs/validation.md`)

**Title:** Savepoint

**Tagline:** Undo for AI agents that work on old software.

**Short description (card):** A safety net for AI agents that operate software with no API. It saves the record before
risky clicks, checks the result when the agent says "done", and restores the record if anything is wrong. Try it live:
break an agent on purpose and watch it get rolled back.

**Longer description (case study, opening):** Many insurers, hospitals and banks run daily work on old screens that have
no API. An AI agent can click through them, but when it fails halfway, or says "done" when nothing was saved, the record
is left broken and someone repairs it by hand. Savepoint wraps the agent in a transaction layer: it checkpoints before
risky steps, checks the outcome against a written contract, rolls back on failure or false completion, and proves each
restore exact by comparing the data row by row.

**Three bullets (results):**
- 600 fault-injected runs on three apps: a claims screen I built, and the real OpenMRS (hospital records) and iDempiere (ERP) running in Docker.
- Without Savepoint, 61 of 200 baseline runs said "done" with the record wrong. With Savepoint, 0 of 200: every failed run ended in a clean, untouched record.
- Every one of the 163 rollbacks in the benchmark restored the data exactly (checked by state diff), and all 59 false "done" claims were caught with no false alarms.

**How it works (5 lines):**
1. Save the record before the agent starts, and again before risky clicks (Save, Delete, OK).
2. After each change, run safety checks (for example, no amount over the cap).
3. When the agent says "done", check the goal ("the amount is 1250.00 and a note exists") and that nothing else changed.
4. If a check fails, restore the checkpoint.
5. Compare the data to the checkpoint, row by row, to prove the restore was exact.

**Tech stack:** Python, Playwright, FastAPI, SQLAlchemy, SQLite / MySQL / PostgreSQL, Docker, plain HTML/CSS/JS front end,
Cloudflare Workers (static assets), Hugging Face Spaces, GitHub Actions.

**Tags:** AI agents, reliability, evaluation, computer use, rollback, legacy systems

### The honest-limits box (put this on the page, near the numbers)

- The agent in every test is a **script that fails on purpose**, not an AI model. The numbers show what Savepoint does
  with known failures. They do not measure how reliable any AI model is.
- The "live Claude run" was **simulated** through the real agent loop. No model was called and nothing was spent.
- ClaimDesk 98 is a fake app I built for safe testing. OpenMRS and iDempiere are real open-source apps run with their demo data.
- The real apps ran 5 trials per task (10 on ClaimDesk). iDempiere's screens were slow and flaky: 15 of its 150 runs ended in a UI timeout and were rolled back cleanly.
- Rollback covers the tables a contract monitors, not the whole database. Apps with outside effects (email, payments) are out of scope.
- Inspired by LegacyWorld (arXiv 2608.14131); atomicity, rollback and pass^k are not new ideas. The contribution is the combination and the exactness proof.

## 4. The numbers (source: `docs/results.md`)

| App | Runs | Atomicity without Savepoint | With Savepoint | False "done" without, with |
|---|---|---|---|---|
| ClaimDesk 98 (built here) | 300 | 70.0% | 100.0% | 27, 0 |
| OpenMRS 2.12 (real) | 150 | 64.0% | 100.0% | 18, 0 |
| iDempiere (real) | 150 | 68.0% | 100.0% | 16, 0 |

Atomicity = runs that either finished correctly or left the data untouched. 95% intervals for the real apps: 92.9% to 100%
with Savepoint. Checkpoint and restore speed (p95): ClaimDesk 47 ms / 94 ms, OpenMRS 71 ms / 529 ms, iDempiere 131 ms / 610 ms.
The "retry" arm (restore the last good state and let the agent try again) lifted valid success on ClaimDesk to 97%
and on OpenMRS to 96%, but only to 54% on iDempiere because of its UI timeouts.

## 5. Images and video to use (all in `docs/portfolio-assets/`)

| File | Use it for |
|---|---|
| `2-try-without-savepoint.png` | Card image / hero: the agent says "done" but the record is wrong |
| `3-try-with-savepoint.png` | The same failure caught and rolled back (use next to image 2, "before / after") |
| `4-benchmark.png` | Benchmark section |
| `5-test-results.png` | "All 600 runs" proof
| `1-overview.png` | Overview page, if you want a wide product shot |
| `savepoint-walkthrough.webm` | Short tour: Try it, test results, benchmark (autoplay muted loop works well on the card) |

## 6. Prompt for the Claude window that edits the portfolio

> Add a Savepoint project card and a case-study page at `/projects/savepoint`, following the existing project pages.
> Do not build or embed a new app: Savepoint is already hosted. Use the copy and numbers in
> `Savepoint/savepoint-repo/docs/PORTFOLIO.md` exactly (section 3 and 4), including the honest-limits box. Buttons:
> "Try it live" → https://savepoint-demo.ksvhari007.workers.dev (primary), "Code" → https://github.com/MayaDispeler/savepoint,
> "Space" → https://huggingface.co/spaces/SrihariV/savepoint. Use the images from `docs/portfolio-assets/` (convert to
> WebP), the portfolio's own design tokens, one page scroll (no scrolling boxes), and reduced-motion-safe video.
> Do not invent numbers, quotes or links, and ask me before any pivotal decision.

## 7. After you add it

- In `Raw Documents and plans/portfolio-tracker.html` the Savepoint row is already Complete, Live, 100%. Nothing to change there.
- If you add the custom domain, replace the `workers.dev` link in the portfolio, in `README.md`, and in the Savepoint `tracker.html` Key facts.

## 8. If you want the experience to change later

- The Try it data comes from `scripts/make_experience_data.py` (re-run it to record fresh runs; about 3 minutes, needs Chromium).
- The page itself is `console/public/try.js`. Deploy with `cd worker && npx wrangler deploy`, and mirror to Hugging Face with
  `hf upload SrihariV/savepoint <folder> . --repo-type space`.
