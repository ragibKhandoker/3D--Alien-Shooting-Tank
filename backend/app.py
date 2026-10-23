import json
import re
import socket
import sys
import urllib.request

from flask import Flask, g, jsonify, request, send_from_directory
from flask_cors import CORS

import auth
import config
import database
import game_runner

app = Flask(__name__, static_folder=str(config.FRONTEND_DIR), static_url_path="")
CORS(app)

SERVICE_NAME = "tank-survival-api"
USERNAME_RE =re.compile(r"^[A-Za-z0-9_]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def error(message, code):
    return jsonify({"error": message}), code


# ---------- Frontend ----------
@app.route("/")
def index():
    return send_from_directory(config.FRONTEND_DIR, "index.html")


# ---------- Health ----------
@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": SERVICE_NAME,
        "database_configured": bool(config.DATABASE_URL),
        "game_file": str(config.GAME_DIR / config.GAME_FILE),
    })


# ---------- Auth ----------
@app.post("/api/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not USERNAME_RE.match(username):
        return error("Username must be 3-32 characters: letters, numbers or _", 400)
    if not EMAIL_RE.match(email):
        return error("Please enter a valid email", 400)
    if len(password) < 6:
        return error("Password must be at least 6 characters", 400)

    try:
        taken = database.user_exists(username, email)
        if taken:
            return error(f"This {taken} is already registered", 409)
        user = database.create_user(username, email, auth.hash_password(password))
    except Exception as e:
        return error(f"Could not register: {e}", 503)

    return jsonify({"token": auth.create_token(user["id"]), "user": user}), 201


@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    login_id = str(data.get("username", "")).strip()
    if "@" in login_id:
        login_id = login_id.lower()
    password = str(data.get("password", ""))
    if not login_id or not password:
        return error("Username/email and password are required", 400)

    try:
        user = database.find_user_for_login(login_id)
    except Exception as e:
        return error(f"Could not log in: {e}", 503)
    if not user or not auth.verify_password(user["password_hash"], password):
        return error("Wrong username/email or password", 401)

    user.pop("password_hash")
    return jsonify({"token": auth.create_token(user["id"]), "user": user})


@app.get("/api/auth/me")
@auth.login_required
def me():
    return jsonify(g.user)


# ---------- Game control ----------
@app.post("/api/game/start")
@auth.login_required
def game_start():
    # game posts its score straight to Flask (not through the frontend dev server)
    api_url = f"http://127.0.0.1:{config.FLASK_PORT}"
    data = request.get_json(silent=True) or {}
    difficulty = str(data.get("difficulty", "medium")).lower()
    if difficulty not in game_runner.DIFFICULTIES:
        return error("difficulty must be easy, medium or hard", 400)
    try:
        session = game_runner.start(g.user, api_url, difficulty)
    except RuntimeError as e:
        return error(str(e), 409)
    except FileNotFoundError as e:
        return error(str(e), 500)
    except game_runner.GameCrashed as e:
        print(f"❌ Game crashed on start:\n{e}")
        return error(f"The game closed right after starting. See backend/game.log.\n{e}", 500)
    return jsonify(session), 201


@app.get("/api/game/status")
def game_status():
    return jsonify(game_runner.status())


@app.post("/api/game/stop")
@auth.login_required
def game_stop():
    try:
        return jsonify({"stopped": game_runner.stop(g.user["id"])})
    except PermissionError as e:
        return error(str(e), 403)


# ---------- Scores ----------
@app.post("/api/scores")
def add_score():
    """Called by project.py on game over. The session id proves which user is playing."""
    data = request.get_json(silent=True) or {}
    owner = game_runner.session_owner(str(data.get("session_id", "")))
    if not owner:
        return error("Unknown game session", 403)
    try:
        score = int(data.get("score"))
        duration = int(data.get("duration_seconds", 0))
    except (TypeError, ValueError):
        return error("score and duration_seconds must be numbers", 400)

    try:
        saved = database.save_score(owner["user_id"], owner["player_name"], score, duration,
                                    data["session_id"], owner["difficulty"])
    except Exception as e:
        return error(f"Could not save score: {e}", 503)
    return jsonify(saved), 201


@app.get("/api/scores/top")
def leaderboard():
    limit = min(request.args.get("limit", 10, type=int), 100)
    difficulty = request.args.get("difficulty") or None
    if difficulty and difficulty not in game_runner.DIFFICULTIES:
        return error("difficulty must be easy, medium or hard", 400)
    try:
        return jsonify(database.top_scores(limit, difficulty))
    except Exception as e:
        return error(f"Could not load scores: {e}", 503)


@app.get("/api/scores/me")
@auth.login_required
def my_scores():
    try:
        return jsonify(database.user_scores(g.user["id"]))
    except Exception as e:
        return error(f"Could not load scores: {e}", 503)


@app.get("/api/scores/me/stats")
@auth.login_required
def my_stats():
    try:
        return jsonify(database.user_stats(g.user["id"]))
    except Exception as e:
        return error(f"Could not load stats: {e}", 503)


# ---------- Startup ----------
def log_database_status():
    if not config.DATABASE_URL:
        print("❌ DATABASE_URL is missing in backend/.env — register/login and scores will not work.")
        return
    try:
        database.init_schema()
        print("✅ Database schema applied (users, scores).")
    except Exception as e:
        print(f"❌ Could not apply database schema (check DATABASE_URL): {e}")
        return
    try:
        db = database.check_connection()
        print("✅ Neon PostgreSQL Database Connected!")
        print(f"   ➜  Host:     {db['host']}")
        print(f"   ➜  Database: {db['database']} (user {db['user']}, PostgreSQL {db['version']})")
        print(f"   ➜  Rows:     {db['users']} users, {db['scores']} scores")
    except Exception as e:
        print(f"❌ Neon PostgreSQL Connection Failed: {e}")


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def handle_port_in_use(port: int):
    """If the port is taken, check whether it is already this API so a second start is harmless."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as res:
            health = json.load(res)
        if health.get("service") == SERVICE_NAME:
            print(f"Tank Survival API is already running at http://localhost:{port}/api; reusing it.")
            sys.exit(0)
        if "game_file" in health:
            print(f"An older version of this backend is still running on port {port}. "
                  "Stop it (Ctrl + C in its terminal) and start again.")
            sys.exit(1)
    except (OSError, ValueError):
        pass  # not JSON / not reachable, so not our API
    print(f"Port {port} is occupied by another program. Stop it or set a different FLASK_PORT in backend/.env.")
    sys.exit(1)


def print_banner(port: int):
    print("\n======================================================")
    print(" 🚀 Tank Survival API is running!")
    print(f" ➜  API URL:     http://localhost:{port}/api")
    print(f" ➜  API Status:  http://localhost:{port}/api/health")
    print(" ➜  Frontend:    http://localhost:4200  (npm start)")
    print(f" ➜  Database:    {'Neon PostgreSQL' if config.DATABASE_URL else 'not configured'}")
    print(f" ➜  Game:        {config.GAME_DIR / config.GAME_FILE}")
    print("======================================================\n", flush=True)


if __name__ == "__main__":
    # Windows consoles may not be UTF-8; keep the emoji from crashing the log
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    port = config.FLASK_PORT
    if port_in_use(port):
        handle_port_in_use(port)
    log_database_status()
    print_banner(port)
    app.run(host="127.0.0.1", port=port, debug=True, use_reloader=False)
