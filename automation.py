import os
import sys
import io
import zipfile
import pandas as pd
import numpy as np
from gtts import gTTS
import cv2
from PIL import Image, ImageDraw, ImageFont
import requests
import ffmpeg

# --- Config ---
STATE_FILE = "state.txt"
ZIP_FILE = "production_package.zip"
MAX_VIDEOS = 1
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# --- Helpers ---
def read_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return int(f.read().strip())
    return 1

def write_state(value):
    with open(STATE_FILE, "w") as f:
        f.write(str(value))

def fetch_csv(csv_url):
    try:
        r = requests.get(csv_url)
        r.raise_for_status()
        return pd.read_csv(io.StringIO(r.text))
    except Exception as e:
        print(f"ERROR: Failed to fetch CSV: {e}")
        sys.exit(1)

def text_to_audio(text, filename):
    tts = gTTS(text=text, lang='en')
    tts.save(filename)

def generate_video(text, audio_file, output_file):
    width, height = 720, 480
    fps = 1  # 1 frame per second for simplicity
    duration = 5  # seconds
    font = ImageFont.truetype(FONT_PATH, 32)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    video = cv2.VideoWriter(output_file, fourcc, fps, (width, height))

    for _ in range(duration):
        img = Image.new("RGB", (width, height), color=(50, 50, 50))
        draw = ImageDraw.Draw(img)
        draw.text((50, height // 2 - 20), text, font=font, fill=(255, 255, 255))
        frame = np.array(img)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        video.write(frame)

    video.release()

    # Merge audio
    try:
        temp_file = "temp_" + output_file
        (
            ffmpeg
            .input(output_file)
            .output(temp_file, vcodec='copy', acodec='aac', audio_bitrate='192k', shortest=None)
            .overwrite_output()
            .run(quiet=True)
        )
        (
            ffmpeg
            .input(temp_file)
            .input(audio_file)
            .output(output_file, vcodec='copy', acodec='aac', strict='experimental')
            .overwrite_output()
            .run(quiet=True)
        )
        os.remove(temp_file)
    except Exception as e:
        print(f"WARN: Audio merge failed: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python automation.py <CSV_URL>")
        sys.exit(1)

    csv_url = sys.argv[1]
    df = fetch_csv(csv_url)
    df['index'] = df.index + 1
    start_index = read_state()

    videos_generated = 0
    with zipfile.ZipFile(ZIP_FILE, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for _, row in df[df['index'] >= start_index].head(MAX_VIDEOS).iterrows():
            idx = row['index']
            topic = row['Creative Problem']
            case = row['Case Study']
            prompt = row['Video Prompt']

            text_content = f"Topic: {topic}\nCase: {case}\nPrompt: {prompt}"

            audio_file = f"voice_{idx}.mp3"
            video_file = f"video_{idx}.mp4"

            # Generate audio and video
            text_to_audio(text_content, audio_file)
            generate_video(text_content, audio_file, video_file)

            # Add to ZIP
            zipf.write(video_file)
            zipf.write(audio_file)

            # Cleanup
            os.remove(video_file)
            os.remove(audio_file)

            videos_generated += 1
            start_index = idx + 1
            break  # Only process one video at a time

    write_state(start_index)
    print({
        "videos_generated": videos_generated,
        "zip_path": ZIP_FILE if videos_generated else "",
        "next_index": start_index
    })


if __name__ == "__main__":
    main()
