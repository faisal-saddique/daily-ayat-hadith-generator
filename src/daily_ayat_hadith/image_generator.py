"""Image generator for daily Ayat and Hadith graphics."""

from PIL import Image, ImageDraw, ImageFont
import textwrap
from pathlib import Path
from datetime import datetime, timedelta
from hijridate import Hijri, Gregorian
import json

# Use RAQM layout engine for proper complex text rendering
LAYOUT_ENGINE = ImageFont.Layout.RAQM


class IslamicImageGenerator:
    """Generate beautiful Islamic images for Ayat and Hadith."""

    def __init__(self, fonts_dir: Path, config_file: Path = None):
        self.fonts_dir = fonts_dir
        self.width = 1080
        self.height = 1920
        self.bg_color = (245, 245, 245)  # Light gray background
        self.text_color = (0, 0, 0)  # Black text
        self.hijri_offset_days = 0  # Default: no offset

        # Load font configuration
        if config_file is None:
            config_file = fonts_dir.parent / "config.json"

        self._load_font_config(config_file)

    def _load_font_config(self, config_file: Path):
        """Load font configuration from config file."""
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

                # Load Hijri offset
                self.hijri_offset_days = config.get('hijri_offset_days', 0)

                font_config = config.get('fonts', {})

                # Get selected fonts
                arabic_font_name = font_config.get('arabic', 'pdms')
                urdu_font_name = font_config.get('urdu', 'jameelnoorinastaleeq')

                # Get font paths
                arabic_fonts = font_config.get('available_arabic_fonts', {})
                urdu_fonts = font_config.get('available_urdu_fonts', {})

                arabic_font_rel = arabic_fonts.get(arabic_font_name, 'fonts/pdms.ttf')
                urdu_font_rel = urdu_fonts.get(urdu_font_name, 'fonts/jameelnoorinastaleeq.ttf')

                # Convert to absolute paths
                self.arabic_font_path = self.fonts_dir.parent / arabic_font_rel
                self.urdu_font_path = self.fonts_dir.parent / urdu_font_rel
        else:
            # Fallback to default fonts
            self.arabic_font_path = self.fonts_dir / "pdms.ttf"
            self.urdu_font_path = self.fonts_dir / "jameelnoorinastaleeq.ttf"

    def _get_display_text(self, text: str, use_raqm: bool = False) -> str:
        """Reshape and reverse Arabic/Urdu text for proper display.

        When using RAQM layout engine, text shaping is handled automatically,
        so we don't need to use arabic_reshaper and bidi.
        """
        if use_raqm:
            # RAQM handles all text shaping and bidi automatically
            return text
        else:
            # For non-RAQM fonts, use manual reshaping
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)

    def _replace_arabic_symbols_for_english(self, text: str) -> str:
        """Replace Arabic Islamic symbols with English equivalents for English text rendering.

        This is needed because English fonts like Helvetica don't support Arabic Unicode characters.
        Handles cases where text may already contain English equivalents to avoid duplicates.
        """
        replacements = {
            '\uFDFA': '(peace be upon him)',  # ﷺ SALLALLAHU ALAYHI WASALLAM
            '\uFDFD': '',  # ﷺ BISMILLAH AR-RAHMAN AR-RAHEEM
            '\u0635\u0644\u0649 \u0627\u0644\u0644\u0647 \u0639\u0644\u064A\u0647 \u0648\u0633\u0644\u0645': '(peace be upon him)',  # صلى الله عليه وسلم
            '\u0639\u0644\u064A\u0647 \u0627\u0644\u0633\u0644\u0627\u0645': '(peace be upon him)',  # عليه السلام (alaihis salaam)
            '\u0631\u0636\u064A \u0627\u0644\u0644\u0647 \u0639\u0646\u0647': '(may Allah be pleased with him)',  # رضي الله عنه (radiyallahu anhu)
            '\u0631\u0636\u064A \u0627\u0644\u0644\u0647 \u0639\u0646\u0647\u0627': '(may Allah be pleased with her)',  # رضي الله عنها (radiyallahu anha)
        }

        for arabic, english in replacements.items():
            # Only replace if the replacement text doesn't already exist next to the Arabic symbol
            # This prevents double replacements like "((peace be upon him))"
            if arabic in text:
                # Check if the English equivalent already appears adjacent to the Arabic symbol
                if english and f"{english}{arabic}" in text:
                    # English already there before symbol, just remove the symbol
                    text = text.replace(f"{english}{arabic}", english)
                elif english and f"{arabic}{english}" in text:
                    # English already there after symbol, just remove the symbol
                    text = text.replace(f"{arabic}{english}", english)
                else:
                    # Normal replacement
                    text = text.replace(arabic, english)

        return text

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
        """Wrap text to fit within max width."""
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = font.getbbox(test_line)
            width = bbox[2] - bbox[0]

            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]

        if current_line:
            lines.append(' '.join(current_line))

        return lines

    def _draw_centered_text(self, draw: ImageDraw.Draw, text: str, y: int,
                           font: ImageFont.FreeTypeFont, color: tuple) -> int:
        """Draw centered text and return the next Y position."""
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (self.width - text_width) // 2
        draw.text((x, y), text, font=font, fill=color)
        return y + text_height

    def _draw_multiline_centered(self, draw: ImageDraw.Draw, lines: list[str], y: int,
                                font: ImageFont.FreeTypeFont, color: tuple,
                                line_spacing: int = 10) -> int:
        """Draw multiple centered lines and return next Y position."""
        for line in lines:
            y = self._draw_centered_text(draw, line, y, font, color)
            y += line_spacing
        return y

    def _calculate_text_height(self, lines: list[str], font: ImageFont.FreeTypeFont, line_spacing: int) -> int:
        """Calculate total height needed for multiline text."""
        if not lines:
            return 0
        total_height = 0
        for line in lines:
            bbox = font.getbbox(line)
            total_height += (bbox[3] - bbox[1]) + line_spacing
        return total_height - line_spacing  # Remove last line spacing

    def _calculate_adaptive_layout(self, content_blocks: list[dict], max_height: int) -> dict:
        """Calculate optimal font sizes and spacing to fit content within max_height.
        Scales up for short content, scales down for long content.

        Args:
            content_blocks: List of dicts with 'text', 'font_size', 'type' (single/multi), 'spacing_after'
            max_height: Maximum available height

        Returns:
            Dict with 'font_scale' and 'spacing_scale' factors
        """
        def calculate_height(f_scale: float, s_scale: float) -> int:
            """Helper to calculate total height for given scales."""
            total = 80  # Starting Y position
            for block in content_blocks:
                scaled_font_size = int(block['font_size'] * f_scale)
                # Create temporary font for calculation
                if 'Amiri' in str(block.get('font_path', '')):
                    temp_font = ImageFont.truetype(str(block['font_path']), scaled_font_size, layout_engine=LAYOUT_ENGINE)
                elif 'Noto' in str(block.get('font_path', '')):
                    temp_font = ImageFont.truetype(str(block['font_path']), scaled_font_size, layout_engine=LAYOUT_ENGINE)
                else:
                    temp_font = ImageFont.truetype(block.get('font_path', '/System/Library/Fonts/Helvetica.ttc'), scaled_font_size)

                if block['type'] == 'multi':
                    lines = self._wrap_text(block['text'], temp_font, self.width - block.get('margin', 100))
                    line_spacing = int(block.get('line_spacing', 10) * s_scale)
                    block_height = self._calculate_text_height(lines, temp_font, line_spacing)
                else:
                    bbox = temp_font.getbbox(block['text'])
                    block_height = bbox[3] - bbox[1]

                total += block_height + int(block.get('spacing_after', 0) * s_scale)

            total += 220  # Min space for reference + date (increased buffer for long content)
            return total

        def check_width_fits(f_scale: float) -> bool:
            """Check if all single-line text blocks fit within image width."""
            for block in content_blocks:
                if block['type'] == 'single':
                    scaled_font_size = int(block['font_size'] * f_scale)
                    # Create temporary font
                    if 'Amiri' in str(block.get('font_path', '')):
                        temp_font = ImageFont.truetype(str(block['font_path']), scaled_font_size, layout_engine=LAYOUT_ENGINE)
                    elif 'Noto' in str(block.get('font_path', '')):
                        temp_font = ImageFont.truetype(str(block['font_path']), scaled_font_size, layout_engine=LAYOUT_ENGINE)
                    else:
                        temp_font = ImageFont.truetype(block.get('font_path', '/System/Library/Fonts/Helvetica.ttc'), scaled_font_size)

                    bbox = temp_font.getbbox(block['text'])
                    text_width = bbox[2] - bbox[0]
                    # Check if text fits with some margin
                    if text_width > self.width - 40:  # 40px total margin (20px on each side)
                        return False
            return True

        # First check if content fits at normal scale
        base_height = calculate_height(1.0, 1.0)

        # If content doesn't fill most of the space (< 90%), scale UP aggressively
        if base_height < max_height * 0.90:
            font_scale = 1.0
            spacing_scale = 1.0

            # Try progressively larger scales - be VERY aggressive with scaling
            # Target: fill 88-95% of available space for optimal aesthetics
            scale_increments = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0]

            for scale_increment in scale_increments:
                test_font_scale = 1.0 + scale_increment
                test_spacing_scale = 1.0 + (scale_increment * 0.9)  # Scale spacing proportionally

                test_height = calculate_height(test_font_scale, test_spacing_scale)

                # Check both height AND width constraints
                # Aim to fill 88-97% of space (was 75-95% before - too conservative)
                height_fits = test_height <= max_height * 0.97  # Leave only 3% buffer
                width_fits = check_width_fits(test_font_scale)

                if height_fits and width_fits:
                    font_scale = test_font_scale
                    spacing_scale = test_spacing_scale
                else:
                    break  # Found the limit

            return {'font_scale': min(font_scale, 3.0), 'spacing_scale': min(spacing_scale, 2.5)}

        # If content fits at normal scale, use it
        if base_height <= max_height:
            return {'font_scale': 1.0, 'spacing_scale': 1.0}

        # Content is too large - scale DOWN
        font_scale = 1.0
        spacing_scale = 1.0

        for attempt in range(10):
            total_height = calculate_height(font_scale, spacing_scale)

            if total_height <= max_height:
                return {'font_scale': font_scale, 'spacing_scale': spacing_scale}

            # Progressively reduce scaling - prioritize spacing reduction first to maintain readability
            if attempt < 3:
                spacing_scale -= 0.12  # Reduce spacing first
            elif attempt < 6:
                font_scale -= 0.05  # Then reduce font size gradually
                spacing_scale -= 0.05
            else:
                font_scale -= 0.04  # Final gentle reductions
                spacing_scale -= 0.04

        # Return final scaling with higher minimums for better readability
        # Balance between readability and fitting all content
        return {'font_scale': max(font_scale, 0.57), 'spacing_scale': max(spacing_scale, 0.40)}

    def generate_ayat_image(self, surah_number: int, ayah_number: int,
                           arabic_text: str, urdu_translation: str,
                           english_translation: str, surah_name: str,
                           date: datetime) -> list[Image.Image]:
        """Generate Ayat image(s). Returns a list of images - single image for short ayat, two images for long ones."""

        aoozubillah_bismillah = "أَعُوذُ بِاللَّهِ مِنَ الشَّيْطَانِ الرَّجِيمِ ۞ بِسۡمِ اللّٰهِ الرَّحۡمٰنِ الرَّحِیۡمِ ۞"
        arabic_with_symbol = arabic_text + " ۞"
        english_clean = self._replace_arabic_symbols_for_english(english_translation)

        # Check if we need multi-page layout
        content_blocks = [
            {'text': aoozubillah_bismillah, 'font_size': 54, 'font_path': self.arabic_font_path, 'type': 'single', 'spacing_after': 60},
            {'text': self._get_display_text(arabic_with_symbol, use_raqm=True), 'font_size': 75, 'font_path': self.arabic_font_path, 'type': 'multi', 'line_spacing': 20, 'margin': 100, 'spacing_after': 80},
            {'text': self._get_display_text(urdu_translation, use_raqm=True), 'font_size': 60, 'font_path': self.urdu_font_path, 'type': 'multi', 'line_spacing': 15, 'margin': 120, 'spacing_after': 60},
            {'text': english_clean, 'font_size': 52, 'font_path': '/System/Library/Fonts/Helvetica.ttc', 'type': 'multi', 'line_spacing': 12, 'margin': 150, 'spacing_after': 60},
        ]

        max_content_height = self.height - 160
        scaling = self._calculate_adaptive_layout(content_blocks, max_content_height)

        # If scaling is too small (fonts would be cramped), use multi-page layout
        if scaling['font_scale'] < 0.75:
            return self._generate_ayat_multipage(
                surah_number, ayah_number, arabic_text, urdu_translation,
                english_translation, surah_name, date
            )

        # Otherwise use single-page layout
        return [self._generate_ayat_single_page(
            surah_number, ayah_number, arabic_text, urdu_translation,
            english_translation, surah_name, date, scaling
        )]

    def _generate_ayat_single_page(self, surah_number: int, ayah_number: int,
                                   arabic_text: str, urdu_translation: str,
                                   english_translation: str, surah_name: str,
                                   date: datetime, scaling: dict) -> Image.Image:
        """Generate a single-page ayat image."""

        # Create image
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        aoozubillah_bismillah = "أَعُوذُ بِاللَّهِ مِنَ الشَّيْطَانِ الرَّجِيمِ ۞ بِسۡمِ اللّٰهِ الرَّحۡمٰنِ الرَّحِیۡمِ ۞"
        arabic_with_symbol = arabic_text + " ۞"
        english_clean = self._replace_arabic_symbols_for_english(english_translation)

        # Load fonts with calculated scaling
        header_font = ImageFont.truetype(str(self.arabic_font_path), int(54 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        arabic_font = ImageFont.truetype(str(self.arabic_font_path), int(75 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        urdu_font = ImageFont.truetype(str(self.urdu_font_path), int(60 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        english_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(52 * scaling['font_scale']))
        reference_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
        date_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 38)

        y = 80

        # A'oodhu billah + Bismillah (RAQM handles text shaping automatically)
        header_display = self._get_display_text(aoozubillah_bismillah, use_raqm=True)
        y = self._draw_centered_text(draw, header_display, y, header_font, self.text_color)
        y += int(60 * scaling['spacing_scale'])

        # Arabic text with symbol (RAQM handles text shaping automatically)
        arabic_display = self._get_display_text(arabic_with_symbol, use_raqm=True)
        arabic_lines = self._wrap_text(arabic_display, arabic_font, self.width - 100)
        y = self._draw_multiline_centered(draw, arabic_lines, y, arabic_font, self.text_color, int(20 * scaling['spacing_scale']))
        y += int(80 * scaling['spacing_scale'])

        # Urdu translation (RAQM handles text shaping automatically)
        urdu_display = self._get_display_text(urdu_translation, use_raqm=True)
        urdu_lines = self._wrap_text(urdu_display, urdu_font, self.width - 120)
        y = self._draw_multiline_centered(draw, urdu_lines, y, urdu_font, self.text_color, int(15 * scaling['spacing_scale']))
        y += int(60 * scaling['spacing_scale'])

        # English translation (already cleaned in content_blocks calculation)
        english_lines = self._wrap_text(english_clean, english_font, self.width - 150)
        y = self._draw_multiline_centered(draw, english_lines, y, english_font, self.text_color, int(12 * scaling['spacing_scale']))
        y += int(60 * scaling['spacing_scale'])

        # Reference
        reference = f"({surah_name} {ayah_number})"
        y = self._draw_centered_text(draw, reference, y, reference_font, self.text_color)

        # Date (Islamic calendar) at fixed bottom position
        # Apply offset for local moon sighting differences
        adjusted_date = date + timedelta(days=self.hijri_offset_days)
        hijri_date = Gregorian(adjusted_date.year, adjusted_date.month, adjusted_date.day).to_hijri()
        hijri_months = ["", "Muharram", "Safar", "Rabi' al-Awwal", "Rabi' al-Thani",
                       "Jumada al-Awwal", "Jumada al-Thani", "Rajab", "Sha'ban",
                       "Ramadan", "Shawwal", "Dhul-Qi'dah", "Dhul-Hijjah"]
        date_str = f"({hijri_date.day}{self._get_ordinal_suffix(hijri_date.day)} {hijri_months[hijri_date.month]}, {hijri_date.year}AH)"
        self._draw_centered_text(draw, date_str, self.height - 100, date_font, self.text_color)

        return img

    def _generate_ayat_multipage(self, surah_number: int, ayah_number: int,
                                arabic_text: str, urdu_translation: str,
                                english_translation: str, surah_name: str,
                                date: datetime) -> list[Image.Image]:
        """Generate two-page ayat layout for very long verses.

        Page 1: Arabic + Urdu
        Page 2: English
        """

        # PAGE 1: Arabic + Urdu
        page1 = self._generate_ayat_page1(
            surah_number, ayah_number, arabic_text, urdu_translation, surah_name
        )

        # PAGE 2: English
        page2 = self._generate_ayat_page2(
            surah_number, ayah_number, english_translation, surah_name, date
        )

        return [page1, page2]

    def _generate_ayat_page1(self, surah_number: int, ayah_number: int,
                            arabic_text: str, urdu_translation: str,
                            surah_name: str) -> Image.Image:
        """Generate page 1 of multi-page ayat: Arabic + Urdu."""

        aoozubillah_bismillah = "أَعُوذُ بِاللَّهِ مِنَ الشَّيْطَانِ الرَّجِيمِ ۞ بِسۡمِ اللّٰهِ الرَّحۡمٰنِ الرَّحِیۡمِ ۞"
        arabic_with_symbol = arabic_text + " ۞"

        # Calculate optimal scaling without English
        content_blocks = [
            {'text': aoozubillah_bismillah, 'font_size': 54, 'font_path': self.arabic_font_path, 'type': 'single', 'spacing_after': 60},
            {'text': self._get_display_text(arabic_with_symbol, use_raqm=True), 'font_size': 75, 'font_path': self.arabic_font_path, 'type': 'multi', 'line_spacing': 20, 'margin': 100, 'spacing_after': 80},
            {'text': self._get_display_text(urdu_translation, use_raqm=True), 'font_size': 60, 'font_path': self.urdu_font_path, 'type': 'multi', 'line_spacing': 15, 'margin': 120, 'spacing_after': 60},
        ]

        max_content_height = self.height - 500  # Extra space for page indicator, reference, and continuation message
        scaling = self._calculate_adaptive_layout(content_blocks, max_content_height)

        # Create image
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        # Load fonts
        header_font = ImageFont.truetype(str(self.arabic_font_path), int(54 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        arabic_font = ImageFont.truetype(str(self.arabic_font_path), int(75 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        urdu_font = ImageFont.truetype(str(self.urdu_font_path), int(60 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        reference_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
        continuation_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
        page_indicator_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)

        y = 80

        # Page indicator at top
        page_text = "(Page 1 of 2)"
        self._draw_centered_text(draw, page_text, y, page_indicator_font, (100, 100, 100))
        y += 60

        # Bismillah
        header_display = self._get_display_text(aoozubillah_bismillah, use_raqm=True)
        y = self._draw_centered_text(draw, header_display, y, header_font, self.text_color)
        y += int(60 * scaling['spacing_scale'])

        # Arabic text
        arabic_display = self._get_display_text(arabic_with_symbol, use_raqm=True)
        arabic_lines = self._wrap_text(arabic_display, arabic_font, self.width - 100)
        y = self._draw_multiline_centered(draw, arabic_lines, y, arabic_font, self.text_color, int(20 * scaling['spacing_scale']))
        y += int(80 * scaling['spacing_scale'])

        # Urdu translation
        urdu_display = self._get_display_text(urdu_translation, use_raqm=True)
        urdu_lines = self._wrap_text(urdu_display, urdu_font, self.width - 120)
        y = self._draw_multiline_centered(draw, urdu_lines, y, urdu_font, self.text_color, int(15 * scaling['spacing_scale']))
        y += int(60 * scaling['spacing_scale'])

        # Reference
        reference = f"({surah_name} {ayah_number})"
        y = self._draw_centered_text(draw, reference, y, reference_font, self.text_color)

        # Continuation indicator at bottom
        continuation_text = "English translation on next page >>"
        self._draw_centered_text(draw, continuation_text, self.height - 100, continuation_font, (100, 100, 100))

        return img

    def _generate_ayat_page2(self, surah_number: int, ayah_number: int,
                            english_translation: str, surah_name: str,
                            date: datetime) -> Image.Image:
        """Generate page 2 of multi-page ayat: English translation."""

        aoozubillah_bismillah = "أَعُوذُ بِاللَّهِ مِنَ الشَّيْطَانِ الرَّجِيمِ ۞ بِسۡمِ اللّٰهِ الرَّحۡمٰنِ الرَّحِیۡمِ ۞"
        english_clean = self._replace_arabic_symbols_for_english(english_translation)

        # Calculate optimal scaling for English page
        content_blocks = [
            {'text': aoozubillah_bismillah, 'font_size': 54, 'font_path': self.arabic_font_path, 'type': 'single', 'spacing_after': 60},
            {'text': english_clean, 'font_size': 58, 'font_path': '/System/Library/Fonts/Helvetica.ttc', 'type': 'multi', 'line_spacing': 12, 'margin': 140, 'spacing_after': 60},
        ]

        max_content_height = self.height - 200  # Extra space for page indicator
        scaling = self._calculate_adaptive_layout(content_blocks, max_content_height)

        # Create image
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        # Load fonts
        header_font = ImageFont.truetype(str(self.arabic_font_path), int(54 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        english_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(58 * scaling['font_scale']))
        reference_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
        date_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 38)
        page_indicator_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)

        y = 80

        # Page indicator at top
        page_text = "(Page 2 of 2)"
        self._draw_centered_text(draw, page_text, y, page_indicator_font, (100, 100, 100))
        y += 60

        # Bismillah
        header_display = self._get_display_text(aoozubillah_bismillah, use_raqm=True)
        y = self._draw_centered_text(draw, header_display, y, header_font, self.text_color)
        y += int(60 * scaling['spacing_scale'])

        # English translation
        english_lines = self._wrap_text(english_clean, english_font, self.width - 140)
        y = self._draw_multiline_centered(draw, english_lines, y, english_font, self.text_color, int(12 * scaling['spacing_scale']))
        y += int(60 * scaling['spacing_scale'])

        # Reference
        reference = f"({surah_name} {ayah_number})"
        y = self._draw_centered_text(draw, reference, y, reference_font, self.text_color)

        # Date (Islamic calendar) at bottom
        adjusted_date = date + timedelta(days=self.hijri_offset_days)
        hijri_date = Gregorian(adjusted_date.year, adjusted_date.month, adjusted_date.day).to_hijri()
        hijri_months = ["", "Muharram", "Safar", "Rabi' al-Awwal", "Rabi' al-Thani",
                       "Jumada al-Awwal", "Jumada al-Thani", "Rajab", "Sha'ban",
                       "Ramadan", "Shawwal", "Dhul-Qi'dah", "Dhul-Hijjah"]
        date_str = f"({hijri_date.day}{self._get_ordinal_suffix(hijri_date.day)} {hijri_months[hijri_date.month]}, {hijri_date.year}AH)"
        self._draw_centered_text(draw, date_str, self.height - 100, date_font, self.text_color)

        return img

    def generate_hadith_image(self, hadith_number: int, arabic_text: str,
                            urdu_translation: str, english_translation: str,
                            date: datetime, grade: str = "", graded_by: str = "") -> list[Image.Image]:
        """Generate Hadith image(s). Returns a list of images - single image for short hadiths, two images for long ones."""

        aoozubillah_bismillah = "أَعُوذُ بِاللَّهِ مِنَ الشَّيْطَانِ الرَّجِيمِ ۞ بِسۡمِ اللّٰهِ الرَّحۡمٰنِ الرَّحِیۡمِ ۞"

        # Check if we need multi-page layout
        # Calculate scaling to see if content would be too cramped
        content_blocks = [
            {'text': aoozubillah_bismillah, 'font_size': 54, 'font_path': self.arabic_font_path, 'type': 'single', 'spacing_after': 60},
            {'text': self._get_display_text(arabic_text, use_raqm=True), 'font_size': 60, 'font_path': self.arabic_font_path, 'type': 'multi', 'line_spacing': 18, 'margin': 100, 'spacing_after': 80},
            {'text': self._get_display_text(urdu_translation, use_raqm=True), 'font_size': 55, 'font_path': self.urdu_font_path, 'type': 'multi', 'line_spacing': 15, 'margin': 120, 'spacing_after': 60},
        ]

        if english_translation:
            english_clean = self._replace_arabic_symbols_for_english(english_translation)
            content_blocks.append({'text': english_clean, 'font_size': 46, 'font_path': '/System/Library/Fonts/Helvetica.ttc', 'type': 'multi', 'line_spacing': 12, 'margin': 150, 'spacing_after': 60})

        if grade:
            grading_text = f"حكم : {grade} {graded_by}"
            content_blocks.append({'text': self._get_display_text(grading_text, use_raqm=True), 'font_size': 38, 'font_path': self.arabic_font_path, 'type': 'single', 'spacing_after': 50})

        max_content_height = self.height - 160
        scaling = self._calculate_adaptive_layout(content_blocks, max_content_height)

        # If scaling is too small (fonts would be cramped), use multi-page layout
        if english_translation and scaling['font_scale'] < 0.75:
            return self._generate_hadith_multipage(
                hadith_number, arabic_text, urdu_translation, english_translation,
                date, grade, graded_by
            )

        # Otherwise use single-page layout
        return [self._generate_hadith_single_page(
            hadith_number, arabic_text, urdu_translation, english_translation,
            date, grade, graded_by, scaling
        )]

    def _generate_hadith_single_page(self, hadith_number: int, arabic_text: str,
                                    urdu_translation: str, english_translation: str,
                                    date: datetime, grade: str, graded_by: str,
                                    scaling: dict) -> Image.Image:
        """Generate a single-page hadith image."""

        # Create image
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        aoozubillah_bismillah = "أَعُوذُ بِاللَّهِ مِنَ الشَّيْطَانِ الرَّجِيمِ ۞ بِسۡمِ اللّٰهِ الرَّحۡمٰنِ الرَّحِیۡمِ ۞"

        # Load fonts with calculated scaling
        header_font = ImageFont.truetype(str(self.arabic_font_path), int(54 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        arabic_font = ImageFont.truetype(str(self.arabic_font_path), int(60 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        urdu_font = ImageFont.truetype(str(self.urdu_font_path), int(55 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        english_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(46 * scaling['font_scale']))
        grading_font = ImageFont.truetype(str(self.arabic_font_path), int(38 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        reference_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
        date_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 38)

        y = 80

        # A'oodhu billah + Bismillah (RAQM handles text shaping automatically)
        header_display = self._get_display_text(aoozubillah_bismillah, use_raqm=True)
        y = self._draw_centered_text(draw, header_display, y, header_font, self.text_color)
        y += int(60 * scaling['spacing_scale'])

        # Arabic hadith (RAQM handles text shaping automatically)
        arabic_display = self._get_display_text(arabic_text, use_raqm=True)
        arabic_lines = self._wrap_text(arabic_display, arabic_font, self.width - 100)
        y = self._draw_multiline_centered(draw, arabic_lines, y, arabic_font, self.text_color, int(18 * scaling['spacing_scale']))
        y += int(80 * scaling['spacing_scale'])

        # Urdu translation (RAQM handles text shaping automatically)
        urdu_display = self._get_display_text(urdu_translation, use_raqm=True)
        urdu_lines = self._wrap_text(urdu_display, urdu_font, self.width - 120)
        y = self._draw_multiline_centered(draw, urdu_lines, y, urdu_font, self.text_color, int(15 * scaling['spacing_scale']))
        y += int(60 * scaling['spacing_scale'])

        # English translation (if available, replace Arabic symbols with English equivalents)
        if english_translation:
            english_clean = self._replace_arabic_symbols_for_english(english_translation)
            english_lines = self._wrap_text(english_clean, english_font, self.width - 150)
            y = self._draw_multiline_centered(draw, english_lines, y, english_font, self.text_color, int(12 * scaling['spacing_scale']))
            y += int(60 * scaling['spacing_scale'])

        # Grading (if available)
        if grade:
            grading_text = f"حكم : {grade} {graded_by}"
            grading_display = self._get_display_text(grading_text, use_raqm=True)
            y = self._draw_centered_text(draw, grading_display, y, grading_font, self.text_color)
            y += int(50 * scaling['spacing_scale'])

        # Reference
        reference = f"(Mishkaat {hadith_number})"
        y = self._draw_centered_text(draw, reference, y, reference_font, self.text_color)

        # Date (Gregorian) at fixed bottom position
        date_str = f"({date.day}{self._get_ordinal_suffix(date.day)} {date.strftime('%B')}, {date.year})"
        self._draw_centered_text(draw, date_str, self.height - 100, date_font, self.text_color)

        return img

    def _generate_hadith_multipage(self, hadith_number: int, arabic_text: str,
                                  urdu_translation: str, english_translation: str,
                                  date: datetime, grade: str, graded_by: str) -> list[Image.Image]:
        """Generate two-page hadith layout for very long hadiths.

        Page 1: Arabic + Urdu
        Page 2: English
        """

        # PAGE 1: Arabic + Urdu
        page1 = self._generate_hadith_page1(
            hadith_number, arabic_text, urdu_translation, grade, graded_by
        )

        # PAGE 2: English
        page2 = self._generate_hadith_page2(
            hadith_number, english_translation, date, grade, graded_by
        )

        return [page1, page2]

    def _generate_hadith_page1(self, hadith_number: int, arabic_text: str,
                              urdu_translation: str, grade: str, graded_by: str) -> Image.Image:
        """Generate page 1 of multi-page hadith: Arabic + Urdu + grading."""

        aoozubillah_bismillah = "أَعُوذُ بِاللَّهِ مِنَ الشَّيْطَانِ الرَّجِيمِ ۞ بِسۡمِ اللّٰهِ الرَّحۡمٰنِ الرَّحِیۡمِ ۞"

        # Calculate optimal scaling without English
        content_blocks = [
            {'text': aoozubillah_bismillah, 'font_size': 54, 'font_path': self.arabic_font_path, 'type': 'single', 'spacing_after': 60},
            {'text': self._get_display_text(arabic_text, use_raqm=True), 'font_size': 60, 'font_path': self.arabic_font_path, 'type': 'multi', 'line_spacing': 18, 'margin': 100, 'spacing_after': 80},
            {'text': self._get_display_text(urdu_translation, use_raqm=True), 'font_size': 55, 'font_path': self.urdu_font_path, 'type': 'multi', 'line_spacing': 15, 'margin': 120, 'spacing_after': 60},
        ]

        if grade:
            grading_text = f"حكم : {grade} {graded_by}"
            content_blocks.append({'text': self._get_display_text(grading_text, use_raqm=True), 'font_size': 38, 'font_path': self.arabic_font_path, 'type': 'single', 'spacing_after': 50})

        max_content_height = self.height - 200  # Extra space for "continued" message
        scaling = self._calculate_adaptive_layout(content_blocks, max_content_height)

        # Create image
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        # Load fonts
        header_font = ImageFont.truetype(str(self.arabic_font_path), int(54 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        arabic_font = ImageFont.truetype(str(self.arabic_font_path), int(60 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        urdu_font = ImageFont.truetype(str(self.urdu_font_path), int(55 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        grading_font = ImageFont.truetype(str(self.arabic_font_path), int(38 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        reference_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
        continuation_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
        page_indicator_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)

        y = 80

        # Page indicator at top
        page_text = "(Page 1 of 2)"
        self._draw_centered_text(draw, page_text, y, page_indicator_font, (100, 100, 100))
        y += 60

        # Bismillah
        header_display = self._get_display_text(aoozubillah_bismillah, use_raqm=True)
        y = self._draw_centered_text(draw, header_display, y, header_font, self.text_color)
        y += int(60 * scaling['spacing_scale'])

        # Arabic hadith
        arabic_display = self._get_display_text(arabic_text, use_raqm=True)
        arabic_lines = self._wrap_text(arabic_display, arabic_font, self.width - 100)
        y = self._draw_multiline_centered(draw, arabic_lines, y, arabic_font, self.text_color, int(18 * scaling['spacing_scale']))
        y += int(80 * scaling['spacing_scale'])

        # Urdu translation
        urdu_display = self._get_display_text(urdu_translation, use_raqm=True)
        urdu_lines = self._wrap_text(urdu_display, urdu_font, self.width - 120)
        y = self._draw_multiline_centered(draw, urdu_lines, y, urdu_font, self.text_color, int(15 * scaling['spacing_scale']))
        y += int(60 * scaling['spacing_scale'])

        # Grading
        if grade:
            grading_text = f"حكم : {grade} {graded_by}"
            grading_display = self._get_display_text(grading_text, use_raqm=True)
            y = self._draw_centered_text(draw, grading_display, y, grading_font, self.text_color)
            y += int(50 * scaling['spacing_scale'])

        # Reference
        reference = f"(Mishkaat {hadith_number})"
        y = self._draw_centered_text(draw, reference, y, reference_font, self.text_color)

        # Continuation indicator at bottom
        continuation_text = "English translation on next page >>"
        self._draw_centered_text(draw, continuation_text, self.height - 100, continuation_font, (100, 100, 100))

        return img

    def _generate_hadith_page2(self, hadith_number: int, english_translation: str,
                              date: datetime, grade: str, graded_by: str) -> Image.Image:
        """Generate page 2 of multi-page hadith: English translation."""

        aoozubillah_bismillah = "أَعُوذُ بِاللَّهِ مِنَ الشَّيْطَانِ الرَّجِيمِ ۞ بِسۡمِ اللّٰهِ الرَّحۡمٰنِ الرَّحِیۡمِ ۞"
        english_clean = self._replace_arabic_symbols_for_english(english_translation)

        # Calculate optimal scaling for English page
        content_blocks = [
            {'text': aoozubillah_bismillah, 'font_size': 54, 'font_path': self.arabic_font_path, 'type': 'single', 'spacing_after': 60},
            {'text': english_clean, 'font_size': 52, 'font_path': '/System/Library/Fonts/Helvetica.ttc', 'type': 'multi', 'line_spacing': 12, 'margin': 140, 'spacing_after': 60},
        ]

        if grade:
            grading_text = f"حكم : {grade} {graded_by}"
            content_blocks.append({'text': self._get_display_text(grading_text, use_raqm=True), 'font_size': 38, 'font_path': self.arabic_font_path, 'type': 'single', 'spacing_after': 50})

        max_content_height = self.height - 200  # Extra space for page indicator
        scaling = self._calculate_adaptive_layout(content_blocks, max_content_height)

        # Create image
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        # Load fonts
        header_font = ImageFont.truetype(str(self.arabic_font_path), int(54 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        english_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(52 * scaling['font_scale']))
        grading_font = ImageFont.truetype(str(self.arabic_font_path), int(38 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
        reference_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
        date_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 38)
        page_indicator_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)

        y = 80

        # Page indicator at top
        page_text = "(Page 2 of 2)"
        self._draw_centered_text(draw, page_text, y, page_indicator_font, (100, 100, 100))
        y += 60

        # Bismillah
        header_display = self._get_display_text(aoozubillah_bismillah, use_raqm=True)
        y = self._draw_centered_text(draw, header_display, y, header_font, self.text_color)
        y += int(60 * scaling['spacing_scale'])

        # English translation
        english_lines = self._wrap_text(english_clean, english_font, self.width - 140)
        y = self._draw_multiline_centered(draw, english_lines, y, english_font, self.text_color, int(12 * scaling['spacing_scale']))
        y += int(60 * scaling['spacing_scale'])

        # Grading
        if grade:
            grading_text = f"حكم : {grade} {graded_by}"
            grading_display = self._get_display_text(grading_text, use_raqm=True)
            y = self._draw_centered_text(draw, grading_display, y, grading_font, self.text_color)
            y += int(50 * scaling['spacing_scale'])

        # Reference
        reference = f"(Mishkaat {hadith_number})"
        y = self._draw_centered_text(draw, reference, y, reference_font, self.text_color)

        # Date at bottom
        date_str = f"({date.day}{self._get_ordinal_suffix(date.day)} {date.strftime('%B')}, {date.year})"
        self._draw_centered_text(draw, date_str, self.height - 100, date_font, self.text_color)

        return img

    def _get_ordinal_suffix(self, day: int) -> str:
        """Get ordinal suffix for day (1st, 2nd, 3rd, etc.)."""
        if 10 <= day % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        return suffix
