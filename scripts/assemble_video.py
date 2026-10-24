import os
import sys
import argparse

# Asosiy mantiq run_pipeline.py da; bu skript uni bitta epizod uchun chaqiradi
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from run_pipeline import assemble_episode_video, assemble_episode_video_ffmpeg

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Asmo - video, 4 qatlamli audio va subtitr montaji")
    parser.add_argument("ep", help="Epizod nomi, masalan: ep02_plants")
    parser.add_argument("--engine", choices=["ffmpeg", "moviepy"], default="ffmpeg",
                        help="ffmpeg (standart, tez) yoki moviepy (asl, sekin)")
    args = parser.parse_args()

    if args.engine == "ffmpeg":
        assemble_episode_video_ffmpeg(args.ep)
    else:
        assemble_episode_video(args.ep)
