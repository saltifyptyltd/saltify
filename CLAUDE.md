# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Marketing site for **Saltify Pty Ltd**, a Canberra-based SaltStack / VCF Salt consultancy. **Multi-page static site** (10 HTML pages — landing + Salt Academy + 8 Learn Salt deep pages), no build step, deployed via **GitHub Pages** (Jekyll `minimal` theme per `_config.yml`) on the custom domain `saltify.work` (see `CNAME`).

The positioning of the copy is load-bearing — it's not boilerplate. The site sells a specific architectural pattern (blue/green Salt **stacks**, git-as-source-of-truth, "rebuild, don't restore"). Edits to copy should preserve that thesis; don't soften it into generic consultancy language. See `project_saltify_value_props.md` in memory for the full value-prop reference.

## Architecture

Three shared files plus the page files:

- **`index.html`** — the landing page. Sections in current order: `hero`, `cred-band`, top Salt Academy promo card, `what-is-salt`, `services` (What we do), `process` (How we work), `uplift` (We build. We train. You run.), philosophy/`about` (The Saltify thesis), `approach` (Stop upgrading in place), curriculum guides grid, `salt-wild` (releases + blog feed), `contact`. Nav anchors point to these IDs — renaming an `id` breaks navigation.
- **`salt-academy.html`** — standalone Salt Academy page (hero + 8-card curriculum grid + Official resources + Salt in the wild + outro CTA). Same `install-promo-card` aesthetic as the landing-page grid.
- **8 Learn Salt deep pages** — `install-guide.html`, `getting-started.html`, `states.html`, `windows.html`, `salt-ai.html`, `salt-ai-tooling.html`, `salt-cheat-sheet.html`, `salt-state-modules.html`. Each is **self-contained**: page-specific styles live in an inline `<style>` block at the top of the page, NOT lifted to `css/style.css`. Established pattern (commit `0f20ae3`); don't lift without explicit ask.
- **`css/style.css`** — design system at the top: CSS custom properties under `:root` (dark, default) and `[data-theme="light"]` overrides. Theme switches by toggling `data-theme` on `<html>` from JS. Card components reuse a `.divider-grid` primitive (1px hairline gaps via `gap: 1px` + background) and a `.hover-card` / `.fade-in` pair — prefer composing these over adding new card variants. Under `.academy-*` only `.academy-toast*` (launch popup) and `.nav-academy` (top-level nav slot) remain — diploma rules removed.
- **`js/script.js`** — seven `init*` functions on `DOMContentLoaded` (`initTheme`, `initNavigation`, `initAnimations`, `initSaltFeed`, `initSaltBlog`, `initStateMap`, `initAcademyToast`). All safely no-op when their target element is absent, so adding to `DOMContentLoaded` doesn't need per-page gating. Feed fetches (`initSaltFeed`, `initSaltBlog`) cache 1hr in `localStorage` (`saltifyReleasesV1` / `saltifyBlogV1`, shared `FEED_TTL_MS`) — GitHub's 60/hr unauth limit is the reason. On fetch failure with no cache, only the failing grid + its subhead is hidden. The `localStorage.saltifyAcademyToastDismissed` key is intentionally still under the legacy "saltify" prefix — renaming it would re-pop the toast for past visitors.

## Workflow

There is no build, no test suite, no linter, no package manager. To preview locally, open `index.html` directly in a browser, or serve the directory (`python3 -m http.server` works fine). Changes ship by pushing to the default branch — GitHub Pages rebuilds and serves from `saltify.work`.

The Salt releases + blog feeds only render against live external APIs, so when iterating on the `.salt-wild` section locally expect either the cached payload or network requests to `api.github.com` and `saltproject.io`.

## Cache busters

Every page links `css/style.css?v=N` and `js/script.js?v=N` (independent counters). **Bump the affected one across all 10 pages** when you change that asset — drift causes wasted refetches as visitors browse across pages. Read the current `?v=N` from any HTML file before bumping; don't keep the number here (it goes stale fast).

## Conventions worth keeping

- The site is fully responsive and supports both dark and light themes; any new component must work in both. Use the existing CSS variables (`--color-bg`, `--color-accent`, `--color-border`, `--radius`, etc.) — never hardcode colors.
- Icons come from Font Awesome 6 via CDN (`<i class="fas fa-…">` solid, `<i class="fab fa-…">` brands). Fonts are **Inter + JetBrains Mono only**. Both font origins have `<link rel="preconnect">` set up; if you add another origin, preconnect it too.
- Code blocks in Learn Salt pages use a `<span class="code-comment">` wrapper for inline comments — match that pattern instead of inventing a new highlight scheme.
- Card grids: `.divider-grid` (hairline-divided) for most sections; `.uplift-grid` is the single-featured-card exception; `.install-promo-grid` is the 3-col card grid used for the curriculum on both `index.html` and `salt-academy.html`. Reuse, don't duplicate.
- External links: `target="_blank" rel="noopener"`, end the visible text with `↗`.

## Voice rules (full text in memory)

- **No FREE / NO SIGNUP / "no email gate"** in self-promo copy — see `feedback_no_free_no_signup_copy.md`.
- **"VCF Salt"** is the canonical brand for Broadcom's commercial Salt build — see `feedback_vcf_salt_naming.md`.
- **Brand is "Salt Academy"** (not "Saltify Academy") — see `project_saltify_academy.md`.
- **Diploma styling is retired** — no corner brackets, Playfair italic, signature seals, "honorary credential" framing.
- **Plain English, short, contrarian, founder-confidence** — see `feedback_user_voice.md`.
- **Don't conflate in-stack HA with blue/green-between-stacks** — different layers; see `project_saltify_value_props.md`.

## Sync rules

- **Curriculum cards mirrored on `index.html` and `salt-academy.html`** — split layout: a 6-card "courses" grid then a "References · for lookup, not reading in order" eyebrow then a 2-card `.install-promo-grid--references` grid. Same copy, same order on both files. Card titles match each destination page's H1 verbatim. Change one, mirror to the other.
- **Per-page canonical tag in `<head>`** — `<link rel="canonical" href="https://saltify.work/<filename>">` on every page (bare `/` for `index.html`), placed right after the `rel="icon"` line. Add when introducing a new page.
- **Launch toast HTML duplicated across 9 pages** (every page except `salt-academy.html`). Change one, change all 9.
- **Local-only `Documentation/` folder** — real keys/PATs/client hostnames; never commit. See `feedback_documentation_local_only.md`.
