"""Generic single-page 'dua card' generator.

Given any hadith that centers on a dua (supplication), produces a single
1080x1920 PNG in this repo's house style:

    heading (small-medium, catchy, Urdu)
    narration prefix   (small — hadith text framing the dua)
    Arabic dua itself   (large — main focus)
    Urdu translation of the dua  (large — main focus)
    narration suffix   (small — concluding dialogue/context)
    reference footer   (fixed, small)

The prefix/suffix carry the surrounding hadith as context, deliberately
smaller than the dua + its translation, which stay the visual focus. This
mirrors the exact structure worked out interactively for the Fatah
Al-Rabani 5576 "dua for grief and anxiety" card — see SKILL.md in this
skill's directory for the full rationale and the cleaning rules to apply
before filling in CONTENT below.

Usage: edit the CONTENT block at the bottom of this file for the new
hadith, then run it (`python generate_dua_card.py`). It reuses
IslamicImageGenerator's adaptive-sizing/drawing helpers and this project's
configured Arabic/Urdu fonts, so the card matches house style without
wiring a new content type into main.py/config.json/state.json — this is a
one-off/on-demand generator, not a recurring daily content type.
"""
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

# .../daily_ayat_and_hadith/.claude/skills/dua-card-generator/reference/this_file.py
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from daily_ayat_hadith.image_generator import IslamicImageGenerator, LAYOUT_ENGINE

# Base font sizes (pre-scaling) settled on for this card type. These scale
# together via IslamicImageGenerator._calculate_adaptive_layout, so the
# small/large size RELATIONSHIP is what matters — the prefix/suffix must
# stay meaningfully smaller than the dua + its translation.
HEADING_SIZE = 60
PREFIX_SIZE = 36
ARABIC_SIZE = 62
URDU_SIZE = 50
SUFFIX_SIZE = 36
REFERENCE_SIZE = 38  # fixed, never scaled — matches ayat/hadith convention

TOP_MARGIN = 70
FOOTER_RESERVE = 100  # fixed reference line, not scaled


@dataclass
class DuaCardContent:
    heading: str            # catchy Urdu heading, e.g. "غم و پریشانی کی دعا"
    prefix: str             # small Urdu narration lead-in ending "...یہ دعا پڑھے:"
    arabic_dua: str         # the dua itself in Arabic, ONLY — no isnad/narration
    urdu_dua: str           # Urdu translation of the dua ONLY (not the narration)
    suffix: str             # small Urdu narration tail (what follows the dua)
    reference: str          # short bilingual/Urdu reference line, e.g.
                            # "الفتح الربانی، حدیث: ۵۵۷۶ — صحیح (مسند احمد: ۳۷۱۲)"
    output_filename: str    # e.g. "fatah_rabbani_5576_ghum_pareshani.png"
    arabic_font: Optional[str] = None  # key into config.json's available_arabic_fonts
                              # (e.g. "pdms", "indopak", "muhammadi", "qalam");
                              # None = use whatever config.json currently selects
                              # (same font the daily ayah generator uses)


class DuaCardGenerator(IslamicImageGenerator):
    def generate_dua_card(self, content: DuaCardContent) -> Image.Image:
        heading_font_path = self.urdu_font_path
        urdu_font_path = self.urdu_font_path

        if content.arabic_font:
            fonts_dir = Path(self.fonts_dir)
            arabic_font_path = fonts_dir / f"{content.arabic_font}.ttf"
        else:
            arabic_font_path = self.arabic_font_path

        content_blocks = [
            {'text': content.heading, 'font_size': HEADING_SIZE, 'font_path': heading_font_path,
             'type': 'single', 'spacing_after': 50},
            {'text': content.prefix, 'font_size': PREFIX_SIZE, 'font_path': urdu_font_path,
             'type': 'multi', 'line_spacing': 8, 'margin': 140, 'spacing_after': 55},
            {'text': content.arabic_dua, 'font_size': ARABIC_SIZE, 'font_path': arabic_font_path,
             'type': 'multi', 'line_spacing': 18, 'margin': 110, 'spacing_after': 60},
            {'text': content.urdu_dua, 'font_size': URDU_SIZE, 'font_path': urdu_font_path,
             'type': 'multi', 'line_spacing': 14, 'margin': 120, 'spacing_after': 55},
            {'text': content.suffix, 'font_size': SUFFIX_SIZE, 'font_path': urdu_font_path,
             'type': 'multi', 'line_spacing': 8, 'margin': 140, 'spacing_after': 0},
        ]

        max_content_height = self.height - TOP_MARGIN - FOOTER_RESERVE
        scaling = self._calculate_adaptive_layout(content_blocks, max_content_height)
        font_scale, spacing_scale = scaling['font_scale'], scaling['spacing_scale']

        # font_scale < ~0.7 here means the hadith is too long for this
        # single-page "small prefix/suffix, large dua" layout at a readable
        # size — split into a 2-page version instead (full Arabic on page
        # 1, full Urdu + reference on page 2) rather than accepting a
        # cramped page. See SKILL.md's "When content doesn't fit" section.
        if font_scale < 0.7:
            print(f"WARNING: font_scale={font_scale:.2f} — content is long for one page; "
                  f"consider the 2-page fallback described in SKILL.md instead of shrinking further.")

        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        heading_font = ImageFont.truetype(str(heading_font_path), int(HEADING_SIZE * font_scale), layout_engine=LAYOUT_ENGINE)
        prefix_font = ImageFont.truetype(str(urdu_font_path), int(PREFIX_SIZE * font_scale), layout_engine=LAYOUT_ENGINE)
        arabic_font = ImageFont.truetype(str(arabic_font_path), int(ARABIC_SIZE * font_scale), layout_engine=LAYOUT_ENGINE)
        urdu_font = ImageFont.truetype(str(urdu_font_path), int(URDU_SIZE * font_scale), layout_engine=LAYOUT_ENGINE)
        suffix_font = ImageFont.truetype(str(urdu_font_path), int(SUFFIX_SIZE * font_scale), layout_engine=LAYOUT_ENGINE)
        reference_font = ImageFont.truetype(str(urdu_font_path), REFERENCE_SIZE, layout_engine=LAYOUT_ENGINE)

        y = TOP_MARGIN

        y = self._draw_centered_text(draw, self._get_display_text(content.heading, use_raqm=True), y, heading_font, self.text_color)
        y += int(50 * spacing_scale)

        prefix_lines = self._wrap_text(self._get_display_text(content.prefix, use_raqm=True), prefix_font, self.width - 140)
        y = self._draw_multiline_centered(draw, prefix_lines, y, prefix_font, (90, 90, 90), int(8 * spacing_scale))
        y += int(55 * spacing_scale)

        arabic_lines = self._wrap_text(self._get_display_text(content.arabic_dua, use_raqm=True), arabic_font, self.width - 110)
        y = self._draw_multiline_centered(draw, arabic_lines, y, arabic_font, self.text_color, int(18 * spacing_scale))
        y += int(60 * spacing_scale)

        urdu_lines = self._wrap_text(self._get_display_text(content.urdu_dua, use_raqm=True), urdu_font, self.width - 120)
        y = self._draw_multiline_centered(draw, urdu_lines, y, urdu_font, self.text_color, int(14 * spacing_scale))
        y += int(55 * spacing_scale)

        suffix_lines = self._wrap_text(self._get_display_text(content.suffix, use_raqm=True), suffix_font, self.width - 140)
        self._draw_multiline_centered(draw, suffix_lines, y, suffix_font, (90, 90, 90), int(8 * spacing_scale))

        self._draw_centered_text(draw, self._get_display_text(content.reference, use_raqm=True), self.height - 80, reference_font, self.text_color)

        return img


def generate(content: DuaCardContent, out_dir: Optional[Path] = None) -> Path:
    """Render `content` and save it. Returns the saved path."""
    fonts_dir = PROJECT_ROOT / "fonts"
    config_file = PROJECT_ROOT / "config.json"
    gen = DuaCardGenerator(fonts_dir, config_file)
    img = gen.generate_dua_card(content)

    out_dir = out_dir or (PROJECT_ROOT / "output" / "dua_cards")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / content.output_filename
    img.save(out_path, quality=95)
    return out_path


# ---------------------------------------------------------------------------
# Edit this block for each new hadith, then run: python generate_dua_card.py
# ---------------------------------------------------------------------------
CONTENT = DuaCardContent(
    heading="غم و پریشانی کی دعا",
    prefix=(
        "رسول اللہ ‌صلی ‌اللہ ‌علیہ ‌وآلہ ‌وسلم نے فرمایا: جب بھی کسی کو کوئی فکر و غم اور رنج و "
        "ملال لاحق ہو اور وہ یہ دعا پڑھے:"
    ),
    arabic_dua=(
        "اللَّهُمَّ إِنِّي عَبْدُكَ، وَابْنُ عَبْدِكَ، وَابْنُ أَمَتِكَ، نَاصِيَتِي بِيَدِكَ، "
        "مَاضٍ فِيَّ حُكْمُكَ، عَدْلٌ فِيَّ قَضَاؤُكَ، أَسْأَلُكَ بِكُلِّ اسْمٍ هُوَ لَكَ سَمَّيْتَ بِهِ نَفْسَكَ، "
        "أَوْ عَلَّمْتَهُ أَحَدًا مِنْ خَلْقِكَ، أَوْ أَنْزَلْتَهُ فِي كِتَابِكَ، أَوْ اسْتَأْثَرْتَ بِهِ فِي عِلْمِ الْغَيْبِ عِنْدَكَ، "
        "أَنْ تَجْعَلَ الْقُرْآنَ رَبِيعَ قَلْبِي، وَنُورَ صَدْرِي، وَجِلَاءَ حُزْنِي، وَذَهَابَ هَمِّي"
    ),
    urdu_dua=(
        "اے اللہ! میں تیرا بندہ ہوں، تیرے بندے کا بیٹا ہوں اور تیری بندی کا بیٹا ہوں، "
        "میری پیشانی تیرے ہاتھ میں ہے، میرے بارے میں تیرا حکم جاری ہے اور میرے بارے میں تیرا "
        "فیصلہ عدل والا ہے، میں تجھ سے تیرے ہر اس خاص نام کے ساتھ سوال کرتا ہوں جو تو نے خود اپنا "
        "نام رکھا ہے یا اسے اپنی کتاب میں نازل کیا ہے یا اپنی مخلوق میں سے کسی کو سکھلایا ہے یا علم "
        "الغیب میں اسے اپنے پاس رکھنے کو ترجیح دی ہے کہ تو قرآن کو میرے دل کی بہار اور میرے سینے کا "
        "نور اور میرے غم کو دور کرنے والا اور میرے فکر کو لے جانے والا بنا دے"
    ),
    suffix=(
        "تو اللہ تعالیٰ اس کے فکر و غم اور رنج و ملال کو دور کرکے اس کے بدلے وسعت اور کشادگی عطا "
        "کرے گا۔ کہا گیا: اے اللہ کے رسول! کیا ہم یہ کلمات سیکھ نہ لیں؟ آپ ‌صلی ‌اللہ ‌علیہ ‌وآلہ "
        "‌وسلم نے فرمایا: کیوں نہیں، ہر سننے والے کو یاد کر لینے چاہئیں۔"
    ),
    reference="الفتح الربانی، حدیث: ۵۵۷۶ — صحیح (مسند احمد: ۳۷۱۲)",
    output_filename="fatah_rabbani_5576_ghum_pareshani.png",
)


if __name__ == "__main__":
    saved = generate(CONTENT)
    print(f"Saved: {saved}")
