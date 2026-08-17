# Discord Leaderboard Bot

A Discord bot that scrapes a website for player data and maintains a live leaderboard in a channel.

---

## Project structure

```
discord-leaderboard-bot/
├── bot.py              # Entry point
├── models.py           # Player dataclass
├── scraper.py          # Scraping logic
├── database.py         # JSON persistence layer
├── cogs/
│   └── leaderboard.py  # Slash commands + background refresh
├── data/               # Auto-created at runtime (gitignored)
│   ├── registrations.json
│   └── leaderboard.json
├── .env.example
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Create a Discord application & bot

1. Go to <https://discord.com/developers/applications> and create a new application.
2. Open **Bot** → enable **Public Bot** if desired.
3. Copy the **Token** — you'll need it in `.env`.
4. Under **OAuth2 → URL Generator**, select scopes `bot` + `applications.commands`
   and permissions `Send Messages`, `Manage Messages` (for pinning), `Read Message History`.
5. Use the generated URL to invite the bot to your server.

### 2. Enable Developer Mode to get IDs

User Settings → Advanced → **Developer Mode** on.  
Right-click yourself → **Copy User ID** for `OWNER_ID`.  
Right-click your server → **Copy Server ID** for `GUILD_ID`.

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your TOKEN, OWNER_ID, and GUILD_ID
```

### 4. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 6. Run the bot

```bash
python bot.py
```

---

## Slash commands

| Command | Who | Description |
|---|---|---|
| `/leaderboard add <player_id>` | Anyone | Register your site player ID. One per Discord account. |
| `/leaderboard remove` | Anyone | Remove your own registration. |
| `/leaderboard remove <player_id>` | Owner | Remove any player's registration. |
| `/leaderboard show` | Anyone | Post (or update) the leaderboard in the current channel. |
| `/leaderboard refresh` | Owner | Force an immediate data refresh. |
| `/leaderboard list` | Owner | View all Discord ↔ player ID mappings. |
| `/leaderboard addplayer` | Owner | Add a player ID to the leaderboard without a Discord account. |
| `/leaderboard removeplayer` | Owner | Remove an unlinked player ID from the leaderboard. |

---

## How the leaderboard updates

- A background task runs every **5 minutes** (configurable via `REFRESH_INTERVAL` in `cogs/leaderboard.py`).
- It calls `scraper.fetch_all_tracked_players()` for every registered player ID.
- The leaderboard embed is edited in-place so the channel stays clean.
- The message is automatically pinned when first posted.

---

## Customising the embed

Edit `build_leaderboard_embed()` in `cogs/leaderboard.py` — it's a plain `discord.Embed` so any Discord.py formatting works.
