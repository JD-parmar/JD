#!/usr/bin/env python3
"""
YouTube Shorts Generator – CSV → Pro MP4 + Thumbnail
Uses: Pexels photos/videos, gTTS, MoviePy, Pillow
"""

import os
import io
import requests
import numpy as np
import pandas as pd
from moviepy.editor import *
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
import re

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
CSV_DATA = """Creative Problem,Case Study,Video Prompt
Water scarcity,Rajasthan village initiative,A remote village in Rajasthan was dying of thirst until locals built underground taankas and revived ancient johads – show dramatic before/after, dusty land turning green, happy women carrying less water
Education access,Himalayan schools,In the freezing Himalayas, children walked hours through snow to study – now solar-powered classrooms with tablets light up remote villages at night, show kids smiling in warm glowing rooms
Traffic congestion,Mumbai smart traffic lights,Mumbai’s insane traffic jams were cut by 40% using AI traffic lights that detect crowds in real-time – show chaotic old footage vs smooth flowing roads today, honking reduced
"""

STATE_FILE = "state.txt"
W, H = 1080, 1920
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
PEXELS_API = "https://api.pexels.com/v1/search"
PEXELS_VIDEO_API = "https://api.pexels.com/videos/search"
HEADERS = {"Authorization": "563492ad6f91700001000001e3e3d3e3e3e3e3e3e3e3e3e3e3e3"}  # Free Pexels key (public)

# ----------------------------------------------------------------------
def get_state():
    return int(open(STATE_FILE).read().strip()) if os.path.exists(STATE_FILE) else 0

def save_state(n):
    open(STATE_FILE, "w").write(str(n))

def load_sheet():
    df = pd.read_csv(io.StringIO(CSV_DATA))
    df = df.rename(columns=lambda x: x.strip())
    df = df.rename(columns={
        "Creative Problem": "problem",
        "Case Study": "case",
        "Video Prompt": "prompt"
    })
    df = df[["problem", "case", "prompt"]].dropna().reset_index(drop=True)
    print(f"Loaded {len(df)} rows")
    return df

def speak(text):
    gTTS(text=text, lang='en', slow=False).save("voice.mp3")

def download_media(query, is_video=False, duration_needed=10):
    url = PEXELS_VIDEO_API if is_video else PEXELS_API
    params = {"query": query, "per_page": 3, "orientation": "portrait"}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        data = r.json()
        items = data.get("videos", data.get("photos", []))
        for item in items:
            src = item["video_files" if is_video else "src"]["original" if is_video else "large"]
            r2 = requests.get(src, timeout=30)
            if len(r2.content) > 500_000:
                ext = ".mp4" if is_video else ".jpg"
                path = f"media_{query.replace(' ', '_')}{ext}"
                open(path, "wb").write(r2.content)
                if is_video:
                    clip = VideoFileClip(path).subclip(0, min(duration_needed, VideoFileClip(path).duration))
                    clip.write_videofile(path, fps=30, codec="libx264", logger=None)
                return path
    except: pass
    return None

def create_subtitle(text, fontsize=88):
    img = Image.new("RGBA", (W, 600), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, fontsize)
    lines = []
    words = text.split()
    line = ""
    for w in words:
        if draw.textlength(line + w + " ", font=font) < W - 200:
            line += w + " "
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

def make_thumbnail(frame, problem):
    if frame.dtype != np.uint8:
        frame = (frame * 255).astype(np.uint8) if frame.max() <= 1.0 else frame.astype(np.uint8)
    img = Image.fromarray(frame)
    draw = ImageDraw.Draw(img)
    big = ImageFont.truetype(FONT, 130)
    draw.text((80, 80), problem.upper(), fill="white", font=big, stroke_width=12, stroke_fill="black")
    draw.text((80, 280), "SOLVED", fill=(255,215,0), font=big, stroke_width=12, stroke_fill="black")
    return img

# ----------------------------------------------------------------------
def main():
    os.makedirs("thumbnails", exist_ok=True)
    df = load_sheet()
    idx = get_state()
    if idx >= len(df):
        print("All done!")
        return

    row = df.iloc[idx]
    problem = row["problem"]
    case = row["case"]
    prompt = row["prompt"]

    # Extract keywords
    before_kw = re.search(r"before.*?,", prompt.lower() + ",")
    after_kw = re.search(r"after.*?,|green|smooth|glowing", prompt.lower())
    before_kw = before_kw.group().split(",")[0].replace("before", "").strip() if before_kw else problem
    after_kw = after_kw.group().split(",")[0].strip() if after_kw else case

    script = f"{prompt} This really happened in {case} and it's still working today."
    print(f"Generating Short #{idx+1}: {problem}")

    # Voice
    speak(script)
    audio = AudioFileClip("voice.mp3")
    duration = audio.duration

    # Download visuals
    before_media = download_media(f"{before_kw} drought", is_video=False) or download_media("desert village", is_video=True)
    after_media = download_media(f"{after_kw} green", is_video=False) or download_media("happy village", is_video=True)

    clips = []
    half = duration / 2

    # Before clip
    if before_media and before_media.endswith(".mp4"):
        clip = VideoFileClip(before_media).subclip(0, half).resize(height=H)
    else:
        img = Image.open(before_media or "fallback_before.jpg")
        clip = ImageClip(np.array(img)).set_duration(half).resize(height=H)
    if clip.w > W: clip = clip.crop(x_center=clip.w//2, width=W)
    clips.append(clip)

    # After clip
    if after_media and after_media.endswith(".mp4"):
        clip = VideoFileClip(after_media).subclip(0, half).resize(height=H)
    else:
        img = Image.open(after_media or "fallback_after.jpg")
        clip = ImageClip(np.array(img)).set_duration(half).resize(height=H)
    if clip.w > W: clip = clip.crop(x_center=clip.w//2, width=W)
    clips.append(clip)

    # Concatenate
    video = concatenate_videocl
