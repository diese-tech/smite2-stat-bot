# smite2-stats-bot – Google Cloud Setup Guide

This guide walks you through everything you need to do **before** the bot can run. Follow each section in order. You do not need to be technical — every step includes exactly what to click.

ForgeLens is designed for **league-owned deployment**. The league owner should create and control the Google account, Cloud project, service account, API keys, shared Drive folder, and generated season sheets. The developer does not need access to league data after handoff.

---

## What You're Setting Up

The bot needs two Google services:

| Service | What it does |
|---|---|
| **Gemini API** | Reads your match screenshots and extracts player stats |
| **Google Sheets API** | Pushes that data into your league spreadsheet automatically |

Both are controlled through a single **Google Cloud project** using one set of credentials.

---

## Section 1 – Create a Dedicated Google Account

> **Why a separate account?** The bot will have full access to your Google Drive and Sheets. Using a dedicated account keeps it isolated from your personal data.

1. Go to [accounts.google.com/signup](https://accounts.google.com/signup)
2. Create an account. Suggested naming convention: `yourleaguename.bot@gmail.com`
3. Save the email and password somewhere safe — you'll need it in later steps.

---

## Section 2 – Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and sign in with the **bot account** you just created.
2. At the top of the page, click the project dropdown (it may say **"Select a project"** or show a previous project name).
3. Click **"New Project"** in the top-right corner of the popup.
4. Set the **Project name** to: `smite2-stats-bot`
5. Leave **Organization** and **Location** at their defaults.
6. Click **"Create"**.
7. Wait a few seconds. When the notification appears, click **"Select Project"** to switch into it.

---

## Section 3 – Enable the Required APIs

You need to turn on two APIs. Do this for each one:

### 3a – Enable the Gemini API

1. In the search bar at the top of the Cloud Console, type: `Gemini API`
2. Click the result that says **"Gemini API"** (listed under Marketplace or APIs & Services).
3. Click the blue **"Enable"** button.
4. Wait for it to activate (usually under 10 seconds).

### 3b – Enable the Google Sheets API

1. In the search bar, type: `Google Sheets API`
2. Click the result under APIs & Services.
3. Click **"Enable"**.

### 3c – Enable the Google Drive API

1. In the search bar, type: `Google Drive API`
2. Click the result under APIs & Services.
3. Click **"Enable"**.

> The Drive API is needed for `/newseason` to create and organize new season sheets automatically.

---

## Section 4 – Get Your Gemini API Key

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — sign in with the **bot account**.
2. Click **"Create API key"**.
3. Select your `smite2-stats-bot` project from the dropdown.
4. Click **"Create API key in existing project"**.
5. Copy the key shown. **Save it now** — you won't be able to see it again.

This key goes into your `.env` file as `GEMINI_API_KEY`.

---

## Section 5 – Create a Service Account

A service account is like a login for the bot itself — it lets the bot access Sheets and Drive without using your personal Google login every time.

1. In the Cloud Console, open the left-hand menu and go to **IAM & Admin → Service Accounts**.
2. Click **"+ Create Service Account"** at the top.
3. Fill in:
   - **Service account name:** `smite2-bot`
   - **Service account ID:** will auto-fill as `smite2-bot`
   - **Description:** `smite2-stats-bot service account`
4. Click **"Create and Continue"**.
5. On the **"Grant this service account access"** step, click the **"Role"** dropdown and select:
   - **Editor** (under Basic)
6. Click **"Continue"**, then **"Done"**.

---

## Section 6 – Download the Credentials JSON

1. You should now see your `smite2-bot` service account listed. Click on it.
2. Go to the **"Keys"** tab.
3. Click **"Add Key" → "Create new key"**.
4. Select **JSON** and click **"Create"**.
5. A file will download automatically — it will be named something like `smite2-stats-bot-xxxxxxxxxx.json`.
6. Rename it to exactly: `credentials.json`
7. Place it in the root of the `smite2-stats-bot/` project folder (same folder as `bot.py`).

> **Important:** Never commit this file to GitHub. It is already listed in `.gitignore`.

---

## Section 7 – Note the Service Account Email

1. Back on the Service Accounts page, find `smite2-bot`.
2. Copy the **email address** — it looks like: `smite2-bot@smite2-stats-bot.iam.gserviceaccount.com`

You will need to **share your Google Sheet with this email** (like you'd share a doc with a colleague) when you create your first season sheet. The bot cannot access a sheet unless it has been shared with the service account.

---

## Section 8 – Set Up Your .env File

1. In the project folder, find the file named `.env.example`.
2. Make a copy of it and rename the copy to `.env` (no `.example`).
3. Open `.env` in a text editor and fill in the values:

```
DISCORD_TOKEN=your_discord_bot_token_here
GOOGLE_CREDENTIALS_PATH=credentials.json
GEMINI_API_KEY=your_gemini_api_key_here   ← from Section 4

SCREENSHOT_CHANNEL_ID=      ← right-click the channel in Discord → Copy ID
JSON_CHANNEL_ID=            ← same process
ADMIN_REPORT_CHANNEL_ID=    ← same process

STAFF_ROLE_IDS=             ← right-click the role in Discord → Copy ID
                               (comma-separate multiple IDs if needed)
STARTING_BALANCE=500        <- default fictional community-points wallet seed
```

> To copy Channel IDs and Role IDs in Discord, you must have **Developer Mode** enabled. Go to Discord Settings → Advanced → Developer Mode → turn it on. Then right-click any channel or role to see "Copy ID".

---

## Section 9 – Install Python Dependencies

Open a terminal in the `smite2-stats-bot/` folder and run:

```bash
pip install -r requirements.txt
```

This installs all libraries the bot needs.

---

## Section 10 – Run the Auth Test

Once your `.env` is filled in and `credentials.json` is in the project folder, run:

```bash
python test_auth.py
```

You should see output like:

```
[OK] credentials.json found
[OK] Gemini API connected — model: gemini-2.0-flash
[OK] Google Sheets API connected
[OK] Google Drive API connected
[OK] All checks passed. Bot is ready to configure.
```

If any check fails, the script will print a specific error message explaining what went wrong. Fix that step and re-run until all checks pass.

**Do not proceed to bot setup until all checks show [OK].**

---

## Troubleshooting

| Error | Likely cause | Fix |
|---|---|---|
| `credentials.json not found` | File is in wrong folder or wrong name | Move/rename it to the project root |
| `403 Permission denied` | API not enabled | Re-check Sections 3a–3c |
| `invalid_grant` or `401` | Credentials file corrupted or wrong project | Re-download credentials.json |
| `GEMINI_API_KEY not set` | .env not filled in | Open .env and add the key |
| `ModuleNotFoundError` | Dependencies not installed | Run `pip install -r requirements.txt` |

---

## Section 10b - Configure ForgeLens in Discord

After the bot is online and slash commands are synced, run the guild setup command from the Discord server that will use ForgeLens:

```text
/forgelens setup
```

The setup flow stores the server's screenshot channel, JSON drop channel, admin report channel, stat admin role, match ID prefix, parent Drive folder, confidence threshold, and starting community-points balance in `guild_config.json`.

ForgeLens community points are fictional league points only. There is no payment integration, real-money wagering, or compliance claim in this bot.

Useful follow-up commands:

```text
/forgelens config
/forgelens channels
/forgelens admin-add
/forgelens admin-remove
/forgelens confidence
/forgelens drive
/forgelens prefix
/forgelens starting-balance
/newseason
/help
```

*Once `test_auth.py` passes, notify Claude Code and it will proceed to Step 2: project scaffolding.*

---

## Section 11 – League Owner: Create the Shared Drive Folder

> **Who does this:** The league owner, once, before the first `/newseason` command is run. Staff do not need to do this.

This creates a top-level Google Drive folder that is shared with your entire staff team. Every season sheet the bot creates will automatically appear inside it, so staff never need to be re-invited.

In multi-guild use, each Discord server should configure its own parent Drive folder and active season. Match IDs, evidence, stats, and season records are scoped by Discord `guild_id`.

1. Go to [drive.google.com](https://drive.google.com) and sign in with **your personal Google account** (not the bot account).
2. Click **"+ New" → "Folder"**.
3. Name it something like: `Frank's Retirement Home Stats`
4. Click **"Create"**.
5. Right-click the new folder → **"Share"** and add two groups:
   - **Staff team** — add each staff member's Google account email, set to **"Viewer"** (or "Editor" if they need to edit sheets directly)
   - **Bot service account** — add `franks-stat-bot@franks-stat-bot.iam.gserviceaccount.com`, set to **"Editor"** (the bot needs Editor access to create season folders inside)
6. Click **"Share"**.
7. Open the folder. Look at the URL in your browser — it will look like:
   ```
   https://drive.google.com/drive/folders/1ABC2DEF3GHI4JKL5MNO
   ```
   Copy the ID at the end (everything after `/folders/`).
8. Open the project's `.env` file and paste it in:
   ```
   PARENT_DRIVE_FOLDER_ID=1ABC2DEF3GHI4JKL5MNO
   ```

That's it. From now on, every `/newseason` the bot runs will create its folder nested inside this shared folder — staff will see it automatically with no extra steps.

---

## Section 12 – Deploying the Bot on Railway (Always On)

Running `python bot.py` on your own machine works for testing, but the bot goes offline when your computer sleeps or restarts. Railway keeps it running 24/7.

**Cost:** Railway's Hobby plan is $5/month. There is a free trial with $5 of credit to start.

---

### Step 1 – Push your code to a private GitHub repository

1. Create a free account at [github.com](https://github.com) if you don't have one.
2. Create a **private** repository called `smite2-stats-bot`.
3. In your project folder, open a terminal and run:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/smite2-stats-bot.git
   git push -u origin main
   ```
4. Verify that `.env` and `franks-retirement-home-credentials.json` are **not** visible in GitHub — they are listed in `.gitignore` and should not appear.

---

### Step 2 – Create a Railway project

1. Go to [railway.app](https://railway.app) and sign in with GitHub.
2. Click **"New Project" → "Deploy from GitHub repo"**.
3. Select your `smite2-stats-bot` repository.
4. Railway will detect Python and install `requirements.txt` automatically. It will also pick up the `Procfile` and know to run `python bot.py`.

---

### Step 3 – Set environment variables

Railway uses environment variables instead of a `.env` file. You need to add all your secrets here.

1. In your Railway project, click the service → **"Variables"** tab.
2. Add each of the following:

| Variable | Value |
|---|---|
| `DISCORD_TOKEN` | Your Discord bot token |
| `GEMINI_API_KEY` | Your Gemini API key |
| `SCREENSHOT_CHANNEL_ID` | Channel ID from your `.env` |
| `JSON_CHANNEL_ID` | Channel ID from your `.env` |
| `ADMIN_REPORT_CHANNEL_ID` | Channel ID from your `.env` |
| `STAFF_ROLE_IDS` | Role ID(s) from your `.env` |
| `PARENT_DRIVE_FOLDER_ID` | Drive folder ID from your `.env` |
| `STARTING_BALANCE` | Default fictional wallet seed, usually `500` |
| `GOOGLE_CREDENTIALS_JSON` | See step below — paste the entire credentials file |

**For `GOOGLE_CREDENTIALS_JSON`:**
Railway can't accept uploaded files, so the credentials are stored as a single environment variable. The bot automatically writes it to a temporary file at startup.

1. Open `franks-retirement-home-credentials.json` in a text editor.
2. Select all the text (it looks like `{ "type": "service_account", ... }`).
3. Copy it and paste the entire thing as the value for `GOOGLE_CREDENTIALS_JSON` in Railway.

Do **not** set `GOOGLE_CREDENTIALS_PATH` on Railway — leave it unset. The bot will use `GOOGLE_CREDENTIALS_JSON` instead.

---

### Step 4 – Deploy

1. Click **"Deploy"**. Railway will build and start the bot.
2. Go to the **"Logs"** tab — you should see:
   ```
   Ready: YourBotName#1234 | Slash commands synced
   No active season. Run /newseason to create one.
   ```
3. If you see errors, check that all environment variables are set correctly.

---

### Redeploying after code changes

Any time you push new code to GitHub, Railway automatically redeploys. No manual steps needed.

```bash
git add .
git commit -m "describe your change"
git push
```

---

### Other hosting options

| Platform | Cost | Notes |
|---|---|---|
| **Fly.io** | Free tier available | Slightly more setup, good long-term option |
| **DigitalOcean Droplet** | ~$6/month | Full control, you manage the server yourself |
| **Always-on PC/server** | Free | Works fine if you have a spare machine that stays on |
