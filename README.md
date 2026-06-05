# 💍 Wedding Guest Ranker

A locally-deployed web app that ranks your wedding guests using pairwise comparisons — modeled after the [Beli](https://beliapp.com) app for restaurants. Instead of rating restaurants, you compare guests head-to-head and the app builds your perfect priority invite list.

## How It Works

Beli uses a **Binary Insertion Sort** algorithm — and so does this app. Here's the process:

1. **Add your guest list** — paste names, import a CSV, or type them in one by one
2. **Compare head-to-head** — two names appear side by side; pick who you'd rather invite
3. **Binary search** — the algorithm zeroes in on each guest's exact rank in ~log₂(N) comparisons
4. **Review & refine** — see your ranked list, drag to reorder, or run Elo refinement on close calls
5. **Export** — download your final priority list as CSV

For 150 guests, expect about 7–8 comparisons per guest — roughly 1,100 total. The app tracks your progress so you can pause and resume anytime.

## Quick Start

```bash
# Clone and run
git clone <repo-url> wedding-guest-ranker
cd wedding-guest-ranker
bash run.sh
```

Then open **http://localhost:5050** in your browser.

**Requirements**: Python 3.8+. Flask is auto-installed on first run.

### Manual setup

```bash
pip install flask
python3 app.py              # Default port 5050
python3 app.py -p 8080      # Custom port
python3 app.py --no-debug   # Production mode
```

## Features

### Core Ranking
- **Binary Insertion Sort** — the same algorithm Beli uses; ~7 comparisons per guest for a 150-person list
- **Elo rating system** — runs in parallel for refinement and confidence scoring
- **Tier priority** — rank "Must Invite" guests before "Nice to Have" guests
- **Smart matchmaking mode** — toggle between serial Beli-style ranking and Elo-optimized pair selection

### Guest Management
- **Bulk import** — paste names (one per line) or CSV with categories
- **Categories** — Family, Friends, Coworkers, Extended Family, Other (customizable)
- **Priority tiers** — Must Invite, Should Invite, Nice to Have, Only If Space
- **Guest notes** — add "+1 allowed", dietary restrictions, travel info, etc.
- **Bulk operations** — select multiple guests and assign tiers in one click

### Comparison UI
- **Side-by-side cards** — click to choose, or use ← → arrow keys
- **Swipe support** — swipe left/right on mobile devices
- **Undo** — `Ctrl+Z` or click the undo button to reverse your last choice
- **Skip** — can't decide? Skip and come back later
- **Animated transitions** — smooth card animations between comparisons
- **Progress tracking** — see exactly how many comparisons remain for each guest
- **Notes on cards** — guest notes appear during comparison for context

### Results & Analysis
- **Confidence scores** — 🟢🟡🔴 indicators show how settled each rank is
- **Invite cutoff line** — set a target count (e.g., 120) and see who makes the cut
- **Drag-and-drop reorder** — manually adjust the final ranking
- **Elo refinement mode** — re-compare adjacent pairs to fine-tune close calls
- **Filter by category or tier** — focus on subsets of your list
- **CSV export** — download the final list with all metadata

### Collaboration
- **Multiple sessions** — create separate ranking sessions (e.g., "My Rankings" vs "Partner's Rankings")
- **Shared guest list** — same guests, independent rankings per session
- **Comparison history** — browse every choice you've made, filter by guest, see biggest upsets

### Quality of Life
- **Dark mode** — toggle in the navbar, respects system preference
- **Mobile responsive** — works on phones and tablets with touch-optimized controls
- **Auto-save** — every action is persisted immediately to JSON files
- **Zero configuration** — no database, no cloud, no accounts

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3 + Flask |
| Frontend | HTML5 + CSS3 + vanilla JavaScript |
| Drag & Drop | SortableJS (CDN) |
| Storage | JSON flat files in `data/` |
| Dependencies | 1 (`flask`) |

## Project Structure

```
wedding-guest-ranker/
├── app.py                  # Flask application — 31 API endpoints
├── run.sh                  # Launch script
├── requirements.txt        # flask
├── ranking/
│   ├── engine.py           # Binary insertion sort + Elo + confidence
│   └── storage.py          # JSON persistence layer
├── static/
│   ├── css/style.css       # Full stylesheet with dark mode
│   └── js/
│       ├── compare.js       # Comparison UI + swipe + undo
│       ├── results.js       # Results + cutoff + confidence
│       ├── guests.js        # Guest CRUD + bulk ops
│       └── history.js       # Comparison history page
├── templates/
│   ├── base.html            # Layout shell with nav + dark mode toggle
│   ├── index.html           # Dashboard with stats + sessions
│   ├── guests.html          # Guest management table
│   ├── compare.html         # Pairwise comparison view
│   ├── results.html         # Ranked list + cutoff + refinement
│   └── history.html         # Comparison history log
└── data/                    # Runtime JSON storage (auto-created)
    └── .gitkeep
```

## API Reference

### Pages
| Route | Description |
|-------|-------------|
| `/` | Dashboard — stats, progress, top-5 preview, session switcher |
| `/guests` | Guest management — add, edit, bulk import, assign categories/tiers |
| `/compare` | Comparison UI — head-to-head guest ranking |
| `/results` | Ranked results — filter, reorder, refine, export |
| `/history` | Comparison history — chronological log with filters |

### Guest API
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/guests` | List all guests |
| `POST` | `/api/guests` | Add single guest |
| `PUT` | `/api/guests/<id>` | Update guest (name, category, tier, notes) |
| `DELETE` | `/api/guests/<id>` | Delete guest |
| `POST` | `/api/guests/import` | Bulk import from text/CSV |
| `POST` | `/api/guests/reset` | Reset all rankings |
| `PUT` | `/api/guests/bulk` | Bulk update multiple guests |

### Comparison API
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/compare/next` | Get next comparison pair |
| `POST` | `/api/compare/choose` | Submit choice (winner/loser IDs) |
| `POST` | `/api/compare/skip` | Skip current guest |
| `POST` | `/api/compare/undo` | Undo last comparison |

### Results API
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/results` | Get ranked list with confidence scores |
| `POST` | `/api/results/reorder` | Save manual drag-and-drop reorder |
| `POST` | `/api/results/refine` | Get next Elo refinement pair |
| `GET` | `/api/export` | Download CSV |

### History & Settings
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/comparisons` | Get comparison history (supports `?limit=&guest_id=`) |
| `GET` | `/api/history/stats` | History statistics |
| `GET` | `/api/settings` | Get all settings |
| `POST` | `/api/settings` | Update settings |
| `GET` | `/api/stats` | Dashboard statistics |
| `POST` | `/api/sessions` | Create ranking session |
| `GET` | `/api/sessions` | List all sessions |
| `POST` | `/api/sessions/<id>/switch` | Switch active session |

## Algorithm Details

### Binary Insertion Sort (Primary)
This is the same algorithm the Beli app uses. For each unranked guest:

1. Maintain a sorted list of already-ranked guests
2. Binary search to find the new guest's position:
   - Compare against the middle guest → choose better
   - Narrow to the appropriate half → repeat
   - After ~log₂(N) steps, the exact position is found
3. Insert the guest and shift subsequent positions

**Complexity**: ~log₂(N) comparisons per guest. For 150 guests: ~7–8 each.

### Elo Rating System (Secondary)
Runs in parallel for confidence scoring and refinement mode:

```
expected = 1 / (1 + 10^((opponent_rating - player_rating) / 400))
new_rating = old_rating + K × (score - expected)
```
- K-factor: 32 (adjustable in settings)
- Used for refinement mode: re-compare adjacent pairs to verify rankings
- Fed into confidence scores alongside comparison count

### Confidence Score
```
confidence = min(1.0, comparisons/10) × (0.3 + 0.7 × gap_factor)
gap_factor = 1 - 1/(1 + elo_gap_to_nearest_neighbor/50)
```

## License

MIT — use it for your wedding, your friend's wedding, or any other ranking problem.
