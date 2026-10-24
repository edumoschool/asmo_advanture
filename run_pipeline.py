import os
import json
import argparse
import requests
import numpy as np
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# moviepy 1.0.3 resize() Image.ANTIALIAS ni chaqiradi, Pillow 10+ da u olib tashlangan
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
    CompositeAudioClip,
    concatenate_videoclips,
    afx
)

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "jBpfuIE2acCO8z3wKNLl")
# eleven_multilingual_v2 o'zbek tilini qo'llamaydi; eleven_v4 qo'llaydi
TTS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_v4")
TTS_LANGUAGE = os.getenv("ELEVENLABS_LANGUAGE", "uz")
SOUND_GEN_URL = "https://api.elevenlabs.io/v1/sound-generation"

SUBTITLE_FONT = os.getenv("SUBTITLE_FONT", r"C:\Windows\Fonts\arialbd.ttf")

EPISODES_ROOT = "episodes"
AUDIO_PROMPTS_FILE = "assets/audio_prompts.json"
SHARED_BG_MUSIC = "assets/main_bg_music.mp3"

# Ovoz balansi koeffitsiyentlari (Audio Mixing Levels)
VOL_VOICEOVER = 1.00  # 100% - Asosiy nutq (Asmo)
VOL_SFX       = 0.35  # 35%  - Sahna effektlari (sakrash, suv, asalari va h.k.)
VOL_BG_MUSIC  = 0.14  # 14%  - Orqa fon musiqasi
VOL_AMBIENCE  = 0.08  # 8%   - Tabiat yoki xona muhiti shovqini


SERIES_TITLE = "Asmoning sarguzashtlari"
INTRO_DURATION = 3.0  # Reels uchun qisqa intro (soniya)
INTRO_VIDEO = "assets/intro.mp4"   # Flow'da animatsiya qilingan intro (bo'lsa)
INTRO_IMAGE = "assets/intro.png"   # aks holda shu rasm sekin zoom bilan
INTRO_JINGLE = "assets/intro_jingle.mp3"
# Sahnalar orasidagi o'tish (FFmpeg xfade nomi: fade, fadewhite, smoothleft, circleopen ...) va davomiyligi; 0 = keskin kesish
TRANSITION = os.getenv("TRANSITION", "fade")
TRANSITION_DURATION = float(os.getenv("TRANSITION_DURATION", "0.4"))
TITLE_FONT = os.getenv("TITLE_FONT") or next(
    (p for p in (os.path.join(os.getenv("LOCALAPPDATA", ""), r"Microsoft\Windows\Fonts\Montserrat-Black.ttf"),
                 r"C:\Windows\Fonts\ariblk.ttf") if os.path.exists(p)), SUBTITLE_FONT)


def intro_title_image(series, episode_line, size=(1080, 1920)):
    """Intro sarlavhasi: yuqori uchdan birda katta sariq serial nomi, ostida oq epizod nomi (shaffof fon)"""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    navy = "#1B2A6B"

    def centered(text, font, y, fill, stroke):
        x = (size[0] - draw.textlength(text, font=font)) / 2
        draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=navy)

    big = ImageFont.truetype(TITLE_FONT, 128)
    y = 170
    for word in series.split():
        centered(word, big, y, "#FFD400", 12)
        y += 150

    small = ImageFont.truetype(TITLE_FONT, 60)
    line = ""
    for word in episode_line.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=small) > size[0] - 120 and line:
            centered(line, small, y + 20, "white", 7)
            y += 78
            line = word
        else:
            line = trial
    if line:
        centered(line, small, y + 20, "white", 7)
    return img


def intro_texts(data):
    """(serial nomi, epizod qatori, intro ovoz matni) - prompts.json dagi episode_title dan.
    Masalan: 'Asmoning sarguzashtlari - 1-qism: Soyalar siri' -> ('Asmoning sarguzashtlari', '1-qism: Soyalar siri', 'Asmoning sarguzashtlari! Soyalar siri!')"""
    title = data.get("episode_title", SERIES_TITLE)
    episode_line = title.split(" - ", 1)[1].strip() if " - " in title else ""
    name = episode_line.split(":", 1)[1].strip() if ":" in episode_line else episode_line
    voice = data.get("intro_voiceover_uz") or (
        f"{SERIES_TITLE}! {name}{'' if name[-1:] in '!?.' else '!'}" if name else f"{SERIES_TITLE}!")
    return SERIES_TITLE, episode_line, voice


def generate_tts_for_episode(ep_name, force=False):
    """1-QATLAM: ElevenLabs TTS orqali Asmoning ovozini yaratish"""
    ep_dir = os.path.join(EPISODES_ROOT, ep_name)
    prompts_file = os.path.join(ep_dir, "prompts.json")
    audio_dir = os.path.join(ep_dir, "audio")

    if not os.path.exists(prompts_file):
        print(f"⚠️ [{ep_name}] prompts.json topilmadi!")
        return False

    if not ELEVENLABS_API_KEY:
        print("❌ ELEVENLABS_API_KEY topilmadi! .env faylini tekshiring.")
        return False

    os.makedirs(audio_dir, exist_ok=True)

    with open(prompts_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }

    # Sahnalar + intro (serial nomi va epizod nomi Asmo ovozida). "voiceover_tts" bo'lsa, ovoz o'sha yozuvni o'qiydi
    # (talaffuzni tuzatish uchun, masalan "quydik" -> "kuydik"); subtitrlar baribir "voiceover_uz" dan olinadi.
    lines = [(s["scene_id"], s.get("voiceover_tts") or s["voiceover_uz"]) for s in data["scenes"]]
    lines.append(("intro", intro_texts(data)[2]))

    print(f"\n🎙 [{ep_name}] Voiceover (TTS) generatsiyasi boshlandi...")
    for scene_id, text_uz in lines:
        out_path = os.path.join(audio_dir, f"{scene_id}.mp3")

        if os.path.exists(out_path) and not force:
            print(f"  ⏭ {scene_id}.mp3 mavjud, o'tkazib yuborildi.")
            continue

        payload = {
            "text": text_uz,
            "model_id": TTS_MODEL,
            "language_code": TTS_LANGUAGE,
            "voice_settings": {
                "stability": 0.40,
                "similarity_boost": 0.80,
                "style": 0.65,
                "use_speaker_boost": True
            }
        }

        res = requests.post(url, json=payload, headers=headers)
        if res.status_code == 200:
            with open(out_path, "wb") as f_out:
                f_out.write(res.content)
            print(f"  ✅ Saqlandi: {scene_id}.mp3")
        else:
            print(f"  ❌ Xato ({scene_id}): {res.status_code} - {res.text}")

    return True


def call_sound_api(prompt, duration, influence, output_path, force=False):
    """ElevenLabs Sound Generation API yordamchi funksiyasi"""
    if os.path.exists(output_path) and not force:
        print(f"  ⏭ Mavjud: {os.path.basename(output_path)}")
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

    print(f"  🎵 Generatsiya ({duration}s): {os.path.basename(output_path)}...")
    res = requests.post(SOUND_GEN_URL, json=payload, headers=headers)

    if res.status_code == 200:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(res.content)
        print(f"  ✅ Saqlandi: {output_path}")
        return True
    else:
        print(f"  ❌ Xato ({output_path}): {res.status_code} - {res.text}")
        return False


def generate_sfx_and_music_for_episode(ep_name, force=False):
    """2, 3, 4-QATAMLAR: Epizod uchun SFX, Ambience va Fon musiqasini yaratish"""
    if not os.path.exists(AUDIO_PROMPTS_FILE):
        print(f"⚠️ {AUDIO_PROMPTS_FILE} topilmadi! SFX generatsiyasi o'tkazib yuborildi.")
        return False

    with open(AUDIO_PROMPTS_FILE, "r", encoding="utf-8") as f:
        audio_data = json.load(f)

    # Global musiqani tekshirish
    for _, item in audio_data.get("global_assets", {}).items():
        call_sound_api(
            prompt=item["prompt"],
            duration=item["duration_seconds"],
            influence=item.get("prompt_influence", 0.7),
            output_path=os.path.join("assets", item["filename"]),
            force=force
        )

    ep_cfg = audio_data.get("episodes", {}).get(ep_name)
    if not ep_cfg:
        print(f"⚠️ [{ep_name}] uchun audio_prompts.json da ma'lumot yo'q.")
        return False

    print(f"\n🔊 [{ep_name}] Musiqa, Ambience va SFX generatsiyasi...")
    ep_audio_dir = os.path.join(EPISODES_ROOT, ep_name, "audio")
    ep_sfx_dir = os.path.join(ep_audio_dir, "sfx")

    if "bg_music" in ep_cfg:
        bg = ep_cfg["bg_music"]
        call_sound_api(
            bg["prompt"], bg["duration_seconds"], bg.get("prompt_influence", 0.7),
            os.path.join(ep_audio_dir, bg["filename"]), force=force
        )

    if "ambience" in ep_cfg:
        amb = ep_cfg["ambience"]
        call_sound_api(
            amb["prompt"], amb["duration_seconds"], amb.get("prompt_influence", 0.6),
            os.path.join(ep_audio_dir, amb["filename"]), force=force
        )

    for sfx_item in ep_cfg.get("scene_sfx", []):
        scene_id = sfx_item["scene_id"]
        sfx_path = os.path.join(ep_sfx_dir, f"{scene_id}_sfx.mp3")
        call_sound_api(
            sfx_item["prompt"], sfx_item.get("duration_seconds", 4.0), 0.75,
            sfx_path, force=force
        )

    return True


def subtitle_clip(text, duration, width=920, fontsize=52):
    """Subtitr klipi (moviepy uchun)"""
    return ImageClip(np.array(subtitle_image(text, width, fontsize))).set_duration(duration)


def subtitle_image(text, width=920, fontsize=52):
    """Subtitr rasmi (sariq matn, qora kontur, shaffof fon) - ImageMagick talab qilmaydi"""
    font = ImageFont.truetype(SUBTITLE_FONT, fontsize)
    stroke = 3
    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if measure.textlength(trial, font=font) <= width - 2 * stroke or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)

    line_h = int(fontsize * 1.25)
    img = Image.new("RGBA", (width, line_h * len(lines) + 2 * stroke), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        x = (width - measure.textlength(ln, font=font)) / 2
        draw.text((x, stroke + i * line_h), ln, font=font, fill="yellow",
                  stroke_width=stroke, stroke_fill="black")
    return img


def assemble_episode_video(ep_name):
    """Barcha video kadrlar, 4 qatlamli audio miks va subtitrlarni yig'ish"""
    ep_dir = os.path.join(EPISODES_ROOT, ep_name)
    prompts_file = os.path.join(ep_dir, "prompts.json")
    videos_dir = os.path.join(ep_dir, "videos")
    audio_dir = os.path.join(ep_dir, "audio")
    sfx_dir = os.path.join(audio_dir, "sfx")
    output_file = os.path.join(ep_dir, f"{ep_name}_final_reel.mp4")

    if not os.path.exists(prompts_file):
        return False

    with open(prompts_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    scene_clips = []
    print(f"\n🎬 [{ep_name}] Video va 4-qatlamli Audio montaj boshlandi...")

    for scene in data["scenes"]:
        scene_id = scene["scene_id"]
        subtitle_text = scene["voiceover_uz"]

        video_path = os.path.join(videos_dir, f"{scene_id}.mp4")
        voice_path = os.path.join(audio_dir, f"{scene_id}.mp3")
        sfx_path   = os.path.join(sfx_dir, f"{scene_id}_sfx.mp3")

        if not os.path.exists(video_path):
            print(f"  ⚠️ Video topilmadi: {video_path}. Sahna tashlab ketildi.")
            continue

        video_clip = VideoFileClip(video_path).resize((1080, 1920))
        voice_clip = AudioFileClip(voice_path).volumex(VOL_VOICEOVER) if os.path.exists(voice_path) else None

        # Flow kliplari 6 s; sahnani rejadagi davomiylikka qisqartirish, lekin ovozni kesmaslik
        target = max(scene.get("duration", video_clip.duration), (voice_clip.duration + 0.3) if voice_clip else 0)
        if video_clip.duration > target:
            video_clip = video_clip.subclip(0, target)
        scene_duration = video_clip.duration
        scene_audio_layers = []

        # 1-Qatlam: Asmo ovozi (Voiceover - 100%)
        if voice_clip:
            if voice_clip.duration > scene_duration:
                voice_clip = voice_clip.subclip(0, scene_duration)
            scene_audio_layers.append(voice_clip)

        # 2-Qatlam: Sahna maxsus effekti (SFX - 35%)
        if os.path.exists(sfx_path):
            sfx_clip = AudioFileClip(sfx_path).volumex(VOL_SFX)
            # Agar SFX sahnadan uzun bo'lsa, sahna davomiyligiga moslab qirqish
            if sfx_clip.duration > scene_duration:
                sfx_clip = sfx_clip.subclip(0, scene_duration)
            scene_audio_layers.append(sfx_clip)

        # Sahna ovozi va SFX ni birlashtirish (Flow klipining o'z ovozi o'rniga)
        if scene_audio_layers:
            video_clip = video_clip.set_audio(CompositeAudioClip(scene_audio_layers).set_duration(scene_duration))
        else:
            video_clip = video_clip.without_audio()

        # Subtitr (Instagram Reels Safe Zone)
        txt_clip = subtitle_clip(subtitle_text, scene_duration).set_position(("center", 1420))

        combined_scene = CompositeVideoClip([video_clip, txt_clip])
        scene_clips.append(combined_scene)

    if not scene_clips:
        print(f"  ❌ [{ep_name}] Yig'ish uchun videolar topilmadi!")
        return False

    # Barcha sahnalarni ketma-ket ulash
    final_video = concatenate_videoclips(scene_clips, method="compose")
    total_duration = final_video.duration

    # Global audio qatlamlar ro'yxati (Sahnalarning o'z ovozi bilan boshlanadi)
    master_audio_tracks = []
    if final_video.audio is not None:
        master_audio_tracks.append(final_video.audio)

    # 3-Qatlam: Orqa fon musiqasi (14% balandlikda, choksiz loop)
    ep_bg_music = os.path.join(audio_dir, "bg_music.mp3")
    bg_path = ep_bg_music if os.path.exists(ep_bg_music) else SHARED_BG_MUSIC
    if os.path.exists(bg_path):
        print(f"  🎶 Fon musiqasi qo'shilmoqda ({int(VOL_BG_MUSIC*100)}%): {bg_path}")
        bg_clip = AudioFileClip(bg_path)
        bg_clip = afx.audio_loop(bg_clip, duration=total_duration).volumex(VOL_BG_MUSIC)
        master_audio_tracks.append(bg_clip)

    # 4-Qatlam: Muhit shovqini / Ambience (8% balandlikda, choksiz loop)
    amb_path = os.path.join(audio_dir, "ambience.mp3")
    if os.path.exists(amb_path):
        print(f"  🌿 Ambience qatlami qo'shilmoqda ({int(VOL_AMBIENCE*100)}%): {amb_path}")
        amb_clip = AudioFileClip(amb_path)
        amb_clip = afx.audio_loop(amb_clip, duration=total_duration).volumex(VOL_AMBIENCE)
        master_audio_tracks.append(amb_clip)

    # Yakuniy Outro Jingle (oxirgi 3.5 soniyada yumshoq qo'shiladi, agar mavjud bo'lsa)
    outro_path = "assets/outro_jingle.mp3"
    if os.path.exists(outro_path) and total_duration > 4:
        outro_clip = AudioFileClip(outro_path).volumex(0.25).set_start(total_duration - 3.8)
        master_audio_tracks.append(outro_clip)

    # Barcha 4 ta audio qatlamni yakuniy videoga biriktirish
    if master_audio_tracks:
        final_video = final_video.set_audio(CompositeAudioClip(master_audio_tracks))

    # Eksport qilish
    final_video.write_videofile(
        output_file,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="medium"
    )
    print(f"🎉 [{ep_name}] To'liq mikslangan Reel tayyor: {output_file}")
    return True


def media_duration(path):
    """Fayl davomiyligi (soniya) - ffmpeg orqali"""
    from moviepy.video.io.ffmpeg_reader import ffmpeg_parse_infos
    return ffmpeg_parse_infos(path)["duration"]


def assemble_episode_video_ffmpeg(ep_name, output_file=None):
    """moviepy bilan bir xil montaj (balanslar, qisqartirish, subtitr), lekin bitta FFmpeg chaqiruvida - bir necha marta tezroq"""
    import shutil
    import subprocess
    import tempfile
    import imageio_ffmpeg

    ep_dir = os.path.join(EPISODES_ROOT, ep_name)
    prompts_file = os.path.join(ep_dir, "prompts.json")
    videos_dir = os.path.join(ep_dir, "videos")
    audio_dir = os.path.join(ep_dir, "audio")
    sfx_dir = os.path.join(audio_dir, "sfx")
    output_file = output_file or os.path.join(ep_dir, f"{ep_name}_final_reel.mp4")

    if not os.path.exists(prompts_file):
        return False

    with open(prompts_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    ffmpeg = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()
    inputs, filters, parts = [], [], []
    fmt = "aformat=sample_rates=44100:channel_layouts=stereo"

    print(f"\n🎬 [{ep_name}] FFmpeg montaj boshlandi...")
    with tempfile.TemporaryDirectory() as tmp:
        n_in = 0

        def inp(path, loop=False, pre=()):
            nonlocal n_in
            inputs.extend(list(pre) + (["-stream_loop", "-1"] if loop else []) + ["-i", path])
            n_in += 1
            return n_in - 1

        T = TRANSITION_DURATION
        durs = []  # har bir bo'lakning (intro + sahnalar) davomiyligi

        # Intro: serial nomi + epizod nomi, jingle va Asmo ovozi (assets/intro.mp4, bo'lmasa assets/intro.png + zoom)
        intro_src = INTRO_VIDEO if os.path.exists(INTRO_VIDEO) else INTRO_IMAGE if os.path.exists(INTRO_IMAGE) else None
        if intro_src:
            intro_voice = os.path.join(audio_dir, "intro.mp3")
            intro_voice_len = media_duration(intro_voice) if os.path.exists(intro_voice) else 0
            d = max(INTRO_DURATION, intro_voice_len + 0.7)
            k = len(parts)
            if intro_src == INTRO_VIDEO:
                v = inp(INTRO_VIDEO)
                vsrc = (f"[{v}:v]tpad=stop_mode=clone:stop_duration=3,trim=0:{d:.3f},setpts=PTS-STARTPTS,"
                        f"scale=1080:1920:flags=lanczos,setsar=1,fps=30")
            else:
                v = inp(INTRO_IMAGE, pre=["-loop", "1", "-framerate", "30", "-t", f"{d:.3f}"])
                vsrc = (f"[{v}:v]scale=2160:3840:flags=lanczos,zoompan=z='1+0.06*on/{int(d * 30)}':"
                        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,setsar=1")
            title_png = os.path.join(tmp, "intro_title.png")
            intro_title_image(*intro_texts(data)[:2]).save(title_png)
            t = inp(title_png, pre=["-loop", "1", "-framerate", "30", "-t", f"{d:.3f}"])
            filters.append(f"{vsrc}[ib{k}];[{t}:v]format=rgba,fade=t=in:st=0.25:d=0.4:alpha=1[it{k}];"
                           f"[ib{k}][it{k}]overlay=0:0:shortest=1,format=yuv420p,settb=AVTB[v{k}]")

            layers = []
            if intro_voice_len:
                filters.append(f"[{inp(intro_voice)}:a]{fmt},volume={VOL_VOICEOVER},adelay=450|450[ivo{k}]")
                layers.append(f"[ivo{k}]")
            if os.path.exists(INTRO_JINGLE):
                filters.append(f"[{inp(INTRO_JINGLE)}:a]{fmt},volume=0.5[ij{k}]")
                layers.append(f"[ij{k}]")
            if layers:
                mix = f"amix=inputs={len(layers)}:normalize=0:duration=longest," if len(layers) > 1 else ""
                filters.append(f"{''.join(layers)}{mix}apad,atrim=0:{d:.3f},asetpts=PTS-STARTPTS[a{k}]")
            else:
                filters.append(f"anullsrc=r=44100:cl=stereo,atrim=0:{d:.3f}[a{k}]")
            parts.append(k)
            durs.append(d)
            print(f"  ✨ Intro qo'shildi ({d:.1f}s): {intro_src}")
        intro_len = durs[0] if durs else 0.0

        for scene in data["scenes"]:
            scene_id = scene["scene_id"]
            video_path = os.path.join(videos_dir, f"{scene_id}.mp4")
            voice_path = os.path.join(audio_dir, f"{scene_id}.mp3")
            sfx_path = os.path.join(sfx_dir, f"{scene_id}_sfx.mp3")

            if not os.path.exists(video_path):
                print(f"  ⚠️ Video topilmadi: {video_path}. Sahna tashlab ketildi.")
                continue

            # Ovoz oldingi sahnadan o'tish tugagach boshlanadi; sahna rejadagi davomiylik yoki ovoz + o'tish + 0.3 s
            # (qaysi biri uzun bo'lsa). Ovoz klipdan uzun bo'lsa, oxirgi kadr ushlab turiladi - ovoz kesilmaydi.
            k = len(parts)
            lead = T if k > 0 else 0.0
            clip_len = media_duration(video_path)
            voice_len = media_duration(voice_path) if os.path.exists(voice_path) else None
            dur = max(scene.get("duration", clip_len), (voice_len + lead + 0.3) if voice_len else 0)

            sub_png = os.path.join(tmp, f"{scene_id}.png")
            subtitle_image(scene["voiceover_uz"]).save(sub_png)

            v, s = inp(video_path), inp(sub_png)
            # Subtitr o'tishlar paytida ko'rinmaydi, shunda ikki sahnaning matni ustma-ust tushmaydi
            filters.append(
                f"[{v}:v]tpad=stop_mode=clone:stop_duration={dur:.3f},trim=0:{dur:.3f},setpts=PTS-STARTPTS,"
                f"scale=1080:1920:flags=lanczos,setsar=1,fps=30[vb{k}];"
                f"[vb{k}][{s}:v]overlay=x=(W-w)/2:y=1420:eof_action=repeat:enable='between(t,{lead:.3f},{dur - T:.3f})',"
                f"format=yuv420p,settb=AVTB[v{k}]"
            )

            layers = []
            if voice_len:
                ms = int(lead * 1000)
                filters.append(f"[{inp(voice_path)}:a]{fmt},volume={VOL_VOICEOVER},adelay={ms}|{ms}[vo{k}]")
                layers.append(f"[vo{k}]")
            if os.path.exists(sfx_path):
                filters.append(f"[{inp(sfx_path)}:a]{fmt},volume={VOL_SFX}[sx{k}]")
                layers.append(f"[sx{k}]")
            if layers:
                # Ovoz + SFX yig'indisi (moviepy CompositeAudioClip kabi, normalizatsiyasiz), sahna uzunligiga moslab
                mix = f"amix=inputs={len(layers)}:normalize=0:duration=longest," if len(layers) > 1 else ""
                filters.append(f"{''.join(layers)}{mix}apad,atrim=0:{dur:.3f},asetpts=PTS-STARTPTS[a{k}]")
            else:
                filters.append(f"anullsrc=r=44100:cl=stereo,atrim=0:{dur:.3f}[a{k}]")

            parts.append(k)
            durs.append(dur)

        # Qo'shiq (prompts.json "song"): epizod oxirida Asmo raqsga tushib kuylaydi. Klip almashinuvi qo'shiq
        # qatorlari bilan bir vaqtda keskin (ritmda), qo'shiq so'zlari ekranda chiqadi.
        song = data.get("song")
        song_len = 0.0
        if song and os.path.exists(song.get("file", "")):
            s_start = float(song.get("start", 0))
            s_end = float(song.get("end", media_duration(song["file"])))
            song_paths = [os.path.join(videos_dir, f"{sc['scene_id']}.mp4") for sc in song["scenes"]]
            missing = [p for p in song_paths if not os.path.exists(p)]
            if missing:
                print(f"  ⚠️ Qo'shiq kliplari yetishmayapti ({len(missing)} ta), qo'shiq qo'shilmadi: {missing[0]}")
            else:
                song_len = s_end - s_start
                k = len(parts)
                fixed = sum(sc["duration"] for sc in song["scenes"][:-1])
                labels = []
                for i, (sc, path) in enumerate(zip(song["scenes"], song_paths)):
                    d = sc["duration"] if i < len(song_paths) - 1 else song_len - fixed
                    filters.append(f"[{inp(path)}:v]tpad=stop_mode=clone:stop_duration={d:.3f},trim=0:{d:.3f},setpts=PTS-STARTPTS,"
                                   f"scale=1080:1920:flags=lanczos,setsar=1,fps=30[sv{k}_{i}]")
                    labels.append(f"[sv{k}_{i}]")
                chain = f"{''.join(labels)}concat=n={len(labels)}:v=1:a=0"
                for j, ly in enumerate(song.get("lyrics", [])):
                    png = os.path.join(tmp, f"lyric_{j}.png")
                    subtitle_image(ly["text"]).save(png)
                    lyric_in = inp(png)
                    filters.append(f"{chain}[sl{k}_{j}]")
                    chain = (f"[sl{k}_{j}][{lyric_in}:v]overlay=x=(W-w)/2:y=1420:eof_action=repeat:"
                             f"enable='between(t,{ly['start'] - s_start:.3f},{ly['end'] - s_start:.3f})'")
                # Qo'shiq asl oxiridan oldin kesilsa ("end"), oxirgi 1.5 s da tovush ham, rasm ham sekin so'nadi
                cut_short = s_end < media_duration(song["file"]) - 0.1
                fade_v = f",fade=t=out:st={song_len - 1.5:.3f}:d=1.5" if cut_short else ""
                fade_a = f",afade=t=out:st={song_len - 1.5:.3f}:d=1.5" if cut_short else ""
                filters.append(f"{chain}{fade_v},format=yuv420p,settb=AVTB[v{k}]")
                filters.append(f"[{inp(song['file'])}:a]atrim={s_start:.3f}:{s_end:.3f},asetpts=PTS-STARTPTS,{fmt},"
                               f"volume={song.get('volume', 1.0)}{fade_a}[a{k}]")
                parts.append(k)
                durs.append(song_len)
                print(f"  🎵 Qo'shiq qo'shildi ({song_len:.1f}s): {song['file']}")

        if not parts:
            print(f"  ❌ [{ep_name}] Yig'ish uchun videolar topilmadi!")
            return False

        if T > 0 and len(parts) > 1:
            # Har bir bo'lak keyingisiga T soniyada eriydi (video xfade + audio acrossfade)
            prev_v, prev_a, offset = f"[v{parts[0]}]", f"[a{parts[0]}]", 0.0
            for i, k in enumerate(parts[1:], 1):
                offset += durs[i - 1] - T
                out_v = "[vcat]" if i == len(parts) - 1 else f"[xv{i}]"
                out_a = "[acat]" if i == len(parts) - 1 else f"[xa{i}]"
                filters.append(f"{prev_v}[v{k}]xfade=transition={TRANSITION}:duration={T:.3f}:offset={offset:.3f}{out_v}")
                filters.append(f"{prev_a}[a{k}]acrossfade=d={T:.3f}:c1=tri:c2=tri{out_a}")
                prev_v, prev_a = out_v, out_a
            total = sum(durs) - T * (len(parts) - 1)
        else:
            filters.append("".join(f"[v{k}][a{k}]" for k in parts) + f"concat=n={len(parts)}:v=1:a=1[vcat][acat]")
            total = sum(durs)

        # Global qatlamlar: fon musiqasi 14%, ambience 8% (loop, intro jingle bilan to'qnashmasligi uchun introdan keyin), outro jingle oxirida
        master = ["[acat]"]
        music_start = max(0.0, intro_len - T) if intro_len else 0.0
        # Qo'shiq bo'lsa, fon musiqasi va ambience qo'shiq boshlanishida so'nadi (1 s), outro jingle esa qo'yilmaydi
        music_end = (total - song_len + T) if song_len else total
        body = music_end - music_start
        tail = f",afade=t=out:st={max(0.0, body - 1.0):.3f}:d=1" if song_len else ""
        delay = f",adelay={int(music_start * 1000)}|{int(music_start * 1000)}" if music_start else ""
        ep_bg_music = os.path.join(audio_dir, "bg_music.mp3")
        bg_path = ep_bg_music if os.path.exists(ep_bg_music) else SHARED_BG_MUSIC
        if os.path.exists(bg_path):
            filters.append(f"[{inp(bg_path, loop=True)}:a]{fmt},volume={VOL_BG_MUSIC},atrim=0:{body:.3f}{tail}{delay}[bg]")
            master.append("[bg]")
        amb_path = os.path.join(audio_dir, "ambience.mp3")
        if os.path.exists(amb_path):
            filters.append(f"[{inp(amb_path, loop=True)}:a]{fmt},volume={VOL_AMBIENCE},atrim=0:{body:.3f}{tail}{delay}[amb]")
            master.append("[amb]")
        outro_path = "assets/outro_jingle.mp3"
        if os.path.exists(outro_path) and total > 4 and not song_len:
            ms = int((total - 3.8) * 1000)
            filters.append(f"[{inp(outro_path)}:a]{fmt},volume=0.25,adelay={ms}|{ms}[outro]")
            master.append("[outro]")
        filters.append(f"{''.join(master)}amix=inputs={len(master)}:normalize=0:duration=first[aout]")

        cmd = [ffmpeg, "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filters),
               "-map", "[vcat]", "-map", "[aout]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
               "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_file]
        result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ❌ FFmpeg xatosi: {result.stderr.strip()[-800:]}")
        return False
    print(f"🎉 [{ep_name}] Reel tayyor ({total:.1f}s): {output_file}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Asmo Reels - 4-Layer Audio & Video Pipeline")
    parser.add_argument(
        "--ep",
        type=str,
        default="all",
        help="Epizod nomi (masalan: ep01_shadows) yoki 'all'"
    )
    parser.add_argument(
        "--step",
        type=str,
        choices=["tts", "sfx", "video", "all"],
        default="all",
        help="Bosqich: tts (ovoz), sfx (musiqa va effektlar), video (montaj), yoki all (barchasi)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Mavjud audio fayllarni qayta generatsiya qilish"
    )
    parser.add_argument(
        "--engine",
        choices=["ffmpeg", "moviepy"],
        default="ffmpeg",
        help="Montaj dvigateli: ffmpeg (standart, ~7x tezroq) yoki moviepy (asl, sekin)"
    )

    args = parser.parse_args()

    if args.ep == "all":
        episodes = sorted([
            d for d in os.listdir(EPISODES_ROOT)
            if os.path.isdir(os.path.join(EPISODES_ROOT, d))
        ])
    else:
        episodes = [args.ep]

    for ep in episodes:
        if args.step in ["tts", "all"]:
            generate_tts_for_episode(ep, force=args.force)
        if args.step in ["sfx", "all"]:
            generate_sfx_and_music_for_episode(ep, force=args.force)
        if args.step in ["video", "all"]:
            if args.engine == "ffmpeg":
                assemble_episode_video_ffmpeg(ep)
            else:
                assemble_episode_video(ep)


if __name__ == "__main__":
    main()