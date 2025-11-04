# -*- coding: utf-8 -*-
# Fully automated Text → Video generator for GitHub Actions
# Updated with Robust Image Fetching (3-Step Fallback)

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

# --- Configuration ---
STATE_FILE_PATH = os.path.join(os.path.dirname(__file__), 'state.txt')
MAX_ITEMS_TO_PROCESS = 1
ZIP_FILE_NAME = "production_package.zip"
TEMP_UPLOAD_DIR = "./temp_upload_dir"
FALLBACK_IMAGE_PATH = "fallback.jpg" # आपको यह फाइल रिपॉजिटरी में डालनी होगी

# --- Utility Functions ---

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
    """Generates script and metadata for the video."""
    joke = f"MOCK JOKE: '{topic}' इतना मजेदार है कि AI भी हँस पड़ा!"
    return (
        f"--- वीडियो स्क्रिप्ट ---\n"
        f"विषय: {topic}\n\n"
        f"स्वागत है! आज हम '{topic}' पर चर्चा करेंगे।\n"
        f"कैप्शन: {topic} | Video Title: {topic} (Index {idx})\n"
        f"Tags: ai, automation, youtube, shorts\n\n"
        f"--- जोक ---\n{joke}\n"
    )

def fetch_background_image(topic: str, output_file: str) -> bool:
    """
    Tries to fetch an image using 3 different methods.
    Returns True if an image is successfully saved to output_file.
    """
    image_data = None
    
    # --- Attempt 1: Unsplash (Using only the first word for safety) ---
    search_term = topic.split(' ')[0]
    unsplash_url = f"https://source.unsplash.com/1280x720/?{search_term}"
    print(f"INFO: Trying Unsplash URL: {unsplash_url}")
    try:
        response = requests.get(unsplash_url, timeout=15)
        if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
            image_data = response.content
            print("INFO: Successfully fetched image from Unsplash.")
    except Exception as e:
        print(f"WARNING: Unsplash failed ({e}). Trying fallback.")
        
    # --- Attempt 2: Picsum (Random Image Fallback) ---
    if image_data is None:
        picsum_url = "https://picsum.photos/1280/720"
        print(f"INFO: Trying Picsum URL: {picsum_url}")
        try:
            response = requests.get(picsum_url, timeout=15)
            if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
                image_data = response.content
                print("INFO: Successfully fetched image from Picsum.")
        except Exception as e:
            print(f"WARNING: Picsum failed ({e}). Trying local fallback.")

    # --- Attempt 3: Local Fallback (If all online failed) ---
    if image_data is None:
        if os.path.exists(FALLBACK_IMAGE_PATH):
            print(f"INFO: Using local fallback image: {FALLBACK_IMAGE_PATH}")
            # Simply copy the local fallback file
            Image.open(FALLBACK_IMAGE_PATH).save(output_file)
            return True
        else:
            print(f"ERROR: All image attempts failed and local {FALLBACK_IMAGE_PATH} is missing.")
            return False

    # Save the successfully fetched image (from Attempt 1 or 2)
    try:
        img = Image.open(BytesIO(image_data))
        img.save(output_file)
        return True
    except Exception as e:
        print(f"CRITICAL ERROR: Could not process/save fetched image data: {e}")
        return False


def generate_real_video(topic_text: str, output_path: str):
    """Generate a real short video (text→voice→image→video)."""
    bg_image_file = "bg.jpg"
    
    # 1. Fetch Background Image (using robust fallback)
    if not fetch_background_image(topic_text, bg_image_file):
        print("ERROR: Aborting video generation due to image failure.")
        return False
    
    try:
        # 2. TTS
        tts = gTTS(topic_text, lang='hi')
        tts.save("voice.mp3")

        # 3. Video Composition
        audio = AudioFileClip("voice.mp3")
        clip = ImageClip(bg_image_file).set_duration(audio.duration).set_audio(audio)
        
        clip.write_videofile(
            output_path, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac",
            logger=None # Suppress verbose MoviePy output
        )
        
        # Cleanup
        os.remove("voice.mp3")
        if os.path.exists(bg_image_file): os.remove(bg_image_file) # Clean up temp image
        
        print(f"✅ Generated video: {output_path}")
        return True
    except Exception as e:
        print(f"ERROR generating video (MoviePy/gTTS stage): {e}")
        # Ensure cleanup even on error
        if os.path.exists("voice.mp3"): os.remove("voice.mp3")
        if os.path.exists(bg_image_file): os.remove(bg_image_file)
        return False

def run_pipeline(csv_url: str):
    start_index = read_state()
    videos_generated = 0
    next_index = start_index
    current_zip = ""

    # Check for the local fallback image before proceeding
    if not os.path.exists(FALLBACK_IMAGE_PATH):
        print(f"CRITICAL: Fallback image '{FALLBACK_IMAGE_PATH}' not found. Please upload a 1280x720 JPG to your GitHub repo.")
        print(json.dumps({"videos_generated": 0, "zip_path": "", "error": f"Missing fallback image: {FALLBACK_IMAGE_PATH}"}, ensure_ascii=False))
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
        print("INFO: No new topics.")
        print(json.dumps({"videos_generated": 0, "zip_path": "", "next_start_index": next_index}, ensure_ascii=False, indent=2))
        return

    # Check if we successfully fetched data, if not, handle error and exit gracefully
    if df.empty:
        print("INFO: CSV loaded but is empty.")
        print(json.dumps({"videos_generated": 0, "zip_path": "", "next_start_index": next_index}, ensure_ascii=False, indent=2))
        return
        
    with zipfile.ZipFile(ZIP_FILE_NAME, "w", zipfile.ZIP_DEFLATED) as zipf:
        for _, row in rows.iterrows():
            i = row['index']
            topic = str(row.get('Topic', f"Auto Topic {i}"))
            
            script = generate_script(topic, i) 
            
            script_name = f"script_{i}.txt"
            video_name = f"video_{i}.mp4"

            if not generate_real_video(topic, video_name):
                # Video generation failed (likely image issue), stop and update state to try next topic next time
                next_index = i + 1 
                # Log failure to console output for GitHub Actions/n8n
                print(json.dumps({
                    "videos_generated": 0, 
                    "zip_path": "", 
                    "error": f"Video generation failed for index {i}: {topic}"
                }, ensure_ascii=False, indent=2))
                break # Stop processing after the first failure

            zipf.writestr(script_name, script)
            zipf.write(video_name)
            os.remove(video_name)

            videos_generated += 1
            next_index = i + 1
            current_zip = ZIP_FILE_NAME
            print(f"INFO: Finished topic {topic}")
            break 

    write_state(next_index)
    # Output result as JSON for GitHub Actions artifact and n8n
    print(json.dumps({
        "videos_generated": videos_generated,
        "zip_path": current_zip,
        "next_start_index": next_index,
        "video_index": next_index - 1 
    }, ensure_ascii=False, indent=2))

def mock_youtube_upload(zip_file_path: str):
    # ... (Mock upload code remains the same)
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

