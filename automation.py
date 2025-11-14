# automation.py – 100% WORKING ON GITHUB ACTIONS (2025 FINAL)
import os, random, pandas as pd, requests, asyncio, numpy as np
from moviepy.editor import *
from PIL import Image, ImageDraw, ImageFont
import edge_tts

# CONFIG
STATE = "state.txt"
W, H = 1080, 1920
DURATION = 58
VOICE = "en-US-AriaNeural"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Built-in topics (works even without topics.csv)
TOPICS = [
    {"Creative Problem": "Water scarcity", "Case Study": "Rajasthan village", "Video Prompt": "Village in Rajasthan had no water. They revived 1000-year-old johads and built taankas. Now they have water all year."},
    {"Creative Problem": "Education access", "Case Study": "Himalayan schools", "Video Prompt": "Children walked 4 hours in snow to school. Now solar classrooms with tablets light up remote villages at night."},
    {"Creative Problem": "Traffic congestion", "Case Study": "Mumbai AI lights", "Video Prompt": "Mumbai cut traffic jams 40% using AI traffic lights that detect crowds in real time."}
]

def state():
    return int(open(STATE).read()) if os.path.exists(STATE) else 0

def save_state(n):
    open(STATE, "w").write(str(n))

def next_row():
    i = state()
    if i >= len(TOPICS):
        print("All done!")
        exit()
    save_state(i + 1)
    return TOPICS[i], i + 1

async def speak(text):
    await edge_tts.Communicate(text, VOICE).save("voice.mp3")

def bg_video():
    try:
        url = "https://videos.pexels.com/video-files/855564/855564-hd_1080_1920_30fps.mp4"  # Direct free vertical video
        r = requests.get(url, timeout=20)
        open("bg.mp4", "wb").write(r.content)
        return True
    except:
        return False

# Pure Pillow subtitles (NO ImageMagick!)
def subtitle_clip(text):
    img = Image.new("RGBA", (W, 500), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 90)
    lines = []
    words = text.split()
    line = ""
    for w in words:
        if draw.textlength(line + w, font) < W-200:
            line += w + " "
        else:
            lines.append(line)
            line = w + " "
    if line: lines.append(line)
    
    y = 80
    for line in lines[:4]:
        bbox = draw.textbbox((0,0), line, font=font)
        x = (W - bbox[2]) // 2
        draw.text((x, y), line, font=font, fill="white", stroke_width=8, stroke_fill="black")
        y += 110
    
    arr = np.array(img)
    return ImageClip(arr).set_duration(5).set_position(("center", 0.7*H)).resize(width=W-100)

def main():
    os.makedirs("thumbnails", exist_ok=True)
    row, num = next_row()
    topic = row["Creative Problem"]
    prompt = row["Video Prompt"] + " This is real and still working in 2025."
    
    print(f"Generating Short #{num}: {topic}")

    # 1. Voice
    asyncio.run(speak(prompt))
    audio = AudioFileClip("voice.mp3").set_duration(DURATION)

    # 2. Background
    if not bg_video():
        bg = ColorClip((W,H), color=(15,25,50), duration=DURATION)
    else:
        bg = VideoFileClip("bg.mp4").resize(height=H).subclip(0,DURATION)
        if bg.w > W: bg = bg.crop(x_center=bg.w//2, width=W)

    # 3. Subtitles
    subs = []
    for i in range(0, len(prompt), 70):
        chunk = prompt[i:i+70]
        if chunk.strip():
            c = subtitle_clip(chunk).set_start(i*0.25).fadein(0.3).fadeout(0.3)
            subs.append(c)

    # 4. Final video
    final = CompositeVideoClip([bg] + subs).set_audio(audio)
    out = f"Short_{num}_{topic.replace(' ', '_')}.mp4"
    final.write_videofile(out, fps=30, codec="libx264", audio_codec="aac", preset="ultrafast", threads=4, verbose=False, logger=None)

    # 5. Thumbnail
    frame = bg.get_frame(10)
    img = Image.fromarray(frame)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 140)
    d.text((80,80), topic.upper(), fill="white", font=f, stroke_width=12, stroke_fill="black")
    d.text((80,300), "SOLVED", fill=(255,220,0), font=f, stroke_width=12, stroke_fill="black")
    img.save(f"thumbnails/thumb_{num}.jpg")

    print(f"DONE → {out} (ready to upload)")

if __name__ == "__main__":
    main()
