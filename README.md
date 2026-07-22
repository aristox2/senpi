# senpi

A Raspberry Pi–powered Telegram channel monitor but there's a twist. Scrapes public channels, auto-translates non-Latin scripts locally, and pipes everything into a Matrix room.

No Telegram API keys. No cloud translation APIs. No more worrying about getting rate limited from Telegram. Nada!

---

## What it does

Telegram's API has some annoying limitations — rate limits, phone number requirements, session management headaches. Your senpi skips all of that by scraping the public web previews (`t.me/s/<channel>`) instead. New posts get forwarded to a private Matrix room, and if a message is in Arabic, Hebrew, Cyrillic, or CJK, it gets translated on-device using [Ollama](https://ollama.com) and sent as a threaded reply.

Images are grabbed during the scrape (before Telegram's CDN links expire) and uploaded to Matrix. Videos get a direct link back to the original post.

```
  t.me/s/<channel>  ──(scrape)──▶  senpi  ──(forward)──▶  Matrix Room
                                     │
                                     ▼
                                  Ollama
                              (local translation)
```

## What you need

- Raspberry Pi (or any Linux box — it's just Python)
- Python 3.10+
- [Ollama](https://ollama.com) with a translation model pulled
- A Matrix account and room

That's literally it. 

## Getting started

```bash
git clone https://github.com/aristox2/SENPI.git
cd SENPI

pip install -r requirements.txt
ollama pull translategemma

cp .env.example .env
# Fill in your Matrix credentials
```

Add the channels you want to watch to `channels.txt`, one handle per line:

```
rnintel
SabrenNewss
idfofficial
```

Run it:

```bash
python main.py
```

## config

Everything lives in `.env`:

| Variable | What it does | Default |
|----------|-------------|---------|
| `MATRIX_TOKEN` | Your Matrix access token | — |
| `MATRIX_ROOM_ID` | Room to post in | — |
| `MATRIX_HOMESERVER` | Matrix server URL | `https://matrix-client.matrix.org` |
| `MATRIX_USER` | Your Matrix user ID (for @-mentions) | — |
| `OLLAMA_MODEL` | Which Ollama model to use for translation | `translategemma` |
| `POLL_MIN` | Min seconds between scrapes | `8` |
| `POLL_MAX` | Max seconds between scrapes | `15` |

## Running as a service

```bash
sudo cp systemd/senpi.service /etc/systemd/system/
sudo systemctl enable --now senpi.service
```

## Translation coverage

Arabic · Farsi · Hebrew · Russian · Ukrainian · Chinese · Japanese · Korean

Anything in a Latin alphabet (English, French, Spanish, transliterations) is left alone — no unnecessary LLM calls.

## License

[MIT](LICENSE)

## Note from dev
1. PLEASE comply with all applicable laws. 
2. You can download matrix on your phone to keep track of everything while on the go
3. Lastly, I highly suggest you pick an Ollama model that isn't too demanding for your hardware. gemma3:1b (~1 GB) runs smooth on a Pi 4 with 4 GB RAM. If you've got more headroom, gemma3:4b or qwen2.5:3b will give you better translations.
