"""Ranking engine — binary insertion sort (Beli-style) + Elo refinement."""
import random
import uuid
from datetime import datetime, timezone
from typing import Optional

from ranking.storage import (
    load_guests,
    save_guests,
    load_comparisons,
    save_comparisons,
    load_settings,
)

# ═══════════════════════════════════════════════════════════════════════
# Binary Insertion Sort (the Beli method)
# ═══════════════════════════════════════════════════════════════════════


def get_next_comparison():
    """
    Determine the next pair of guests to compare.
    Uses binary insertion sort: pick the next unranked guest and compare
    them against the midpoint of the currently-ranked list.

    Returns:
        dict with guest_a, guest_b, progress info — or None if all ranked.
    """
    guests = load_guests()
    comparisons = load_comparisons()

    ranked = [g for g in guests if g["status"] == "ranked"]
    unranked = [g for g in guests if g["status"] == "unranked"]
    in_progress = [g for g in guests if g["status"] == "in_progress"]

    if not unranked and not in_progress:
        return None  # All done

    # Sort ranked by position
    ranked.sort(key=lambda g: g["position"] if g["position"] is not None else 99999)

    # Pick the guest currently being placed (or start a new one)
    current_guest = None
    if in_progress:
        current_guest = in_progress[0]
    elif unranked:
        # Pick based on tier priority, then random within tier
        tier_order = {"must_invite": 0, "should_invite": 1, "nice_to_have": 2, "only_if_space": 3, None: 4}
        unranked.sort(key=lambda g: (tier_order.get(g.get("tier"), 4), random.random()))
        current_guest = unranked[0]
        # Mark as in_progress
        for g in guests:
            if g["id"] == current_guest["id"]:
                g["status"] = "in_progress"
                break
        save_guests(guests)

    if not current_guest:
        return None

    # Build the ranked list (excluding current guest)
    ranked_ids = {g["id"] for g in ranked}

    # Determine binary search bounds for this guest
    return _get_comparison_for_guest(current_guest, ranked, guests, comparisons)


def _get_comparison_for_guest(current_guest, ranked, all_guests, comparisons):
    """Find the next comparison for the guest being placed via binary search."""
    gid = current_guest["id"]

    # Find comparisons involving this guest + a ranked guest (from this session)
    relevant = [
        c for c in comparisons
        if c["phase"] in ("binary_insertion", None)
        and ((c["guest_a_id"] == gid) or (c["guest_b_id"] == gid))
    ]

    # Determine current binary search bounds
    # After each win: new guest is BETTER than the opponent (higher rank)
    # After each loss: new guest is WORSE than the opponent (lower rank)
    # ranked[0] = best (position 0), ranked[-1] = worst

    if len(ranked) == 0:
        # No ranked guests yet — just place it at position 0
        for g in all_guests:
            if g["id"] == gid:
                g["status"] = "ranked"
                g["position"] = 0
                break
        save_guests(all_guests)
        # Try next guest
        return get_next_comparison()

    # Binary search state:
    # left = lowest position new guest could occupy (best rank)
    # right = highest position new guest could occupy (worst rank)
    # Start: left=0, right=len(ranked)
    # When new guest beats ranked[k]: new guest is better → right = k - 1
    # When new guest loses to ranked[k]: new guest is worse → left = k + 1

    left = 0
    right = len(ranked)  # position could be at the very end

    for c in relevant:
        winner_id = c["winner_id"]
        opponent_id = c["guest_b_id"] if c["guest_a_id"] == gid else c["guest_a_id"]

        # Find opponent's position
        opp_pos = None
        for r in ranked:
            if r["id"] == opponent_id:
                opp_pos = r["position"]
                break

        if opp_pos is None:
            continue

        if winner_id == gid:
            # New guest beat opponent → new guest is better (lower position number)
            right = min(right, opp_pos - 1)
        else:
            # New guest lost to opponent → new guest is worse (higher position number)
            left = max(left, opp_pos + 1)

    # If bounds have converged
    if left > right:
        insert_pos = left
        _place_guest(current_guest, all_guests, ranked, insert_pos)
        return get_next_comparison()

    # Pick midpoint for comparison
    # Map ranked positions to actual indices in the ranked list
    mid_pos = (left + right) // 2

    # Find the ranked guest at position mid_pos
    opponent = None
    for r in ranked:
        if r["position"] == mid_pos:
            opponent = r
            break

    if opponent is None:
        # mid_pos might be len(ranked), meaning append at end
        # Compare against the last ranked guest
        opponent = ranked[-1]

    # Don't re-compare the same pair
    already_compared = any(
        c["guest_a_id"] in (gid, opponent["id"])
        and c["guest_b_id"] in (gid, opponent["id"])
        for c in comparisons
    )
    if already_compared:
        # We shouldn't hit this if the binary search is correct, but just in case
        # Try to narrow further by comparing against position near the middle
        for offset in [1, -1, 2, -2]:
            alt_pos = mid_pos + offset
            if 0 <= alt_pos < len(ranked):
                alt_opponent = None
                for r in ranked:
                    if r["position"] == alt_pos:
                        alt_opponent = r
                        break
                if alt_opponent:
                    already2 = any(
                        c["guest_a_id"] in (gid, alt_opponent["id"])
                        and c["guest_b_id"] in (gid, alt_opponent["id"])
                        for c in comparisons
                    )
                    if not already2:
                        opponent = alt_opponent
                        mid_pos = alt_pos
                        break

    # Calculate how many comparisons done for this guest so far
    comparisons_for_guest = len(relevant)
    # Estimate remaining comparisons: log2 of remaining positions + 1
    remaining_positions = max(0, right - left + 1)
    import math
    est_remaining = math.ceil(math.log2(remaining_positions + 1)) if remaining_positions > 0 else 0

    progress = {
        "total_guests": len(all_guests),
        "ranked_count": len([g for g in all_guests if g["status"] == "ranked"]),
        "current_guest_name": current_guest["name"],
        "comparisons_for_guest": comparisons_for_guest,
        "estimated_remaining": est_remaining,
    }

    return {
        "guest_a": current_guest,
        "guest_b": opponent,
        "progress": progress,
    }


def _place_guest(guest, all_guests, ranked, position):
    """Insert guest at the given position, shifting others down."""
    gid = guest["id"]

    # Shift ranked guests at or after this position down by 1
    for g in all_guests:
        if g["position"] is not None and g["position"] >= position:
            g["position"] += 1

    # Place the guest
    for g in all_guests:
        if g["id"] == gid:
            g["position"] = position
            g["status"] = "ranked"
            break

    save_guests(all_guests)


def process_choice(winner_id, loser_id):
    """
    Process a comparison choice.
    Records the comparison and continues the binary search.
    """
    guests = load_guests()
    comparisons = load_comparisons()

    # Record the comparison
    comparison = {
        "id": str(uuid.uuid4())[:8],
        "guest_a_id": winner_id,
        "guest_b_id": loser_id,
        "winner_id": winner_id,
        "phase": "binary_insertion",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    comparisons.append(comparison)
    save_comparisons(comparisons)

    # Update comparison counts
    for g in guests:
        if g["id"] in (winner_id, loser_id):
            g["comparisons_done"] = g.get("comparisons_done", 0) + 1

    # Elo update
    _update_elo(winner_id, loser_id, guests)

    save_guests(guests)

    # Check if we can get the next comparison
    next_comp = get_next_comparison()
    if next_comp is None:
        return {"done": True, "message": "All guests ranked!"}
    return {"done": False, **next_comp}


def _update_elo(winner_id, loser_id, guests):
    """Update Elo ratings for both guests."""
    settings = load_settings()
    K = settings.get("elo_k_factor", 32)

    winner = next((g for g in guests if g["id"] == winner_id), None)
    loser = next((g for g in guests if g["id"] == loser_id), None)
    if not winner or not loser:
        return

    R_w = winner["elo_rating"]
    R_l = loser["elo_rating"]

    expected_w = 1.0 / (1.0 + 10.0 ** ((R_l - R_w) / 400.0))
    expected_l = 1.0 - expected_w

    winner["elo_rating"] = round(R_w + K * (1.0 - expected_w), 1)
    loser["elo_rating"] = round(R_l + K * (0.0 - expected_l), 1)


# ═══════════════════════════════════════════════════════════════════════
# Results & Stats
# ═══════════════════════════════════════════════════════════════════════


def get_ranked_list():
    """Return all ranked guests sorted by position."""
    guests = load_guests()
    ranked = [g for g in guests if g["status"] == "ranked" and g["position"] is not None]
    ranked.sort(key=lambda g: g["position"])
    return ranked


def get_stats():
    """Return dashboard statistics."""
    guests = load_guests()
    comparisons = load_comparisons()
    total = len(guests)
    ranked = len([g for g in guests if g["status"] == "ranked"])
    unranked = total - ranked
    in_progress = len([g for g in guests if g["status"] == "in_progress"])
    return {
        "total_guests": total,
        "ranked_count": ranked,
        "unranked_count": unranked,
        "in_progress_count": in_progress,
        "comparison_count": len(comparisons),
        "percent_complete": round(ranked / total * 100) if total > 0 else 0,
    }


# ═══════════════════════════════════════════════════════════════════════
# Elo Refinement Mode
# ═══════════════════════════════════════════════════════════════════════


def start_refinement():
    """
    Return the next pair of adjacent-ranked guests for Elo refinement.
    Users can verify close rankings by re-comparing adjacent pairs.
    """
    ranked = get_ranked_list()
    comparisons = load_comparisons()

    if len(ranked) < 2:
        return None

    # Pick the closest-rated adjacent pair that hasn't been refined recently
    candidates = []
    for i in range(len(ranked) - 1):
        a, b = ranked[i], ranked[i + 1]
        rating_diff = abs(a["elo_rating"] - b["elo_rating"])
        # Check if this pair was already compared in refinement
        already = any(
            c["phase"] == "refinement"
            and {c["guest_a_id"], c["guest_b_id"]} == {a["id"], b["id"]}
            for c in comparisons
        )
        candidates.append({
            "a": a,
            "b": b,
            "diff": rating_diff,
            "already": already,
        })

    # Prioritize pairs with small rating differences that haven't been refined
    candidates.sort(key=lambda c: (c["already"], c["diff"]))

    if not candidates:
        return None

    pick = candidates[0]
    return {
        "guest_a": pick["a"],
        "guest_b": pick["b"],
        "rating_diff": round(pick["diff"], 1),
        "already_compared": pick["already"],
    }


def get_binary_search_state():
    """Return current binary search state for debugging / progress display."""
    guests = load_guests()
    comparisons = load_comparisons()
    ranked = [g for g in guests if g["status"] == "ranked"]
    in_progress = [g for g in guests if g["status"] == "in_progress"]

    result = {
        "total": len(guests),
        "ranked": len(ranked),
        "unranked": len([g for g in guests if g["status"] == "unranked"]),
        "in_progress": len(in_progress),
        "comparisons": len(comparisons),
    }

    if in_progress:
        guest = in_progress[0]
        ranked.sort(key=lambda g: g["position"] if g["position"] is not None else 99999)
        result["current_guest"] = guest["name"]

        # Calculate current bounds
        gid = guest["id"]
        relevant = [
            c for c in comparisons
            if c["phase"] in ("binary_insertion", None)
            and ((c["guest_a_id"] == gid) or (c["guest_b_id"] == gid))
        ]
        left = 0
        right = len(ranked)
        for c in relevant:
            winner_id = c["winner_id"]
            opponent_id = c["guest_b_id"] if c["guest_a_id"] == gid else c["guest_a_id"]
            opp_pos = None
            for r in ranked:
                if r["id"] == opponent_id:
                    opp_pos = r["position"]
                    break
            if opp_pos is not None:
                if winner_id == gid:
                    right = min(right, opp_pos - 1)
                else:
                    left = max(left, opp_pos + 1)
        result["bounds"] = {"left": left, "right": right}

    return result


# ═══════════════════════════════════════════════════════════════════════
# Undo
# ═══════════════════════════════════════════════════════════════════════


def undo_last_comparison():
    """Remove the last comparison and rebuild all state from scratch."""
    comparisons = load_comparisons()
    if not comparisons:
        return {"ok": False, "message": "Nothing to undo"}

    removed = comparisons.pop()
    save_comparisons(comparisons)

    # Rebuild all state from remaining comparisons
    _rebuild_all_state(comparisons)

    # Get next comparison to return
    next_comp = get_next_comparison()
    if next_comp is None:
        return {"ok": True, "done": True, "message": "All guests ranked!"}
    return {"ok": True, "done": False, **next_comp}


def _rebuild_all_state(comparisons):
    """Rebuild guest positions and Elo ratings by replaying all comparisons."""
    guests = load_guests()

    # Reset all guests
    for g in guests:
        g["position"] = None
        g["elo_rating"] = 1500.0
        g["comparisons_done"] = 0
        g["status"] = "unranked"

    # Replay comparisons to rebuild Elo ratings
    for c in comparisons:
        winner_id = c["winner_id"]
        loser_id = (
            c["guest_b_id"] if c["guest_a_id"] == winner_id else c["guest_a_id"]
        )
        for g in guests:
            if g["id"] in (winner_id, loser_id):
                g["comparisons_done"] = g.get("comparisons_done", 0) + 1
        _update_elo(winner_id, loser_id, guests)

    # Rebuild positions from binary insertion sort comparisons
    # Process guests in the order they were first compared
    processed_order = []
    seen = set()
    for c in comparisons:
        if c["phase"] in ("binary_insertion", None):
            gid = c["guest_a_id"]
            if gid not in seen:
                seen.add(gid)
                processed_order.append(gid)

    ranked = []
    for gid in processed_order:
        guest = next((g for g in guests if g["id"] == gid), None)
        if not guest:
            continue

        # Determine position based on this guest's comparisons
        relevant = [
            c for c in comparisons
            if c["phase"] in ("binary_insertion", None)
            and ((c["guest_a_id"] == gid) or (c["guest_b_id"] == gid))
        ]

        left = 0
        right = len(ranked)
        for c in relevant:
            winner_id = c["winner_id"]
            opponent_id = (
                c["guest_b_id"] if c["guest_a_id"] == gid else c["guest_a_id"]
            )
            opp_pos = None
            for i, r in enumerate(ranked):
                if r["id"] == opponent_id:
                    opp_pos = i
                    break
            if opp_pos is not None:
                if winner_id == gid:
                    right = min(right, opp_pos - 1)
                else:
                    left = max(left, opp_pos + 1)

        insert_pos = max(left, 0) if left > right else left

        # Insert at position
        for g in guests:
            if g["position"] is not None and g["position"] >= insert_pos:
                g["position"] += 1
        guest["position"] = insert_pos
        guest["status"] = "ranked"

        # Insert into ranked tracking list
        ranked.insert(insert_pos, guest)
        # Re-index ranked positions
        for i, r in enumerate(ranked):
            r["position"] = i

    # If there are guests that were never compared but are ranked, place them at end
    remaining = [g for g in guests if g["status"] != "ranked"]
    for g in remaining:
        pos = len(ranked)
        g["position"] = pos
        g["status"] = "ranked"
        ranked.append(g)

    save_guests(guests)


# ═══════════════════════════════════════════════════════════════════════
# Confidence Scores
# ═══════════════════════════════════════════════════════════════════════


def get_ranked_with_confidence():
    """Return ranked list with confidence score for each guest."""
    ranked = get_ranked_list()
    for i, guest in enumerate(ranked):
        guest["confidence"] = _compute_confidence(guest, ranked, i)
    return ranked


def _compute_confidence(guest, ranked, index):
    """Compute 0-1 confidence score for a guest's position."""
    comparisons = guest.get("comparisons_done", 0)
    compare_factor = min(1.0, comparisons / 10.0)

    # Elo gap to neighbors
    elo = guest["elo_rating"]
    min_gap = float("inf")
    if index > 0:
        min_gap = min(min_gap, abs(elo - ranked[index - 1]["elo_rating"]))
    if index < len(ranked) - 1:
        min_gap = min(min_gap, abs(elo - ranked[index + 1]["elo_rating"]))
    if min_gap == float("inf"):
        min_gap = 400

    gap_factor = 1.0 - 1.0 / (1.0 + min_gap / 50.0)

    confidence = compare_factor * (0.3 + 0.7 * gap_factor)
    return round(min(1.0, max(0.0, confidence)), 2)


# ═══════════════════════════════════════════════════════════════════════
# Comparison History
# ═══════════════════════════════════════════════════════════════════════


def get_comparison_history(limit=50, guest_id=None):
    """Return comparison history with guest names resolved."""
    comparisons = load_comparisons()
    guests = {g["id"]: g for g in load_guests()}

    result = []
    for c in reversed(comparisons):
        if guest_id and c["guest_a_id"] != guest_id and c["guest_b_id"] != guest_id:
            continue
        winner_id = c["winner_id"]
        loser_id = (
            c["guest_b_id"] if c["guest_a_id"] == winner_id else c["guest_a_id"]
        )
        result.append({
            "id": c["id"],
            "winner_name": guests.get(winner_id, {}).get("name", "Unknown"),
            "loser_name": guests.get(loser_id, {}).get("name", "Unknown"),
            "winner_id": winner_id,
            "loser_id": loser_id,
            "phase": c.get("phase", "binary_insertion"),
            "created_at": c.get("created_at", ""),
        })
        if len(result) >= limit:
            break

    return result


def get_history_stats():
    """Return statistics about comparison history."""
    comparisons = load_comparisons()
    guests = load_guests()
    guest_map = {g["id"]: g for g in guests}

    if not comparisons:
        return {"total": 0, "biggest_upset": None, "most_compared": None}

    biggest_upset = None
    biggest_diff = 0
    compare_counts = {}

    for c in comparisons:
        winner = guest_map.get(c["winner_id"])
        loser_id = (
            c["guest_b_id"] if c["guest_a_id"] == c["winner_id"] else c["guest_a_id"]
        )
        loser = guest_map.get(loser_id)

        for gid in (c["guest_a_id"], c["guest_b_id"]):
            compare_counts[gid] = compare_counts.get(gid, 0) + 1

        if winner and loser:
            elo_diff = loser.get("elo_rating", 1500) - winner.get("elo_rating", 1500)
            if elo_diff > biggest_diff:
                biggest_diff = elo_diff
                biggest_upset = {
                    "winner_name": winner["name"],
                    "loser_name": loser["name"],
                    "elo_diff": round(elo_diff, 1),
                }

    most_compared_id = max(compare_counts, key=compare_counts.get, default=None)
    most_compared = None
    if most_compared_id and most_compared_id in guest_map:
        most_compared = {
            "name": guest_map[most_compared_id]["name"],
            "count": compare_counts[most_compared_id],
        }

    return {
        "total": len(comparisons),
        "biggest_upset": biggest_upset,
        "most_compared": most_compared,
    }
