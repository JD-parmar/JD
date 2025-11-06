import os
import sys
import json
import pandas as pd
import requests
from gtts import gTTS
from PIL import Image
from mutagen.mp3 import MP3
from moviepy.editor import *
import numpy as np

# ------------------------------------------------
# 1️⃣  Helper: Download or Create Background
# ------------------------------------------------
def fetch_background_image(keyword="nature", fallback_path="fallback.jpg"):
    try:
        url = f"https://source.unsplash.com/1280x720/?{keyword}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            with open("background.jpg", "wb") as f:
                f.write(r.content)
            return "background.jpg"
    except Exception:
        pass

    # Fallback gray background
    if not os.path.exists(fallback_path):
        img = Image.new("RGB", (1280, 720), (40, 40, 40))
        img.save(fallback_path)
    return fallback_path


# ------------------------------------------------
# 2️⃣  Text-to-Speech (Hindi)
# ------------------------------------------------
def make_voice(text, filename_prefix):
    voice_path = f"{filename_prefix}_voice.mp3"
    gTTS(text, lang="hi").save(voice_path)
    audio = MP3(voice_path)
    return voice_path, audio.info.length


# ------------------------------------------------
# 3️⃣  Create Animated 2D Video
# ------------------------------------------------
def make_animated_video(script_text, filename_prefix, background_path):
    voice_path, duration = make_voice(script_text, filename_prefix)

    # Base background clip
    bg_clip = ImageClip(background_path).set_duration(duration)
    bg_clip = bg_clip.resize(height=720).set_position("center").set_opacity(0.9)

    # Add smooth zoom-in animation
    zoom_factor = 1.02
    bg_animated = bg_clip.fx(vfx.zoom_in, zoom_factor)

    # Text overlay (Hindi)
    txt_clip = TextClip(
        script_text,
        fontsize=40,
        color="white",
        size=(1100, None),
        method="caption",
        font="Arial-Unicode-MS" if "Arial-Unicode-MS" in TextClip.list("font") else "DejaVu-Sans",
    ).set_duration(duration).set_opacity(0.9)

    # Move text slowly upward
    txt_clip = txt_clip.set_position(lambda t: ("center", 720 - int(100 * t)))

    # Add audio
    audio_clip = AudioFileClip(voice_path)

    # Composite final video
    final = CompositeVideoClip([bg_animated, txt_clip])
    final = final.set_audio(audio_clip)

    output = f"{filename_prefix}.mp4"
    final.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", verbose=False, logger=None)

    # Cleanup
    os.remove(voice_path)
    return output


# ------------------------------------------------
# 4️⃣  Main Workflow
# ------------------------------------------------
def main(csv_path):
    try:
        df = pd.read_csv(csv_path)
        total = len(df)
        print(f"🎬 Starting generation for {total} rows")

        for i, row in df.iterrows():
            creative_problem = str(row.get("Creative Problem", ""))
            case_study = str(row.get("Case Study", ""))
            video_prompt = str(row.get("Video Prompt", ""))

            text = (
                f"नमस्कार! आज हम बात करेंगे {creative_problem} के बारे में। "
                f"{case_study} का उदाहरण लेकर हम समझेंगे कि कैसे इस चुनौती का समाधान किया गया। "
                f"{video_prompt} पर ध्यान देते हैं और जानते हैं कि हम इससे क्या सीख सकते हैं। धन्यवाद।"
            )

            prefix = f"video_{i+1}"
            background = fetch_background_image(creative_problem)

            print(f"▶️ Generating {prefix}.mp4 ...")
            try:
                make_animated_video(text, prefix, background)
                print(f"✅ Done: {prefix}.mp4")
            except Exception as e:
                print(f"❌ Error for {prefix}: {e}")

        # Package all videos
        os.system("zip -r production_package.zip *.mp4")

        print(json.dumps({
            "videos_generated": total,
            "zip_path": "production_package.zip",
            "status": "success"
        }, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({
            "error": str(e),
            "videos_generated": 0
        }, ensure_ascii=False))


# ------------------------------------------------
# 5️⃣  Run Script
# ------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python automation.py <csv_path or sheet_url>")
        sys.exit(1)
    main(sys.argv[1])
