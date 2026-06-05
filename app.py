"""Wedding Guest Ranker — Flask Application."""
import os
import uuid
from functools import wraps
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request, session, redirect, url_for

from ranking.storage import (
    load_guests,
    load_comparisons,
    load_settings,
    save_guests,
    save_comparisons,
    save_settings,
)
from ranking.engine import (
    get_next_comparison,
    process_choice,
    get_ranked_list,
    get_stats,
    start_refinement,
    get_binary_search_state,
    undo_last_comparison,
    get_ranked_with_confidence,
    get_comparison_history,
    get_history_stats,
)

# ── Authentication ──────────────────────────────────────────────────

CREDENTIALS = {
    "allium": "070899",
}


def login_required(f):
    """Decorator that requires login for page routes and API routes."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            # For API routes, return 401 JSON
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login_page", next=request.path))
        return f(*args, **kwargs)

    return decorated


def create_app():
    app = Flask(__name__)
    app.secret_key = os.urandom(24)

    # Ensure data directory exists
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(data_dir, exist_ok=True)
    app.config["DATA_DIR"] = data_dir

    # Wire up the storage module's data directory
    import ranking.storage as storage_module
    storage_module.DATA_DIR = data_dir

    # ── Login route (unprotected) ───────────────────────────────────

    @app.route("/login", methods=["GET", "POST"])
    def login_page():
        """Login page — the only unprotected route."""
        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if username in CREDENTIALS and CREDENTIALS[username] == password:
                session["logged_in"] = True
                session["username"] = username
                next_url = request.args.get("next", "/")
                return redirect(next_url)
            error = "Invalid username or password."
        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        """Log out and clear session."""
        session.clear()
        return redirect(url_for("login_page"))

    # ── Page routes ──────────────────────────────────────────────────

    @app.route("/")
    @login_required
    def index():
        """Dashboard home page."""
        stats = get_stats()
        ranked = get_ranked_list()
        top5 = ranked[:5]
        return render_template("index.html", stats=stats, top5=top5)

    @app.route("/guests")
    @login_required
    def guests_page():
        """Guest management page."""
        guests = load_guests()
        settings = load_settings()
        return render_template(
            "guests.html", guests=guests, settings=settings
        )

    @app.route("/compare")
    @login_required
    def compare_page():
        """Pairwise comparison page."""
        return render_template("compare.html")

    @app.route("/results")
    @login_required
    def results_page():
        """Ranked results page."""
        settings = load_settings()
        return render_template("results.html", settings=settings)

    # ── Guest API ────────────────────────────────────────────────────

    @app.route("/api/guests", methods=["GET"])
    @login_required
    def api_get_guests():
        guests = load_guests()
        return jsonify(guests)

    @app.route("/api/guests", methods=["POST"])
    @login_required
    def api_add_guest():
        data = request.get_json()
        guests = load_guests()
        new_guest = {
            "id": str(uuid.uuid4())[:8],
            "name": data["name"].strip(),
            "category": data.get("category", ""),
            "tier": data.get("tier") or None,
            "notes": data.get("notes", ""),
            "position": None,
            "elo_rating": 1500.0,
            "comparisons_done": 0,
            "status": "unranked",
        }
        guests.append(new_guest)
        save_guests(guests)
        return jsonify(new_guest), 201

    @app.route("/api/guests/<guest_id>", methods=["PUT"])
    @login_required
    def api_update_guest(guest_id):
        data = request.get_json()
        guests = load_guests()
        for g in guests:
            if g["id"] == guest_id:
                if "name" in data:
                    g["name"] = data["name"].strip()
                if "category" in data:
                    g["category"] = data["category"]
                if "tier" in data:
                    g["tier"] = data.get("tier") or None
                if "notes" in data:
                    g["notes"] = data.get("notes", "")
                save_guests(guests)
                return jsonify(g)
        return jsonify({"error": "Guest not found"}), 404

    @app.route("/api/guests/<guest_id>", methods=["DELETE"])
    @login_required
    def api_delete_guest(guest_id):
        guests = load_guests()
        guests = [g for g in guests if g["id"] != guest_id]
        # Also clean up comparisons referencing this guest
        comparisons = load_comparisons()
        comparisons = [
            c
            for c in comparisons
            if c["guest_a_id"] != guest_id and c["guest_b_id"] != guest_id
        ]
        save_guests(guests)
        save_comparisons(comparisons)
        return jsonify({"ok": True})

    @app.route("/api/guests/import", methods=["POST"])
    @login_required
    def api_import_guests():
        """Bulk import guests from text (one name per line) or CSV."""
        data = request.get_json()
        text = data.get("text", "")
        category = data.get("category", "")
        tier = data.get("tier") or None

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        guests = load_guests()
        added = []

        for line in lines:
            # Support simple CSV: "Name,Category" or just "Name"
            if "," in line:
                parts = [p.strip() for p in line.split(",", 1)]
                name = parts[0]
                cat = parts[1] if parts[1] else category
            else:
                name = line
                cat = category

            new_guest = {
                "id": str(uuid.uuid4())[:8],
                "name": name,
                "category": cat,
                "tier": tier,
                "notes": "",
                "position": None,
                "elo_rating": 1500.0,
                "comparisons_done": 0,
                "status": "unranked",
            }
            guests.append(new_guest)
            added.append(new_guest)

        save_guests(guests)
        return jsonify({"added": len(added), "guests": added}), 201

    @app.route("/api/guests/reset", methods=["POST"])
    @login_required
    def api_reset_guests():
        """Reset all guests to unranked state."""
        guests = load_guests()
        for g in guests:
            g["position"] = None
            g["elo_rating"] = 1500.0
            g["comparisons_done"] = 0
            g["status"] = "unranked"
        save_guests(guests)
        save_comparisons([])
        return jsonify({"ok": True})

    @app.route("/api/guests/bulk", methods=["PUT"])
    @login_required
    def api_bulk_update_guests():
        """Bulk update multiple guests (assign tier/category/notes)."""
        data = request.get_json()
        guest_ids = data.get("guest_ids", [])
        updates = data.get("updates", {})
        guests = load_guests()
        updated = 0
        for g in guests:
            if g["id"] in guest_ids:
                if "category" in updates:
                    g["category"] = updates["category"]
                if "tier" in updates:
                    g["tier"] = updates.get("tier") or None
                if "notes" in updates:
                    g["notes"] = updates.get("notes", "")
                updated += 1
        save_guests(guests)
        return jsonify({"ok": True, "updated": updated})

    # ── Comparison API ───────────────────────────────────────────────

    @app.route("/api/compare/next", methods=["GET"])
    @login_required
    def api_next_comparison():
        result = get_next_comparison()
        if result is None:
            return jsonify({"done": True})
        return jsonify({"done": False, **result})

    @app.route("/api/compare/choose", methods=["POST"])
    @login_required
    def api_choose():
        data = request.get_json()
        winner_id = data["winner_id"]
        loser_id = data["loser_id"]
        result = process_choice(winner_id, loser_id)
        return jsonify(result)

    @app.route("/api/compare/skip", methods=["POST"])
    @login_required
    def api_skip():
        data = request.get_json()
        guest_id = data.get("guest_id")
        # Move the guest to end of ranked list and mark as ranked
        guests = load_guests()
        ranked = get_ranked_list()
        for g in guests:
            if g["id"] == guest_id:
                g["status"] = "ranked"
                g["position"] = len(ranked)
                break
        save_guests(guests)
        return jsonify({"ok": True})

    @app.route("/api/compare/undo", methods=["POST"])
    @login_required
    def api_undo():
        """Undo the last comparison."""
        result = undo_last_comparison()
        return jsonify(result)

    @app.route("/api/compare/state", methods=["GET"])
    @login_required
    def api_compare_state():
        """Get current binary search state for debugging."""
        state = get_binary_search_state()
        return jsonify(state)

    # ── Results API ──────────────────────────────────────────────────

    @app.route("/api/results", methods=["GET"])
    @login_required
    def api_results():
        ranked = get_ranked_with_confidence()
        return jsonify(ranked)

    @app.route("/api/results/reorder", methods=["POST"])
    @login_required
    def api_reorder():
        """Save manual drag-and-drop reorder."""
        data = request.get_json()
        ordered_ids = data.get("ordered_ids", [])
        guests = load_guests()

        # Update positions based on new order
        for i, gid in enumerate(ordered_ids):
            for g in guests:
                if g["id"] == gid:
                    g["position"] = i
                    g["status"] = "ranked"
                    break

        save_guests(guests)
        return jsonify({"ok": True})

    @app.route("/api/results/refine", methods=["POST"])
    @login_required
    def api_refine():
        """Start or continue Elo refinement mode."""
        result = start_refinement()
        if result is None:
            return jsonify({"done": True})
        return jsonify({"done": False, **result})

    @app.route("/api/export", methods=["GET"])
    @login_required
    def api_export():
        """Export ranked list as CSV."""
        ranked = get_ranked_list()
        lines = ["Rank,Name,Category,Tier,Elo Rating,Comparisons"]
        for i, g in enumerate(ranked):
            lines.append(
                f'{i + 1},"{g["name"]}",{g["category"] or ""},{g["tier"] or ""},'
                f'{g["elo_rating"]:.0f},{g["comparisons_done"]}'
            )
        csv_text = "\n".join(lines)
        from flask import Response

        return Response(
            csv_text,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=wedding_guests.csv"},
        )

    # ── Settings API ─────────────────────────────────────────────────

    @app.route("/api/stats", methods=["GET"])
    @login_required
    def api_stats():
        stats = get_stats()
        return jsonify(stats)

    @app.route("/api/settings", methods=["GET"])
    @login_required
    def api_get_settings():
        settings = load_settings()
        return jsonify(settings)

    @app.route("/api/settings", methods=["POST"])
    @login_required
    def api_update_settings():
        data = request.get_json()
        settings = load_settings()
        for key in ("guest_limit", "compare_mode", "elo_k_factor"):
            if key in data:
                settings[key] = data[key]
        save_settings(settings)
        return jsonify(settings)

    @app.route("/api/settings/categories", methods=["POST"])
    @login_required
    def api_update_categories():
        data = request.get_json()
        settings = load_settings()
        settings["categories"] = data.get("categories", settings["categories"])
        save_settings(settings)
        return jsonify(settings["categories"])

    # ── Comparison History API ──────────────────────────────────────

    @app.route("/api/comparisons", methods=["GET"])
    @login_required
    def api_comparisons():
        limit = request.args.get("limit", 100, type=int)
        guest_id = request.args.get("guest_id", None, type=str)
        history = get_comparison_history(limit=limit, guest_id=guest_id)
        return jsonify(history)

    @app.route("/api/history/stats", methods=["GET"])
    @login_required
    def api_history_stats():
        stats = get_history_stats()
        return jsonify(stats)

    # ── History page ────────────────────────────────────────────────

    @app.route("/history")
    @login_required
    def history_page():
        return render_template("history.html")

    # ── Sessions API ────────────────────────────────────────────────

    @app.route("/api/sessions", methods=["GET"])
    @login_required
    def api_get_sessions():
        settings = load_settings()
        return jsonify(settings.get("sessions", []))

    @app.route("/api/sessions", methods=["POST"])
    @login_required
    def api_create_session():
        data = request.get_json()
        settings = load_settings()
        new_session = {
            "id": str(uuid.uuid4())[:8],
            "name": data.get("name", "New Session"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        settings.setdefault("sessions", []).append(new_session)
        save_settings(settings)
        return jsonify(new_session), 201

    @app.route("/api/sessions/<session_id>/switch", methods=["POST"])
    @login_required
    def api_switch_session(session_id):
        settings = load_settings()
        # Save current session state
        current_id = settings.get("active_session", "default")
        _save_session_data(current_id)

        # Switch
        settings["active_session"] = session_id
        save_settings(settings)

        # Load new session data
        _load_session_data(session_id)
        return jsonify({"ok": True, "active_session": session_id})

    return app


def _session_file(session_id, filename):
    """Get the session-specific filename."""
    if session_id == "default":
        return filename
    return f"session_{session_id}_{filename}"


def _save_session_data(session_id):
    """Save current guests and comparisons to session-specific files."""
    import ranking.storage as st
    import json, os

    guests = st.load_guests()
    comparisons = st.load_comparisons()

    guest_path = os.path.join(st.DATA_DIR, _session_file(session_id, "guests.json"))
    comp_path = os.path.join(st.DATA_DIR, _session_file(session_id, "comparisons.json"))

    with open(guest_path, "w") as f:
        json.dump(guests, f, indent=2, default=str)
    with open(comp_path, "w") as f:
        json.dump(comparisons, f, indent=2, default=str)


def _load_session_data(session_id):
    """Load session-specific guests and comparisons into main files."""
    import ranking.storage as st
    import json, os, shutil

    guest_path = os.path.join(st.DATA_DIR, _session_file(session_id, "guests.json"))
    comp_path = os.path.join(st.DATA_DIR, _session_file(session_id, "comparisons.json"))

    # If session file exists, copy to main files
    if os.path.exists(guest_path):
        shutil.copy(guest_path, os.path.join(st.DATA_DIR, "guests.json"))
    else:
        st.save_guests([])

    if os.path.exists(comp_path):
        shutil.copy(comp_path, os.path.join(st.DATA_DIR, "comparisons.json"))
    else:
        st.save_comparisons([])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Wedding Guest Ranker")
    parser.add_argument("-p", "--port", type=int, default=5050, help="Port to listen on")
    parser.add_argument("--no-debug", action="store_true", help="Disable debug mode")
    args = parser.parse_args()

    app = create_app()
    app.run(debug=not args.no_debug, port=args.port)
