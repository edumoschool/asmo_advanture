import os
import json
from PIL import Image, ImageDraw, ImageFont, ImageOps

COVERS_JSON = "assets/cover_prompts.json"
EPISODES_ROOT = "episodes"
# Intro sarlavhasi bilan bir xil shrift (run_pipeline.py dagi TITLE_FONT)
TITLE_FONT = os.getenv("TITLE_FONT") or next(
    (p for p in (os.path.join(os.getenv("LOCALAPPDATA", ""), r"Microsoft\Windows\Fonts\Montserrat-Black.ttf"),
                 r"C:\Windows\Fonts\ariblk.ttf", r"C:\Windows\Fonts\arialbd.ttf") if os.path.exists(p)), None)

def add_title_to_covers():
    with open(COVERS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)["covers"]

    for ep_name, cfg in data.items():
        raw_path = os.path.join(EPISODES_ROOT, ep_name, "cover_raw.png")
        out_path = os.path.join(EPISODES_ROOT, ep_name, "cover_final.jpg")

        if not os.path.exists(raw_path):
            continue

        # Flow rasmlari aniq 9:16 emas (768x1376) - cho'zmasdan, markazdan kesib 1080x1920 ga keltirish
        img = ImageOps.fit(Image.open(raw_path).convert("RGB"), (1080, 1920), Image.LANCZOS)
        draw = ImageDraw.Draw(img)
        title = cfg["title_overlay_uz"]

        # Qalin va bolalarbop shrift (Montserrat Black yoki Arial Black)
        font = ImageFont.truetype(TITLE_FONT, cfg.get("font_size", 110)) if TITLE_FONT else ImageFont.load_default()

        # Matnni markazlashtirib, qora hoshiya (stroke) va sariq rang bilan yozish.
        # Profil to'ri Reelsni 3:4 ga kesadi (y=240..1680), sarlavha shu oraliqda qolishi kerak
        draw.multiline_text(
            (540, cfg.get("title_y", 430)),
            title,
            font=font,
            fill=(255, 230, 0),
            stroke_width=10,
            stroke_fill=(0, 0, 0),
            anchor="mm",
            align="center",
            spacing=12
        )

        img.save(out_path, quality=95)
        print(f"✅ Muqova tayyor: {out_path}")

if __name__ == "__main__":
    add_title_to_covers()