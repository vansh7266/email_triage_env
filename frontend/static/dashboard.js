// ── State ──────────────────────────────────────────────────────────────────
const state = {
    allEmails: [],
    currentFilter: "all",
    sortBy: "newest",
    nextPageToken: null,
    isFetching: false,
    cancelFetching: false,
    toastTimer: null,
};

const priorityOrder = { high: 0, medium: 1, low: 2 };

// Cached DOM references
const el = {};

// ── DOM Binding ─────────────────────────────────────────────────────────────
function bindElements() {
    el.splash       = document.getElementById("splash-screen");
    el.splashCopy   = document.getElementById("splash-copy");
    el.userEmail    = document.getElementById("user-email");
    el.triageBtn    = document.getElementById("triage-btn");
    el.stopBtn      = document.getElementById("stop-btn");
    el.loadMoreBtn  = document.getElementById("load-more-btn");
    el.fetchStatus  = document.getElementById("fetch-status");
    el.loadingBar   = document.getElementById("loading-bar");
    el.filterRow    = document.getElementById("filter-row");
    el.emailList    = document.getElementById("email-list");
    el.deptList     = document.getElementById("department-list");
    el.watchList    = document.getElementById("watch-list");
    el.sortSelect   = document.getElementById("sort-select");
    el.toast        = document.getElementById("toast");
    el.stats = {
        total:       document.getElementById("stat-total"),
        avg:         document.getElementById("stat-avg"),
        high:        document.getElementById("stat-high"),
        escalations: document.getElementById("stat-escalations"),
        topTopic:    document.getElementById("stat-top-cat"),
    };
}

// ── Splash ──────────────────────────────────────────────────────────────────
function setupSplash() {
    if (!el.splash) return;
    const messages = [
        "Loading your workspace...",
        "Preparing the review queue...",
        "Setting up safe rendering...",
    ];
    let i = 0;
    const iv = setInterval(() => {
        i = (i + 1) % messages.length;
        if (el.splashCopy) el.splashCopy.textContent = messages[i];
    }, 400);
    setTimeout(() => {
        clearInterval(iv);
        el.splash.classList.add("is-hidden");
    }, 1400);
}

// ── Events ──────────────────────────────────────────────────────────────────
function bindEvents() {
    el.triageBtn.addEventListener("click",  () => runTriage(100));
    el.stopBtn.addEventListener("click",    stopFetching);
    el.loadMoreBtn.addEventListener("click",() => runTriage(100));
    el.sortSelect.addEventListener("change", (e) => {
        state.sortBy = e.target.value;
        renderQueue();
        renderWatchList();
    });
}

// ── Profile ─────────────────────────────────────────────────────────────────
async function loadProfile() {
    try {
        const res = await fetch("/auth/me", { credentials: "include" });
        if (res.status === 401) { window.location.href = "/"; return; }
        const data = await res.json();
        const emailText = data.email || "Gmail connected";
        // Preserve the SVG icon, just update text node
        const userChip = el.userEmail;
        userChip.childNodes.forEach(n => { if (n.nodeType === 3) n.remove(); });
        userChip.appendChild(document.createTextNode(emailText));
    } catch {
        // Keep "Loading..." as fallback
    }
}

// ── Controls ────────────────────────────────────────────────────────────────
function toggleControls() {
    const hasResults = state.allEmails.length > 0;
    el.triageBtn.disabled = state.isFetching;
    el.triageBtn.innerHTML = state.isFetching
        ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true" style="width:18px;height:18px;animation:spin 1s linear infinite"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg> Triaging...`
        : `<svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" style="width:18px;height:18px"><path fill-rule="evenodd" d="M15.312 11.424a5.5 5.5 0 01-9.201 2.466l-.312-.311h2.433a.75.75 0 000-1.5H3.989a.75.75 0 00-.75.75v4.242a.75.75 0 001.5 0v-2.43l.31.31a7 7 0 0011.712-3.138.75.75 0 00-1.449-.39zm1.23-3.723a.75.75 0 00.219-.53V2.929a.75.75 0 00-1.5 0V5.36l-.31-.31A7 7 0 003.239 8.188a.75.75 0 101.448.389A5.5 5.5 0 0113.89 6.11l.311.31h-2.432a.75.75 0 000 1.5h4.243a.75.75 0 00.53-.219z" clip-rule="evenodd"/></svg> Start Triage`;
    el.stopBtn.classList.toggle("is-hidden", !state.isFetching);
    el.loadMoreBtn.classList.toggle(
        "is-hidden",
        state.isFetching || !state.nextPageToken || !hasResults
    );
}

function stopFetching() {
    if (!state.isFetching) return;
    state.cancelFetching = true;
    setFetchStatus("Stopping after the current batch...");
    showToast("Run will pause after this batch.");
}

function setFetchStatus(msg) { if (el.fetchStatus) el.fetchStatus.textContent = msg; }
function setProgress(val) { if (el.loadingBar) el.loadingBar.style.width = `${Math.max(0, Math.min(100, val))}%`; }

// ── Toast ───────────────────────────────────────────────────────────────────
function showToast(msg) {
    el.toast.textContent = msg;
    el.toast.classList.add("is-visible");
    if (state.toastTimer) clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(() => el.toast.classList.remove("is-visible"), 3200);
}

// ── Triage ──────────────────────────────────────────────────────────────────
async function runTriage(limit = 100) {
    if (state.isFetching) return;
    state.isFetching = true;
    state.cancelFetching = false;
    toggleControls();

    if (!state.allEmails.length) renderSkeletons();
    let fetched = 0;
    setProgress(8);
    setFetchStatus("Starting live triage...");

    try {
        while (fetched < limit) {
            if (state.cancelFetching) break;
            setFetchStatus(`Processing batch… ${state.allEmails.length} emails loaded`);
            setProgress(Math.min(10 + (fetched / limit) * 78, 92));

            const res = await fetch("/triage", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({ page_token: state.nextPageToken }),
            });

            if (res.status === 401) { window.location.href = "/"; return; }

            let payload = {};
            try { payload = await res.json(); } catch { payload = {}; }
            if (!res.ok) throw new Error(payload.detail || "Triage request failed.");

            const results = Array.isArray(payload.results) ? payload.results : [];
            state.nextPageToken = payload.next_page_token || null;

            if (!results.length) {
                if (!state.allEmails.length) {
                    renderEmptyState("Inbox is clear", "No unread emails found. Start a new triage run when messages arrive.");
                }
                setFetchStatus(state.nextPageToken ? "No emails in this batch." : "All unread emails loaded.");
                break;
            }

            mergeEmails(results);
            fetched += results.length;
            updateStats();
            renderFilters();
            renderQueue();
            renderDepartments();
            renderWatchList();

            if (!state.nextPageToken) {
                setFetchStatus("All unread emails for this session loaded.");
                break;
            }
        }

        if (state.cancelFetching) {
            setFetchStatus(`${state.allEmails.length} emails loaded. Run paused.`);
            showToast("Triage paused.");
        } else if (fetched > 0) {
            setFetchStatus(
                state.nextPageToken
                    ? `${state.allEmails.length} emails loaded. More available.`
                    : `${state.allEmails.length} emails loaded — end of unread queue.`
            );
            showToast(`Loaded ${fetched} new results.`);
        }
    } catch (err) {
        const msg = err instanceof Error ? err.message : "Triage failed.";
        setFetchStatus("Triage could not complete.");
        if (!state.allEmails.length) renderEmptyState("Could not load results", msg);
        showToast(msg);
    } finally {
        state.isFetching = false;
        state.cancelFetching = false;
        setProgress(100);
        setTimeout(() => setProgress(0), 600);
        toggleControls();
        updateStats();
        renderFilters();
        renderQueue();
        renderDepartments();
        renderWatchList();
    }
}

// ── Data helpers ─────────────────────────────────────────────────────────────
function mergeEmails(incoming) {
    const map = new Map(state.allEmails.map(e => [e.email_id, e]));
    incoming.forEach(e => map.set(e.email_id, e));
    state.allEmails = Array.from(map.values());
}

function buildCounts(items, keyFn) {
    const c = new Map();
    items.forEach(i => { const k = keyFn(i); c.set(k, (c.get(k) || 0) + 1); });
    return Array.from(c.entries()).sort((a, b) => b[1] - a[1]);
}

function sortEmails(list) {
    const arr = [...list];
    if (state.sortBy === "priority") {
        arr.sort((a, b) => {
            const pd = (priorityOrder[a.priority] ?? 9) - (priorityOrder[b.priority] ?? 9);
            return pd !== 0 ? pd : byNewest(a, b);
        });
    } else if (state.sortBy === "confidence") {
        arr.sort((a, b) => {
            const cd = Number(b.score || 0) - Number(a.score || 0);
            return cd !== 0 ? cd : byNewest(a, b);
        });
    } else {
        arr.sort(byNewest);
    }
    return arr;
}

function byNewest(a, b) {
    return parseTs(b.received_at) - parseTs(a.received_at);
}

function parseTs(v) {
    const d = v ? new Date(v) : null;
    return d && !isNaN(d.getTime()) ? d.getTime() : 0;
}

function getFiltered() {
    const list = [...state.allEmails];
    if (state.currentFilter === "escalate") return list.filter(e => e.escalate);
    if (state.currentFilter === "high") return list.filter(e => e.priority === "high");
    if (state.currentFilter.startsWith("topic:")) {
        const t = state.currentFilter.slice("topic:".length);
        return list.filter(e => e.topic === t);
    }
    return list;
}

// ── Stats ────────────────────────────────────────────────────────────────────
function updateStats() {
    const total = state.allEmails.length;
    const high  = state.allEmails.filter(e => e.priority === "high").length;
    const esc   = state.allEmails.filter(e => e.escalate).length;
    const avg   = total
        ? Math.round((state.allEmails.reduce((s, e) => s + Number(e.score || 0), 0) / total) * 100)
        : 0;
    const counts = buildCounts(state.allEmails, e => e.topic || "General");
    const top = counts[0] ? counts[0][0] : "—";

    el.stats.total.textContent       = String(total);
    el.stats.avg.textContent         = `${avg}%`;
    el.stats.high.textContent        = String(high);
    el.stats.escalations.textContent = String(esc);
    el.stats.topTopic.textContent    = top;
}

// ── Filters ──────────────────────────────────────────────────────────────────
function renderFilters() {
    el.filterRow.replaceChildren();
    const filters = [
        { key: "all",      label: "All" },
        { key: "escalate", label: "🚨 Escalations" },
        { key: "high",     label: "🔴 High priority" },
    ];
    buildCounts(state.allEmails, e => e.topic || "General")
        .slice(0, 4)
        .forEach(([t]) => filters.push({ key: `topic:${t}`, label: t }));

    if (!filters.some(f => f.key === state.currentFilter)) state.currentFilter = "all";

    filters.forEach(f => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "filter-btn" + (f.key === state.currentFilter ? " is-active" : "");
        btn.textContent = f.label;
        btn.addEventListener("click", () => {
            state.currentFilter = f.key;
            renderFilters();
            renderQueue();
        });
        el.filterRow.appendChild(btn);
    });
}

// ── Queue ────────────────────────────────────────────────────────────────────
function renderQueue() {
    el.emailList.replaceChildren();
    if (!state.allEmails.length && state.isFetching) { renderSkeletons(); return; }
    if (!state.allEmails.length) {
        renderEmptyState(
            "Start a triage run",
            "Click 'Start Triage' to fetch your unread Gmail messages. Results appear in real-time as each batch is processed."
        );
        return;
    }
    const filtered = sortEmails(getFiltered());
    if (!filtered.length) {
        renderEmptyState("No emails match this filter", "Try clearing the filter or loading more messages.");
        return;
    }
    const frag = document.createDocumentFragment();
    filtered.forEach((email, i) => frag.appendChild(buildCard(email, i)));
    el.emailList.appendChild(frag);
}

// ── Card Builder ─────────────────────────────────────────────────────────────
function buildCard(email, index) {
    const card = document.createElement("div");
    card.className = "email-card" + (email.escalate ? " is-escalated" : "");
    card.style.setProperty("--delay", `${Math.min(index, 10) * 40}ms`);
    card.setAttribute("aria-label", `Email: ${email.subject || "No subject"}`);

    // Priority bar
    const bar = document.createElement("div");
    bar.className = `email-priority-bar priority-${email.priority || "low"}`;
    card.appendChild(bar);

    // Inner wrapper
    const inner = document.createElement("div");
    inner.className = "email-card-inner";

    // ── Left column ──
    const left = document.createElement("div");
    left.className = "email-left";

    // Header row: avatar + sender/meta
    const hdr = document.createElement("div");
    hdr.className = "email-header";

    const av = document.createElement("div");
    av.className = "avatar";
    av.textContent = avatarChar(email);

    const ident = document.createElement("div");
    ident.className = "email-ident";

    const sender = document.createElement("div");
    sender.className = "email-sender";
    sender.textContent = email.sender_name || email.sender || "Unknown sender";

    const meta = document.createElement("div");
    meta.className = "email-meta";
    meta.textContent = buildMeta(email);

    ident.append(sender, meta);
    hdr.append(av, ident);

    // Subject
    const subj = document.createElement("div");
    subj.className = "email-subject";
    subj.textContent = email.subject || "No subject";

    // Summary (preview/body truncated)
    const summary = document.createElement("div");
    summary.className = "email-summary";
    summary.textContent = email.preview || email.body || "No preview available.";

    // Chips
    const chips = document.createElement("div");
    chips.className = "email-chips";
    chips.append(
        chip(email.topic || "General", "chip-topic"),
        chip(fmtPriority(email.priority), `chip-priority-${email.priority || "low"}`),
        chip(fmtDept(email.department), "chip-department")
    );
    if (email.escalate) chips.appendChild(chip("⚡ Escalate", "chip-escalate"));
    chips.appendChild(chip(email.source === "heuristic" ? "Fallback" : "AI routed", "chip-source"));

    // Reasoning
    const reason = document.createElement("div");
    reason.className = "email-reasoning";
    reason.textContent = email.reasoning || "AI routing decision applied.";

    left.append(hdr, subj, summary, chips, reason);

    // ── Right column ──
    const right = document.createElement("div");
    right.className = "email-right";

    const ring = document.createElement("div");
    ring.className = `score-ring ${scoreClass(email.score)}`;
    ring.textContent = `${Math.round(Number(email.score || 0) * 100)}%`;

    const lbl = document.createElement("div");
    lbl.className = "score-label";
    lbl.textContent = "confidence";

    right.append(ring, lbl);

    inner.append(left, right);
    card.appendChild(inner);
    return card;
}

// ── Departments ───────────────────────────────────────────────────────────────
function renderDepartments() {
    el.deptList.replaceChildren();
    if (!state.allEmails.length) {
        const p = document.createElement("p");
        p.className = "sidebar-empty";
        p.textContent = "Run triage to see distribution";
        el.deptList.appendChild(p);
        return;
    }
    const counts = buildCounts(state.allEmails, e => fmtDept(e.department));
    const max = counts[0] ? counts[0][1] : 1;

    counts.forEach(([dept, count]) => {
        const row = document.createElement("div");
        row.className = "dept-row";

        const labelRow = document.createElement("div");
        labelRow.className = "dept-label-row";
        const name = document.createElement("span");
        name.className = "dept-name";
        name.textContent = dept;
        const cnt = document.createElement("span");
        cnt.className = "dept-count";
        cnt.textContent = String(count);
        labelRow.append(name, cnt);

        const bar = document.createElement("div");
        bar.className = "dept-bar";
        const fill = document.createElement("span");
        fill.className = "dept-fill";
        fill.style.width = `${Math.max(8, (count / max) * 100)}%`;
        bar.appendChild(fill);

        row.append(labelRow, bar);
        el.deptList.appendChild(row);
    });
}

// ── Watch List ────────────────────────────────────────────────────────────────
function renderWatchList() {
    el.watchList.replaceChildren();
    const queue = sortEmails(
        state.allEmails.filter(e => e.escalate || e.priority === "high")
    ).slice(0, 5);

    if (!queue.length) {
        const p = document.createElement("p");
        p.className = "sidebar-empty";
        p.textContent = "High-priority cards appear here";
        el.watchList.appendChild(p);
        return;
    }

    queue.forEach(email => {
        const card = document.createElement("div");
        card.className = "watch-card";

        const title = document.createElement("h4");
        title.textContent = email.subject || "No subject";

        const info = document.createElement("p");
        info.textContent = `${email.topic || "General"} · ${fmtDept(email.department)} · ${Math.round(Number(email.score || 0) * 100)}%`;

        card.append(title, info);
        el.watchList.appendChild(card);
    });
}

// ── Empty State ───────────────────────────────────────────────────────────────
function renderEmptyState(title, message) {
    el.emailList.replaceChildren();
    const wrap = document.createElement("div");
    wrap.className = "empty-state";

    const iconWrap = document.createElement("div");
    iconWrap.className = "empty-icon";
    iconWrap.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75"/></svg>`;

    const h3 = document.createElement("h3");
    h3.textContent = title;

    const p = document.createElement("p");
    p.textContent = message;

    wrap.append(iconWrap, h3, p);

    if (!state.allEmails.length && !state.isFetching) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "empty-btn";
        btn.innerHTML = `<svg viewBox="0 0 20 20" fill="currentColor" style="width:18px;height:18px"><path fill-rule="evenodd" d="M15.312 11.424a5.5 5.5 0 01-9.201 2.466l-.312-.311h2.433a.75.75 0 000-1.5H3.989a.75.75 0 00-.75.75v4.242a.75.75 0 001.5 0v-2.43l.31.31a7 7 0 0011.712-3.138.75.75 0 00-1.449-.39zm1.23-3.723a.75.75 0 00.219-.53V2.929a.75.75 0 00-1.5 0V5.36l-.31-.31A7 7 0 003.239 8.188a.75.75 0 101.448.389A5.5 5.5 0 0113.89 6.11l.311.31h-2.432a.75.75 0 000 1.5h4.243a.75.75 0 00.53-.219z" clip-rule="evenodd"/></svg> Start Triage`;
        btn.addEventListener("click", () => runTriage(100));
        wrap.appendChild(btn);
    }

    el.emailList.appendChild(wrap);
}

// ── Skeleton Loader ───────────────────────────────────────────────────────────
function renderSkeletons() {
    el.emailList.replaceChildren();
    const list = document.createElement("div");
    list.className = "skeleton-list";
    for (let i = 0; i < 4; i++) {
        const c = document.createElement("div");
        c.className = "skeleton-card";
        list.appendChild(c);
    }
    el.emailList.appendChild(list);
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function chip(label, cls) {
    const s = document.createElement("span");
    s.className = `chip ${cls}`;
    s.textContent = label;
    return s;
}

function avatarChar(email) {
    const src = email.sender_name || email.sender || email.subject || "T";
    return src.trim().charAt(0).toUpperCase() || "T";
}

function buildMeta(email) {
    const parts = [];
    if (email.sender_email && email.sender_email !== email.sender_name) {
        parts.push(email.sender_email);
    }
    const ts = fmtTimestamp(email.received_at);
    if (ts) parts.push(ts);
    return parts.join(" · ") || "Live triage result";
}

function fmtTimestamp(v) {
    if (!v) return "";
    const d = new Date(v);
    if (isNaN(d.getTime())) return "";
    const now = new Date();
    if (now.toDateString() === d.toDateString()) {
        return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    }
    return d.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function fmtDept(v) {
    return String(v || "customer_success")
        .split("_").map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
}

function fmtPriority(v) {
    const n = String(v || "medium");
    return `${n.charAt(0).toUpperCase()}${n.slice(1)} priority`;
}

function scoreClass(score) {
    const n = Number(score || 0);
    if (n >= 0.75) return "score-high";
    if (n >= 0.5)  return "score-mid";
    return "score-low";
}

// @keyframes spin is now defined in dashboard.css (CSP-safe)

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
    bindElements();
    setupSplash();
    bindEvents();
    toggleControls();
    renderFilters();
    renderQueue();
    renderDepartments();
    renderWatchList();
    updateStats();
    await loadProfile();
});
