/* ═══════════════════════════════════════════════════════════════════
   Comparison History Page
   ═══════════════════════════════════════════════════════════════════ */

let allHistory = [];

// ── Load History ───────────────────────────────────────────────────

async function loadHistory() {
    try {
        // Load history and stats in parallel
        const [histResp, statsResp, guestsResp] = await Promise.all([
            fetch('/api/comparisons?limit=200'),
            fetch('/api/history/stats'),
            fetch('/api/guests'),
        ]);

        allHistory = await histResp.json();
        const stats = await statsResp.json();
        const guests = await guestsResp.json();

        renderStats(stats);
        populateGuestFilter(guests);
        renderHistory(allHistory);
    } catch (err) {
        console.error('Failed to load history:', err);
    }
}

function renderStats(stats) {
    document.getElementById('stat-total').textContent = stats.total || 0;

    if (stats.biggest_upset) {
        document.getElementById('stat-upset').innerHTML =
            `<span style="font-size: 0.9rem;">${escapeHtml(stats.biggest_upset.winner_name)} beat ${escapeHtml(stats.biggest_upset.loser_name)}</span>
             <br><span style="font-size: 0.75rem; color: var(--color-text-muted);">+${stats.biggest_upset.elo_diff} Elo upset</span>`;
    } else {
        document.getElementById('stat-upset').textContent = '—';
    }

    if (stats.most_compared) {
        document.getElementById('stat-most').innerHTML =
            `<span style="font-size: 0.9rem;">${escapeHtml(stats.most_compared.name)}</span>
             <br><span style="font-size: 0.75rem; color: var(--color-text-muted);">${stats.most_compared.count} comparisons</span>`;
    } else {
        document.getElementById('stat-most').textContent = '—';
    }
}

function populateGuestFilter(guests) {
    const select = document.getElementById('filter-guest');
    guests.forEach(g => {
        const option = document.createElement('option');
        option.value = g.id;
        option.textContent = g.name;
        select.appendChild(option);
    });
}

function renderHistory(entries) {
    const container = document.getElementById('history-list');

    if (!entries.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="icon">📜</div>
                <h3>No comparisons yet</h3>
                <p>Start ranking guests to build your comparison history!</p>
                <a href="/compare" class="btn btn-primary mt-4">Start Ranking</a>
            </div>`;
        return;
    }

    container.innerHTML = entries.map(entry => {
        const time = formatTimeAgo(entry.created_at);
        const phaseLabel = entry.phase === 'refinement' ? 'Refinement' : 'Sort';
        const phaseClass = entry.phase === 'refinement' ? 'badge-should' : 'badge-default';

        return `
            <div class="history-entry">
                <span>You chose</span>
                <span class="winner">${escapeHtml(entry.winner_name)}</span>
                <span>over</span>
                <span class="loser">${escapeHtml(entry.loser_name)}</span>
                <span class="phase-badge ${phaseClass}">${phaseLabel}</span>
                <span class="time">${time}</span>
            </div>`;
    }).join('');
}

function formatTimeAgo(isoString) {
    if (!isoString) return '';
    const now = new Date();
    const then = new Date(isoString);
    const seconds = Math.floor((now - then) / 1000);

    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ── Filtering ──────────────────────────────────────────────────────

document.getElementById('filter-guest').addEventListener('change', applyHistoryFilters);
document.getElementById('filter-phase').addEventListener('change', applyHistoryFilters);
document.getElementById('btn-clear-history-filters').addEventListener('click', () => {
    document.getElementById('filter-guest').value = '';
    document.getElementById('filter-phase').value = '';
    renderHistory(allHistory);
});

async function applyHistoryFilters() {
    const guestId = document.getElementById('filter-guest').value;
    const phase = document.getElementById('filter-phase').value;

    let url = '/api/comparisons?limit=200';
    if (guestId) url += `&guest_id=${guestId}`;
    if (phase) url += `&phase=${phase}`;

    try {
        const resp = await fetch(url);
        const data = await resp.json();
        renderHistory(data);
    } catch (err) {
        console.error('Failed to filter:', err);
    }
}

// ── Initialize ─────────────────────────────────────────────────────

loadHistory();
