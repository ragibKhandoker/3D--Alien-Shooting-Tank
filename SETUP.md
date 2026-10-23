# Website setup (Flask + AngularJS + Neon PostgreSQL)

```
backend/            Flask API
  app.py            routes (auth, game control, scores)
  auth.py           password hashing + login tokens
  database.py       PostgreSQL queries (users, scores)
  game_runner.py    launches First Program/project.py as a process
  config.py         reads backend/.env
frontend/           AngularJS app (served by Flask)
  index.html        shell + nav bar
  views/            login.html, register.html, play.html
  js/app.js         routes, AuthService, API calls, controllers
database/
  schema.sql        tables (created automatically when the backend starts)
First Program/
  project.py        the actual game (reports its score on game over)
```

## User flow
1. **Register** (username, email, password) or **Log in** → Flask returns a token.
2. The frontend stores the token and sends it as `Authorization: Bearer <token>` on every request.
3. The **Play** page is only reachable when logged in → **Start game**.
4. Flask starts `project.py` → the game window opens on the PC running Flask.
5. On game over the game sends its score with a secret session id → Flask saves it to that user.
6. Leaderboard + "My recent games" refresh automatically.

## How to run

### Step 1 — Neon database (one time)
1. Sign up at https://neon.tech and create a project.
2. Project **Dashboard → Connect** → copy the connection string. It looks like
   `postgresql://user:password@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require`

### Step 2 — Backend config (one time)
Open `backend/.env` and paste it:
```
DATABASE_URL=postgresql://user:password@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require
```
`SECRET_KEY` is already generated. If `.env` is missing, copy `.env.example` to `.env`.
Tables are created automatically the first time the backend starts.

### Step 3 — Install dependencies (one time)
```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Step 4 — Install frontend packages (one time)
```powershell
cd frontend
npm install
```

### Step 5 — Run (every time)
```powershell
cd frontend
npm start
```
`npm start`, `npm run dev` and `npm run server` all do the same thing, from the `frontend` folder
or the project root folder. They do **not** work from other folders (for example `backend\venv\Scripts`) —
npm looks for `package.json` in the current folder. You don't need to activate the venv.

This starts **both** servers:
- Flask backend → http://127.0.0.1:5000
- AngularJS frontend → **http://127.0.0.1:4200** (`/api` calls are proxied to Flask)

The browser opens by itself once the backend is ready. Stop with **Ctrl + C**.
Running it again while it is already running is harmless ("already running; reusing it").

Only one of them (optional): `npm run backend` or `npm run frontend`.

### Step 6 — Play
http://127.0.0.1:4200 → Register → Start game.

## API
| Method | Path | Auth | Body |
|---|---|---|---|
| POST | /api/auth/register | – | `{ username, email, password }` |
| POST | /api/auth/login | – | `{ username (or email), password }` |
| GET  | /api/auth/me | ✔ | – |
| POST | /api/game/start | ✔ | – |
| POST | /api/game/stop | ✔ | – |
| GET  | /api/game/status | – | – |
| POST | /api/scores | game session id | `{ session_id, score, duration_seconds }` |
| GET  | /api/scores/top | – | `?limit=10` |
| GET  | /api/scores/me | ✔ | – |
| GET  | /api/health | – | – |

## Troubleshooting
- **"Database is not configured"** → fill `DATABASE_URL` in `backend/.env`, restart.
- **"WARNING: database not ready"** on startup → check the connection string (password, `?sslmode=require`).
- **"relation users does not exist"** → run `database/schema.sql` in Neon's SQL Editor.
- **Game window doesn't open** → test the game alone: `cd "First Program"` then `python project.py`.
- **Logged out after restart** → make sure `SECRET_KEY` in `.env` is set (not empty).
