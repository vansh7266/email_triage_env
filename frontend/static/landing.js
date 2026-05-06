// ── Splash ──────────────────────────────────────────────────────────────────
(function setupSplash() {
    const splash = document.getElementById("splash");
    if (!splash) return;
    setTimeout(() => splash.classList.add("is-hidden"), 1200);
})();

// ── Error Banner ─────────────────────────────────────────────────────────────
(function showErrorBanner() {
    const params = new URLSearchParams(window.location.search);
    const authError = params.get("auth_error");
    if (!authError) return;
    const banner = document.getElementById("error-banner");
    const text   = document.getElementById("error-banner-text");
    if (!banner || !text) return;
    const detail = params.get("auth_detail");
    text.textContent = detail ? `${authError} — ${detail}` : authError;
    banner.classList.remove("is-hidden");
    // Clean URL without reloading
    const clean = window.location.pathname;
    window.history.replaceState({}, "", clean);
})();

// ── Sticky header scroll shadow ──────────────────────────────────────────────
(function headerScroll() {
    const header = document.getElementById("header");
    if (!header) return;
    const update = () => header.classList.toggle("scrolled", window.scrollY > 8);
    update();
    window.addEventListener("scroll", update, { passive: true });
})();

// ── Apply delay classes (CSP-safe alternative to inline style="--delay") ─────
(function applyDelayClasses() {
    document.querySelectorAll("[data-delay]").forEach(el => {
        const d = el.getAttribute("data-delay");
        if (d) el.classList.add(`delay-${d}`);
    });
})();

// ── Scroll-triggered animations ───────────────────────────────────────────────
(function revealOnScroll() {
    const els = document.querySelectorAll(".animate-fade-up, .animate-fade-left");
    if (!els.length) return;

    const io = new IntersectionObserver(
        (entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-visible");
                    io.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.08, rootMargin: "0px 0px -40px 0px" }
    );

    els.forEach(el => {
        // If element is already above the fold, reveal immediately
        const rect = el.getBoundingClientRect();
        if (rect.top < window.innerHeight * 0.9) {
            el.classList.add("is-visible");
        } else {
            io.observe(el);
        }
    });
})();

// ── Smooth scroll for anchor links ────────────────────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener("click", e => {
        const id = a.getAttribute("href");
        if (!id || id === "#") return;
        const target = document.querySelector(id);
        if (!target) return;
        e.preventDefault();
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        // Close mobile nav if open
        const nav = document.querySelector(".nav");
        const toggle = document.getElementById("nav-toggle");
        if (nav && nav.classList.contains("is-open")) {
            nav.classList.remove("is-open");
            if (toggle) {
                toggle.classList.remove("is-active");
                toggle.setAttribute("aria-expanded", "false");
            }
        }
    });
});

// ── Mobile nav toggle (class-based, CSP-safe) ─────────────────────────────────
(function mobileNav() {
    const toggle = document.getElementById("nav-toggle");
    const nav    = document.querySelector(".nav");
    if (!toggle || !nav) return;

    toggle.addEventListener("click", () => {
        const isOpen = nav.classList.toggle("is-open");
        toggle.classList.toggle("is-active", isOpen);
        toggle.setAttribute("aria-expanded", String(isOpen));
    });

    // Close nav on Escape key
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && nav.classList.contains("is-open")) {
            nav.classList.remove("is-open");
            toggle.classList.remove("is-active");
            toggle.setAttribute("aria-expanded", "false");
            toggle.focus();
        }
    });
})();
