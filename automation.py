# -*- coding: utf-8 -*-
# Fully automated Text → Video generator for GitHub Actions
# Updated for cleaner execution on GitHub Actions.

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

# --- Utility Functions ---

def read_state(default_index=1):
    try:
        with open(STATE_FILE_PATH, "r") as f:
            return int(f.read().strip())
    except Exception:
        return default_index

def write_state(next_index):
    with open(STATE_FILE_PATH, "w") as f:
        f.write(str(next_index))

def generate_script(topic: str, idx: int) -> str:
    """Generates a mock script and metadata."""
    joke = f"MOCK JOKE: '{topic}' इतना मजेदार है कि AI भी हँस पड़ा!"
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
        # 1. TTS
        tts = gTTS(topic_text, lang='hi')
        tts.save("voice.mp3")

        # 2. Image Fetch
        # Using Hindi text in URL might cause issues; using a general query is safer.
        url = f"https://source.unsplash.com/1280x720/?{topic_text.split(' ')[0]}" 
        img_data = requests.get(url, timeout=10).content
        img = Image.open(BytesIO(img_data))
        img.save("bg.jpg")

        # 3. Video Composition
        audio = AudioFileClip("voice.mp3")
        clip = ImageClip("bg.jpg").set_duration(audio.duration).set_audio(audio)
        
        # *** सुधारी गई लाइन: 'logger=None' जोड़ा गया ताकि MoviePy बहुत ज़्यादा लॉग न करे ***
        clip.write_videofile(
            output_path, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac",
            logger=None # Suppress verbose MoviePy output
        )
        
        # Cleanup
        os.remove("voice.mp3")
        os.remove("bg.jpg")

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
        # *** सुधारी गई लाइन: एरर पर स्पष्ट JSON आउटपुट ***
        print(json.dumps({"videos_generated": 0, "zip_path": "", "error": str(e)}, ensure_ascii=False))
        return

    if rows.empty:
        print("INFO: No new topics.")
        # *** सुधारी गई लाइन: कोई टॉपिक न होने पर स्पष्ट JSON आउटपुट ***
        print(json.dumps({"videos_generated": 0, "zip_path": "", "next_start_index": next_index}, ensure_ascii=False, indent=2))
        return

    with zipfile.ZipFile(ZIP_FILE_NAME, "w", zipfile.ZIP_DEFLATED) as zipf:
        for _, row in rows.iterrows():
            i = row['index']
            topic = str(row.get('Topic', f"Auto Topic {i}"))
            
            # *** सुधारी गई लाइन: generate_script में index पास किया गया (consistency के लिए) ***
            script = generate_script(topic, i) 
            
            script_name = f"script_{i}.txt"
            video_name = f"video_{i}.mp4"

            if not generate_real_video(topic, video_name):
                # Video generation failed, stop and try next time
                next_index = i + 1 
                break

            zipf.writestr(script_name, script)
            zipf.write(video_name)
            os.remove(video_name)

            videos_generated += 1
            next_index = i + 1
            current_zip = ZIP_FILE_NAME
            print(f"INFO: Finished topic {topic}")
            break # Process only one item per run

    write_state(next_index)
    # Output result as JSON for GitHub Actions artifact and n8n
    print(json.dumps({
        "videos_generated": videos_generated,
        "zip_path": current_zip,
        "next_start_index": next_index,
        "video_index": next_index - 1 
    }, ensure_ascii=False, indent=2))

def mock_youtube_upload(zip_file_path: str):
    # ... (Mock upload code remains the same as it's not the critical part)
    if not os.path.exists(zip_file_path):
        print("ERROR: ZIP not found.")
        return
    # ... (rest of the mock upload logic)
    print("✅ Upload simulation done.")

def main():
    if len(sys.argv) > 2 and sys.argv[1] == "upload-youtube":
        # We don't need to install shutil explicitly since it's part of the standard library
        import shutil 
        if os.path.exists(TEMP_UPLOAD_DIR):
            shutil.rmtree(TEMP_UPLOAD_DIR)
        mock_youtube_upload(sys.argv[2])
        return
    if len(sys.argv) < 2:
        print("Usage: python automation.py <csv_url>")
        sys.exit(1)
    csv_url = sys.argv[1]
    run_pipeline(csv_url)

if __name__ == "__main__":
    main()
