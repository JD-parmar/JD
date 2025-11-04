# -*- coding: utf-8 -*-
# Fully automated Text → Video generator for GitHub Actions

import sys
import os
import json
import pandas as pd
import zipfile
from gtts import gTTS
from moviepy.editor import ImageClip, AudioFileClip
import requests
from PIL import Image
from io import BytesIO

STATE_FILE_PATH = os.path.join(os.path.dirname(__file__), 'state.txt')
MAX_ITEMS_TO_PROCESS = 1
ZIP_FILE_NAME = "production_package.zip"
TEMP_UPLOAD_DIR = "./temp_upload_dir"

def read_state(default_index=1):
    try:
        with open(STATE_FILE_PATH, "r") as f:
            return int(f.read().strip())
    except Exception:
        return default_index

def write_state(next_index):
    with open(STATE_FILE_PATH, "w") as f:
        f.write(str(next_index))

def generate_script(topic: str) -> str:
    joke = f"MOCK JOKE: '{topic}' इतना मजेदार है कि AI भी हँस पड़ा!"
    idx = read_state()
    return (
        f"--- वीडियो स्क्रिप्ट ---\n"
        f"विषय: {topic}\n\n"
        f"स्वागत है! आज हम '{topic}' पर चर्चा करेंगे।\n"
        f"कैप्शन: {topic} | Video Title: {topic} (Index {idx})\n"
        f"Tags: ai, automation, youtube, shorts\n\n"
        f"--- जोक ---\n{joke}\n"
    )

def generate_real_video(topic_text: str, output_path: str):
    """Generate a real short video (text→voice→image→video)."""
    try:
        tts = gTTS(topic_text, lang='hi')
        tts.save("voice.mp3")

        url = f"https://source.unsplash.com/1280x720/?{topic_text.replace(' ', '-')}"
        img_data = requests.get(url).content
        img = Image.open(BytesIO(img_data))
        img.save("bg.jpg")

        audio = AudioFileClip("voice.mp3")
        clip = ImageClip("bg.jpg").set_duration(audio.duration).set_audio(audio)
        clip.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")

        print(f"✅ Generated video: {output_path}")
        return True
    except Exception as e:
        print(f"ERROR generating video: {e}")
        return False

def run_pipeline(csv_url: str):
    start_index = read_state()
    videos_generated = 0
    next_index = start_index
    current_zip = ""

    try:
        df = pd.read_csv(csv_url)
        df['index'] = df.index + 1
        rows = df[df['index'] >= start_index].head(MAX_ITEMS_TO_PROCESS)
    except Exception as e:
        print(f"ERROR loading CSV: {e}")
        return

    if rows.empty:
        print("INFO: No new topics.")
        return

    with zipfile.ZipFile(ZIP_FILE_NAME, "w", zipfile.ZIP_DEFLATED) as zipf:
        for _, row in rows.iterrows():
            i = row['index']
            topic = str(row.get('Topic', f"Auto Topic {i}"))
            script_name = f"script_{i}.txt"
            video_name = f"video_{i}.mp4"

            script = generate_script(topic)
            if not generate_real_video(topic, video_name):
                continue

            zipf.writestr(script_name, script)
            zipf.write(video_name)
            os.remove(video_name)

            videos_generated += 1
            next_index = i + 1
            current_zip = ZIP_FILE_NAME
            print(f"INFO: Finished topic {topic}")
            break

    write_state(next_index)
    print(json.dumps({
        "videos_generated": videos_generated,
        "zip_path": current_zip,
        "next_start_index": next_index
    }, ensure_ascii=False, indent=2))

def mock_youtube_upload(zip_file_path: str):
    if not os.path.exists(zip_file_path):
        print("ERROR: ZIP not found.")
        return
    os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)
    with zipfile.ZipFile(zip_file_path, "r") as z:
        z.extractall(TEMP_UPLOAD_DIR)
    for f in os.listdir(TEMP_UPLOAD_DIR):
        if f.endswith(".mp4"):
            print(f"🎬 Mock uploading {f} to YouTube...")
    print("✅ Upload simulation done.")

def main():
    if len(sys.argv) > 2 and sys.argv[1] == "upload-youtube":
        mock_youtube_upload(sys.argv[2])
        return
    if len(sys.argv) < 2:
        print("Usage: python automation.py <csv_url>")
        sys.exit(1)
    csv_url = sys.argv[1]
    run_pipeline(csv_url)

if __name__ == "__main__":
    main()
