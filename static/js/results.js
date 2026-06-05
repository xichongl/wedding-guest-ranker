/* ═══════════════════════════════════════════════════════════════════
   Results View — ranked list + cutoff + confidence + refinement
   ═══════════════════════════════════════════════════════════════════ */

const TIER_LABELS = {
    'must_invite': 'Must Invite',
    'should_invite': 'Should Invite',
    'nice_to_have': 'Nice to Have',
    'only_if_space': 'Only If Space',
};

const TIER_BADGE_CLASS = {
    'must_invite': 'badge-must',
    'should_invite': 'badge-should',
    'nice_to_have': 'badge-nice',
    'only_if_space': 'badge-space',
};

let allGuests = [];
let sortable = null;
let guestLimit = null;

// ── Load & Render ──────────────────────────────────────────────────

async function loadResults() {
    try {
        const resp = await fetch('/api/results');
        allGuests = await resp.json();
        renderResults(allGuests);
    } catch (err) {
        console.error('Failed to load results:', err);
    }
}

function renderResults(guests) {
    const list = document.getElementById('results-list');
    document.getElementById('result-count').textContent =
        `${guests.length} guest${guests.length !== 1 ? 's' : ''} ranked`;

    if (!guests.length) {
        list.innerHTML = `
            <li class="empty-state">
                <div class="icon">📊</div>
                <h3>No guests ranked yet</h3>
                <p>Start comparing guests to build your ranked list!</p>
                <a href="/compare" class="btn btn-primary mt-4">Start Ranking</a>
            </li>`;
        return;
    }

    let html = '';
    guests.forEach((g, i) => {
        const tierBadgeHtml = g.tier
            ? `<span class="badge ${TIER_BADGE_CLASS[g.tier] || 'badge-default'}">${TIER_LABELS[g.tier] || g.tier}</span>`
            : '';
        const catBadgeHtml = g.category
            ? `<span class="badge badge-default">${g.category}</span>`
            : '';
        const elo = Math.round(g.elo_rating);
        const conf = g.confidence || 0;
        const confClass = conf >= 0.8 ? 'confidence-high' : conf >= 0.5 ? 'confidence-moderate' : 'confidence-low';
        const confLabel = conf >= 0.8 ? 'Confident' : conf >= 0.5 ? 'Moderate' : 'Uncertain';
        const confTitle = `Confidence: ${confLabel} (${Math.round(conf * 100)}%) · ${g.comparisons_done} comparisons · Elo: ${elo}`;

        // Determine if above/below cutoff
        let cutoffClass = '';
        if (guestLimit !== null && guestLimit > 0) {
            cutoffClass = i < guestLimit ? 'invited' : 'waitlisted';
        }

        html += `
            <li class="result-item ${cutoffClass}" data-guest-id="${g.id}" title="${confTitle}">
                <span class="result-rank">#${i + 1}</span>
                <span class="result-name">${escapeHtml(g.name)}</span>
                <div class="result-meta">
                    <span class="confidence-dot ${confClass}" title="${confTitle}"></span>
                    ${catBadgeHtml}
                    ${tierBadgeHtml}
                    <span class="result-elo">Elo: ${elo}</span>
                    <span class="result-elo">${g.comparisons_done} cmp</span>
                </div>
            </li>`;

        // Insert cutoff divider
        if (guestLimit !== null && guestLimit > 0 && i === guestLimit - 1 && i < guests.length - 1) {
            html += `
                <li class="cutoff-divider">
                    ⏳ Cutoff — ${guestLimit} invited, ${guests.length - guestLimit} waitlisted
                </li>`;
        }
    });

    list.innerHTML = html;

    // Update cutoff summary
    updateCutoffSummary(guests.length);

    // Re-initialize SortableJS
    initSortable();
}

function updateCutoffSummary(total) {
    const summary = document.getElementById('cutoff-summary');
    if (guestLimit !== null && guestLimit > 0 && total > 0) {
        const invited = Math.min(guestLimit, total);
        const waitlisted = Math.max(0, total - guestLimit);
        summary.textContent = `✅ ${invited} invited · ⏳ ${waitlisted} waitlisted`;
    } else {
        summary.textContent = '';
    }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ── SortableJS Drag-and-Drop ───────────────────────────────────────

function initSortable() {
    const list = document.getElementById('results-list');
    if (sortable) sortable.destroy();

    sortable = new Sortable(list, {
        animation: 200,
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        filter: '.cutoff-divider',
        onEnd: async function() {
            const items = list.querySelectorAll('.result-item');
            const orderedIds = Array.from(items).map(item => item.dataset.guestId);

            items.forEach((item, i) => {
                const rankEl = item.querySelector('.result-rank');
                if (rankEl) rankEl.textContent = `#${i + 1}`;
            });

            try {
                await fetch('/api/results/reorder', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ordered_ids: orderedIds }),
                });
                // Reload to update confidence and cutoff visuals
                await loadResults();
            } catch (err) {
                console.error('Failed to save reorder:', err);
            }
        },
    });
}

// ── Filtering ──────────────────────────────────────────────────────

document.getElementById('filter-category').addEventListener('change', applyFilters);
document.getElementById('filter-tier').addEventListener('change', applyFilters);
document.getElementById('btn-clear-filters').addEventListener('click', () => {
    document.getElementById('filter-category').value = '';
    document.getElementById('filter-tier').value = '';
    applyFilters();
});

function applyFilters() {
    const categoryFilter = document.getElementById('filter-category').value;
    const tierFilter = document.getElementById('filter-tier').value;

    let filtered = allGuests;
    if (categoryFilter) {
        filtered = filtered.filter(g => g.category === categoryFilter);
    }
    if (tierFilter) {
        filtered = filtered.filter(g => g.tier === tierFilter);
    }

    renderResults(filtered);
}

// ── Cutoff Line ────────────────────────────────────────────────────

async function loadCutoffSetting() {
    try {
        const resp = await fetch('/api/settings');
        const settings = await resp.json();
        guestLimit = settings.guest_limit || null;
        document.getElementById('cutoff-input').value = guestLimit || '';
    } catch (e) {
        /* ignore */
    }
}

document.getElementById('cutoff-input').addEventListener('input', async function() {
    const val = this.value.trim();
    guestLimit = val ? parseInt(val) : null;

    // Save to settings
    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ guest_limit: guestLimit }),
        });
    } catch (e) {
        /* ignore */
    }

    renderResults(allGuests);
});

// ── Elo Refinement Mode ────────────────────────────────────────────

let refinePair = null;
let refineActive = false;

document.getElementById('btn-refine').addEventListener('click', async () => {
    refineActive = !refineActive;

    if (refineActive) {
        document.getElementById('btn-refine').textContent = '🔬 Stop Refinement';
        document.getElementById('refine-section').classList.remove('hidden');
        document.getElementById('btn-refine').classList.add('btn-primary');
        document.getElementById('btn-refine').classList.remove('btn-outline');
        await loadRefinementPair();
    } else {
        stopRefinement();
    }
});

document.getElementById('btn-refine-quit').addEventListener('click', stopRefinement);

async function loadRefinementPair() {
    try {
        const resp = await fetch('/api/results/refine', { method: 'POST' });
        const data = await resp.json();

        if (data.done) {
            document.getElementById('refine-status').textContent =
                '✅ All adjacent pairs confirmed! Your ranking is solid.';
            document.getElementById('refine-card-a').classList.add('hidden');
            document.getElementById('refine-card-b').classList.add('hidden');
            return;
        }

        refinePair = data;
        const a = data.guest_a;
        const b = data.guest_b;

        document.getElementById('refine-name-a').textContent = a.name;
        document.getElementById('refine-meta-a').textContent =
            `${a.category || ''} · Elo: ${Math.round(a.elo_rating)}`;
        document.getElementById('refine-card-a').dataset.guestId = a.id;
        document.getElementById('refine-card-a').classList.remove('hidden', 'selected');

        document.getElementById('refine-name-b').textContent = b.name;
        document.getElementById('refine-meta-b').textContent =
            `${b.category || ''} · Elo: ${Math.round(b.elo_rating)}`;
        document.getElementById('refine-card-b').dataset.guestId = b.id;
        document.getElementById('refine-card-b').classList.remove('hidden', 'selected');

        const status = data.already_compared ? '(re-checking)' : '(new)';
        document.getElementById('refine-status').textContent =
            `Rating gap: ${data.rating_diff} Elo ${status}`;

    } catch (err) {
        console.error('Failed to load refinement:', err);
    }
}

async function refineChoose(winnerCard) {
    if (!refinePair || !refineActive) return;

    const winnerId = winnerCard.dataset.guestId;
    const loserCard = winnerCard === document.getElementById('refine-card-a')
        ? document.getElementById('refine-card-b')
        : document.getElementById('refine-card-a');
    const loserId = loserCard.dataset.guestId;

    winnerCard.classList.add('selected', 'pulse');

    try {
        await fetch('/api/compare/choose', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ winner_id: winnerId, loser_id: loserId }),
        });
        await loadResults();
        await loadRefinementPair();
    } catch (err) {
        console.error('Failed to record refinement:', err);
    }
}

async function refineSkip() {
    if (!refineActive) return;
    await loadRefinementPair();
}

function stopRefinement() {
    refineActive = false;
    refinePair = null;
    document.getElementById('btn-refine').textContent = '🔬 Refine Rankings';
    document.getElementById('btn-refine').classList.remove('btn-primary');
    document.getElementById('btn-refine').classList.add('btn-outline');
    document.getElementById('refine-section').classList.add('hidden');
}

document.getElementById('refine-card-a').addEventListener('click', function() { refineChoose(this); });
document.getElementById('refine-card-b').addEventListener('click', function() { refineChoose(this); });
document.getElementById('btn-refine-skip').addEventListener('click', refineSkip);

document.addEventListener('keydown', (e) => {
    if (!refineActive) return;
    if (e.key === 'ArrowLeft') {
        e.preventDefault();
        refineChoose(document.getElementById('refine-card-a'));
    } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        refineChoose(document.getElementById('refine-card-b'));
    } else if (e.key === 's' || e.key === 'S') {
        e.preventDefault();
        refineSkip();
    }
});

// ── Initialize ─────────────────────────────────────────────────────

(async function init() {
    await loadCutoffSetting();
    loadResults();
})();
