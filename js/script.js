'use strict';

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initNavigation();
    initAnimations();
    initSaltFeed();
});

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
    }
}

function initNavigation() {
    const navbar = document.querySelector('.navbar');
    const hamburger = document.querySelector('.hamburger');
    const navMenu = document.querySelector('.nav-menu');
    const navLinks = document.querySelectorAll('.nav-link');

    function closeNav() {
        hamburger.classList.remove('active');
        navMenu.classList.remove('active');
        hamburger.setAttribute('aria-expanded', 'false');
    }

    hamburger?.addEventListener('click', () => {
        const isActive = hamburger.classList.toggle('active');
        navMenu.classList.toggle('active');
        hamburger.setAttribute('aria-expanded', String(isActive));
    });

    navLinks.forEach(link => link.addEventListener('click', closeNav));

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && navMenu.classList.contains('active')) closeNav();
    });

    window.addEventListener('scroll', debounce(() => {
        navbar.classList.toggle('scrolled', window.scrollY > 50);
    }, 150));
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
   ================================ */
function initSaltFeed() {
    const container = document.getElementById('saltFeed');
    if (!container) return;

    container.innerHTML = skeletons(6);

    const url = 'https://api.github.com/repos/saltstack/salt/releases?per_page=12';

    fetch(url)
        .then(r => { if (!r.ok) throw new Error(); return r.json(); })
        .then(releases => {
            // Stable tags only — Salt uses vNNNN.N(.N) and marks RCs with prerelease=false sometimes
            const stable = /^v\d+(\.\d+)+$/;
            const valid = releases
                .filter(r => !r.draft && !r.prerelease && stable.test(r.tag_name))
                .slice(0, 6);
            if (valid.length === 0) throw new Error();
            container.innerHTML = valid.map(releaseCard).join('');
        })
        .catch(() => {
            const section = container.closest('.salt-wild');
            if (section) section.style.display = 'none';
        });
}

function releaseCard(release) {
    const age = timeAgo(release.published_at);
    const title = release.name && release.name.trim()
        ? release.name
        : release.tag_name;
    return `
        <a class="release-card" href="${escHtml(release.html_url)}" target="_blank" rel="noopener noreferrer">
            <div class="release-card-top">
                <span class="release-tag">${escHtml(release.tag_name)}</span>
                <span class="release-age">${age}</span>
            </div>
            <h3 class="release-title">${escHtml(title)}</h3>
            <div class="release-footer">
                <span class="release-stat"><i class="fab fa-github"></i> saltstack/salt</span>
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

function debounce(fn, delay) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
}
