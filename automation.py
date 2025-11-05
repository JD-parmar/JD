import os
import sys
import csv
import json
import pandas as pd
import requests
from gtts import gTTS
from PIL import Image
import cv2
from mutagen.mp3 import MP3
import numpy as np

# ---------------------------
# 1️⃣ Helper functions
# ---------------------------

def read_state(state_file="state.txt"):
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            return int(f.read().strip() or 0)
    return 0

def write_state(index, state_file="state.txt"):
    with open(state_file, "w") as f:
        f.write(str(index))

# ---------------------------
# 2️⃣ Script generator
# ---------------------------

def generate_script(creative_problem, case_study, video_prompt):
    topic_line = f"विषय: {creative_problem}"
    case_line = f"केस स्टडी: {case_study}"
    script_text = (
        f"नमस्कार! आज हम बात करेंगे {creative_problem} के बारे में। "
        f"{case_study} का उदाहरण लेकर हम समझेंगे कि कैसे इस चुनौती का समाधान किया गया। "
        f"{video_prompt} पर ध्यान देते हैं और जानते हैं कि हम इससे क्या सीख सकते हैं। "
        f"धन्यवाद।"
    )
    return f"{topic_line}\n{case_line}\n\n{script_text}", script_text

# ---------------------------
# 3️⃣ Background Image
# ---------------------------

def fetch_background_image(keyword="nature", fallback_path="fallback.jpg"):
    try:
        url = f"https://source.unsplash.com/1280x720/?{keyword}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open("background.jpg", "wb") as f:
                f.write(response.content)
            return "background.jpg"
    except Exception:
        pass

    try:
        url = "https://picsum.photos/1280/720"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open("background.jpg", "wb") as f:
                f.write(response.content)
            return "background.jpg"
    except Exception:
        pass

    # fallback image
    if os.path.exists(fallback_path):
        return fallback_path

    # auto-generate fallback
    print("⚠️ Fallback image missing — generating a placeholder.")
    img = Image.new("RGB", (1280, 720), color=(40, 40, 40))
    img.save(fallback_path)
    return fallback_path

# ---------------------------
# 4️⃣ Generate Video
# ---------------------------

def generate_real_video(script_text, filename_prefix, background_path):
    voice_path = f"{filename_prefix}_voice.mp3"
    gTTS(script_text, lang="hi").save(voice_path)

    audio = MP3(voice_path)
    duration = audio.info.length
    frame_rate = 30
    total_frames = int(duration * frame_rate)

    bg = cv2.imread(background_path)
    bg = cv2.resize(bg, (1280, 720))

    video_path = f"{filename_prefix}_video.avi"
    out = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*"XVID"), frame_rate, (1280, 720))

    for _ in range(total_frames):
        out.write(bg)
    out.release()

    final_video = f"{filename_prefix}.mp4"
    os.system(f"ffmpeg -y -i {video_path} -i {voice_path} -c:v libx264 -c:a aac -shortest {final_video}")

    os.remove(video_path)
    os.remove(voice_path)
    return final_video

# ---------------------------
# 5️⃣ Main
# ---------------------------

def main(csv_path):
    try:
        df = pd.read_csv(csv_path)
        start_idx = read_state()
        total = len(df)
        print(f"🔹 Starting from index {start_idx} of {total}")

        for i in range(start_idx, total):
            row = df.iloc[i]
            creative_problem = str(row.get("Creative Problem", ""))
            case_study = str(row.get("Case Study", ""))
            video_prompt = str(row.get("Video Prompt", ""))

            script_file, script_text = generate_script(creative_problem, case_study, video_prompt)
            background = fetch_background_image(creative_problem)

            prefix = f"video_{i+1}"
            script_path = f"{prefix}.txt"
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_file)

            video_path = generate_real_video(script_text, prefix, background)

            print(f"✅ Generated {video_path}")
            write_state(i + 1)

        os.system("zip -r production_package.zip *.mp4 *.txt")

        print(json.dumps({
            "videos_generated": total - start_idx,
            "zip_path": "production_package.zip",
            "status": "success"
        }, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({
            "error": str(e),
            "videos_generated": 0
        }, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Please provide CSV path or Google Sheet export link.")
        sys.exit(1)
    main(sys.argv[1])
