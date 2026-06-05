/* ═══════════════════════════════════════════════════════════════════
   Guest Management — import, edit, delete, bulk ops, notes
   ═══════════════════════════════════════════════════════════════════ */

// ── Bulk Import ────────────────────────────────────────────────────

document.getElementById('btn-import').addEventListener('click', async () => {
    const textarea = document.getElementById('guest-input');
    const category = document.getElementById('import-category').value;
    const tier = document.getElementById('import-tier').value;
    const text = textarea.value.trim();

    if (!text) {
        alert('Please paste at least one guest name.');
        return;
    }

    const btn = document.getElementById('btn-import');
    btn.disabled = true;
    btn.textContent = 'Adding...';

    try {
        const resp = await fetch('/api/guests/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, category, tier }),
        });
        const data = await resp.json();
        textarea.value = '';
        btn.textContent = `✅ Added ${data.added} guest(s)!`;
        setTimeout(() => {
            btn.textContent = '➕ Add Guests';
            btn.disabled = false;
        }, 2000);
        location.reload();
    } catch (err) {
        alert('Error adding guests: ' + err.message);
        btn.disabled = false;
        btn.textContent = '➕ Add Guests';
    }
});

// ── Category & Tier Changes ────────────────────────────────────────

document.querySelectorAll('.category-select').forEach(select => {
    select.addEventListener('change', async (e) => {
        const guestId = e.target.dataset.guestId;
        await updateGuest(guestId, { category: e.target.value });
    });
});

document.querySelectorAll('.tier-select').forEach(select => {
    select.addEventListener('change', async (e) => {
        const guestId = e.target.dataset.guestId;
        await updateGuest(guestId, { tier: e.target.value || null });
    });
});

// ── Notes Edit ─────────────────────────────────────────────────────

document.querySelectorAll('.notes-input').forEach(input => {
    let saveTimeout;
    input.addEventListener('input', (e) => {
        clearTimeout(saveTimeout);
        const guestId = e.target.dataset.guestId;
        saveTimeout = setTimeout(() => {
            updateGuest(guestId, { notes: e.target.value });
        }, 500);
    });
});

async function updateGuest(guestId, data) {
    try {
        await fetch(`/api/guests/${guestId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
    } catch (err) {
        console.error('Update failed:', err);
    }
}

// ── Delete Guest ───────────────────────────────────────────────────

document.querySelectorAll('.delete-guest').forEach(btn => {
    btn.addEventListener('click', async (e) => {
        const guestId = e.target.dataset.guestId;
        const row = document.querySelector(`tr[data-guest-id="${guestId}"]`);
        const name = row.querySelector('.guest-name-cell').textContent;

        if (!confirm(`Delete "${name}"?`)) return;

        try {
            await fetch(`/api/guests/${guestId}`, { method: 'DELETE' });
            row.remove();
            updateGuestCount();
            updateSelection();
        } catch (err) {
            alert('Error deleting guest: ' + err.message);
        }
    });
});

// ── Reset All Rankings ─────────────────────────────────────────────

document.getElementById('btn-reset-all').addEventListener('click', async () => {
    if (!confirm('Reset ALL guest rankings? This will clear all comparisons and start fresh. This cannot be undone.')) {
        return;
    }

    try {
        await fetch('/api/guests/reset', { method: 'POST' });
        location.reload();
    } catch (err) {
        alert('Error resetting: ' + err.message);
    }
});

// ── Bulk Selection ─────────────────────────────────────────────────

const selectAllCheckbox = document.getElementById('select-all');
const bulkBar = document.getElementById('bulk-bar');
const selectedCount = document.getElementById('selected-count');

selectAllCheckbox.addEventListener('change', function() {
    document.querySelectorAll('.guest-select').forEach(cb => {
        cb.checked = this.checked;
    });
    updateSelection();
});

document.querySelectorAll('.guest-select').forEach(cb => {
    cb.addEventListener('change', updateSelection);
});

function updateSelection() {
    const checked = document.querySelectorAll('.guest-select:checked');
    const count = checked.length;
    selectedCount.textContent = `${count} selected`;

    if (count > 0) {
        bulkBar.classList.remove('hidden');
        selectAllCheckbox.indeterminate = count < document.querySelectorAll('.guest-select').length;
    } else {
        bulkBar.classList.add('hidden');
        selectAllCheckbox.indeterminate = false;
        selectAllCheckbox.checked = false;
    }
}

// Bulk tier assignment
document.querySelectorAll('.bulk-tier-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
        const tier = btn.dataset.tier;
        const checked = document.querySelectorAll('.guest-select:checked');
        const guestIds = Array.from(checked).map(cb => cb.dataset.guestId);

        if (!guestIds.length) return;
        if (!confirm(`Assign tier "${tier || 'None'}" to ${guestIds.length} guest(s)?`)) return;

        try {
            await fetch('/api/guests/bulk', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    guest_ids: guestIds,
                    updates: { tier: tier || null },
                }),
            });
            location.reload();
        } catch (err) {
            alert('Error: ' + err.message);
        }
    });
});

// ── Helpers ────────────────────────────────────────────────────────

function updateGuestCount() {
    const rows = document.querySelectorAll('#guest-table-body tr');
    document.getElementById('guest-count').textContent = rows.length;
    rows.forEach((row, i) => {
        const indexCell = row.querySelectorAll('td')[1];  // second td is the # column
        if (indexCell) indexCell.textContent = i + 1;
    });
}
