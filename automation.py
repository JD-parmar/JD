# -*- coding: utf-8 -*-
# Final Automated Text -> Video Generator for GitHub Actions (Highly Robust Version)
# Uses Open-Source Libraries: pandas, gTTS, requests, Pillow, opencv-python, mutagen.

import sys
import os
import json
import pandas as pd
import zipfile
import subprocess 
import numpy as np
import cv2 
import requests
from PIL import Image
from io import BytesIO
from gtts import gTTS
from mutagen.mp3 import MP3 
import time

# --- Configuration ---
STATE_FILE_PATH = os.path.join(os.path.dirname(__file__), 'state.txt')
MAX_ITEMS_TO_PROCESS = 1
ZIP_FILE_NAME = "production_package.zip"
FALLBACK_IMAGE_PATH = "fallback.jpg" # Required: A 1280x720 JPG file in the repo
TEMP_VOICE_FILE = "voice.mp3"
TEMP_IMAGE_FILE = "bg_temp.jpg"

# --- Utility Functions (read_state, write_state, generate_script - अपरिवर्तित) ---

def read_state(default_index=1):
    """Reads the next index from the state file."""
    try:
        if not os.path.exists(STATE_FILE_PATH):
            return default_index
        with open(STATE_FILE_PATH, "r") as f:
            return int(f.read().strip())
    except Exception:
        return default_index

def write_state(next_index):
    """Writes the next index to the state file."""
    try:
        with open(STATE_FILE_PATH, "w") as f:
            f.write(str(next_index))
    except Exception as e:
        print(f"ERROR writing state file: {e}")

def generate_script(row: pd.Series, idx: int) -> tuple[str, str]:
    """Generates a structured Hindi voiceover script targeting 50-59 seconds."""
    
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
        f"Tags: shorts, youtube_shorts, {problem.replace(' ', '_')}, case_study\n"
        f"\n--- Voiceover Script ---\n{tts_script_content}"
    )
    
    return script_file_content, tts_script_content


def fetch_background_image(topic: str, output_file: str) -> bool:
    """Robust 3-Step Image Fetching."""
    image_data = None
    
    # Attempt 1: Unsplash
    search_term = topic.split(' ')[0]
    unsplash_url = f"https://source.unsplash.com/1280x720/?{search_term}"
    try:
        response = requests.get(unsplash_url, timeout=10, allow_redirects=True)
        if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
            image_data = response.content
            time.sleep(1) # Be polite to Unsplash
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
            print(f"CRITICAL ERROR: All image attempts failed and local {FALLBACK_IMAGE_PATH} is missing.")
            return False

    # Save the successfully fetched image
    try:
        img = Image.open(BytesIO(image_data))
        img.save(output_file, "jpeg") 
        return True
    except Exception:
        return False


def cleanup_temp_files():
    """Ensures temporary files are deleted after the video generation attempt."""
    for f in [TEMP_VOICE_FILE, TEMP_IMAGE_FILE, "temp_video.mp4"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception as e:
                print(f"WARNING: Could not clean up {f}: {e}")

def generate_real_video(script_text_for_tts: str, topic_for_image: str, output_path: str):
    """Generate a static video using OpenCV and FFmpeg with robust error handling."""
    
    temp_video_path = "temp_video.mp4" # Consistent name for cleanup

    # 1. Fetch Background Image
    if not fetch_background_image(topic_for_image, TEMP_IMAGE_FILE):
        return False
    
    try:
        # 2. TTS (Voice Over)
        tts = gTTS(script_text_for_tts, lang='hi')
        tts.save(TEMP_VOICE_FILE)

        # 3. Video Composition (OpenCV)
        audio_info = MP3(TEMP_VOICE_FILE)
        duration = audio_info.info.length

        frame = cv2.imread(TEMP_IMAGE_FILE)
        if frame is None:
            raise Exception(f"OpenCV could not load image: {TEMP_IMAGE_FILE}")
            
        height, width, _ = frame.shape
        fps = 24
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
        video_writer = cv2.VideoWriter(temp_video_path, fourcc, fps, (width, height))

        total_frames = int(duration * fps)
        
        for _ in range(total_frames):
            video_writer.write(frame)

        video_writer.release()
        
        # Check if the temporary video file was actually created
        if not os.path.exists(temp_video_path):
             raise Exception("OpenCV failed to create temporary video file.")
        
        # 4. Combine Video and Audio (FFmpeg CLI)
        ffmpeg_command = (
            f"ffmpeg -y -i {temp_video_path} -i {TEMP_VOICE_FILE} -c:v copy -c:a aac "
            f"-strict experimental -b:a 192k -shortest {output_path}"
        )
        
        print(f"INFO: Running FFmpeg command...")
        
        # Run FFmpeg command
        result = subprocess.run(
            ffmpeg_command, 
            shell=True, 
            check=False, # Do not raise exception automatically
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )

        if result.returncode != 0:
            print(f"ERROR: FFmpeg command failed with exit code {result.returncode}.")
            print(f"FFmpeg STDOUT: {result.stdout.decode('utf-8')}")
            print(f"FFmpeg STDERR: {result.stderr.decode('utf-8')}")
            # Ensure proper cleanup before exit
            cleanup_temp_files()
            return False
            
        # Final check if the target video was created
        if not os.path.exists(output_path):
            print("ERROR: FFmpeg ran but final video file was not created.")
            cleanup_temp_files()
            return False

        # 5. Final Cleanup
        cleanup_temp_files()
        
        print(f"✅ Generated video: {output_path} (Duration: {duration:.2f}s)")
        return True
    
    except Exception as e:
        print(f"CRITICAL ERROR during video generation: {e}")
        cleanup_temp_files()
        return False

# --- Pipeline Execution ---

def run_pipeline(csv_url: str):
    start_index = read_state()
    videos_generated = 0
    next_index = start_index
    current_zip = ""

    if not os.path.exists(FALLBACK_IMAGE_PATH):
        error_msg = f"CRITICAL: Fallback image '{FALLBACK_IMAGE_PATH}' not found. Please add a 1280x720 JPG to your repo."
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
        
    try:
        # ZIP file handling is inside a try block to ensure robustness
        with zipfile.ZipFile(ZIP_FILE_NAME, "w", zipfile.ZIP_DEFLATED) as zipf:
            for _, row in rows.iterrows():
                i = row['index']
                main_topic = str(row.get('Creative Problem', f"Auto Topic {i}"))
                
                script_file_content, tts_script_content = generate_script(row, i) 
                
                script_name = f"script_{i}.txt"
                video_name = f"video_{i}.mp4"

                if not main_topic or main_topic == "nan":
                    print(f"WARNING: Skipping index {i} due to empty or invalid Creative Problem.")
                    next_index = i + 1
                    continue
                
                # 2. Generate Video
                if not generate_real_video(tts_script_content, main_topic, video_name):
                    next_index = i + 1 
                    print(json.dumps({
                        "videos_generated": 0, 
                        "zip_path": "", 
                        "error": f"Video generation failed for index {i}: {main_topic}. Stopping pipeline."
                    }, ensure_ascii=False, indent=2))
                    break 

                # 3. Packaging and Artifact Handling Check
                try:
                    zipf.writestr(script_name, script_file_content)
                    if os.path.exists(video_name):
                        zipf.write(video_name)
                        os.remove(video_name)
                    else:
                        raise Exception(f"Video file {video_name} not found after successful generation attempt.")
                except Exception as e:
                    print(f"ERROR: Failed to package video/script into ZIP: {e}")
                    next_index = i + 1
                    # Ensure cleanup of main video file if it exists but failed to zip
                    if os.path.exists(video_name): os.remove(video_name)
                    break 

                videos_generated += 1
                next_index = i + 1
                current_zip = ZIP_FILE_NAME
                print(f"INFO: Successfully processed topic {main_topic}")
                break 

    except Exception as e:
        print(f"CRITICAL ERROR in main pipeline loop or ZIP creation: {e}")
        # Final output if the zip creation itself fails
        print(json.dumps({"videos_generated": 0, "zip_path": "", "error": f"Pipeline failure: {e}"}, ensure_ascii=False, indent=2))
        return

    # 4. Update State and Output
    write_state(next_index)
    print(json.dumps({
        "videos_generated": videos_generated,
        "zip_path": current_zip,
        "next_start_index": next_index,
        "video_index": next_index - 1
    }, ensure_ascii=False, indent=2))

def main():
    if len(sys.argv) < 2:
        print("Usage: python automation.py <csv_url>")
        sys.exit(1)
    csv_url = sys.argv[1]
    run_pipeline(csv_url)

if __name__ == "__main__":
    main()
