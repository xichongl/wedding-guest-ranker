/* ═══════════════════════════════════════════════════════════════════
   Comparison UI — pairwise selection + undo + swipe + smart mode
   ═══════════════════════════════════════════════════════════════════ */

let currentPair = null;
let selecting = false;
let smartMode = false;

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

// ── Load Comparison ────────────────────────────────────────────────

async function loadNextComparison() {
    try {
        const resp = await fetch('/api/compare/next');
        const data = await resp.json();

        if (data.done) {
            showDone();
            return;
        }

        currentPair = data;
        showComparison(data);
        updateProgress(data.progress);
    } catch (err) {
        console.error('Failed to load comparison:', err);
        showEmpty();
    }
}

function showComparison(data) {
    document.getElementById('compare-active').classList.remove('hidden');
    document.getElementById('compare-done').classList.add('hidden');
    document.getElementById('compare-empty').classList.add('hidden');

    const a = data.guest_a;
    const b = data.guest_b;

    // Card A
    document.getElementById('name-a').textContent = a.name;
    document.getElementById('meta-a').textContent = guestMeta(a);
    document.getElementById('notes-a').textContent = a.notes || '';
    document.getElementById('notes-a').style.display = a.notes ? 'block' : 'none';
    document.getElementById('card-a').dataset.guestId = a.id;
    document.getElementById('card-a').classList.remove('selected', 'swiping', 'swiping-left', 'swiping-right', 'card-enter-left', 'card-enter-right', 'card-exit-left', 'card-exit-right');

    // Card B
    document.getElementById('name-b').textContent = b.name;
    document.getElementById('meta-b').textContent = guestMeta(b);
    document.getElementById('notes-b').textContent = b.notes || '';
    document.getElementById('notes-b').style.display = b.notes ? 'block' : 'none';
    document.getElementById('card-b').dataset.guestId = b.id;
    document.getElementById('card-b').classList.remove('selected', 'swiping', 'swiping-left', 'swiping-right', 'card-enter-left', 'card-enter-right', 'card-exit-left', 'card-exit-right');

    // Entrance animations
    document.getElementById('card-a').classList.add('card-enter-left');
    document.getElementById('card-b').classList.add('card-enter-right');

    // Reset swipe indicators
    document.querySelectorAll('.swipe-indicator').forEach(el => el.classList.remove('visible'));

    selecting = false;
}

function updateProgress(progress) {
    if (!progress) return;

    const pct = progress.total_guests > 0
        ? Math.round(progress.ranked_count / progress.total_guests * 100)
        : 0;

    document.getElementById('progress-fill').style.width = pct + '%';
    document.getElementById('progress-info').innerHTML =
        `<strong>${progress.ranked_count}</strong> of <strong>${progress.total_guests}</strong> guests ranked (${pct}%)`;

    const done = progress.comparisons_for_guest || 0;
    const remaining = progress.estimated_remaining;
    let estText = '';
    if (remaining !== undefined && remaining >= 0) {
        estText = ` · ${done} done, ~${remaining} more for this guest`;
    }
    document.getElementById('current-guest-info').textContent =
        `Placing: ${progress.current_guest_name}${estText}`;
}

function showDone() {
    document.getElementById('compare-active').classList.add('hidden');
    document.getElementById('mode-toggle').classList.add('hidden');
    document.getElementById('compare-done').classList.remove('hidden');
    document.getElementById('compare-empty').classList.add('hidden');
    document.getElementById('progress-fill').style.width = '100%';
    document.getElementById('progress-info').innerHTML = '<strong>All guests ranked!</strong> 🎉';
    document.getElementById('current-guest-info').textContent = '';
}

function showEmpty() {
    document.getElementById('compare-active').classList.add('hidden');
    document.getElementById('mode-toggle').classList.add('hidden');
    document.getElementById('compare-done').classList.add('hidden');
    document.getElementById('compare-empty').classList.remove('hidden');
}

function guestMeta(guest) {
    const parts = [];
    if (guest.category) parts.push(guest.category);
    if (guest.tier) parts.push(TIER_LABELS[guest.tier] || guest.tier);
    if (guest.elo_rating) parts.push(`Elo: ${Math.round(guest.elo_rating)}`);
    return parts.join(' · ');
}

// ── Make a Choice ──────────────────────────────────────────────────

async function choose(winnerCard) {
    if (selecting || !currentPair) return;
    selecting = true;

    const winnerId = winnerCard.dataset.guestId;
    const loserCard = winnerCard === document.getElementById('card-a')
        ? document.getElementById('card-b')
        : document.getElementById('card-a');
    const loserId = loserCard.dataset.guestId;

    // Exit animation for the losing card
    if (loserCard === document.getElementById('card-a')) {
        loserCard.classList.add('card-exit-left');
        winnerCard.classList.add('card-exit-right');
    } else {
        loserCard.classList.add('card-exit-right');
        winnerCard.classList.add('card-exit-left');
    }
    winnerCard.classList.add('selected', 'pulse');

    try {
        const resp = await fetch('/api/compare/choose', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ winner_id: winnerId, loser_id: loserId }),
        });
        const data = await resp.json();

        if (data.done) {
            showDone();
            return;
        }

        currentPair = data;
        setTimeout(() => {
            showComparison(data);
            updateProgress(data.progress);
        }, 300);
    } catch (err) {
        console.error('Failed to record choice:', err);
        selecting = false;
        winnerCard.classList.remove('selected', 'pulse', 'card-exit-left', 'card-exit-right');
        loserCard.classList.remove('card-exit-left', 'card-exit-right');
    }
}

// ── Undo ───────────────────────────────────────────────────────────

async function undoLast() {
    if (selecting) return;
    selecting = true;

    try {
        const resp = await fetch('/api/compare/undo', { method: 'POST' });
        const data = await resp.json();

        if (data.ok) {
            showUndoToast();
            if (data.done) {
                showDone();
                selecting = false;
                return;
            }
            currentPair = data;
            showComparison(data);
            updateProgress(data.progress);
        }
    } catch (err) {
        console.error('Failed to undo:', err);
    }
    selecting = false;
}

function showUndoToast() {
    // Remove any existing toast
    const existing = document.querySelector('.undo-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'undo-toast';
    toast.innerHTML = '↩ Last comparison undone!';
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2000);
}

// ── Skip ───────────────────────────────────────────────────────────

async function skipCurrent() {
    if (selecting || !currentPair) return;
    selecting = true;

    const guestId = currentPair.guest_a.id;

    try {
        await fetch('/api/compare/skip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ guest_id: guestId }),
        });
        await loadNextComparison();
    } catch (err) {
        console.error('Failed to skip:', err);
        selecting = false;
    }
}

// ── Smart Mode Toggle ──────────────────────────────────────────────

async function toggleSmartMode(enabled) {
    smartMode = enabled;
    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ compare_mode: enabled ? 'smart' : 'serial' }),
        });
        // Reload comparison with new mode
        await loadNextComparison();
    } catch (err) {
        console.error('Failed to toggle mode:', err);
    }
}

// ── Touch / Swipe Support ─────────────────────────────────────────

function initSwipe(cardElement) {
    let startX = 0;
    let startY = 0;
    let currentX = 0;
    let swiping = false;
    let swipeThreshold = 80;

    cardElement.addEventListener('touchstart', (e) => {
        if (selecting) return;
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
        swiping = true;
        currentX = 0;
    }, { passive: true });

    cardElement.addEventListener('touchmove', (e) => {
        if (!swiping || selecting) return;
        currentX = e.touches[0].clientX - startX;
        const currentY = e.touches[0].clientY - startY;

        // Only horizontal swipes
        if (Math.abs(currentX) > Math.abs(currentY) && Math.abs(currentX) > 10) {
            e.preventDefault();
            cardElement.style.transform = `translateX(${currentX}px)`;
            cardElement.classList.add('swiping');

            // Show swipe indicator
            const indicator = currentX < 0
                ? cardElement.querySelector('.swipe-indicator-left')
                : cardElement.querySelector('.swipe-indicator-right');
            if (indicator && Math.abs(currentX) > 40) {
                indicator.classList.add('visible');
            }
        }
    });

    cardElement.addEventListener('touchend', (e) => {
        if (!swiping || selecting) { swiping = false; return; }
        swiping = false;
        cardElement.classList.remove('swiping');
        cardElement.style.transform = '';

        // Hide indicators
        cardElement.querySelectorAll('.swipe-indicator').forEach(el => el.classList.remove('visible'));

        if (currentX > swipeThreshold) {
            // Swiped right — choose this card
            cardElement.classList.add('swiping-right');
            setTimeout(() => choose(cardElement), 150);
        } else if (currentX < -swipeThreshold) {
            // Swiped left — choose other card
            cardElement.classList.add('swiping-left');
            const other = cardElement === document.getElementById('card-a')
                ? document.getElementById('card-b')
                : document.getElementById('card-a');
            setTimeout(() => choose(other), 150);
        }
    });
}

// ── Event Listeners ────────────────────────────────────────────────

document.getElementById('card-a').addEventListener('click', function() { choose(this); });
document.getElementById('card-b').addEventListener('click', function() { choose(this); });
document.getElementById('btn-skip').addEventListener('click', skipCurrent);
document.getElementById('btn-undo').addEventListener('click', undoLast);

// Smart mode toggle
document.getElementById('smart-mode-checkbox').addEventListener('change', function() {
    toggleSmartMode(this.checked);
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (selecting) return;

    // Don't intercept when typing in inputs
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

    if (e.key === 'ArrowLeft') {
        e.preventDefault();
        choose(document.getElementById('card-a'));
    } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        choose(document.getElementById('card-b'));
    } else if (e.key === 's' || e.key === 'S') {
        e.preventDefault();
        skipCurrent();
    } else if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        e.preventDefault();
        undoLast();
    }
});

// ── Initialize Swipe ───────────────────────────────────────────────

initSwipe(document.getElementById('card-a'));
initSwipe(document.getElementById('card-b'));

// ── Initialize ─────────────────────────────────────────────────────

// Load saved mode preference
(async function init() {
    try {
        const resp = await fetch('/api/settings');
        const settings = await resp.json();
        if (settings.compare_mode === 'smart') {
            document.getElementById('smart-mode-checkbox').checked = true;
            smartMode = true;
        }
    } catch (e) { /* ignore */ }
    loadNextComparison();
})();
