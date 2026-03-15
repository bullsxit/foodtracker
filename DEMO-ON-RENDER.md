# Put the demo live on Render – step-by-step (no errors)

Follow these steps in order. All terminal commands are in **Section 4** in one block for copy-paste.

---

## 1. Get a Telegram bot token (if you don’t have one)

1. Open Telegram and message [@BotFather](https://t.me/BotFather).
2. Send: `/newbot`
3. Follow the prompts (name, username). Copy the token BotFather gives you (e.g. `123456789:ABCdefGHI...`). You’ll use it as `TELEGRAM_BOT_TOKEN` on Render.

---

## 2. Get a PostgreSQL connection string (Neon, free)

1. Go to [neon.tech](https://neon.tech) and sign up (free).
2. **Create a project** (e.g. name: `foodtracker`), pick a region.
3. In the project: **Connection Details** → copy the **connection string** (looks like `postgresql://user:password@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`).
4. Keep it somewhere safe; you’ll paste it as `DATABASE_URL` on Render.

---

## 3. Push your code to GitHub (if not already)

- Your project must be in a GitHub repo (public or private).
- If it’s not pushed yet: create a repo on GitHub, then in your project folder run the commands in **Section 4** (the first block) to add, commit, and push.

---

## 4. Terminal commands (copy and paste all at once)

Run these in a terminal. They: go to your project, stage all changes, commit, and push to the current branch (works for `main` or `master`).

```bash
cd /Users/dsorocovici/Desktop/foodtracker && git add -A && git status && git commit -m "Enable DEMO_MODE on Render so anyone can open the app without Telegram" && git push origin HEAD
```

- If you get “nothing to commit”, your changes are already committed; run only:  
  `cd /Users/dsorocovici/Desktop/foodtracker && git push origin HEAD`
- If `git push` asks for login, use your GitHub Personal Access Token or SSH as you normally do.
- After a successful push, go to **Section 5**.

---

## 5. Create the Web Service on Render

1. Go to [dashboard.render.com](https://dashboard.render.com) and sign in with GitHub.
2. Click **New +** → **Web Service**.
3. Connect the GitHub account if asked, then select the repo that contains this project (e.g. `yourusername/foodtracker`).
4. Use these settings exactly:

   | Field | Value |
   |--------|--------|
   | **Name** | `foodtracker` (or any name you like) |
   | **Region** | Choose one (e.g. Frankfurt, Ohio) |
   | **Branch** | `main` (or `master` if that’s your default) |
   | **Runtime** | `Python 3` |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `uvicorn webapp.server:app --host 0.0.0.0 --port $PORT` |

5. Click **Advanced** and add **Environment Variables** one by one (Add Environment Variable):

   | Key | Value |
   |-----|--------|
   | `TELEGRAM_BOT_TOKEN` | The token from BotFather (Section 1) |
   | `BOT_WEBHOOK_URL` | Leave **empty** for now |
   | `DATABASE_URL` | The Neon connection string from Section 2 |
   | `DEMO_MODE` | `1` |
   | `FOOD_AI_PROVIDER` | `mock` |

   (If you use the repo’s `render.yaml`, `DEMO_MODE` and `FOOD_AI_PROVIDER` may already be set; if so, just confirm `DEMO_MODE` is `1`.)

6. Click **Create Web Service**. Wait for the first deploy to finish (Build + Deploy).

---

## 6. Set the webhook URL (so the bot menu works too)

1. In Render, open your **foodtracker** service.
2. Go to **Environment**.
3. Find `BOT_WEBHOOK_URL` and click **Edit**.
4. Set the value to your **exact** Render URL **without** a trailing slash, e.g.:
   - `https://foodtracker-xxxx.onrender.com`  
   (Use the URL Render shows at the top of the service page.)
5. Save. Render will redeploy once.

---

## 7. Get your public demo link

After the deploy is **Live** (green):

- **App (demo) URL:**  
  `https://YOUR-SERVICE-NAME.onrender.com/webapp/`  

Replace `YOUR-SERVICE-NAME` with your actual Render service name (e.g. `foodtracker-abc1`). You can copy the full URL from the Render dashboard (service → top of page, then add `/webapp/`).

- Anyone can open this link in a browser (no Telegram, no login). They’ll see all pages with sample data; forms are disabled and nothing is saved.

---

## 8. Quick check

1. Open in a browser: `https://YOUR-SERVICE-NAME.onrender.com/webapp/`
2. You should see a blue “Preview – datele nu sunt salvate…” banner and the dashboard with demo data.
3. Click the tabs (Zilnic, Istoric, Progres, Setări, Clasament) – all should load. Buttons that would save show “Preview only. Modifications are disabled.” if clicked.

If the first load is slow (30–60 s), that’s Render’s free-tier cold start; the next request will be fast.

---

## Troubleshooting

| Problem | What to do |
|--------|------------|
| Build failed on Render | In Render → **Logs** check the error. Often: wrong **Build** or **Start** command, or missing `requirements.txt`. |
| “Application failed to respond” / 503 | Wait 1–2 minutes after deploy. If it stays: check **Logs** for Python errors (e.g. missing env var or DB connection). |
| Database errors in Logs | Check `DATABASE_URL`: paste the **exact** Neon connection string; no extra spaces. |
| Demo link shows “user not found” or blank | Ensure `DEMO_MODE` is set to `1` in Render → **Environment**, then **Manual Deploy** → **Deploy latest commit**. |
| Need to redeploy after a code change | Push to GitHub; Render will auto-deploy. Or in Render: **Manual Deploy** → **Deploy latest commit**. |

---

**Summary:** Push code (Section 4) → Create Web Service on Render (Section 5) → Set `BOT_WEBHOOK_URL` (Section 6) → Share `https://YOUR-SERVICE-NAME.onrender.com/webapp/` (Section 7).
