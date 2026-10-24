import os
import sys
import argparse

# Asosiy mantiq run_pipeline.py da; bu skript uni bitta epizod uchun chaqiradi
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from run_pipeline import generate_tts_for_episode

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Asmo - ElevenLabs TTS (o'zbekcha ovoz)")
    parser.add_argument("ep", help="Epizod nomi, masalan: ep02_plants")
    parser.add_argument("--force", action="store_true", help="Mavjud mp3 fayllarni qayta yaratish")
    args = parser.parse_args()

    generate_tts_for_episode(args.ep, force=args.force)
