import os
import sys
import pandas as pd
import numpy as np
from gtts import gTTS
import cv2
from mutagen.mp3 import MP3
import requests
from PIL import Image

# Helper to fetch background
def fetch_background(keyword="nature"):
    try:
        url = f"https://source.unsplash.com/1280x720/?{keyword}"
        r = requests.get(url, timeout=10)
        with open("background.jpg", "wb") as f:
            f.write(r.content)
        return "background.jpg"
    except:
        # fallback
        img = Image.new("RGB", (1280,720), color=(50,50,50))
        img.save("background.jpg")
        return "background.jpg"

# Generate video from text
def generate_video(script_text, filename_prefix, background_path):
    voice_path = f"{filename_prefix}_voice.mp3"
    gTTS(script_text, lang="hi").save(voice_path)
    audio = MP3(voice_path)
    duration = audio.info.length

    frame_rate = 30
    total_frames = int(duration * frame_rate)

    bg = cv2.imread(background_path)
    bg = cv2.resize(bg, (1280,720))

    video_path = f"{filename_prefix}_video.avi"
    out = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*"XVID"), frame_rate, (1280,720))

    # Add simple animated text
    for i in range(total_frames):
        frame = bg.copy()
        y_pos = 50 + (i % 100)  # simple vertical movement
        cv2.putText(frame, script_text[:50]+"...", (50,y_pos), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
        out.write(frame)
    out.release()

    final_video = f"{filename_prefix}.mp4"
    os.system(f"ffmpeg -y -i {video_path} -i {voice_path} -c:v libx264 -c:a aac -shortest {final_video}")
    os.remove(video_path)
    os.remove(voice_path)
    return final_video

def main(csv_path):
    df = pd.read_csv(csv_path)
    for idx, row in df.iterrows():
        creative_problem = str(row.get("Creative Problem",""))
        case_study = str(row.get("Case Study",""))
        video_prompt = str(row.get("Video Prompt",""))

        script_text = f"{creative_problem} - {case_study} - {video_prompt}"
        bg = fetch_background(creative_problem)
        prefix = f"video_{idx+1}"
        generate_video(script_text, prefix, bg)

    os.system("zip -r production_package.zip *.mp4")

if __name__=="__main__":
    if len(sys.argv)<2:
        print("Provide CSV URL")
        sys.exit(1)
    main(sys.argv[1])
