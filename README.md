# 🚗 Tank Survival 3D (OpenGL Game)

## 📖 Overview
**Tank Survival 3D** is an OpenGL-based 3D game where the player controls a tank driving through a procedurally generated cityscape.  
Your goal is to **survive, destroy enemies, collect power-ups, and score as high as possible** while navigating the environment.  

## 👥 Teammates
- [Safin Ahmed Tonmoy](https://github.com/safinahmedtonmoy7860/Car-Game)
- [Shams Rubaiat Shammo](https://github.com/shamso-github)
- [Khandoker Md. Ragib Ahsan](https://github.com/ragibKhandoker)



# 🛡️ Tank Survival 3D

A 3D tank shooter made with **Python + OpenGL**, played from a website with **accounts, difficulty levels and a global leaderboard**.

Drive your tank through a city, blast alien waves, collect blue power-ups and survive as long as you can. Every finished game is saved to your account.

![Gameplay](frontend/assets/gameplay.jpg)

---

## 📑 Contents
- [Features](#-features)
- [How it works](#-how-it-works)
- [Requirements](#-requirements)
- [Setup (first time)](#-setup-first-time)
- [Running the project](#️-running-the-project-every-time)
- [How to play](#-how-to-play)
- [Configuration](#️-configuration-backendenv)
- [npm commands](#-npm-commands)
- [Project structure](#-project-structure)
- [Troubleshooting](#-troubleshooting)
- [API reference](#-api-reference)
- [Team](#-team)

---

## ✨ Features

**Game**
- 🌆 3D city with buildings, trees, roads and day / evening lighting
- 🚀 Drive, steer, brake, boost and **jump over aliens**
- 💥 Every **F** press (or left click) fires a shell instantly; shells hit reliably even at high speed
- 👾 Alien waves with **Easy / Medium / Hard** difficulty
- 🔵 Blue power-up balls (+10 points)
- 🎯 On-screen HUD: score, lives, speed, boost bar, shell status and keyboard buttons that light up when pressed
- ⏸️ Pause / resume (**P** or **Esc**)
- 🔊 Sound: cannon, tank engine (follows your speed), explosions, crash, power-up and game over (**M** to mute)

**Website**
- 🔐 Register / log in (passwords are hashed, login uses signed tokens)
- 🎚️ Choose difficulty, then start the game with one click
- 📊 Your stats: best score, games played, average and global rank
- 🏆 Leaderboard with gold / silver / bronze podium, filter by difficulty
- 🕓 "My recent games" history
- 📱 Works on desktop and mobile screens

**Tech stack:** Python 3 · PyOpenGL / freeglut · pygame (audio) · Flask · AngularJS 1.8 · PostgreSQL on [Neon](https://neon.tech)

---

## 🧠 How it works

```
 Browser (AngularJS, port 4200)
        │  /api/...
        ▼
 Flask backend (port 5000) ──────────► Neon PostgreSQL (users, scores)
        │  "Start game"
        ▼
 Game window (project.py) opens on the same PC
        │  game over → sends the score
        └──────────────► Flask → saved to your account
```

> ⚠️ **The game is a desktop program.** It opens in a window on the computer where the backend runs.
> So the website is meant to be used **on the same PC** (`http://127.0.0.1:4200`). Hosting it online
> (Vercel, Render, …) would open the game on the server, not for the visitor.

---

## 📋 Requirements

| What | Version | Download |
|---|---|---|
| **Windows** | 10 or 11 | – (the npm scripts and bundled freeglut DLLs are for Windows) |
| **Python** | 3.10 or newer | https://www.python.org/downloads/ — tick **"Add Python to PATH"** during install |
| **Node.js** | 18 or newer (LTS) | https://nodejs.org |
| **Git** | any | https://git-scm.com |
| **Neon account** | free | https://neon.tech |

Check that they are installed (open **PowerShell**):
```powershell
python --version
node --version
npm --version
git --version
```

---

## 🔧 Setup (first time)

Do these steps once.

### 1. Download the project
```powershell
git clone https://github.com/ragibKhandoker/3D--Alien-Shooting-Tank.git
cd 3D--Alien-Shooting-Tank
```

### 2. Create the database on Neon
1. Sign up at https://neon.tech and click **New Project** (any name, any region).
2. On the project **Dashboard**, click **Connect**.
3. Copy the **connection string**. It looks like:
   ```
   postgresql://neondb_owner:xxxxxxxx@ep-xxxx-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
   Keep it secret — it contains your database password.

You don't need to create any tables. The backend creates them automatically the first time it starts.

### 3. Set up the backend (Python)
```powershell
cd backend
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt
```
This creates a private Python environment in `backend\venv` and installs Flask, psycopg, PyOpenGL and pygame.

### 4. Create `backend\.env`
```powershell
Copy-Item .env.example .env
venv\Scripts\python -c "import secrets; print(secrets.token_hex(32))"
```
Open `backend\.env` in any editor and fill in:
```ini
DATABASE_URL=postgresql://...your Neon connection string...?sslmode=require
SECRET_KEY=paste-the-long-random-text-printed-above
```
Leave the other lines as they are. `.env` is in `.gitignore`, so it is never uploaded to GitHub.

### 5. Set up the frontend (Node.js)
```powershell
cd ..\frontend
npm install
```

That's it — setup is done. ✅

---

## ▶️ Running the project (every time)

```powershell
cd 3D--Alien-Shooting-Tank\frontend
npm start
```

This one command starts **both** servers:
- **Flask backend** → http://127.0.0.1:5000
- **Website** → http://127.0.0.1:4200

The browser opens by itself as soon as the backend is ready. In the terminal you should see:
```
[backend] ✅ Database schema applied (users, scores).
[backend] ✅ Neon PostgreSQL Database Connected!
[backend]  🚀 Tank Survival API is running!
[frontend] Frontend running at http://127.0.0.1:4200
[frontend] Backend is ready. Opening http://127.0.0.1:4200
```

- `npm run dev` and `npm run server` do exactly the same as `npm start`.
- It also works from the project root folder (`3D--Alien-Shooting-Tank`).
- Running it again while it is already running is harmless — it says *"already running; reusing it"*.
- **Stop** both servers with **Ctrl + C** in that terminal.
- You do **not** need to activate the venv; the scripts use `backend\venv` automatically.

### Then play
1. Open http://127.0.0.1:4200 (if it didn't open by itself).
2. Click **Register**, create an account (username, email, password).
3. Choose **Easy**, **Medium** or **Hard**.
4. Click **START GAME**. A terminal window and the **Tank Raider** game window open.
   If you don't see them, check the taskbar — Windows sometimes opens them behind the browser.
5. Play! When you lose all 5 lives the score is saved and appears on the website.

### Play without the website (optional)
```powershell
cd "First Program"
..\backend\venv\Scripts\python project.py
```
Runs the game on Medium. Scores are not saved in this mode.

---

## 🎮 How to play

Shoot aliens for points, jump over the ones you can't stop, and grab the blue balls. Bumping into an alien costs a life — lose all 5 and it's game over.

### Controls
| Key | Action |
|---|---|
| **W** | Accelerate |
| **S** | Reverse |
| **A / D** | Steer left / right |
| **Space** | Brake |
| **F** or **Left click** | Fire a shell (one per press) |
| **J** | Jump (clears aliens) |
| **1** | Boost |
| **G / H** | First-person / third-person view |
| **← → ↑ ↓** | Rotate the camera |
| **C** | Day / evening, auto / manual |
| **P** or **Esc** | Pause / resume |
| **R** | Restart |
| **M** | Sound on / off |

### Scoring
| Event | Points |
|---|---|
| Alien destroyed | **+15** |
| Blue power-up collected | **+10** |
| Crashing into an alien | −1 life |

### Difficulty
| Level | New aliens every | Aliens per wave | Max on screen | Alien speed |
|---|---|---|---|---|
| 🟢 **Easy** | 5 s | 1 | 6 | 80 % |
| 🟡 **Medium** | 3 s | 1 | 15 | 100 % |
| 🔴 **Hard** | 1.5 s | 2 | 30 | 125 % |

Want different numbers? Edit `DIFFICULTY_SETTINGS` near the top of `First Program/project.py`.

---

## ⚙️ Configuration (`backend/.env`)

| Variable | Required | Default | What it does |
|---|---|---|---|
| `DATABASE_URL` | ✅ | – | Neon / PostgreSQL connection string |
| `SECRET_KEY` | ✅ | random on each start | Signs login tokens. If empty, everyone is logged out on every restart |
| `FLASK_PORT` | | `5000` | Backend port |
| `FLASK_HOST` | | `127.0.0.1` | `127.0.0.1` = this PC only |
| `FLASK_DEBUG` | | `0` | `1` shows detailed error pages while developing. Keep `0` otherwise |
| `GAME_DIR` | | `../First Program` | Folder that contains the game |
| `GAME_FILE` | | `project.py` | Game file to launch |

---

## 📦 npm commands

Run these inside `frontend` (or the project root):

| Command | What it does |
|---|---|
| `npm install` | Install frontend packages (first time only; from the root use `npm run setup`) |
| `npm start` | Start backend **and** website, open the browser |
| `npm run dev` / `npm run server` | Same as `npm start` |
| `npm run backend` | Only the Flask backend |
| `npm run frontend` | Only the website (expects the backend on port 5000) |

---

## 📁 Project structure

```
3D--Alien-Shooting-Tank/
├── First Program/
│   ├── project.py            the game (OpenGL)
│   ├── game_sound.py         sound effects (pygame)
│   ├── sounds/               WAV files + generate_sounds.py that creates them
│   └── OpenGL/               bundled PyOpenGL with the freeglut DLLs for Windows
├── backend/
│   ├── app.py                Flask routes + startup checks
│   ├── auth.py               password hashing, login tokens
│   ├── database.py           PostgreSQL queries
│   ├── game_runner.py        starts / stops the game process
│   ├── game_launcher.py      runs the game inside its own terminal window
│   ├── config.py             reads backend/.env
│   ├── requirements.txt
│   └── .env.example          template for backend/.env
├── frontend/
│   ├── index.html            page shell + navigation
│   ├── views/                play.html, login.html, register.html
│   ├── js/app.js             AngularJS app (routes, API calls, controllers)
│   ├── css/style.css
│   ├── scripts/serve.js      dev server (/api → Flask, opens the browser)
│   └── package.json          npm scripts
├── database/
│   └── schema.sql            tables (applied automatically)
└── package.json              lets npm commands work from the root too
```

---

## 🩺 Troubleshooting

**`npm error enoent Could not read package.json`**
You ran npm in the wrong folder (for example `backend\venv\Scripts`). Go to the `frontend` folder (or the project root) and run `npm start` again.

**`Missing script: "..."`**
Use one of the commands in [npm commands](#-npm-commands).

**"Backend is offline" on the website**
The Flask backend isn't running. Run `npm start` in `frontend` and look at the `[backend]` lines for an error. The page reconnects by itself.

**`❌ DATABASE_URL is missing` or `❌ Neon PostgreSQL Connection Failed`**
Check `backend\.env`: the connection string must be complete, on one line, without quotes, and end with `?sslmode=require`. Restart with `npm start`.

**`An older version of this backend is still running on port 5000`**
Close the other terminal that runs the project (Ctrl + C), then start again.

**`Port 5000 is occupied by another program`**
Another app uses port 5000. Close it, or set `FLASK_PORT=5001` in `backend\.env`.

**`'python' is not recognized`**
Reinstall Python and tick **"Add Python to PATH"**, then open a new PowerShell window.

**`venv\Scripts\activate` says "running scripts is disabled"**
You don't need to activate the venv — use `venv\Scripts\python ...` as shown above. (Or allow it once with `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.)

**I clicked Start game but nothing appeared**
Look at the taskbar for **Tank Raider** — the window may be behind the browser. If the website shows *"The game closed right after starting"*, the reason is in `backend\game.log`.

**No sound**
Make sure the speakers aren't muted and you didn't press **M**. If the game terminal prints `Sound disabled: ...`, reinstall the backend packages:
`backend\venv\Scripts\python -m pip install -r backend\requirements.txt`

**Logged out after every restart**
Set `SECRET_KEY` in `backend\.env` (see setup step 4).

**Change the sound effects**
Edit `First Program/sounds/generate_sounds.py`, then run `python generate_sounds.py` in that folder.

---

## 🔌 API reference

| Method | Path | Login needed | Body / query |
|---|---|---|---|
| POST | `/api/auth/register` | – | `{ username, email, password }` |
| POST | `/api/auth/login` | – | `{ username (or email), password }` |
| GET | `/api/auth/me` | ✔ | – |
| POST | `/api/game/start` | ✔ | `{ difficulty: "easy" \| "medium" \| "hard" }` |
| POST | `/api/game/stop` | ✔ | – |
| GET | `/api/game/status` | – | – |
| POST | `/api/scores` | game session | sent by the game: `{ session_id, score, duration_seconds }` |
| GET | `/api/scores/top` | – | `?limit=10&difficulty=hard` |
| GET | `/api/scores/me` | ✔ | – |
| GET | `/api/scores/me/stats` | ✔ | – |
| GET | `/api/health` | – | – |

"Login needed" means the request carries `Authorization: Bearer <token>` from `/api/auth/login`.

---


```bash
pip install PyOpenGL PyOpenGL_accelerate
