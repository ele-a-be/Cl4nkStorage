# Serverless Telegram Cloud

**Turn Telegram into your personal, unlimited file storage system.**

This is a Python-based Telegram bot that uses a private channel as a hard drive and Vercel as the "brain." It allows you to store files, organized by a virtual file system, without ever paying for a server or storage.

**Why?** Because 2GB file limits (per file) and unlimited total storage are too good to pass up.

## Features

* **Zero Cost:** Runs on Vercel's Free Tier (Serverless) + Telegram Free.
* **Infinite Storage:** Leverages Telegram's "Saved Messages" architecture.
* **No Servers:** The code only runs when you upload a file. No 24/7 VPS required.
* **Database-in-Cloud:** Even the file index (`system.json`) lives in Telegram. Your bot is stateless.
* **Privacy:** You own the bot, the channel, and the data.

## How it Works

1.  **Upload:** You send a file to the bot.
2.  **Trigger:** Telegram's Webhook wakes up Vercel.
3.  **Process:** The bot forwards the file to a private channel (your "disk").
4.  **Index:** The bot updates a JSON file pinned in that same channel (your "database").
5.  **Sleep:** Vercel goes back to sleep.

## Quick Start

### 1. Prerequisites
* A **Telegram Account**.
* A **GitHub Account**.
* A **Vercel Account** (Free).

### 2. Get your Secrets
1.  **Bot Token:** Chat with `@BotFather` on Telegram to create a new bot and get the HTTP API Token.
2.  **Storage Channel:** Create a **Private Channel** on Telegram. Add your new bot as an **Administrator**.
3.  **Channel ID:** Send a message in that channel, forward it to `@userinfobot`, and copy the ID (it usually starts with `-100`).

### 3. Deploy
You don't need to touch a terminal.

1.  **Fork this repo.**
2.  Log in to **[Vercel](https://vercel.com)** and click **"Add New Project"**.
3.  Select your forked repo.
4.  **Important:** Under **Environment Variables**, add these two:
    * `BOT_TOKEN`: `your_token_here`
    * `CHANNEL_ID`: `your_channel_id_here`
5.  Click **Deploy**.

### 4. Connect the Webhook
Once Vercel finishes deploying, copy the **Domain** it gives you (e.g., `https://ghost-drive.vercel.app`).

Open your browser and run this URL to tell Telegram where your bot lives:
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://<YOUR_VERCEL_DOMAIN>/api/telegram

*Replace `<YOUR_BOT_TOKEN>` and `<YOUR_VERCEL_DOMAIN>` with your actual details.*

If you see `{"ok": true}`, you are live! 🟢

## Usage
* **Upload:** Just drag and drop any file (up to 20MB*) into the bot chat.
* **Download:** Click the file button to get it back.
* **Delete:** Remove files via the bot interface.

*> Note: The Vercel Serverless function has a timeout of 10s. Large file uploads work because Telegram handles the heavy lifting, but complex operations on 1GB+ files might require a VPS instead of Serverless.*

## Disclaimer
This project is for educational purposes. While it works great for personal backups, relying on any third-party platform (Telegram) for critical data storage carries risks. Always keep a local backup of important data.