'use strict';

const RELEASES_CACHE_KEY = 'saltifyReleasesV1';
const BLOG_CACHE_KEY = 'saltifyBlogV1';
const FEED_TTL_MS = 60 * 60 * 1000;
const BLOG_FEED_URL = 'https://saltproject.io/blog/index.xml';

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initNavigation();
    initAnimations();
    initSaltFeed();
    initSaltBlog();
    initStateMap();
    initAcademyToast();
});

function initAcademyToast() {
    const toast = document.getElementById('academyToast');
    const closeBtn = document.getElementById('academyToastClose');
    if (!toast || !closeBtn) return;

    const dismissedKey = 'saltifyAcademyToastDismissed';
    if (localStorage.getItem(dismissedKey)) {
        toast.classList.add('academy-toast--hidden');
        return;
    }
    toast.setAttribute('aria-hidden', 'false');

    closeBtn.addEventListener('click', () => {
        toast.classList.add('academy-toast--hidden');
        toast.setAttribute('aria-hidden', 'true');
        localStorage.setItem(dismissedKey, '1');
    });
}

function initTheme() {
    const toggle = document.getElementById('themeToggle');
    const icon = document.getElementById('themeIcon');
    const saved = localStorage.getItem('theme') || 'dark';

    applyTheme(saved);

    toggle?.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        applyTheme(next);
        localStorage.setItem('theme', next);
    });

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        if (icon) {
            icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
        toggle?.setAttribute('aria-pressed', String(theme === 'light'));
    }
}

function initNavigation() {
    const navbar = document.querySelector('.navbar');
    const dropdown = document.querySelector('.nav-dropdown');
    const dropdownToggle = document.querySelector('.nav-dropdown-toggle');

    function setExpanded(isOpen) {
        dropdownToggle?.setAttribute('aria-expanded', String(isOpen));
    }

    function closeDropdown() {
        dropdown?.classList.remove('is-open');
        setExpanded(false);
    }

    /* Mobile: tap toggles the submenu. Desktop opens via :hover / :focus-within
       in CSS — JS just keeps aria-expanded honest for screen readers. */
    dropdownToggle?.addEventListener('click', e => {
        if (window.innerWidth <= 768) {
            e.preventDefault();
            e.stopPropagation();
            setExpanded(dropdown.classList.toggle('is-open'));
        }
    });

    if (dropdown) {
        dropdown.addEventListener('pointerenter', () => {
            if (window.innerWidth > 768) setExpanded(true);
        });
        dropdown.addEventListener('pointerleave', () => {
            if (window.innerWidth > 768) setExpanded(false);
        });
        dropdown.addEventListener('focusin', () => setExpanded(true));
        dropdown.addEventListener('focusout', e => {
            if (!dropdown.contains(e.relatedTarget)) setExpanded(false);
        });
    }

    document.addEventListener('click', e => {
        if (dropdown?.classList.contains('is-open') && !dropdown.contains(e.target)) {
            closeDropdown();
        }
    });

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && dropdown?.classList.contains('is-open')) closeDropdown();
    });

    if (navbar) {
        let pending = false;
        window.addEventListener('scroll', () => {
            if (pending) return;
            pending = true;
            requestAnimationFrame(() => {
                navbar.classList.toggle('scrolled', window.scrollY > 50);
                pending = false;
            });
        }, { passive: true });
    }
}

function initAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.12 });

    document.querySelectorAll('.fade-in').forEach(el => observer.observe(el));
}

/* ================================
   Salt in the wild — GitHub releases for saltstack/salt
   localStorage cache (1h TTL) avoids hitting GH's 60/hr unauth limit
   on every page load and keeps the section instant on repeat visits.
   ================================ */
function initSaltFeed() {
    const container = document.getElementById('saltFeed');
    if (!container) return;

    const cached = readReleaseCache();
    if (cached) {
        container.innerHTML = cached.map(releaseCard).join('');
        if (Date.now() - cached.cachedAt < FEED_TTL_MS) return;
    } else {
        container.innerHTML = skeletons(6);
    }

    fetch('https://api.github.com/repos/saltstack/salt/releases?per_page=12')
        .then(r => { if (!r.ok) throw new Error(); return r.json(); })
        .then(releases => {
            const stable = /^v\d+(\.\d+)+$/;
            const valid = releases
                .filter(r => !r.draft && !r.prerelease && stable.test(r.tag_name))
                .slice(0, 6);
            if (valid.length === 0) throw new Error();
            const trimmed = valid.map(r => ({
                tag_name: r.tag_name,
                name: r.name,
                published_at: r.published_at,
                html_url: r.html_url,
            }));
            container.innerHTML = trimmed.map(releaseCard).join('');
            writeReleaseCache(trimmed);
        })
        .catch(() => {
            if (cached) return;
            hideGridAndSubhead(container);
        });
}

function initSaltBlog() {
    const container = document.getElementById('saltBlog');
    if (!container) return;

    const cached = readBlogCache();
    if (cached) {
        container.innerHTML = cached.map(blogCard).join('');
        if (Date.now() - cached.cachedAt < FEED_TTL_MS) return;
    } else {
        container.innerHTML = skeletons(6);
    }

    fetch(BLOG_FEED_URL)
        .then(r => { if (!r.ok) throw new Error(); return r.text(); })
        .then(xmlText => {
            const xml = new DOMParser().parseFromString(xmlText, 'text/xml');
            if (xml.querySelector('parsererror')) throw new Error();
            const items = Array.from(xml.querySelectorAll('item')).slice(0, 6);
            if (items.length === 0) throw new Error();
            const posts = items.map(item => ({
                title: textOf(item, 'title'),
                link: textOf(item, 'link'),
                pubDate: textOf(item, 'pubDate'),
            }));
            container.innerHTML = posts.map(blogCard).join('');
            writeBlogCache(posts);
        })
        .catch(() => {
            if (cached) return;
            hideGridAndSubhead(container);
        });
}

function hideGridAndSubhead(container) {
    container.style.display = 'none';
    const prev = container.previousElementSibling;
    if (prev && prev.classList.contains('salt-wild-subhead')) {
        prev.style.display = 'none';
    }
}

function readReleaseCache() {
    try {
        const raw = localStorage.getItem(RELEASES_CACHE_KEY);
        if (!raw) return null;
        const { cachedAt, releases } = JSON.parse(raw);
        if (!Array.isArray(releases) || releases.length === 0) return null;
        return Object.assign(releases, { cachedAt });
    } catch { return null; }
}

function writeReleaseCache(releases) {
    try {
        localStorage.setItem(RELEASES_CACHE_KEY, JSON.stringify({
            cachedAt: Date.now(),
            releases,
        }));
    } catch { /* quota / private mode — ignore */ }
}

function readBlogCache() {
    try {
        const raw = localStorage.getItem(BLOG_CACHE_KEY);
        if (!raw) return null;
        const { cachedAt, posts } = JSON.parse(raw);
        if (!Array.isArray(posts) || posts.length === 0) return null;
        return Object.assign(posts, { cachedAt });
    } catch { return null; }
}

function writeBlogCache(posts) {
    try {
        localStorage.setItem(BLOG_CACHE_KEY, JSON.stringify({
            cachedAt: Date.now(),
            posts,
        }));
    } catch { /* quota / private mode — ignore */ }
}

function blogCard(post) {
    const date = formatShortDate(post.pubDate);
    const age = timeAgo(post.pubDate);
    return `
        <a class="release-card hover-card" href="${escHtml(post.link)}" target="_blank" rel="noopener noreferrer">
            <div class="release-card-top">
                <span class="release-tag">${escHtml(date)}</span>
                <span class="release-age">${age}</span>
            </div>
            <h3 class="release-title">${escHtml(post.title)}</h3>
            <div class="release-footer">
                <span class="release-stat"><i class="fas fa-rss" aria-hidden="true"></i> saltproject.io/blog</span>
                <span class="release-link">Read post ↗</span>
            </div>
        </a>`;
}

function formatShortDate(rfcDate) {
    const d = new Date(rfcDate);
    if (isNaN(d)) return '';
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
}

function textOf(parent, tag) {
    const el = parent.querySelector(tag);
    return el ? el.textContent.trim() : '';
}

function releaseCard(release) {
    const age = timeAgo(release.published_at);
    const title = release.name && release.name.trim()
        ? release.name
        : release.tag_name;
    return `
        <a class="release-card hover-card" href="${escHtml(release.html_url)}" target="_blank" rel="noopener noreferrer">
            <div class="release-card-top">
                <span class="release-tag">${escHtml(release.tag_name)}</span>
                <span class="release-age">${age}</span>
            </div>
            <h3 class="release-title">${escHtml(title)}</h3>
            <div class="release-footer">
                <span class="release-stat"><i class="fab fa-github" aria-hidden="true"></i> saltstack/salt</span>
                <span class="release-link">Release notes ↗</span>
            </div>
        </a>`;
}

function skeletons(n) {
    return Array.from({ length: n }, () => `
        <div class="release-card release-skeleton">
            <div class="skel-line skel-short"></div>
            <div class="skel-line skel-long"></div>
            <div class="skel-line skel-medium"></div>
            <div class="skel-line skel-thin"></div>
        </div>`).join('');
}

function timeAgo(dateStr) {
    const diff = Date.now() - new Date(dateStr).getTime();
    const h = Math.floor(diff / 3_600_000);
    if (h < 1)  return 'just now';
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    if (d < 30) return `${d}d ago`;
    return `${Math.floor(d / 30)}mo ago`;
}

function escHtml(str) {
    return String(str ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

/* ================================
   State Modules Map (salt-states-map.html)
   Loads data/salt-states.json, renders a card per module grouped into
   functional categories. Search + OS chip filters; all collapsed on load.
   ================================ */
function initStateMap() {
    const container = document.getElementById('mapContainer');
    if (!container) return;

    fetch('data/salt-states.json')
        .then(r => { if (!r.ok) throw new Error('fetch failed'); return r.json(); })
        .then(renderStateMap)
        .catch(() => {
            container.innerHTML = '<div class="map-error"><i class="fas fa-triangle-exclamation"></i> Couldn\'t load the modules map. Refresh the page or try again later.</div>';
        });
}

function renderStateMap(data) {
    const container = document.getElementById('mapContainer');
    const { categories, modules, stats } = data;

    /* Hero stat counters */
    const statTotal = document.getElementById('statTotal');
    const statCurated = document.getElementById('statCurated');
    if (statTotal) statTotal.textContent = stats.total;
    if (statCurated) statCurated.textContent = stats.curated;

    /* Group modules by category */
    const byCat = {};
    categories.forEach(c => byCat[c.id] = []);
    modules.forEach(m => {
        if (m.category && byCat[m.category]) byCat[m.category].push(m);
    });

    /* Render each category section. All categories start collapsed —
       the user clicks a category head to expand it. */
    container.innerHTML = categories.map(cat => {
        const cards = byCat[cat.id] || [];
        const cardsHtml = cards.length
            ? `<div class="map-cards">${cards.map(stateMapCard).join('')}</div>`
            : `<div class="map-cat-empty">Curation in progress — coming soon.</div>`;
        return `
            <div class="map-category" data-open="false" data-cat="${escHtml(cat.id)}">
                <div class="map-cat-head" role="button" tabindex="0" aria-expanded="false" aria-controls="cat-body-${escHtml(cat.id)}">
                    <span class="map-cat-toggle">▸</span>
                    <div style="flex:1; min-width:0;">
                        <h3 class="map-cat-title">${escHtml(cat.label)}</h3>
                        <p class="map-cat-blurb">${escHtml(cat.blurb)}</p>
                    </div>
                    <span class="map-cat-count">${cards.length}</span>
                </div>
                <div class="map-cat-body" id="cat-body-${escHtml(cat.id)}">
                    ${cardsHtml}
                </div>
            </div>`;
    }).join('');

    wireStateMapInteractions();
}

function stateMapCard(m) {
    const safeName = escHtml(m.name);
    const os = m.os || [];
    const summary = m.summary || '';
    const osBadges = os.map(o => {
        const cls = `os-${String(o).replace(/[^a-z0-9-]/gi, '-').toLowerCase()}`;
        return `<span class="map-os-badge ${cls}">${escHtml(o)}</span>`;
    }).join('');
    const mainFn = m.main ? `<p class="map-card-main">main: <code>${escHtml(m.main)}</code></p>` : '';

    const exHtml = (m.examples || []).map(ex => `<pre><code>${escHtml(ex)}</code></pre>`).join('');
    const fnsHtml = (m.functions || []).map(f =>
        `<div><code><span class="fn-name">${safeName}.${escHtml(f.name)}</span><span class="fn-sig">${escHtml(f.signature)}</span></code></div>`
    ).join('');

    let detailsHtml = '';
    let toggleHtml = '';
    if (exHtml || fnsHtml) {
        detailsHtml = `
            <div class="map-card-details">
                ${exHtml ? `<h5>Example</h5>${exHtml}` : ''}
                ${fnsHtml ? `<h5>Functions</h5><div class="map-fnlist">${fnsHtml}</div>` : ''}
            </div>`;
        toggleHtml = `<button type="button" class="map-card-toggle">▸ details</button>`;
    }

    const docLink = `<a class="map-card-doclink" href="${escHtml(m.docs_url)}" target="_blank" rel="noopener">More detail? Official docs ↗</a>`;

    return `
        <article class="map-card" data-name="${safeName}" data-os="${escHtml(os.join(' '))}" data-summary="${escHtml(summary.toLowerCase())}">
            <div class="map-card-top">
                <h4 class="map-card-name">${safeName}</h4>
            </div>
            <div class="map-card-os">${osBadges}</div>
            <p class="map-card-summary">${escHtml(summary)}</p>
            ${mainFn}
            <div class="map-card-actions">
                ${toggleHtml}
                ${docLink}
            </div>
            ${detailsHtml}
        </article>`;
}

function wireStateMapInteractions() {
    /* Category fold toggle */
    document.querySelectorAll('.map-cat-head').forEach(head => {
        const open = () => {
            const cat = head.closest('.map-category');
            const isOpen = cat.dataset.open === 'true';
            cat.dataset.open = String(!isOpen);
            head.setAttribute('aria-expanded', String(!isOpen));
        };
        head.addEventListener('click', open);
        head.addEventListener('keydown', e => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); }
        });
    });

    /* Per-card details toggle */
    document.querySelectorAll('.map-card-toggle').forEach(btn => {
        btn.addEventListener('click', () => {
            const card = btn.closest('.map-card');
            const isOpen = card.dataset.open === 'true';
            card.dataset.open = String(!isOpen);
            btn.textContent = (isOpen ? '▸' : '▾') + ' details';
        });
    });

    /* Search + OS filter */
    const searchInput = document.getElementById('mapSearch');
    const osChips = document.querySelectorAll('#mapOsChips .map-chip');
    let activeOs = 'all';

    function applyFilters() {
        const q = (searchInput?.value || '').trim().toLowerCase();
        document.querySelectorAll('.map-category').forEach(cat => {
            let visible = 0;
            cat.querySelectorAll('.map-card').forEach(card => {
                const name = card.dataset.name || '';
                const summary = card.dataset.summary || '';
                const os = card.dataset.os || '';
                const matchSearch = !q || name.includes(q) || summary.includes(q);
                const matchOs = activeOs === 'all' || os.split(/\s+/).includes(activeOs);
                const show = matchSearch && matchOs;
                card.style.display = show ? '' : 'none';
                if (show) visible++;
            });
            /* Auto-open category with matches when filtering, auto-collapse when no matches */
            if (q || activeOs !== 'all') {
                cat.dataset.open = visible > 0 ? 'true' : 'false';
                cat.querySelector('.map-cat-head')?.setAttribute('aria-expanded', String(visible > 0));
            }
            cat.querySelector('.map-cat-count').textContent = visible;
        });
    }

    searchInput?.addEventListener('input', applyFilters);
    osChips.forEach(chip => {
        chip.addEventListener('click', () => {
            osChips.forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            activeOs = chip.dataset.os;
            applyFilters();
        });
    });
}

