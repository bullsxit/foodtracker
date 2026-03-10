# Deploy FoodTracker as a Telegram Mini App (free tier)

This guide gets the app running on **free services only**: **Render** (web app + bot) and **Neon** (PostgreSQL). The leaderboard and all user data are stored in one database, so the global leaderboard works for everyone.

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

---

## 6. Free tier limits (summary)

| Service | Limit |
|--------|--------|
| **Render** | Free web services spin down after ~15 min of no traffic; first request after that may take 30–60 s to wake. |
| **Neon** | Free tier: 0.5 GB storage, generous compute; no credit card required. |

To reduce cold starts, you can use a free “cron” service (e.g. cron-job.org) to hit your Render URL every 10–15 minutes; keep the interval respectful to stay within fair use.

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
  - The app uses a **single DB connection** (pool_size=1) on Neon so that multiple users (second, third, etc.) don’t hit connection limits; requests wait for the connection in turn.

- **Second user / new account gets error when registering:**  
  - The app is configured to use one PostgreSQL connection at a time (Neon-friendly). If you still see errors, check Render **Logs** for the real exception; fix any DB or validation issue reported there.
  - **"value out of int32 range" / telegram_id:** Some Telegram user IDs are larger than 2^31−1. The app uses BIGINT for `telegram_id`. If the DB was created before this change, run the migration once in Neon **SQL Editor**: execute the statements in `scripts/migrate_telegram_id_bigint.sql` (ALTER each table’s `telegram_id` to BIGINT).

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
