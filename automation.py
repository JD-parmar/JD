import os
import sys
import pandas as pd
import numpy as np
from gtts import gTTS
import cv2
from mutagen.mp3 import MP3
import requests
from PIL import Image
import ffmpeg  # ✅ for merging video + audio

# ---------------------------------------------------
# Helper: Fetch a background image from Unsplash
# ---------------------------------------------------
def fetch_background(keyword="nature"):
    """
    Fetches a 1280x720 image from Unsplash based on a keyword.
    Creates a fallback gray image if download fails.
    """
    try:
        url = f"https://source.unsplash.com/1280x720/?{keyword}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            with open("background.jpg", "wb") as f:
                f.write(r.content)
            return "background.jpg"
        else:
            raise Exception("Bad status code")
    except Exception as e:
        print(f"[WARN] Using fallback background due to error: {e}")
        img = Image.new("RGB", (1280, 720), color=(50, 50, 50))
        img.save("background.jpg")
        return "background.jpg"


# ---------------------------------------------------
# Generate a single video
# ---------------------------------------------------
def generate_video(script_text, filename_prefix, background_path):
    """
    Creates a narrated video using text, speech, and a background image.
    """
    # --- Create voice audio ---
    voice_path = f"{filename_prefix}_voice.mp3"
    print(f"🎙️ Generating voice for: {filename_prefix}")
    gTTS(script_text, lang="hi").save(voice_path)
    audio = MP3(voice_path)
    duration = audio.info.length

    # --- Setup video parameters ---
    frame_rate = 30
    total_frames = int(duration * frame_rate)
    bg = cv2.imread(background_path)
    bg = cv2.resize(bg, (1280, 720))

    # --- Create video frames with animated text ---
    video_temp = f"{filename_prefix}_temp.avi"
    out = cv2.VideoWriter(video_temp, cv2.VideoWriter_fourcc(*"XVID"), frame_rate, (1280, 720))

    # Trim long text for overlay
    display_text = (script_text[:70] + "...") if len(script_text) > 70 else script_text

    for i in range(total_frames):
        frame = bg.copy()
        # Simple up-down text animation
        y_pos = 200 + int(50 * np.sin(i / 15.0))
        cv2.putText(frame, display_text, (60, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        out.write(frame)
    out.release()

    # --- Combine video + audio using ffmpeg-python ---
    final_video = f"{filename_prefix}.mp4"
    print(f"🎬 Combining audio and video → {final_video}")
    (
        ffmpeg
        .input(video_temp)
        .input(voice_path)
        .output(final_video, vcodec='libx264', acodec='aac', shortest=None)
        .run(overwrite_output=True, quiet=True)
    )

    # --- Cleanup temporary files ---
    os.remove(video_temp)
    os.remove(voice_path)
    return final_video


# ---------------------------------------------------
# Main program
# ---------------------------------------------------
def main(csv_path):
    """
    Reads CSV with columns:
    Creative Problem | Case Study | Video Prompt
    Creates one MP4 per row and zips all videos.
    """
    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV file not found: {csv_path}")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    required_cols = {"Creative Problem", "Case Study", "Video Prompt"}
    if not required_cols.issubset(df.columns):
        print(f"[ERROR] CSV must include columns: {', '.join(required_cols)}")
        sys.exit(1)

    for idx, row in df.iterrows():
        creative_problem = str(row.get("Creative Problem", "")).strip()
        case_study = str(row.get("Case Study", "")).strip()
        video_prompt = str(row.get("Video Prompt", "")).strip()

        script_text = f"{creative_problem}. {case_study}. {video_prompt}"
        prefix = f"video_{idx + 1}"
        print(f"\n🚀 Creating video {idx + 1}/{len(df)}: {creative_problem}")
        bg_path = fetch_background(creative_problem or "nature")

        try:
            generate_video(script_text, prefix, bg_path)
        except Exception as e:
            print(f"[ERROR] Failed to create video {idx + 1}: {e}")

    # --- Zip all output videos ---
    print("\n📦 Packaging all videos into production_package.zip")
    os.system("zip -r production_package.zip *.mp4")
    print("✅ Done! All videos generated successfully.")


# ---------------------------------------------------
# Script entry point
# ---------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python video_generator.py <path_to_csv>")
        sys.exit(1)
    main(sys.argv[1])
