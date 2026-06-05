"""JSON-file storage layer for wedding guest data."""
import json
import os


DATA_DIR = None  # Set by app.py at startup


def _path(filename):
    return os.path.join(DATA_DIR, filename)


def _read(filename, default):
    path = _path(filename)
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)


def _write(filename, data):
    path = _path(filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ── Guests ────────────────────────────────────────────────────────────

def load_guests():
    return _read("guests.json", [])


def save_guests(guests):
    _write("guests.json", guests)


# ── Comparisons ───────────────────────────────────────────────────────

def load_comparisons():
    return _read("comparisons.json", [])


def save_comparisons(comparisons):
    _write("comparisons.json", comparisons)


# ── Settings ──────────────────────────────────────────────────────────

DEFAULT_SETTINGS = {
    "categories": [
        {"id": "family", "name": "Family", "color": "#4A90D9"},
        {"id": "friends", "name": "Friends", "color": "#7ED321"},
        {"id": "coworkers", "name": "Coworkers", "color": "#F5A623"},
        {"id": "extended_family", "name": "Extended Family", "color": "#D0021B"},
        {"id": "other", "name": "Other", "color": "#9B9B9B"},
    ],
    "tiers": [
        {"id": "must_invite", "label": "Must Invite", "color": "#27AE60"},
        {"id": "should_invite", "label": "Should Invite", "color": "#2980B9"},
        {"id": "nice_to_have", "label": "Nice to Have", "color": "#F39C12"},
        {"id": "only_if_space", "label": "Only If Space", "color": "#E74C3C"},
    ],
    "elo_k_factor": 32,
    "guest_limit": None,  # Target guest count for cutoff line
    "compare_mode": "serial",  # "serial" (Beli-style) or "smart" (Elo-matchmade)
    "sessions": [{"id": "default", "name": "My Rankings", "created_at": None}],
    "active_session": "default",
}


def load_settings():
    settings = _read("settings.json", None)
    if settings is None:
        settings = dict(DEFAULT_SETTINGS)  # copy defaults
        save_settings(settings)
    # Merge any missing defaults
    for key, value in DEFAULT_SETTINGS.items():
        if key not in settings:
            settings[key] = value
    return settings


def save_settings(settings):
    _write("settings.json", settings)
