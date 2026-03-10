# Deploy FoodTracker as a Telegram Mini App (free tier)

This guide gets the app running on **free services only**: **Render** (web app + bot) and **Neon** (PostgreSQL). The leaderboard and all user data are stored in one database, so the global leaderboard works for everyone.

---

## Branch strategy (production vs experiments)

| Branch / tag | Role |
|--------------|------|
| **master** | Production. Deploy on Render from this branch. |
| **v1.0-stable** | Git tag = snapshot of the current working production version (backup before optimizations). |
| **optimize** | Experiment branch for optimizations (lazy charts, cache, lighter API). Do **not** deploy production from here until merged into master. |

- To restore production to the tagged version: `git checkout v1.0-stable` (detached) or merge that tag into master.
- To work on optimizations: `git checkout optimize`; when stable, merge into master and redeploy.

### Revert la aplicația care mergea (backup)

Dacă după modificări deploy-urile nu mai merg și vrei să revii la versiunea salvată:

1. **Ce ai salvat:** codul aplicației la momentul tag-ului `v1.0-stable` (backup complet al codului). Baza de date (Neon) și variabilele de pe Render rămân cum sunt – nu se pierd.
2. **Ca Render să deployeze din nou versiunea veche:**
   - În repo, pe calculatorul tău:
     - `git fetch origin`
     - `git checkout master`
     - `git reset --hard v1.0-stable`   (sau `origin/v1.0-stable` dacă tag-ul e push-uit)
     - `git push origin master --force`
   - Render va face automat un nou deploy de pe `master`; va rula codul de la `v1.0-stable`.
3. **Important:** Fă push la tag înainte de orice experiment, ca să existe și pe GitHub:  
   `git push origin v1.0-stable`  
   Dacă tag-ul e deja pe GitHub, poți reveni oricând la el (chiar și de pe alt calculator sau după un clone nou).

---

## Prerequisites

- A **GitHub** account and this repo pushed to GitHub (public or private; Render connects via GitHub).
- A **Telegram bot** and its token from [@BotFather](https://t.me/BotFather):
  - Send `/newbot` (or use an existing bot), get the token like `123456:ABC-DEF...`.
  - Save it as `TELEGRAM_BOT_TOKEN` for the next steps.

---

## 1. Create a free PostgreSQL database (Neon)

1. Go to [neon.tech](https://neon.tech) and sign up (free).
2. Create a new project (e.g. `foodtracker`), region closest to you.
3. In the project dashboard, open **Connection Details** and copy the **connection string** (e.g. `postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`).
4. Save it; you will use it as `DATABASE_URL` on Render.  
   The app will rewrite `postgres://` / `postgresql://` to `postgresql+asyncpg://` automatically.

---

## 2. Deploy the app on Render

1. Go to [render.com](https://render.com) and sign in with GitHub.
2. **New → Web Service**.
3. Connect the GitHub repo that contains this project (e.g. `yourusername/foodtracker`).
4. Configure:
   - **Name:** e.g. `foodtracker`
   - **Region:** choose one close to your users
   - **Branch:** `main` (or your default branch)
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn webapp.server:app --host 0.0.0.0 --port $PORT`
5. **Environment variables** (Add Environment Variable):

   | Key                 | Value |
   |---------------------|--------|
   | `TELEGRAM_BOT_TOKEN` | Your bot token from BotFather |
   | `BOT_WEBHOOK_URL`    | **Leave empty for now** (you’ll set it after first deploy) |
   | `DATABASE_URL`       | The Neon connection string from step 1 |

6. Click **Create Web Service**. Render will build and deploy.
7. When the deploy finishes, open the service URL (e.g. `https://foodtracker-xxxx.onrender.com`). You should see the API (e.g. a blank page or “FoodTracker WebApp API” if you open the root).
8. **Set the webhook URL:**
   - In Render: **Environment** → edit `BOT_WEBHOOK_URL` → set it to your **exact** service URL **without** a trailing slash, e.g. `https://foodtracker-xxxx.onrender.com`.
   - Save. Render will redeploy. After that, the bot runs in **webhook mode** and the in-chat **Menu** button will open the Mini App.

---

## 3. (Optional) Configure the bot in BotFather

- **Menu button:** The app sets it automatically when `BOT_WEBHOOK_URL` is set. Users see “Deschide aplicația” in the bot chat and can open the Mini App from there.
- To add a **Web App** link in BotFather (e.g. for “Edit Bot” → “Menu Button”): set the Web App URL to  
  `https://YOUR-RENDER-URL.onrender.com/webapp/`  
  (replace with your real Render service URL).

---

## 4. How users open the Mini App

- **From the bot:** Open the bot in Telegram → tap **Menu** (or the “Deschide aplicația” button) → the Mini App opens (phone, tablet, or desktop).
- **Direct link (e.g. for testing):**  
  `https://YOUR-RENDER-URL.onrender.com/webapp/`  
  In a normal browser you’ll need `?tid=YOUR_TELEGRAM_ID` to mimic a user; from Telegram this isn’t needed because the app reads the user from the Telegram WebApp SDK.

---

## 5. Leaderboard

- All users use the **same** Neon database. The **Leaderboard** tab in the Mini App (5th tab) shows a single global ranking (score + streak). No extra configuration.

### 5.1 Wipe database (fresh start)

**Important:** The Mini App on Telegram uses the database configured in **Render** (Environment → `DATABASE_URL`). To wipe that data, you must run the wipe **against that same URL**. If your local `.env` has a different URL (e.g. SQLite or another Neon project), you would wipe the wrong database and the Mini App will still show old data.

**Option 1 – Use the same URL as Render (recommended)**

1. In **Render**: open your FoodTracker service → **Environment** → find `DATABASE_URL` → click **Reveal** and copy the full value (starts with `postgresql://` or `postgres://`).
2. On your machine, from the project root with venv activated, run (paste your copied URL inside the quotes):
   ```bash
   DATABASE_URL="postgresql://user:pass@host/db?sslmode=require" python scripts/wipe_database.py --yes
   ```
   Replace the whole `"postgresql://..."` with your actual value from Render.
3. You should see: `Truncated all tables (PostgreSQL).` and `Done. Database is empty.`
4. Open the Mini App again in Telegram; it should ask you to register from scratch.

**Option 2 – Neon SQL Editor (same database as Render)**

1. In **Render** → Environment, note which Neon project/database `DATABASE_URL` points to (host looks like `ep-xxx-xxx.region.aws.neon.tech`).
2. In **Neon**: go to [neon.tech](https://neon.tech) → the **same** project (and branch if you use one) that Render uses.
3. Open **SQL Editor** and run:
   ```sql
   TRUNCATE TABLE water_intake, workouts, foods, daily_calories, weight_history, users RESTART IDENTITY CASCADE;
   ```
4. Open the Mini App again in Telegram; it should ask you to register from scratch.

If you use a local `.env` with a different `DATABASE_URL` (e.g. for local dev), do **not** rely on `python scripts/wipe_database.py` without setting `DATABASE_URL` in the command as in Option 1 — otherwise you will wipe the wrong database.

---

## 6. Free tier limits (summary)

| Service | Limit |
|--------|--------|
| **Render** | Free web services spin down after ~15 min of no traffic; first request after that may take 30–60 s to wake. |
| **Neon** | Free tier: 0.5 GB storage, generous compute; no credit card required. |

To reduce cold starts, you can use a free “cron” service (e.g. cron-job.org) to hit your Render URL every 10–15 minutes; keep the interval respectful to stay within fair use.

The app is optimized for free tier: **matplotlib/pandas** load only when generating charts (lazy import), and the **leaderboard** is cached in memory for 60 seconds and invalidated when users add meals, water, workouts, or change profile.

---

## 7. Troubleshooting

- **Bot doesn’t respond:**  
  - Ensure `BOT_WEBHOOK_URL` is set and has no trailing slash.  
  - Check Render **Logs** for errors (e.g. “Telegram webhook set”).

- **Mini App shows “Lipsește ID-ul utilizatorului”:**  
  - If opened from Telegram: ensure the app is opened via the bot’s Menu / “Deschide aplicația” (so the Telegram WebApp SDK is present).  
  - If opened in a normal browser: add `?tid=YOUR_TELEGRAM_ID` to the URL.

- **Database errors:**  
  - Check `DATABASE_URL` (Neon connection string).  
  - Ensure the project has `asyncpg` in `requirements.txt` (for PostgreSQL).

- **Leaderboard empty:**  
  - At least one user must have completed onboarding and have score/streak data. Use the app, add meals/water/workouts, then open the Leaderboard tab.

- **Deploy exits with status 3 / Matplotlib:** The app sets `MPLBACKEND=Agg` at startup for headless servers. If problems persist, add env var `MPLBACKEND` = `Agg` on Render.

---

## 8. Local development (unchanged)

- **Without hosting:**  
  Terminal 1: `python main.py`  
  Terminal 2: `uvicorn webapp.server:app --reload --port 8000`  
  Browser: `http://127.0.0.1:8000/webapp/?tid=YOUR_TELEGRAM_ID`

- **Do not** set `BOT_WEBHOOK_URL` locally so the bot keeps using polling via `main.py`.
