# automation.py — FULLY AUTOMATIC YouTube Shorts from your Google Sheet
import os
import pandas as pd
import requests
import numpy as np
from moviepy.editor import *
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
import io

# YOUR GOOGLE SHEET (MUST be published to web as CSV!)
CSV_URL = "https://docs.google.com/spreadsheets/d/1kJWflnWA6BpZqyndGu4zqKXL2rlTRYBLGVOjOjXrXt0/export?format=csv"

STATE_FILE = "state.txt"
W, H = 1080, 1920
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
BG_URL = "https://videos.pexels.com/video-files/855564/855564-hd_1080_1920_30fps.mp4"

def get_state():
    return int(open(STATE_FILE).read().strip()) if os.path.exists(STATE_FILE) else 0

def save_state(n):
    open(STATE_FILE, "w").write(str(n))

def load_sheet():
    try:
        r = requests.get(CSV_URL, timeout=20)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        # Clean column names (removes spaces, hidden characters)
        df.columns = [col.strip() for col in df.columns]
        return df.dropna(subset=["Creative Problem", "Case Study", "Video Prompt"])
    except Exception as e:
        print(f"Error loading sheet: {e}")
        exit(1)

def download_bg():
    try:
        r = requests.get(BG_URL, timeout=20)
        if len(r.content) > 1_000_000:
            open("bg.mp4", "wb").write(r.content)
            return True
    except:
        pass
    return False

def speak(text):
    gTTS(text=text, lang='en', slow=False).save("voice.mp3")

def create_subtitle(text):
    img = Image.new("RGBA", (W, 600), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 88)
    
    words = text.split()
    lines = []
    line = ""
    for word in words:
        test = line + word + " "
        if draw.textlength(test, font) < W - 200:
            line = test
        else:
            lines.append(line.strip())
            line = word + " "
    if line: lines.append(line.strip())

    y = 120
    for line in lines[:4]:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=font, fill="white", stroke_width=8, stroke_fill="black")
        y += 130

    return ImageClip(np.array(img)).set_position(("center", 0.68 * H))

def main():
    os.makedirs("thumbnails", exist_ok=True)
    df = load_sheet()
    idx = get_state()

    if idx >= len(df):
        print("All rows in your Google Sheet have been processed!")
        exit(0)

    row = df.iloc[idx]
    problem = str(row["Creative Problem"]).strip()
    case = str(row["Case Study"]).strip()
    prompt = str(row["Video Prompt"]).strip()

    script = f"{prompt} This actually happened in {case} and it's still working perfectly in 2025."
    title = f"How {case.split()[0]} Solved {problem} Forever"

    print(f"Generating Short #{idx+1}: {title}")

    # Generate voice
    speak(script)
    audio = AudioFileClip("voice.mp3")
    duration = audio.duration

    # Background
    bg = ColorClip((W, H), color=(10, 20, 50), duration=duration)
    if download_bg():
        try:
            vid = VideoFileClip("bg.mp4").subclip(0, duration).resize(height=H)
            if vid.w > W:
                vid = vid.crop(x_center=vid.w//2, width=W)
            bg = vid
        except:
            print("Using solid color background")

    # Subtitles
    subs = []
    for i in range(0, len(script), 68):
        chunk = script[i:i+68].strip()
        if chunk:
            sub = create_subtitle(chunk).set_start(i * 0.27).set_duration(5).fadein(0.4).fadeout(0.4)
            subs.append(sub)

    # Final video
    final = CompositeVideoClip([bg] + subs).set_audio(audio)
    output = f"Short_{idx+1}_{problem.replace(' ', '_')[:20]}.mp4"
    final.write_videofile(output, fps=30, codec="libx264", audio_codec="aac",
                          preset="ultrafast", threads=6, verbose=False, logger=None)

    # Thumbnail
    frame = bg.get_frame(min(8, duration-1))
    img = Image.fromarray(frame)
    draw = ImageDraw.Draw(img)
    big = ImageFont.truetype(FONT, 130)
    draw.text((80, 80), problem.upper(), fill="white", font=big, stroke_width=12, stroke_fill="black")
    draw.text((80, 280), "SOLVED", fill=(255, 215, 0), font=big, stroke_width=12, stroke_fill="black")
    img.save(f"thumbnails/thumb_{idx+1}.jpg")

    save_state(idx + 1)
    print(f"SUCCESS! Generated: {output} ({duration:.1f}s)")

if __name__ == "__main__":
    main()
