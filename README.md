📚 "Asmoning sarguzashtlari" — Claude Code & AI Production Guide
1. Loyiha Konsepsiyasi va Maqsadi
Format: Instagram Reels (9:16 vertikal, 1080x1920, 30–45 soniya).

Bosh qahramon: Asmo — 4–5 yoshli, qiziquvchan, sarguzashtsevar qizaloq (Pixar 3D animatsiya uslubida).

Musiqa va Audio: 4 qatlamli professional audio miksing (Asmo ovozi 100%, SFX 35%, Fon musiqasi 14%, Ambience muhit 8%).

Texnologik stek: Claude Code (Python / FFmpeg / MoviePy), Google Flow (Imagen 3 & Veo), ElevenLabs (TTS & Sound Generation API).

2. Loyiha Papka Strukturasi (Directory Structure)
Claude Code loyihani yaratayotganda quyidagi arxitekturaga amal qilishi shart:

asmo-reels/
├── assets/
│   ├── audio_prompts.json      # Barcha epizodlar uchun SFX va Musiqa promptlari
│   ├── main_bg_music.mp3       # Global fon musiqasi
│   └── outro_jingle.mp3        # Yakuniy jingle
├── episodes/
│   ├── ep01_shadows/
│   │   ├── prompts.json        # Sahnalar, image/video promptlar va ovoz matnlari
│   │   ├── videos/             # Google Flow'dan olingan scene_01.mp4 ... scene_08.mp4
│   │   └── audio/              # TTS, bg_music, ambience va sfx/ papkasi
│   ├── ep02_plants/
│   ├── ep03_toothbrush/
│   ├── ep04_bees/
│   └── ep05_sharing/
├── run_pipeline.py             # TTS, SFX va Video montajni boshqaruvchi bosh skript
└── .env                        # API kalitlar (ELEVENLABS_API_KEY)

3. Qahramonning Doimiyligi (Base Character Prompt)
Google Flow orqali har bir kadrda Asmo bir xil ko‘rinishi uchun har bir image_prompt boshiga quyidagi baza qo‘shiladi:

3D Pixar style animation, vertical 9:16 aspect ratio. Asmo, a cute 5-year-old Uzbek girl with big curious brown eyes, round cheeks, and black hair tied in two bouncy pigtails with yellow hairbands. She is wearing colorful yellow overalls over a white striped t-shirt, and red sneakers. Bright, warm lighting, high detail, 8k resolution.

4. Claude Code uchun Barcha Terminal Buyruqlari (Commands Guide)
Loyiha papkasida terminal ochib, Claude Code orqali quyidagi buyruqlarni ketma-ket bajarasiz:

🛠️ 1-Bosqich: Kutubxonalarni o‘rnatish va muhitni sozlash
"Loyiha uchun moviepy, requests, python-dotenv, imageio-ffmpeg kutubxonalarini o‘rnat. .env faylida ELEVENLABS_API_KEY borligini tekshir."

Kutubxonalar loyiha ichidagi .venv muhitiga o‘rnatilgan (moviepy 1.0.3). Buyruqlarni shu muhit orqali ishga tushiring:

.venv\Scripts\python run_pipeline.py --ep ep01_shadows --step tts

.env sozlamalari:
- ELEVENLABS_API_KEY — API kalit
- ELEVENLABS_VOICE_ID — Asmoning ovozi (hozir: "Asmo", ElevenLabs Voice Design orqali yaratilgan, AeyMh9juKpv8Lxr5gXFN; avvalgi Jessica takelari audio/voice_jessica_backup/ da)

Talaffuz: agar biror so‘z noto‘g‘ri o‘qilsa, sahnaga "voiceover_tts" qo‘shing — ovoz shu yozuvni o‘qiydi, subtitr esa "voiceover_uz" dan olinadi (masalan ep02 scene_04: "quydik" -> "kuydik").
- ELEVENLABS_MODEL — TTS modeli, standart eleven_v4 (eleven_multilingual_v2 o‘zbek tilini qo‘llamaydi)

🎙️ 2-Bosqich: Ovozlarni (TTS) generatsiya qilish
Barcha qismlar uchun Asmoning o‘zbekcha ovozlarini yaratish:

python run_pipeline.py --ep all --step tts

(Faqat bitta qism uchun: python run_pipeline.py --ep ep01_shadows --step tts)

🔊 3-Bosqich: SFX, Ambience va Fon musiqalarini yaratish
ElevenLabs Sound API orqali har bir sahna uchun maxsus effektlar va musiqalarni generatsiya qilish:

python run_pipeline.py --ep all --step sfx

🎬 4-Bosqich: Videolarni yig‘ish va Montaj qilish
Google Flow’dan yuklab olingan scene_01.mp4 ... scene_08.mp4 fayllarini videos/ papkalariga joylagach, tayyor Instagram Reel (_final_reel.mp4) ni yig‘ish:

python run_pipeline.py --ep all --step video

Standart montaj dvigateli — FFmpeg (bitta epizod ~2–3 daqiqa). Asl moviepy dvigateli ham qoldirilgan (natija bir xil, lekin ~19 daqiqa):

python run_pipeline.py --ep ep01_shadows --step video --engine moviepy

Flow kliplari 6 soniyalik. Sahna rejadagi 5 soniya davom etadi, ovoz uzunroq bo‘lsa — ovoz + o‘tish + 0.3 soniya (klip yetmasa, oxirgi kadr ushlab turiladi, ovoz kesilmaydi).

Intro (FFmpeg dvigatelida): har bir epizod ~4 soniyalik intro bilan boshlanadi — assets/intro.mp4 (Flow'da animatsiya qilingan; bo‘lmasa assets/intro.png sekin zoom bilan), "Asmoning sarguzashtlari" sarlavhasi va epizod nomi (prompts.json dagi episode_title dan), assets/intro_jingle.mp3 va Asmoning ovozi (audio/intro.mp3 — tts bosqichida avtomatik yaratiladi). Fon musiqasi introdan keyin boshlanadi.

Qo‘shiq (ixtiyoriy): prompts.json ga "song" bloki qo‘shilsa, epizod oxirida qo‘shiqli klip yig‘iladi — "file" (masalan assets/soyam_music.mp3), "start" (qo‘shiq qayerdan boshlanadi, soniya), "volume" (0.6 — epizod ovoziga moslangan), "scenes" (videos/song_01.mp4 ... — har birining "duration" i qo‘shiq qatoriga mos; oxirgisi qolgan vaqtni oladi) va "lyrics" (har bir qator va u kuylanadigan vaqt — ekranda ♪ bilan chiqadi). Qo‘shiq paytida fon musiqasi so‘nadi va outro jingle qo‘yilmaydi. Namuna: episodes/ep01_shadows/prompts.json.

Sahna o‘tishlari: har bir sahna keyingisiga 0.4 soniyada eriydi (video + audio). Ovoz o‘tish tugagach boshlanadi, subtitr o‘tish paytida yashiriladi. .env orqali o‘zgartirish mumkin: TRANSITION=fade (yoki fadewhite, smoothleft, circleopen ...), TRANSITION_DURATION=0.4 (0 = keskin kesish).

⚡ 5-Bosqich: To‘liq jarayonni bitta buyruqda bajarish (Barchasi)

python run_pipeline.py --ep all --step all

Epizod kodi,Nomi / Mavzusi,O‘rganiladigan bilim / Asosiy g‘oya
ep01_shadows,Soyalar siri,Yorug‘lik to‘silganda soya hosil bo‘lishi
ep02_plants,O‘simlik qanday chanqaydi?,O‘simliklar ildizi orqali suv ichishi
ep03_toothbrush,Tish cho‘tkasi — qahramon,Kuniga 2 mahal tish yuvish (gigiyena)
ep04_bees,Asalarilar nega vizzillaydi?,Qanot qoqish tezligi va asal yig‘ish
ep05_sharing,Bo‘lishish — bu baxt!,Do‘stlar bilan o‘yinchoqlarni bo‘lishish
