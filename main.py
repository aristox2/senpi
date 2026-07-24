#!/usr/bin/env python3
#Hola, como estas
import asyncio
import os
import re
import requests
import aiohttp
import uuid
import random
import json
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from colorama import Fore, Style, init
from dotenv import load_dotenv
from ollama import AsyncClient

init(autoreset=True)
load_dotenv()

ollama_client = AsyncClient()

# ── Config─────────────────────────────────────────────────────────────────

# Channels — loaded from channels.txt (one handle per line, # for comments)
CHANNELS_FILE = os.getenv("CHANNELS_FILE", "channels.txt")

def load_channels(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    channels = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                channels.append(line.lstrip("@"))
    return channels

CHANNELS = load_channels(CHANNELS_FILE)

# Matrix
MATRIX_TOKEN      = os.getenv("MATRIX_TOKEN")
MATRIX_ROOM_ID    = os.getenv("MATRIX_ROOM_ID")
MATRIX_HOMESERVER = os.getenv("MATRIX_HOMESERVER", "https://matrix-client.matrix.org")
MATRIX_USER       = os.getenv("MATRIX_USER", "")
MATRIX_SEND_URL   = f"{MATRIX_HOMESERVER}/_matrix/client/v3/rooms/{MATRIX_ROOM_ID}/send/m.room.message"
MATRIX_UPLOAD_URL = f"{MATRIX_HOMESERVER}/_matrix/media/v3/upload"
MATRIX_HEADERS    = {"Authorization": f"Bearer {MATRIX_TOKEN}"}

# Ollama
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "translategemma")

# Polling
POLL_INTERVAL_MIN = int(os.getenv("POLL_MIN", "8"))
POLL_INTERVAL_MAX = int(os.getenv("POLL_MAX", "15"))

# Limits
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB

# ── Scraping session ──────────────────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/117.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]

scrape_session = requests.Session()
scrape_session.headers.update({
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
})


def get_scrape_headers():
    return {"User-Agent": random.choice(USER_AGENTS)}


# ── Matrix helpers ────────────────────────────────────────────────────────────

async def matrix_send_text(session: aiohttp.ClientSession, text: str, reply_to: str = None, mention: bool = False) -> str | None:
    """Send a text message to the Matrix room. Returns event_id."""
    txn_id = uuid.uuid4().hex
    body = {
        "msgtype": "m.text",
        "body": text,
        "format": "org.matrix.custom.html",
        "formatted_body": text.replace("\n", "<br>"),
    }
    if mention and MATRIX_USER:
        body["m.mentions"] = {"user_ids": [MATRIX_USER]}
    if reply_to:
        body["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to}}
    try:
        async with session.put(
            f"{MATRIX_SEND_URL}/{txn_id}",
            headers=MATRIX_HEADERS,
            json=body,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status not in (200, 201):
                print(f"{Fore.RED}  ✗ Matrix send failed: {r.status}")
                return None
            data = await r.json()
            return data.get("event_id")
    except Exception as e:
        print(f"{Fore.RED}  ✗ Matrix error: {e}")
        return None


async def matrix_send_image(session: aiohttp.ClientSession, img_bytes: bytes, content_type: str = "image/jpeg", reply_to: str = None) -> str | None:
    """Upload image bytes to Matrix and send to the room. Returns event_id."""
    if not img_bytes or len(img_bytes) > MAX_UPLOAD_BYTES:
        return None
    try:
        txn_id = uuid.uuid4().hex
        async with session.post(
            f"{MATRIX_UPLOAD_URL}?filename={txn_id}.jpg",
            headers={**MATRIX_HEADERS, "Content-Type": content_type},
            data=img_bytes,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as r:
            if r.status not in (200, 201):
                return None
            data = await r.json()
            mxc_uri = data.get("content_uri")

        if not mxc_uri:
            return None

        txn_id2 = uuid.uuid4().hex
        img_body = {
            "msgtype": "m.image",
            "body": "image",
            "url": mxc_uri,
            "info": {"mimetype": content_type},
        }
        if reply_to:
            img_body["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to}}

        async with session.put(
            f"{MATRIX_SEND_URL}/{txn_id2}",
            headers=MATRIX_HEADERS,
            json=img_body,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status not in (200, 201):
                print(f"{Fore.RED}  ✗ Matrix image send failed: {r.status}")
                return None
            print(f"{Fore.GREEN}  🖼 Image sent to Matrix")
            data = await r.json()
            return data.get("event_id")
    except Exception as e:
        print(f"{Fore.RED}  ✗ Image upload error: {e}")
        return None


# ── Translation ───────────────────────────────────────────────────────────────

def needs_translation(text: str) -> bool:
    """Returns True if text contains non-Latin scripts that need translation."""
    if not text:
        return False
    return bool(re.search(
        r"[\u0600-\u06FF\u0590-\u05FF\u0400-\u04FF\u4E00-\u9FFF\u3040-\u30FF]",
        text,
    ))


async def ai_translate(text: str) -> dict | None:
    """Translate text using the local Ollama model. Returns {"lang": ..., "translation": ...}."""
    prompt = (
        "Translate only to English. Output ONLY JSON: "
        '{"lang": "...","translation": "..."}\n\n'
        f"Text: {text}"
    )
    try:
        r = await ollama_client.generate(
            model=OLLAMA_MODEL,
            prompt=prompt,
            keep_alive="-1s",
            options={"num_ctx": 512, "num_thread": 4, "temperature": 0},
        )
        raw = r["response"].strip()
        clean = re.sub(r"```json|```", "", raw).strip()
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        return json.loads(match.group()) if match else None
    except Exception as e:
        print(f"{Fore.RED}  ✗ Translation error: {e}")
        return None


# ── Scraper ───────────────────────────────────────────────────────────────────

def scrape_channel(channel: str) -> list[dict]:
    """Scrape t.me/s/<channel> for posts. Returns list of post dicts."""
    url = f"https://t.me/s/{channel}"
    try:
        scrape_session.headers.update(get_scrape_headers())
        resp = scrape_session.get(url, timeout=10)
        if resp.status_code != 200:
            print(f"{Fore.YELLOW}  ⚠ HTTP {resp.status_code} for {channel}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        posts = []

        for msg in soup.select(".tgme_widget_message"):
            data_post = msg.get("data-post", "")
            try:
                msg_id = int(data_post.split("/")[-1])
            except (ValueError, IndexError):
                continue

            # Text
            text_el = msg.select_one(".tgme_widget_message_text")
            text = text_el.get_text(separator="\n").strip() if text_el else ""

            # Timestamp
            time_el = msg.select_one(".tgme_widget_message_date time")
            if time_el and time_el.get("datetime"):
                dt = datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M UTC")
            else:
                time_str = datetime.now(timezone.utc).strftime("%H:%M UTC")

            # Image
            image_url = None
            photo_el = msg.select_one(".tgme_widget_message_photo_wrap")
            if photo_el:
                style = photo_el.get("style", "")
                match = re.search(r"url\('(.+?)'\)", style)
                if match:
                    image_url = match.group(1)

            # Video flag
            has_video = bool(msg.select_one(".tgme_widget_message_video"))

            post_url = f"https://t.me/{data_post}"

            # Download image immediately (CDN URLs expire)
            image_bytes = None
            image_mimetype = None
            if image_url:
                try:
                    scrape_session.headers.update(get_scrape_headers())
                    img_resp = scrape_session.get(image_url, timeout=15)
                    if img_resp.status_code == 200:
                        image_bytes = img_resp.content
                        image_mimetype = img_resp.headers.get("Content-Type", "image/jpeg")
                except Exception:
                    pass

            if text or image_bytes or has_video:
                posts.append({
                    "id": msg_id,
                    "text": text,
                    "time": time_str,
                    "image_bytes": image_bytes,
                    "image_mimetype": image_mimetype,
                    "post_url": post_url,
                    "has_video": has_video,
                })

        return posts

    except Exception as e:
        print(f"{Fore.RED}  ✗ Scrape error ({channel}): {e}")
        return []


# ── Per-channel monitor ───────────────────────────────────────────────────────

async def monitor_channel(channel: str, session: aiohttp.ClientSession):
    handle = f"@{channel}"
    seen_ids = set()
    first_run = True

    print(f"{Fore.CYAN}  Monitoring {handle}")

    while True:
        try:
            posts = await asyncio.to_thread(scrape_channel, channel)

            # First run — seed seen IDs without forwarding
            if first_run:
                for p in posts:
                    seen_ids.add(p["id"])
                first_run = False
                await asyncio.sleep(random.uniform(POLL_INTERVAL_MIN, POLL_INTERVAL_MAX))
                continue

            new_posts = [p for p in posts if p["id"] not in seen_ids]

            for post in sorted(new_posts, key=lambda x: x["id"]):
                seen_ids.add(post["id"])

                text = post["text"]
                time_str = post["time"]
                image_bytes = post["image_bytes"]
                image_mimetype = post["image_mimetype"]
                has_video = post["has_video"]
                post_url = post["post_url"]

                display = text[:60].replace("\n", " ") if text else "[media]"
                print(f"{Fore.WHITE}[{time_str}] {Fore.CYAN}{handle}: {Fore.WHITE}{display}")

                # Build message
                header = f"📡 {handle} · {time_str}"
                if text:
                    header += f"\n\n{text}"

                if has_video:
                    header += f"\n\n🎥 Video attached — {post_url}"
                    event_id = await matrix_send_text(session, header, mention=True)
                elif image_bytes:
                    event_id = await matrix_send_text(session, header, mention=True)
                    img_event = await matrix_send_image(session, image_bytes, image_mimetype, reply_to=event_id)
                    if not img_event:
                        await matrix_send_text(session, "🖼 [Image unavailable]", reply_to=event_id)
                elif text:
                    event_id = await matrix_send_text(session, header, mention=True)
                else:
                    event_id = None

                # Translate non-Latin text — threaded as a reply
                if text and needs_translation(text):
                    print(f"  🧠 Translating {handle}...")
                    intel = await ai_translate(text[:500])
                    if intel:
                        translation = intel.get("translation", "")
                        lang = intel.get("lang", "")
                        await matrix_send_text(
                            session, f"🌐 [{lang}]\n\n{translation}", reply_to=event_id, mention=True
                        )
                        print(f"{Fore.BLUE}  📤 Translation sent")

        except Exception as e:
            print(f"{Fore.RED}  ✗ Monitor error ({channel}): {e}")

        await asyncio.sleep(random.uniform(POLL_INTERVAL_MIN, POLL_INTERVAL_MAX))


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    os.system("cls" if os.name == "nt" else "clear")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  SENPI — Matrix Edition")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}\n")

    if not CHANNELS:
        print(f"{Fore.RED}✗ No channels found. Add handles to {CHANNELS_FILE} (one per line).")
        return

    if not MATRIX_TOKEN or not MATRIX_ROOM_ID:
        print(f"{Fore.RED}✗ MATRIX_TOKEN or MATRIX_ROOM_ID missing from .env")
        return

    async with aiohttp.ClientSession() as session:
        await matrix_send_text(session, "🛡️ SENPI ONLINE\n")
        print(f"{Fore.GREEN}✓ Online — monitoring {len(CHANNELS)} channel(s)\n")

        # Stagger channel starts
        tasks = []
        for ch in CHANNELS:
            await asyncio.sleep(1)
            tasks.append(asyncio.create_task(monitor_channel(ch, session)))
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.RED}Shutting down...")

