# senpi

A Raspberry Pi–powered Telegram channel monitor. Scrapes public channels, auto-translates non-Latin scripts locally, and pipes everything into a Matrix room.

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

## Disclaimer

senpi scrapes publicly accessible Telegram channel previews for open-source intelligence research. PLEASE comply with all applicable laws.
