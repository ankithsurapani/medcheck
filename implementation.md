# Current Task — Phase 3a: Search Site (static-data MVP)

**Read first:** `CLAUDE.md` (current status + decisions), `plan.md` §1 (non-negotiables — these gate every page, not optional polish), §3 (schema, `failure_category` is a JSON array), §3.3 (21-category vocabulary), §4 Phase 3 (now split 3a/3b, this ticket is 3a only).

**Design direction:** use the `ui-ux-pro-max` skill for visual/UX decisions (style, layout, typography, color, accessibility). This ticket scopes *what* to build and the constraints it must respect; the skill should drive *how it looks*.

## Why static data, not a live API

Phase 2 (entity resolution) hasn't run and there's no FastAPI yet. Rather than block the UI on either, this ticket ships against a static pre-built JSON export of `data/medcheck.db` — the same artifact already planned as the API fallback (`plan.md` §2), so building it now does double duty. No Railway/Fly.io hosting needed yet. A live API is Phase 3b, later.

## Task

1. **Export script** (`scripts/export_static.py` or similar) — dump `data/medcheck.db` → static JSON consumed by `web/`. Two shapes, not one blob, since 6,155 full records is too heavy for mobile-first (`plan.md` §4 Phase 3a):
   - a **lightweight search index**: id, drug name, batch number, manufacturer, month, failure category — small enough to ship to the client for instant fuzzy search
   - **full per-record data**, used at build time for static detail pages (Next.js SSG/`generateStaticParams`) — good for SEO, which `plan.md` §2 flags as mattering a lot here
   Re-run whenever `medcheck.db` changes; not committed to git (regenerate, like `data/medcheck.db` itself).

2. **`web/` Next.js + Tailwind app**:
   - **Search** — drug name (fuzzy, typo-tolerant — a client-side index lib like Fuse.js/MiniSearch is a reasonable fit, your call), batch number (exact), manufacturer (substring match on `manufacturer_raw` — see boundary below)
   - **Result card** — drug, batch, manufacturer, month, failure reason in plain language (not the raw CDSCO text alone), source link, and the mandatory non-dismissible safety copy (`plan.md` §1.2, verbatim)
   - **Result/detail page** — everything on the card, plus: the "batch failure ≠ product failure" note (§1.3, must be visible, not footnoted), `label_claim_disputed` shown prominently when true (§5.5 — defamation risk if buried or missing), and low-confidence fields (`parse_confidence`, empty `state`, etc.) shown as *unknown*, never silently blank or guessed (§1.4)
   - **"No results" page** — explicit: not found means not flagged in *our* data, not verified safe
   - **Manufacturer page** — all records matching that exact `manufacturer_raw` string, chronological, with a visible note that this is raw-name matching, not a resolved company identity (near-duplicate names are separate pages for now — Phase 2 isn't done)
   - **Mobile-first** — this is the primary target, not an afterthought
   - **No login, no signup, no tracking tied to identity** (§1.5)

3. **Plain-language failure explanations** — one short paragraph per `failure_category` bucket (21 total, `plan.md` §3.3), factual and non-alarming, same tone as the dissolution example in §4 Phase 3a. Cover every bucket including `other` (explain that CDSCO's stated reason didn't match a known test).

## Explicit boundary — do NOT do yet

- No live FastAPI / `api/` code — static export only, this ticket.
- No entity resolution — manufacturer matching is exact-string on `manufacturer_raw`, not fuzzy/merged. Don't build a resolution shortcut inside the UI layer to compensate; that's Phase 2's job and doing it here risks exactly the reputational-harm scenario `plan.md` §5.3/§2 Phase 2 warns about (wrongly merging two companies).
- No Hindi/i18n content — English only this ticket, but don't hardcode English strings in a way that blocks adding it later (Phase 3b).
- No recommendation of alternate medicine, no price/pharmacy features (`plan.md` §6, unchanged).

## Done when

- [ ] Static export script runs, produces both the lightweight index and per-record data, documented (how to re-run it after a `medcheck.db` update)
- [ ] Search works for drug name (fuzzy), batch number (exact), manufacturer (substring) against real data
- [ ] Result/detail pages render all required non-negotiable copy — spot check a `label_claim_disputed=true` record and a record with missing `state` to confirm both render correctly, not silently
- [ ] "No results" and manufacturer pages exist and say what they need to say
- [ ] Mobile viewport checked, not just desktop
- [ ] All 21 failure categories have a written explanation
- [ ] `CLAUDE.md` updated: Current Status, Decisions Log, Key Learnings

## Before ending the session

Update `CLAUDE.md`:
- **Current Status** → what's built, what's still open in 3a, any record counts/screenshots-worth-noting
- **Decisions Log** → search library chosen, any deviation from this scope
- **Key Learnings** → anything about the data that surprised you once it hit a UI (e.g. which fields are messiest to display, any records that read oddly)

Do not start Phase 3b (Hindi, live API, resolved manufacturer identity) or Phase 2 even if it feels like the natural next step — that's the next ticket, written after the planner reviews what this one built.
