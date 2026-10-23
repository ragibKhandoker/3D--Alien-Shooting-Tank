"""Starts / stops project.py (the OpenGL game) in its own terminal window.

The terminal and game window open on the machine where Flask is running,
so this works when you open the website on the same PC as the backend.
"""
import os
import subprocess
import sys
import threading
import time
import uuid

import config
from game_launcher import CRASH_MARKER

LAUNCHER = config.BASE_DIR / "game_launcher.py"
GAME_LOG = config.BASE_DIR / "game.log"  # crash details written by the launcher
STARTUP_CHECK_SECONDS = 2

DIFFICULTIES = ("easy", "medium", "hard")

# Windows: give the game its own visible terminal window
NEW_CONSOLE = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0

_lock = threading.Lock()
_process: subprocess.Popen | None = None
_session: dict | None = None


class GameCrashed(Exception):
    pass


def _crash_details() -> str | None:
    """The traceback if the launcher reported a crash, else None."""
    try:
        text = GAME_LOG.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not text.startswith(CRASH_MARKER):
        return None
    return "\n".join(text.splitlines()[-6:])


def _alive() -> bool:
    return _process is not None and _process.poll() is None


def is_running() -> bool:
    # a crashed game keeps its terminal open for reading the error, but is not "running"
    return _alive() and _crash_details() is None


def status() -> dict:
    with _lock:
        if is_running():
            return {"running": True, **_public(_session)}
        return {"running": False, "last_session": _public(_session) if _session else None}


def _public(session: dict) -> dict:
    return {k: session[k] for k in ("player_name", "user_id", "started_at", "difficulty")}


def session_owner(session_id: str) -> dict | None:
    """The user who owns this game session (the game reports scores with it)."""
    with _lock:
        if _session and session_id and _session["session_id"] == session_id:
            return {k: _session[k] for k in ("user_id", "player_name", "difficulty")}
        return None


def _kill():
    if not _alive():
        return
    _process.terminate()
    try:
        _process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _process.kill()


def start(user: dict, api_url: str, difficulty: str = "medium") -> dict:
    global _process, _session
    with _lock:
        if is_running():
            raise RuntimeError(f"Game is already running for {_session['player_name']}")
        _kill()  # close a leftover terminal from a crashed game

        game_path = config.GAME_DIR / config.GAME_FILE
        if not game_path.exists():
            raise FileNotFoundError(f"Game file not found: {game_path}")

        session_id = str(uuid.uuid4())
        env = os.environ.copy()
        env["TANK_API_URL"] = api_url
        env["TANK_PLAYER"] = user["username"]
        env["TANK_SESSION_ID"] = session_id
        env["TANK_DIFFICULTY"] = difficulty
        # the game prints emoji; never let the console encoding crash it
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        GAME_LOG.write_text("", encoding="utf-8")
        _process = subprocess.Popen(
            [sys.executable, str(LAUNCHER), str(game_path), str(GAME_LOG)],
            cwd=str(config.GAME_DIR),
            env=env,
            creationflags=NEW_CONSOLE,
        )

        # A broken game usually dies within a second; report why instead of pretending it started
        deadline = time.time() + STARTUP_CHECK_SECONDS
        while time.time() < deadline:
            details = _crash_details()
            if details or not _alive():
                _kill()
                raise GameCrashed(details or f"exit code {_process.returncode}")
            time.sleep(0.2)

        _session = {
            "session_id": session_id,
            "user_id": user["id"],
            "player_name": user["username"],
            "difficulty": difficulty,
            "started_at": time.time(),
        }
        return _public(_session)


def stop(user_id: int) -> bool:
    with _lock:
        if not is_running():
            _kill()
            return False
        if _session["user_id"] != user_id:
            raise PermissionError("Only the player who started the game can stop it")
        _kill()
        return True
