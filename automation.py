# -*- coding: utf-8 -*-
# Fully automated Text → Video generator for GitHub Actions
# Now using OpenCV and FFmpeg for video composition (replacing moviepy)

import sys
import os
import json
import pandas as pd
import zipfile
import subprocess # FFMPEG कमांड चलाने के लिए
import requests
import numpy as np
import cv2 # OpenCV को आयात करें
from PIL import Image
from io import BytesIO
from gtts import gTTS
from mutagen.mp3 import MP3 # ऑडियो अवधि जानने के लिए

# --- Configuration ---
STATE_FILE_PATH = os.path.join(os.path.dirname(__file__), 'state.txt')
MAX_ITEMS_TO_PROCESS = 1
ZIP_FILE_NAME = "production_package.zip"
TEMP_UPLOAD_DIR = "./temp_upload_dir"
FALLBACK_IMAGE_PATH = "fallback.jpg" # आपको यह फाइल रिपॉजिटरी में डालनी होगी

# --- Utility Functions (read_state, write_state, generate_script - अपरिवर्तित) ---

def read_state(default_index=1):
    try:
        if not os.path.exists(STATE_FILE_PATH):
            return default_index
        with open(STATE_FILE_PATH, "r") as f:
            return int(f.read().strip())
    except Exception:
        return default_index

def write_state(next_index):
    with open(STATE_FILE_PATH, "w") as f:
        f.write(str(next_index))

def generate_script(topic: str, idx: int) -> str:
    joke = f"MOCK JOKE: '{topic}' इतना मजेदार है कि AI भी हँस पड़ा!"
    video_text = f"स्वागत है! आज हम '{topic}' पर चर्चा करेंगे।"
    
    return (
        f"--- वीडियो स्क्रिप्ट ---\n"
        f"विषय: {topic}\n"
        f"वीडियो के लिए पाठ: {video_text}\n\n"
        f"कैप्शन: {topic} | Video Title: {topic} (Index {idx})\n"
        f"Tags: ai, automation, youtube, shorts\n\n"
        f"--- जोक ---\n{joke}\n"
    )

def fetch_background_image(topic: str, output_file: str) -> bool:
    """Robust Image Fetching: 3-Step Fallback (अपरिवर्तित)"""
    image_data = None
    
    # Attempt 1: Unsplash
    search_term = topic.split(' ')[0]
    unsplash_url = f"https://source.unsplash.com/1280x720/?{search_term}"
    try:
        response = requests.get(unsplash_url, timeout=10, allow_redirects=True)
        if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
            image_data = response.content
    except Exception:
        pass
        
    # Attempt 2: Picsum
    if image_data is None:
        picsum_url = "https://picsum.photos/1280/720"
        try:
            response = requests.get(picsum_url, timeout=10)
            if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
                image_data = response.content
        except Exception:
            pass

    # Attempt 3: Local Fallback
    if image_data is None:
        if os.path.exists(FALLBACK_IMAGE_PATH):
            try:
                img = Image.open(FALLBACK_IMAGE_PATH)
                img.save(output_file, "jpeg") 
                return True
            except Exception:
                return False
        else:
            return False

    # Save the successfully fetched image
    try:
        img = Image.open(BytesIO(image_data))
        img.save(output_file, "jpeg") 
        return True
    except Exception:
        return False


def generate_real_video(topic_text: str, output_path: str):
    """Generate a real short video using OpenCV and FFmpeg."""
    
    full_script_text = f"स्वागत है! आज हम '{topic_text}' पर चर्चा करेंगे।"
    bg_image_file = "bg_temp.jpg" 
    temp_video_path = "temp_" + output_path # ऑडियो के बिना अस्थायी वीडियो

    # 1. Fetch Background Image
    if not fetch_background_image(topic_text, bg_image_file):
        print("ERROR: Aborting video generation due to image failure.")
        return False
    
    try:
        # 2. TTS
        tts = gTTS(full_script_text, lang='hi')
        tts.save("voice.mp3")

        # 3. Video Composition (OpenCV)
        audio_info = MP3("voice.mp3")
        duration = audio_info.info.length

        frame = cv2.imread(bg_image_file)
        if frame is None:
            raise Exception(f"Could not load image: {bg_image_file}")
            
        height, width, _ = frame.shape
        fps = 24
        
        # mp4v अधिकांश Linux/GitHub Actions runners पर संगत है
        fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
        video_writer = cv2.VideoWriter(temp_video_path, fourcc, fps, (width, height))

        total_frames = int(duration * fps)
        
        for _ in range(total_frames):
            video_writer.write(frame)

        video_writer.release()
        
        # 4. Combine Video and Audio (FFmpeg CLI)
        # GitHub Actions में FFmpeg पहले से स्थापित है।
        ffmpeg_command = (
            f"ffmpeg -y -i {temp_video_path} -i voice.mp3 -c:v copy -c:a aac "
            f"-strict experimental -b:a 192k -shortest {output_path}"
        )
        
        # Subprocess का उपयोग करके कमांड चलाएँ
        subprocess.run(
            ffmpeg_command, 
            shell=True, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        
        # 5. Cleanup
        os.remove("voice.mp3")
        os.remove(temp_video_path)
        if os.path.exists(bg_image_file): os.remove(bg_image_file)
        
        print(f"✅ Generated video: {output_path}")
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"ERROR: FFmpeg command failed. {e.stderr.decode()}")
        return False
    except Exception as e:
        print(f"ERROR generating video (OpenCV/FFmpeg stage): {e}")
        # Ensure cleanup even on error
        if os.path.exists("voice.mp3"): os.remove("voice.mp3")
        if os.path.exists(bg_image_file): os.remove(bg_image_file)
        if os.path.exists(temp_video_path): os.remove(temp_video_path)
        return False

# --- Pipeline Execution (run_pipeline, mock_youtube_upload, main - अपरिवर्तित) ---
def run_pipeline(csv_url: str):
    start_index = read_state()
    videos_generated = 0
    next_index = start_index
    current_zip = ""

    if not os.path.exists(FALLBACK_IMAGE_PATH):
        error_msg = f"CRITICAL: Fallback image '{FALLBACK_IMAGE_PATH}' not found."
        print(error_msg)
        print(json.dumps({"videos_generated": 0, "zip_path": "", "error": error_msg}, ensure_ascii=False, indent=2))
        return

    try:
        df = pd.read_csv(csv_url)
        df['index'] = df.index + 1
        rows = df[df['index'] >= start_index].head(MAX_ITEMS_TO_PROCESS)
    except Exception as e:
        print(f"ERROR loading CSV: {e}")
        print(json.dumps({"videos_generated": 0, "zip_path": "", "error": str(e)}, ensure_ascii=False, indent=2))
        return

    if rows.empty:
        print(f"INFO: No new topics to process starting from index {start_index}.")
        print(json.dumps({"videos_generated": 0, "zip_path": "", "next_start_index": next_index}, ensure_ascii=False, indent=2))
        return
        
    with zipfile.ZipFile(ZIP_FILE_NAME, "w", zipfile.ZIP_DEFLATED) as zipf:
        for _, row in rows.iterrows():
            i = row['index']
            topic = str(row.get('Topic', f"Auto Topic {i}"))
            
            script = generate_script(topic, i) 
            
            script_name = f"script_{i}.txt"
            video_name = f"video_{i}.mp4"

            if not topic or topic == "nan":
                 print(f"WARNING: Skipping index {i} due to empty or invalid Topic.")
                 next_index = i + 1
                 continue
            
            if not generate_real_video(topic, video_name):
                next_index = i + 1 
                print(json.dumps({
                    "videos_generated": 0, 
                    "zip_path": "", 
                    "error": f"Video generation failed for index {i}: {topic}. Set state to {next_index}."
                }, ensure_ascii=False, indent=2))
                break 

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
        "next_start_index": next_index,
        "video_index": next_index - 1 
    }, ensure_ascii=False, indent=2))

def mock_youtube_upload(zip_file_path: str):
    if not os.path.exists(zip_file_path):
        print("ERROR: ZIP not found.")
        return
    import shutil
    os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_file_path, "r") as z:
            z.extractall(TEMP_UPLOAD_DIR)
        
        for f in os.listdir(TEMP_UPLOAD_DIR):
            if f.endswith(".mp4"):
                print(f"🎬 Mock uploading {f} to YouTube...")
        print("✅ Upload simulation done.")
    finally:
        if os.path.exists(TEMP_UPLOAD_DIR):
            shutil.rmtree(TEMP_UPLOAD_DIR)

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
