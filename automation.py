#!/usr/bin/env python3
"""
Daily Trending YouTube Short Generator
Date: November 15, 2025 | 10:54 AM IST
Topic: Bihar Election 2025 – NDA Landslide Victory!
"""

import os
import re
import requests
import numpy as np
from datetime import datetime
from moviepy.editor import *
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
STATE_FILE = "state.txt"
W, H = 1080, 1920
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
PEXELS_SEARCH = "https://api.pexels.com/v1/search"
PEXELS_VIDEO = "https://api.pexels.com/videos/search"
HEADERS = {"Authorization": "563492ad6f91700001000001e3e3d3e3e3e3e3e3e3e3e3e3e3e3"}  # Public Pexels key

# TODAY'S TRENDING TOPIC (Nov 15, 2025)
TOPIC = "Bihar Election 2025 NDA Landslide Victory"
CASE = "Patna, Bihar"
PROMPT = (
    "Bihar just delivered a historic verdict – NDA led by Nitish Kumar and BJP wins 210+ seats in a massive landslide. "
    "From caste alliances to Modi's rallies, this is a game-changer. Dusty rallies turned into victory celebrations – "
    "show dramatic crowd footage, cheering supporters, and NDA leaders waving from stages. "
    "This happened in Patna, Bihar on November 15, 2025 – and it's trending across India!"
)

# ----------------------------------------------------------------------
def get_state():
    return int(open(STATE_FILE).read().strip()) if os.path.exists(STATE_FILE) else 0

def save_state(n):
    open(STATE_FILE, "w").write(str(n))

def speak(text):
    gTTS(text=text, lang='en', slow=False).save("voice.mp3")

def download_media(query, is_video=False, duration=10):
    url = PEXELS_VIDEO if is_video else PEXELS_SEARCH
    params = {"query": query, "per_page": 5, "orientation": "portrait"}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        data = r.json()
        items = data.get("videos") or data.get("photos", [])
        for item in items:
            files = item.get("video_files") or [item["src"]]
            src = next((f["link"] for f in files if "hd" in f.get("file_type", "") or "portrait" in f.get("file_type", "")), None)
            if not src:
                src = item["src"]["original"] if not is_video else files[0]["link"]
            r2 = requests.get(src, timeout=30)
            if len(r2.content) < 100_000: continue
            ext = ".mp4" if is_video else ".jpg"
            path = f"media_{query.replace(' ', '_')[:20]}{ext}"
            open(path, "wb").write(r2.content)
            if is_video:
                clip = VideoFileClip(path).subclip(0, min(duration, VideoFileClip(path).duration))
                clip.write_videofile(path, codec="libx264", fps=30, logger=None)
            return path
    except Exception as e:
        print(f"Download failed for '{query}': {e}")
    return None

def create_subtitle(text, fontsize=88):
    img = Image.new("RGBA", (W, 600), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, fontsize)
    words = text.split()
    lines, line = [], ""
    for w in words:
        test = line + w + " "
        if draw.textlength(test, font=font) < W - 200:
            line = test
        else:
            lines.append(line.strip())
            line = w + " "
    if line: lines.append(line.strip())
    y = 120
    for l in lines[:4]:
        bbox = draw.textbbox((0, 0), l, font=font)
        x = (W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), l, font=font, fill="white", stroke_width=8, stroke_fill="black")
        y += 130
    return ImageClip(np.array(img)).set_position(("center", 0.68 * H))

def make_thumbnail(frame, title):
    if frame.dtype != np.uint8:
        frame = (frame * 255).astype(np.uint8) if frame.max() <= 1.0 else frame.astype(np.uint8)
    img = Image.fromarray(frame)
    draw = ImageDraw.Draw(img)
    big = ImageFont.truetype(FONT, 110)
    small = ImageFont.truetype(FONT, 80)
    draw.text((80, 80), title.upper(), fill="white", font=big, stroke_width=12, stroke_fill="black")
    draw.text((80, 280), "NDA WINS BIHAR!", fill=(255,215,0), font=small, stroke_width=10, stroke_fill="black")
    return img

# ----------------------------------------------------------------------
def main():
    os.makedirs("thumbnails", exist_ok=True)
    idx = get_state()
    if idx > 0:
        print("Today's Short already generated!")
        return

    script = PROMPT
    print(f"Generating Trending Short: {TOPIC}")

    # Voice
    speak(script)
    audio = AudioFileClip("voice.mp3")
    duration = audio.duration
    half = duration / 2

    # Download visuals
    before_media = download_media("election rally crowd india", is_video=True, duration=half) or \
                   download_media("political rally dusty", is_video=False)
    after_media = download_media("nda victory celebration", is_video=True, duration=half) or \
                  download_media("supporters cheering bjp", is_video=False)

    # Fallback
    if not before_media:
        before_media = download_media("indian election", is_video=False)
    if not after_media:
        after_media = download_media("victory crowd", is_video=False)

    # Create clips
    def make_clip(path, dur):
        if path.endswith(".mp4"):
            return VideoFileClip(path).subclip(0, dur).resize(height=H).crop(x_center=W//2, width=W)
        else:
            return ImageClip(np.array(Image.open(path))).set_duration(dur).resize(height=H).crop(x_center=W//2, width=W)

    clip1 = make_clip(before_media, half)
    clip2 = make_clip(after_media, half)
    video = concatenate_videoclips([clip1, clip2], method="compose")

    # Subtitles
    subs = []
    for i in range(0, len(script), 70):
        chunk = script[i:i+70].strip()
        if chunk:
            sub = create_subtitle(chunk).set_start(i * 0.27).set_duration(5).fadein(0.4).fadeout(0.4)
            subs.append(sub)

    final = CompositeVideoClip([video] + subs).set_audio(audio)
    safe_name = "Bihar_Election_2025"
    output = f"Short_Trending_{safe_name}.mp4"
    final.write_videofile(output, fps=30, codec="libx264", audio_codec="aac", preset="ultrafast", threads=6, logger=None)

    # Thumbnail
    try:
        frame = clip2.get_frame(half - 1)
        thumb = make_thumbnail(frame, "BIHAR ELECTION 2025")
        thumb.save(f"thumbnails/thumb_trending.jpg")
    except Exception as e:
        print(f"Thumbnail failed: {e}")

    save_state(1)
    print(f"SUCCESS: {output} READY ({duration:.1f}s)")

if __name__ == "__main__":
    main()
