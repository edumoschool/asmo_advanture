import os
import json
import argparse
import requests
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
SOUND_GEN_URL = "https://api.elevenlabs.io/v1/sound-generation"
AUDIO_PROMPTS_FILE = "assets/audio_prompts.json"
EPISODES_ROOT = "episodes"


def call_elevenlabs_sound_api(prompt, duration, influence, output_path, force=False):
    """ElevenLabs Sound Generation API ga murojaat qilish va mp3 saqlash"""
    if os.path.exists(output_path) and not force:
        print(f"  ⏭ Mavjud, o'tkazib yuborildi: {output_path}")
        return True

    headers = {
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    payload = {
        "text": prompt,
        "duration_seconds": duration,
        "prompt_influence": influence
    }

    print(f"  🎵 Generatsiya qilinmoqda ({duration}s): {os.path.basename(output_path)}...")
    res = requests.post(SOUND_GEN_URL, json=payload, headers=headers)

    if res.status_code == 200:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(res.content)
        print(f"  ✅ Saqlandi: {output_path}")
        return True
    else:
        print(f"  ❌ Xatolik ({output_path}): {res.status_code} - {res.text}")
        return False


def generate_audio_assets(target_ep="all", force=False):
    if not ELEVENLABS_API_KEY:
        print("❌ ELEVENLABS_API_KEY topilmadi! .env faylini tekshiring.")
        return

    with open(AUDIO_PROMPTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Umumiy (Global) musiqalarni yaratish
    print("\n🌍 Global musiqa fayllari tekshirilmoqda...")
    for key, item in data.get("global_assets", {}).items():
        out_path = os.path.join("assets", item["filename"])
        call_elevenlabs_sound_api(
            prompt=item["prompt"],
            duration=item["duration_seconds"],
            influence=item.get("prompt_influence", 0.7),
            output_path=out_path,
            force=force
        )

    # 2. Epizodlar bo'yicha musiqa va SFX larni yaratish
    episodes_data = data.get("episodes", {})
    ep_list = episodes_data.keys() if target_ep == "all" else [target_ep]

    for ep_name in ep_list:
        if ep_name not in episodes_data:
            print(f"⚠️ {ep_name} audio_prompts.json ichida topilmadi!")
            continue

        print(f"\n🎬 [{ep_name}] uchun Orqa fon musiqasi va SFX yaratilmoqda...")
        ep_cfg = episodes_data[ep_name]
        ep_audio_dir = os.path.join(EPISODES_ROOT, ep_name, "audio")
        ep_sfx_dir = os.path.join(ep_audio_dir, "sfx")

        # a) Epizodning maxsus fon musiqasi (bg_music.mp3)
        if "bg_music" in ep_cfg:
            bg = ep_cfg["bg_music"]
            call_elevenlabs_sound_api(
                prompt=bg["prompt"],
                duration=bg["duration_seconds"],
                influence=bg.get("prompt_influence", 0.7),
                output_path=os.path.join(ep_audio_dir, bg["filename"]),
                force=force
            )

        # b) Epizod muhit shovqini (ambience.mp3)
        if "ambience" in ep_cfg:
            amb = ep_cfg["ambience"]
            call_elevenlabs_sound_api(
                prompt=amb["prompt"],
                duration=amb["duration_seconds"],
                influence=amb.get("prompt_influence", 0.6),
                output_path=os.path.join(ep_audio_dir, amb["filename"]),
                force=force
            )

        # c) Har bir sahna uchun SFX (sfx/scene_01_sfx.mp3 ...)
        for sfx_item in ep_cfg.get("scene_sfx", []):
            scene_id = sfx_item["scene_id"]
            sfx_path = os.path.join(ep_sfx_dir, f"{scene_id}_sfx.mp3")
            call_elevenlabs_sound_api(
                prompt=sfx_item["prompt"],
                duration=sfx_item.get("duration_seconds", 4.0),
                influence=0.75,
                output_path=sfx_path,
                force=force
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ElevenLabs Music & SFX Generator")
    parser.add_argument("--ep", type=str, default="all", help="Epizod nomi (masalan: ep01_shadows) yoki 'all'")
    parser.add_argument("--force", action="store_true", help="Mavjud fayllarni qayta generatsiya qilish")
    args = parser.parse_args()

    generate_audio_assets(target_ep=args.ep, force=args.force)