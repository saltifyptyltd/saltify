# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Marketing site for **Saltify Pty Ltd**, a Canberra-based SaltStack / VMware Aria Automation Config consultancy. Single-page static site, no build step, deployed via **GitHub Pages** (Jekyll `minimal` theme per `_config.yml`) on the custom domain `saltify.work` (see `CNAME`).

The positioning of the copy is load-bearing — it's not boilerplate. The site sells a specific architectural pattern (blue/green Salt masters, git-as-source-of-truth, "rebuild, don't restore"). Edits to copy should preserve that thesis; don't soften it into generic consultancy language.

## Architecture

Three files do all the work:

- `index.html` — the entire page. Sections are plain `<section id="…">` blocks (`hero`, `what-is-salt`, `services`, `uplift`, `approach`, `salt101`, philosophy/about, `process`, `salt-wild`, `contact`). The nav anchors point to these IDs, so renaming an `id` breaks navigation.
- `css/style.css` — design system at the top: CSS custom properties under `:root` (dark, default) and `[data-theme="light"]` overrides. Theme switches by toggling `data-theme` on `<html>` from JS. Card components reuse a `.divider-grid` primitive (1px hairline gaps between grid cells via `gap: 1px` + background) and a `.hover-card` / `.fade-in` pair — prefer composing these over adding new card variants.
- `js/script.js` — four init functions called on `DOMContentLoaded`: `initTheme` (persists to `localStorage['theme']`), `initNavigation` (hamburger + scroll class), `initAnimations` (IntersectionObserver adds `.visible` to `.fade-in` elements), `initSaltFeed` (fetches `saltstack/salt` GitHub releases into `#saltFeed`). The Salt feed has a 1-hour `localStorage` cache (`saltifyReleasesV1`, `RELEASES_TTL_MS`) — this exists because the GitHub unauthenticated API limit is 60/hr per IP, and the cached path renders synchronously on repeat visits before any fetch. If the fetch fails and there's no cache, the entire `.salt-wild` section is hidden rather than showing a broken state.

## Workflow

There is no build, no test suite, no linter, no package manager. To preview locally, open `index.html` directly in a browser, or serve the directory (`python3 -m http.server` works fine). Changes ship by pushing to the default branch — GitHub Pages rebuilds and serves from `saltify.work`.

The Salt releases feed only renders against the live GitHub API, so when iterating on that section locally expect either the cached payload or a network request to `api.github.com`.

## Conventions worth keeping

- The site is fully responsive and supports both dark and light themes; any new component must work in both. Use the existing CSS variables (`--color-bg`, `--color-accent`, `--color-border`, etc.) — never hardcode colors.
- Icons come from Font Awesome 6 via CDN (`<i class="fas fa-…">`) and fonts from Google Fonts (Inter + JetBrains Mono). Both have `<link rel="preconnect">` set up; if you add another origin, preconnect it too.
- Code blocks in `Salt 101` use a `<span class="code-comment">` wrapper for inline comments — match that pattern instead of inventing a new highlight scheme.
- Card grids use `.divider-grid` (hairline-divided) for most sections; `.uplift-grid` is the exception (single featured card). Reuse, don't duplicate.
