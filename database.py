"""
database.py
-----------
Lightweight JSON-backed persistence.

Stores two things:
  - registrations: {discord_user_id (str) -> site_player_id (str)}
  - leaderboard:   {site_player_id  (str) -> Player dict}
"""

import json
import asyncio
from pathlib import Path
from models import Player

DATA_DIR = Path(__file__).parent / "data"
REGISTRATIONS_FILE = DATA_DIR / "registrations.json"
UNLINKED_FILE      = DATA_DIR / "unlinked.json"
LEADERBOARD_FILE   = DATA_DIR / "leaderboard.json"

# In-memory cache (loaded once on startup)
_registrations: dict[str, str] = {}      # discord_id -> player_id
_unlinked: set[str] = set()              # player_ids with no Discord account
_leaderboard: dict[str, Player] = {}     # player_id  -> Player
_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

def load():
    """Load persisted data from disk into memory. Call once at bot startup."""
    DATA_DIR.mkdir(exist_ok=True)

    global _registrations, _leaderboard

    if REGISTRATIONS_FILE.exists():
        _registrations = json.loads(REGISTRATIONS_FILE.read_text())
    else:
        _registrations = {}

    if UNLINKED_FILE.exists():
        _unlinked = set(json.loads(UNLINKED_FILE.read_text()))
    else:
        _unlinked = set()

    if LEADERBOARD_FILE.exists():
        raw = json.loads(LEADERBOARD_FILE.read_text())
        _leaderboard = {pid: Player.from_dict(d) for pid, d in raw.items()}
    else:
        _leaderboard = {}


def _save_registrations():
    REGISTRATIONS_FILE.write_text(json.dumps(_registrations, indent=2))


def _save_unlinked():
    UNLINKED_FILE.write_text(json.dumps(sorted(_unlinked), indent=2))


def _save_leaderboard():
    LEADERBOARD_FILE.write_text(
        json.dumps({pid: p.to_dict() for pid, p in _leaderboard.items()}, indent=2)
    )


# ---------------------------------------------------------------------------
# Registrations
# ---------------------------------------------------------------------------

async def get_player_id(discord_id: int) -> str | None:
    """Return the site player ID linked to a Discord user, or None."""
    return _registrations.get(str(discord_id))


async def register(discord_id: int, player_id: str, owner_id: int | None = None) -> tuple[bool, str]:
    """
    Link a Discord user to a site player ID.

    Rules:
      - Non-owners can only hold one registration.
      - The same player_id cannot be claimed by two different Discord accounts.

    Returns (success: bool, message: str).
    """
    async with _lock:
        did = str(discord_id)
        is_owner = (owner_id is not None and discord_id == owner_id)

        # Check if player_id is already claimed by someone else
        for existing_did, existing_pid in _registrations.items():
            if existing_pid == player_id and existing_did != did:
                return False, f"Player ID `{player_id}` is already registered to another Discord account."

        # Non-owners: enforce one-registration limit
        if not is_owner and did in _registrations:
            return False, (
                f"You already have a registration (`{_registrations[did]}`). "
                "Remove it first with `/leaderboard remove`."
            )

        _registrations[did] = player_id
        _save_registrations()
        return True, f"Successfully registered player ID `{player_id}`."


async def unregister(discord_id: int) -> tuple[bool, str]:
    """Remove a Discord user's registration. Returns (success, message)."""
    async with _lock:
        did = str(discord_id)
        if did not in _registrations:
            return False, "You don't have any registration to remove."
        removed_pid = _registrations.pop(did)
        _save_registrations()
        return True, f"Removed registration for player ID `{removed_pid}`."


async def remove_registration_for_player(player_id: str) -> bool:
    """Owner utility: remove whoever is registered under a given player_id."""
    async with _lock:
        target_did = None
        for did, pid in _registrations.items():
            if pid == player_id:
                target_did = did
                break
        if target_did is None:
            return False
        del _registrations[target_did]
        _save_registrations()
        return True


def all_player_ids() -> list[str]:
    """Return every tracked site player ID (linked and unlinked)."""
    return list(set(_registrations.values()) | _unlinked)


def all_registrations() -> dict[str, str]:
    """Return a copy of the full discord_id -> player_id mapping."""
    return dict(_registrations)


# ---------------------------------------------------------------------------
# Unlinked players (owner-added, no Discord account attached)
# ---------------------------------------------------------------------------

async def add_unlinked(player_id: str) -> tuple[bool, str]:
    """
    Add a player ID to the leaderboard without linking it to any Discord account.
    Returns (success, message).
    """
    async with _lock:
        # Already tracked via a Discord registration?
        if player_id in _registrations.values():
            return False, f"Player ID `{player_id}` is already linked to a Discord account."
        if player_id in _unlinked:
            return False, f"Player ID `{player_id}` is already on the leaderboard."
        _unlinked.add(player_id)
        _save_unlinked()
        return True, f"Player ID `{player_id}` added to the leaderboard."


async def remove_unlinked(player_id: str) -> tuple[bool, str]:
    """
    Remove an unlinked player ID.
    Returns (success, message).
    """
    async with _lock:
        if player_id not in _unlinked:
            return False, f"Player ID `{player_id}` is not in the unlinked list."
        _unlinked.discard(player_id)
        _save_unlinked()
        return True, f"Removed unlinked player ID `{player_id}`."


def all_unlinked() -> list[str]:
    """Return a copy of the unlinked player ID set."""
    return sorted(_unlinked)


# ---------------------------------------------------------------------------
# Leaderboard cache
# ---------------------------------------------------------------------------

async def update_leaderboard(players: list[Player]):
    """Replace the in-memory leaderboard cache and persist it."""
    async with _lock:
        _leaderboard.clear()
        for p in players:
            _leaderboard[p.id] = p
        _save_leaderboard()


def get_leaderboard() -> list[Player]:
    """Return players sorted by rating descending."""
    return sorted(_leaderboard.values(), key=lambda p: p.rating, reverse=True)