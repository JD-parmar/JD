# -*- coding: utf-8 -*-
# Final Automated Text -> Video Generator for GitHub Actions
# Author: JD Automation
# Uses: pandas, gTTS, requests, Pillow, opencv-python, mutagen

import sys, os, json, time, zipfile, subprocess
import pandas as pd
import requests
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from gtts import gTTS
from mutagen.mp3 import MP3

# --- Configuration ---
STATE_FILE_PATH = os.path.join(os.path.dirname(__file__), 'state.txt')
MAX_ITEMS_TO_PROCESS = 1
ZIP_FILE_NAME = "production_package.zip"
FALLBACK_IMAGE_PATH = "fallback.jpg"
TEMP_VOICE_FILE = "voice.mp3"
TEMP_IMAGE_FILE = "bg_temp.jpg"

# --- State Functions ---
def read_state(default_index=1):
    try:
        if not os.path.exists(STATE_FILE_PATH):
            return default_index
        with open(STATE_FILE_PATH, "r") as f:
            return int(f.read().strip())
    except:
        return default_index

def write_state(next_index):
    try:
        with open(STATE_FILE_PATH, "w") as f:
            f.write(str(next_index))
    except Exception as e:
        print(f"ERROR writing state file: {e}")

# --- Script Generator ---
def generate_script(row: pd.Series, idx: int) -> tuple[str, str]:
    problem = row.get('Creative Problem', 'एक महत्वपूर्ण समस्या')
    case_study = row.get('Case Study', 'कोई केस स्टडी नहीं मिली')
    prompt = row.get('Video Prompt', 'इस विषय पर गहराई से बात करें')

    tts_script_content = (
        f"नमस्ते दोस्तों! आज हम एक बहुत ही महत्वपूर्ण और दिलचस्प समस्या पर ध्यान देंगे: '{problem}'। "
        f"कई बार हम सोचते हैं कि यह समस्या क्यों आती है, लेकिन असल कहानी हमारी केस स्टडी में है। "
        f"हमारी गहन छानबीन के दौरान, हमने पाया कि {case_study}। "
        f"यह दिखाता है कि समाधान हमेशा सरल नहीं होता। '{prompt}' पर आधारित यह वीडियो आपको एक नया दृष्टिकोण देगा। "
        f"याद रखें, हर समस्या का समाधान है, बस सही नज़रिए की ज़रूरत है। "
        f"इस पर अपनी राय कमेंट में ज़रूर दें। धन्यवाद!"
    )

    script_file_content = (
        f"--- Video Metadata (Index {idx}) ---\n"
        f"Title: {problem} - एक केस स्टडी\n"
        f"Tags: shorts, youtube_shorts, {problem.replace(' ', '_')}, case_study\n\n"
        f"--- Voiceover Script ---\n{tts_script_content}"
    )
    return script_file_content, tts_script_content

# --- Image Fetching ---
def create_fallback_image():
    """Creates a 1280x720 fallback image if missing."""
    print("INFO: Creating fallback.jpg automatically...")
    img = Image.new('RGB', (1280, 720), color=(70, 70, 70))
    draw = ImageDraw.Draw(img)
    text = "Fallback Background"
    draw.text((440, 340), text, fill=(255, 255, 255))
    img.save(FALLBACK_IMAGE_PATH, "JPEG")

def fetch_background_image(topic: str, output_file: str) -> bool:
    image_data = None
    search_term = topic.split(' ')[0]
    unsplash_url = f"https://source.unsplash.com/1280x720/?{search_term}"

    try:
        response = requests.get(unsplash_url, timeout=10)
        if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
            image_data = response.content
            time.sleep(1)
    except:
        pass

    if image_data is None:
        picsum_url = "https://picsum.photos/1280/720"
        try:
            response = requests.get(picsum_url, timeout=10)
            if response.status_code == 200:
                image_data = response.content
        except:
            pass

    if image_data is None:
        if not os.path.exists(FALLBACK_IMAGE_PATH):
            create_fallback_image()
        Image.open(FALLBACK_IMAGE_PATH).save(output_file, "JPEG")
        return True

    try:
        img = Image.open(BytesIO(image_data))
        img.save(output_file, "JPEG")
        return True
    except:
        return False

# --- Cleanup ---
def cleanup_temp_files():
    for f in [TEMP_VOICE_FILE, TEMP_IMAGE_FILE, "temp_video.mp4"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception as e:
                print(f"WARNING: Cleanup failed for {f}: {e}")

# --- Video Generator ---
def generate_real_video(script_text_for_tts: str, topic_for_image: str, output_path: str):
    if not fetch_background_image(topic_for_image, TEMP_IMAGE_FILE):
        return False

    try:
        tts = gTTS(script_text_for_tts, lang='hi')
        tts.save(TEMP_VOICE_FILE)

        audio_info = MP3(TEMP_VOICE_FILE)
        duration = audio_info.info.length

        frame = cv2.imread(TEMP_IMAGE_FILE)
        if frame is None:
            raise Exception("OpenCV could not load background image")

        height, width, _ = frame.shape
        fps = 24
        total_frames = int(duration * fps)
        video_writer = cv2.VideoWriter("temp_video.mp4", cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))

        for _ in range(total_frames):
            video_writer.write(frame)
        video_writer.release()

        ffmpeg_cmd = f"ffmpeg -y -i temp_video.mp4 -i {TEMP_VOICE_FILE} -c:v copy -c:a aac -shortest {output_path}"
        subprocess.run(ffmpeg_cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        cleanup_temp_files()
        print(f"✅ Generated video: {output_path} ({duration:.2f}s)")
        return True
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        cleanup_temp_files()
        return False

# --- Pipeline ---
def run_pipeline(csv_url: str):
    start_index = read_state()
    next_index = start_index
    videos_generated = 0
    current_zip = ZIP_FILE_NAME

    try:
        df = pd.read_csv(csv_url)
        df['index'] = df.index + 1
        rows = df[df['index'] >= start_index].head(MAX_ITEMS_TO_PROCESS)
    except Exception as e:
        print(f"ERROR loading CSV: {e}")
        return

    if rows.empty:
        print("INFO: No new topics to process.")
        return

    with zipfile.ZipFile(current_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for _, row in rows.iterrows():
            i = row['index']
            main_topic = str(row.get('Creative Problem', f"Auto Topic {i}"))
            script_file_content, tts_script_content = generate_script(row, i)
            script_name = f"script_{i}.txt"
            video_name = f"video_{i}.mp4"

            if not generate_real_video(tts_script_content, main_topic, video_name):
                continue

            zipf.writestr(script_name, script_file_content)
            if os.path.exists(video_name):
                zipf.write(video_name)
                os.remove(video_name)

            videos_generated += 1
            next_index = i + 1
            break

    write_state(next_index)
    print(json.dumps({
        "videos_generated": videos_generated,
        "zip_path": current_zip,
        "next_start_index": next_index
    }, ensure_ascii=False, indent=2))

def main():
    if len(sys.argv) < 2:
        print("Usage: python automation.py <csv_url>")
        sys.exit(1)
    csv_url = sys.argv[1]
    run_pipeline(csv_url)

if __name__ == "__main__":
    main()
