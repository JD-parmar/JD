import os
import sys
import json
import pandas as pd
from gtts import gTTS
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import ffmpeg
import zipfile
import requests
import io

# --- Config ---
STATE_FILE_PATH = "state.txt"
MAX_ITEMS_TO_PROCESS = 1
ZIP_FILE_NAME = "production_package.zip"

VIDEO_WIDTH = 640
VIDEO_HEIGHT = 480
FPS = 24
DURATION = 5  # seconds per video
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# --- State Management ---
def read_state(default=0):
    try:
        with open(STATE_FILE_PATH, "r") as f:
            return int(f.read().strip())
    except Exception:
        return default

def write_state(index):
    with open(STATE_FILE_PATH, "w") as f:
        f.write(str(index))

# --- Google Sheet CSV Fetch ---
def fetch_google_sheet(sheet_url):
    """
    Converts Google Sheet URL to CSV export and reads into pandas.
    """
    try:
        # Convert edit URL to export CSV URL
        if "/edit" in sheet_url:
            sheet_id = sheet_url.split("/d/")[1].split("/")[0]
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        else:
            csv_url = sheet_url

        response = requests.get(csv_url)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        return df
    except Exception as e:
        print(f"ERROR: Failed to fetch Google Sheet: {e}")
        sys.exit(1)

# --- Text to Speech ---
def text_to_speech(text, filename):
    tts = gTTS(text=text, lang='en')
    tts.save(filename)
    return filename

# --- Video Frame Generation ---
def generate_frames(text_lines):
    frames = []
    font = ImageFont.truetype(FONT_PATH, 32)
    for i in range(FPS * DURATION):
        img = Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        y = 50
        for line in text_lines:
            w, h = draw.textsize(line, font=font)
            draw.text(((VIDEO_WIDTH-w)/2, y), line, font=font, fill=(255,255,255))
            y += h + 20
        frame = np.array(img)
        frames.append(frame)
    return frames

# --- Video Creation using OpenCV ---
def create_video(frames, video_path, audio_path=None):
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, FPS, (VIDEO_WIDTH, VIDEO_HEIGHT))
    for frame in frames:
        out.write(frame)
    out.release()

    if audio_path:
        # Merge audio with ffmpeg
        temp_path = "temp_video.mp4"
        os.rename(video_path, temp_path)
        ffmpeg.input(temp_path).output(audio_path, video_path, vcodec='copy', acodec='aac', strict='experimental', shortest=None).run(overwrite_output=True)
        os.remove(temp_path)

# --- Main Automation Pipeline ---
def run_pipeline(sheet_url):
    start_index = read_state()
    videos_generated = 0
    next_index = start_index
    zip_path = ""

    df = fetch_google_sheet(sheet_url)
    df['index'] = df.index + 1
    rows_to_process = df[df['index'] > start_index].head(MAX_ITEMS_TO_PROCESS)

    if rows_to_process.empty:
        return {"videos_generated": 0, "zip_path": "", "next_index": start_index}

    with zipfile.ZipFile(ZIP_FILE_NAME, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for _, row in rows_to_process.iterrows():
            idx = row['index']
            topic = row['Creative Problem']
            case = row['Case Study']
            prompt = row['Video Prompt']

            script_file = f"script_{idx}.txt"
            video_file = f"video_{idx}.mp4"
            audio_file = f"voice_{idx}.mp3"

            # Save script
            script_text = f"Topic: {topic}\nCase Study: {case}\nPrompt: {prompt}"
            with open(script_file, "w") as f:
                f.write(script_text)

            # Generate voice
            text_to_speech(script_text, audio_file)

            # Generate frames
            text_lines = [f"Topic: {topic}", f"Case: {case}", f"Prompt: {prompt}"]
            frames = generate_frames(text_lines)

            # Create video + merge audio
            create_video(frames, video_file, audio_file)

            # Add to zip
            zipf.write(script_file)
            zipf.write(video_file)
            zipf.write(audio_file)

            # Cleanup
            os.remove(script_file)
            os.remove(video_file)
            os.remove(audio_file)

            videos_generated += 1
            next_index = idx
            zip_path = ZIP_FILE_NAME
            break  # only 1 video per run

    write_state(next_index)
    return {"videos_generated": videos_generated, "zip_path": zip_path, "next_index": next_index}

# --- Main ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python automation.py <Google_Sheet_URL>")
        sys.exit(1)
    sheet_url = sys.argv[1]
    result = run_pipeline(sheet_url)
    print(json.dumps(result))
