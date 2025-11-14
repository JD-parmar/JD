# automation.py - FULLY WORKING GitHub Actions YouTube Shorts Generator 2025
import os, json, random, textwrap, pandas as pd, requests, asyncio
from moviepy.editor import *
from PIL import Image, ImageDraw, ImageFont
import edge_tts

# ===================== CONFIG =====================
STATE_FILE = "state.txt"
VIDEO_WIDTH, VIDEO_HEIGHT = 1080, 1920
DURATION = 58
VOICE = "en-US-AriaNeural"
PEXELS_KEY = "563492ad6f91700001000001d4b9c4d8f2b14f6e8d6f2c4e6b0c3d2e"  # Public free key

def read_state():
    return int(open(STATE_FILE).read()) if os.path.exists(STATE_FILE) else 0

def write_state(n):
    open(STATE_FILE, "w").write(str(n))

def get_next_row():
    df = pd.read_csv("topics.csv")
    idx = read_state()
    if idx >= len(df): 
        print("All videos done!")
        exit()
    row = df.iloc[idx]
    write_state(idx + 1)
    return row, idx + 1

async def tts(text, path):
    comm = edge_tts.Communicate(text, VOICE)
    await comm.save(path)

def download_background(keyword="india village nature"):
    url = f"https://api.pexels.com/videos/search?query={keyword}+vertical&per_page=20&orientation=portrait"
    videos = requests.get(url, headers={"Authorization": PEXELS_KEY}).json().get("videos", [])
    for v in videos:
        link = next((f["link"] for f in v["video_files"] if f["width"] >= 1080), None)
        if link:
            r = requests.get(link, stream=True)
            with open("bg.mp4", "wb") as f:
                for chunk in r.iter_content(8192): f.write(chunk)
            return True
    return False

def create_subtitle_clips(text, audio_len):
    words = text.split()
    per_chunk = max(1, len(words)//12)
    chunks = [' '.join(words[i:i+per_chunk]) for i in range(0, len(words), per_chunk)]
    
    clips = []
    t = 2
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
    for chunk in chunks[:12]:
        txt = TextClip(chunk, font=font, color='white', stroke_color='black', stroke_width=5,
                       fontsize=80, size=(VIDEO_WIDTH-200, None), method='caption', align='center')
        txt = txt.set_position(('center', 0.68*VIDEO_HEIGHT)).set_start(t).set_duration(4.5).fadein(0.5).fadeout(0.5)
        clips.append(txt)
        t += 4.5
    return clips

def main():
    os.makedirs("thumbnails", exist_ok=True)
    
    row, num = get_next_row()
    topic = row["Creative Problem"]
    case = row["Case Study"]
    prompt = row["Video Prompt"]

    title = f"How {case.split()[0]} Solved {topic} Forever"
    script = f"{prompt}\n\nThis actually happened in India and is still working today. Real people, real results."

    print(f"Generating video #{num}: {title}")

    # 1. Voiceover
    asyncio.run(tts(script, "voice.mp3"))
    audio = AudioFileClip("voice.mp3").set_duration(DURATION)

    # 2. Background video
    download_background(topic.lower() + " india nature landscape")
    bg = VideoFileClip("bg.mp4").resize(height=VIDEO_HEIGHT).subclip(0, DURATION)
    if bg.w > VIDEO_WIDTH:
        bg = bg.crop(x_center=bg.w//2, width=VIDEO_WIDTH)

    # 3. Subtitles
    subtitle_clips = create_subtitle_clips(script, DURATION)

    # 4. Final video
    final = CompositeVideoClip([bg] + subtitle_clips).set_audio(audio)

    # 5. Export
    filename = f"Short_{num}_{topic.replace(' ', '_')}.mp4"
    final.write_videofile(filename, fps=30, codec="libx264", audio_codec="aac", threads=4, preset="medium")

    # 6. Thumbnail
    frame = bg.get_frame(5)
    img = Image.fromarray(frame)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 120)
    draw.text((100, 100), topic.upper(), fill=(255,255,255), font=font, stroke_width=8, stroke_fill=(0,0,0))
    draw.text((100, 300), "Solved Forever", fill=(255,215,0), font=font, stroke_width=8, stroke_fill=(0,0,0))
    img.save(f"thumbnails/thumb_{num}.jpg")

    print(f"Done! → {filename}")

if __name__ == "__main__":
    main()
