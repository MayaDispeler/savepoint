# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Plain static HTML, CSS and JavaScript (no build step), hosted as static assets on Cloudflare Workers and mirrored as a Hugging Face static Space. Confirmed by the existing deployment; the owner did not ask for a framework.

## Users

Two audiences, both confirmed by the owner ("both"): (1) portfolio visitors, such as recruiters and hiring managers, who arrive from the owner's portfolio with about two minutes and no background; (2) AI engineers who want the precise mechanism, definitions and numbers. Both must be able to understand every screen without reading the PRD.

## Product Purpose

Savepoint is a transactional safety layer for computer-use AI agents that operate legacy software with no API. It checkpoints data before risky steps, checks the result against a written task rule when the agent says "done", rolls back on failure or false completion, and proves each restore exact by a state diff. This app is the public face of it: an interactive "break the agent, then undo it" experience, plus the full test evidence (600 runs on three apps).

## Positioning

The mechanism is the combination: checkpoint, written goal contract with a frame check (nothing else changed), automatic rollback, and an exactness proof, all measured against a no-protection baseline on a synthetic app and two real open-source apps. Atomicity, rollback and pass^k are not claimed as novel. Credit: LegacyWorld (arXiv 2608.14131), legacy-use, TClone, DART, AgentRewind.

## Operating Context

Static, read-only viewer of recorded data (`data/bundle.js`, `data/experience.js`); no backend. Links are shared from a portfolio, so pages need stable deep links (hash routes). Used on laptops and phones.

## Capabilities and Constraints

- The agent in every run is a scripted fault-injecting agent, not a language model; a live Claude run was simulated (no API call, no spend). This must be stated wherever numbers appear.
- Apps: ClaimDesk 98 (synthetic, built here), OpenMRS 2.12 and iDempiere (real open-source apps run in Docker).
- Numbers come only from `docs/results.json`; never invent numbers, quotes or links.
- Outcome classes: Correct (VS), Safe fail (VF), False done (IS), Mess left (IF), Restore failed.
- No requests outside the app's own origin; one page scroll, no nested scroll areas; every outcome shown as icon plus word, never colour alone.

## Brand Commitments

Name: Savepoint. Voice: plain, direct, honest about limits. Light (white) theme with a proper semantic colour system (owner request). Primary links: https://savepoint-demo.ksvhari007.workers.dev, https://huggingface.co/spaces/SrihariV/savepoint, https://github.com/MayaDispeler/savepoint.

## Evidence on Hand

600 recorded runs, 15 recorded "Try it" runs with per-event record state, before/after screenshots of rollbacks, 30 task contracts (YAML), docs/validation.md. No customer testimonials or pricing exist and none may be implied.

## Product Principles

1. Explain in plain words first; keep the precise term one click away (tooltips, glossary, technical disclosures).
2. Show real recorded data, never staged outcomes; label synthetic material.
3. Failures get the same visual weight and clarity as successes.
4. Every screen says what it is, how to read it, and what to do next.

## Accessibility & Inclusion

WCAG AA contrast, keyboard operable with visible focus, reduced-motion respected, meaning never carried by colour alone, works at phone width.
