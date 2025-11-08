import os
import sys
import pandas as pd
import numpy as np
from gtts import gTTS
import cv2
from mutagen.mp3 import MP3
import requests
from PIL import Image
import ffmpeg
import zipfile
import glob

def fetch_background(keyword="nature"):
    """Download a background image or create fallback."""
    try:
        url = f"https://source.unsplash.com/1280x720/?{keyword}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            with open("background.jpg", "wb") as f:
                f.write(r.content)
            return "background.jpg"
    except Exception as e:
        print(f"[WARN] Unsplash fetch failed: {e}")

    # Fallback image
    img = Image.new("RGB", (1280, 720), color=(30, 30, 30))
    img.save("background.jpg")
    return "background.jpg"

def generate_video(script_text, filename_prefix, background_path):
    """Generate one video with Hindi narration."""
    voice_path = f"{filename_prefix}_voice.mp3"
    print(f"Generating voice: {voice_path}")
    gTTS(script_text, lang="hi").save(voice_path)
    audio = MP3(voice_path)
    duration = audio.info.length

    frame_rate = 30
    total_frames = int(duration * frame_rate)

    bg = cv2.imread(background_path)
    if bg is None:
        raise RuntimeError("Failed to read background image.")
    bg = cv2.resize(bg, (1280, 720))

    tmp_video = f"{filename_prefix}_temp.avi"
    out = cv2.VideoWriter(tmp_video, cv2.VideoWriter_fourcc(*"XVID"), frame_rate, (1280, 720))

    text = (script_text[:70] + "...") if len(script_text) > 70 else script_text
    for i in range(total_frames):
        frame = bg.copy()
        y_pos = 200 + int(60 * np.sin(i / 20))
        cv2.putText(frame, text, (50, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        out.write(frame)
    out.release()

    final_video = f"{filename_prefix}.mp4"
    try:
        (
            ffmpeg
            .input(tmp_video)
            .input(voice_path)
            .output(final_video, vcodec="libx264", acodec="aac", shortest=None)
            .run(overwrite_output=True, quiet=True)
        )
    except ffmpeg.Error as e:
        print("[ERROR] FFmpeg merge failed:", e.stderr.decode())
        raise e

    os.remove(tmp_video)
    os.remove(voice_path)
    print(f"Created video: {final_video}")
    return final_video

def zip_videos(zip_name="production_package.zip"):
    mp4_files = glob.glob("*.mp4")
    if not mp4_files:
        print("[WARN] No mp4 files found to zip.")
        return False

    with zipfile.ZipFile(zip_name, "w") as zf:
        for f in mp4_files:
            zf.write(f)
    print(f"Created zip archive: {zip_name}")
    return True

def main(csv_path):
    """Read CSV and create all videos."""
    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV not found: {csv_path}")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    required_cols = {"Creative Problem", "Case Study", "Video Prompt"}
    if not required_cols.issubset(df.columns):
        print(f"[ERROR] CSV must contain columns: {', '.join(required_cols)}")
        sys.exit(1)

    for idx, row in df.iterrows():
        creative_problem = str(row.get("Creative Problem", "")).strip()
        case_study = str(row.get("Case Study", "")).strip()
        video_prompt = str(row.get("Video Prompt", "")).strip()

        script_text = f"{creative_problem}. {case_study}. {video_prompt}"
        prefix = f"video_{idx + 1}"
        print(f"\n🎬 Generating video {idx + 1}: {creative_problem or 'Untitled'}")

        bg = fetch_background(creative_problem or "nature")
        try:
            generate_video(script_text, prefix, bg)
        except Exception as e:
            print(f"[ERROR] Video {idx+1} failed: {e}")

    zipped = zip_videos()
    if not zipped:
        print("[WARN] No videos were zipped.")
    else:
        print("\n✅ All videos generated and zipped successfully!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python automation.py <your_csv_file>")
        sys.exit(1)
    main(sys.argv[1])
