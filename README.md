# Whop Checkout Bot

Telegram bot for automated Whop checkout with temp email & OTP handling.

## Files

| File | Purpose |
|---|---|
| `bot.py` | Main bot — fully self-contained, no other dependencies |
| `requirements.txt` | Python dependencies |
| `render.yaml` | Render.com deployment config |

## Local run

```bash
pip install -r requirements.txt
BOT_TOKEN=your_token python bot.py
```

Or set `BOT_TOKEN` directly at the top of `bot.py`.

## Deploy to Render

1. Push this folder to a GitHub repo
2. Go to [render.com](https://render.com) → New → Blueprint
3. Connect the repo — `render.yaml` auto-configures a **Worker** service
4. Set `BOT_TOKEN` in Render dashboard → Environment → Add env var
5. Deploy

## Commands

### User (approved only)
- `/setproduct` or drop a `whop.com` URL — validate & save product
- `/product` — view saved product
- `/buy` or drop `CC|MM|YY|CVV` — run checkout
- `/clear` — clear product

### Owner only (`5826246696`)
- `/a <id>` — approve user
- `/da <id>` — remove user
- `/users` — list approved users
- `/broadcast <msg>` — send to all users
