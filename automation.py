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
import tempfile
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def fetch_background(keyword="nature"):
    try:
        url = f"https://source.unsplash.com/1280x720/?{keyword}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            with open("background.jpg", "wb") as f:
                f.write(r.content)
            return "background.jpg"
    except Exception as e:
        logging.warning(f"Unsplash fetch failed: {e}")

    img = Image.new("RGB", (1280, 720), color=(30, 30, 30))
    img.save("background.jpg")
    return "background.jpg"

def generate_video(script_text, filename_prefix, background_path):
    with tempfile.TemporaryDirectory() as tmpdir:
        voice_path = os.path.join(tmpdir, "voice.mp3")
        tmp_video = os.path.join(tmpdir, "temp.avi")
        final_video = f"{filename_prefix}.mp4"

        gTTS(script_text, lang="hi").save(voice_path)
        audio = MP3(voice_path)
        duration = audio.info.length

        frame_rate = 30
        total_frames = int(duration * frame_rate)

        bg = cv2.imread(background_path)
        if bg is None:
            raise RuntimeError("Failed to read background image.")
        bg = cv2.resize(bg, (1280, 720))

        out = cv2.VideoWriter(tmp_video, cv2.VideoWriter_fourcc(*"XVID"), frame_rate, (1280, 720))
        text = (script_text[:70] + "...") if len(script_text) > 70 else script_text

        for i in range(total_frames):
            frame = bg.copy()
            y_pos = 200 + int(60 * np.sin(i / 20))
            cv2.putText(frame, text, (50, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            out.write(frame)

        out.release()

        (
            ffmpeg
            .input(tmp_video)
            .input(voice_path)
            .output(final_video, vcodec="libx264", acodec="aac", shortest=True)
            .run(overwrite_output=True, quiet=True)
        )

        logging.info(f"✅ Generated: {final_video}")
        return final_video

def main(csv_path):
    if not os.path.exists(csv_path):
        logging.error(f"CSV not found: {csv_path}")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    required = {"Creative Problem", "Case Study", "Video Prompt"}
    missing = required - set(df.columns)
    if missing:
        logging.error(f"Missing columns: {', '.join(missing)}")
        sys.exit(1)

    for idx, row in df.iterrows():
        creative_problem = str(row.get("Creative Problem", "")).strip()
        case_study = str(row.get("Case Study", "")).strip()
        video_prompt = str(row.get("Video Prompt", "")).strip()

        script_text = f"{creative_problem}. {case_study}. {video_prompt}"
        prefix = f"video_{idx + 1}"

        logging.info(f"\n🎬 Generating video {idx + 1}: {creative_problem or 'Untitled'}")
        bg = fetch_background(creative_problem or "nature")

        try:
            generate_video(script_text, prefix, bg)
        except Exception as e:
            logging.error(f"Video {idx + 1} failed: {e}")

    os.system("zip -r production_package.zip *.mp4")
    logging.info("\n✅ All videos generated successfully!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python video_generator.py <your_csv_file>")
        sys.exit(1)
    main(sys.argv[1])
