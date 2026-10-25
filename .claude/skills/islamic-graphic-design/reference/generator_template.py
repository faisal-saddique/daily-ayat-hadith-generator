"""Skeleton for a new generate_<type>_image() method on IslamicImageGenerator.

This is NOT a standalone script - it's boilerplate to copy into
src/daily_ayat_hadith/image_generator.py as a new method (or a small set of
methods) on the existing IslamicImageGenerator class, mirroring the pattern
used by generate_ayat_image()/_generate_ayat_single_page() and
generate_hadith_image()/_generate_hadith_single_page().

See ../SKILL.md for the full design-system reference (colors, spacing, the
adaptive-sizing algorithm, RAQM requirements, footer/pill conventions, and
"Deviating from house style" for when a new content type legitimately needs
something the current ayat/hadith generators don't have - a border, a
different footer, no date at all, its own accent color, etc.).

Every numeric constant below is a starting point copied from the existing
generators - adjust deliberately, not by guessing, and leave a comment when
you depart from it. Nothing here is mandatory: delete methods or blocks you
don't need (skip the multi-page path for content that's always short, skip
the date block entirely for content with no calendar relevance, add a
border block if this content type wants a frame).

Replace every TODO with real code/values for your content type.
"""

from PIL import Image, ImageDraw, ImageFont

# LAYOUT_ENGINE already exists as a module-level constant in
# image_generator.py - import it, don't redefine it:
#
#   from .image_generator import LAYOUT_ENGINE
#
# Pass layout_engine=LAYOUT_ENGINE on every ImageFont.truetype(...) call
# that loads an Arabic or Urdu font. Required, not optional - see SKILL.md
# "RAQM text shaping."


def generate_TYPE_image(self, content_text, source_label, date=None, **extra_fields) -> list:
    """Generate <TYPE> image(s). Returns a list of PIL Images - a single
    image for content that fits on one page, multiple images (with
    "_page{N}" filenames) if the adaptive layout decides it needs to
    paginate. Mirrors generate_ayat_image() / generate_hadith_image().

    Params here are placeholders, not a required shape - rename, add, or
    remove to match what this content type actually needs:
      - date=None is a valid, expected case for content with no
        date/footer at all (e.g. an evergreen quote or poem excerpt).
      - extra_fields is where anything else belongs: a badge/category
        label, a border style flag, a poet/scholar attribution, etc.
    """

    # 1. Prepare any RAQM-shaped Arabic/Urdu strings up front. Always
    #    use_raqm=True - the False branch is dead/broken code, see SKILL.md.
    #
    #    display_text = self._get_display_text(content_text, use_raqm=True)

    # 2. Build the content_blocks list used to size and test-fit everything.
    #    Base font sizes below are placeholders - anchor your choices to the
    #    "Base font sizes actually used" table in SKILL.md for content of
    #    comparable weight (a short quote is closer to the ayat header size;
    #    a longer passage closer to the hadith body size).
    content_blocks = [
        # Optional single-line header/label, e.g. a category tag or opener.
        # {'text': header_display, 'font_size': 54, 'font_path': self.arabic_font_path,
        #  'type': 'single', 'spacing_after': 60},

        # Primary body content (wrapped, multi-line).
        # {'text': body_display, 'font_size': 60, 'font_path': self.arabic_font_path,
        #  'type': 'multi', 'line_spacing': 18, 'margin': 100, 'spacing_after': 80},

        # Secondary translation/attribution block, if any.
        # {'text': secondary_text, 'font_size': 46, 'font_path': '/System/Library/Fonts/Helvetica.ttc',
        #  'type': 'multi', 'line_spacing': 12, 'margin': 150, 'spacing_after': 60},
    ]

    # 3. Reserve fixed top/footer space and compute the adaptive scale.
    #    `height - 160` is what the existing single-page ayat/hadith layouts
    #    reserve for their top margin + reference line + date line - it is
    #    NOT a universal constant. Size this to what THIS content type
    #    actually draws at top/bottom:
    #      - no date, no badge, no border -> reserve can be much smaller.
    #      - a border/frame -> add its inset on both top and bottom.
    #      - an optional badge/pill (like EVENT_PILL_RESERVE = 90) -> add a
    #        fixed reserve for it UNCONDITIONALLY, so the main content's
    #        font scale doesn't visibly shift depending on whether the
    #        badge happens to render for a given piece of content.
    footer_reserve = 160  # TODO: tune - 0 is valid if there's genuinely no footer
    max_content_height = self.height - footer_reserve
    scaling = self._calculate_adaptive_layout(content_blocks, max_content_height)

    # 4. Escape hatch: don't accept a cramped single page. Branch to a
    #    multi-page layout (copy the shape of _generate_ayat_multipage /
    #    _generate_hadith_multipage) if scaling is too small.
    if scaling['font_scale'] < 0.75:
        raise NotImplementedError(
            "Add a _generate_TYPE_multipage(...) fallback here, mirroring "
            "_generate_ayat_multipage() / _generate_hadith_multipage()."
        )

    page = self._generate_TYPE_single_page(content_text, source_label, date, scaling, **extra_fields)
    return [page]


def _generate_TYPE_single_page(self, content_text, source_label, date, scaling: dict, **extra_fields) -> Image.Image:
    """Render one page. Mirrors _generate_ayat_single_page() /
    _generate_hadith_single_page()."""

    img = Image.new('RGB', (self.width, self.height), self.bg_color)
    draw = ImageDraw.Draw(img)

    # --- Optional: border / frame --------------------------------------
    # The shipped ayat/hadith generators draw zero borders, dividers, or
    # icons - that's a deliberate minimalist choice for THEIR plain daily-
    # post look, not a technical limit. A different content type (an event
    # poster, a poetry card, a certificate-style announcement) may
    # legitimately want a frame. If you add one, draw it first (before any
    # text) and reserve an inset margin so text never sits flush against it:
    #
    # border_inset = 48
    # border_color = (0, 0, 0)  # pick deliberately - doesn't have to match body text
    # draw.rectangle(
    #     [border_inset, border_inset, self.width - border_inset, self.height - border_inset],
    #     outline=border_color, width=3,
    # )
    # y_start = border_inset + 40  # feed into your top margin below instead of the bare 80

    y = 80  # top margin - adjust if you added a border inset above

    # --- Primary content -------------------------------------------------
    # Load fonts at the scaled size. layout_engine=LAYOUT_ENGINE is required
    # for any Arabic/Urdu font load - see SKILL.md "RAQM text shaping".
    #
    # header_font = ImageFont.truetype(str(self.arabic_font_path), int(54 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
    # y = self._draw_centered_text(draw, header_display, y, header_font, self.text_color)
    # y += int(60 * scaling['spacing_scale'])
    #
    # body_font = ImageFont.truetype(str(self.arabic_font_path), int(60 * scaling['font_scale']), layout_engine=LAYOUT_ENGINE)
    # body_lines = self._wrap_text(body_display, body_font, self.width - 100)
    # y = self._draw_multiline_centered(draw, body_lines, y, body_font, self.text_color, int(18 * scaling['spacing_scale']))
    # y += int(80 * scaling['spacing_scale'])

    # --- Optional: category badge / attribution pill ---------------------
    # Reuse the shape/gradient/shrink-to-fit approach of _draw_event_pill
    # (image_generator.py:122-202) for any small badge - a poet's name, a
    # source label, a "New" tag. It doesn't have to carry a date, and it
    # doesn't have to look like an Islamic-event pill specifically - the
    # reusable part is the mechanic (rounded shape, shrink-to-fit, gradient
    # or flat fill), not the exact colors.
    #
    # y = self._draw_event_pill(img, draw, {
    #     'name_en': source_label, 'name_ur': '',
    #     'bg_color': '#333333', 'text_color': '#FFFFFF',
    # }, y)

    # --- Optional: reference / citation line ------------------------------
    # reference_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
    # reference = f"({source_label})"
    # y = self._draw_centered_text(draw, reference, y, reference_font, self.text_color)

    # --- Optional: footer date ---------------------------------------------
    # Only draw this if the content type actually wants a date. Plenty of
    # content (an evergreen quote, a poem with no calendar relevance) has
    # no reason to carry one at all - just omit this whole block for those,
    # and shrink `footer_reserve` above to match instead of leaving dead
    # whitespace sized for a date that never renders.
    #
    # Pick ONE convention deliberately if you do want a date (see SKILL.md
    # "Hijri date / footer conventions"):
    #   - Hijri, if this content is Islamic-calendar-anchored (like ayat) -
    #     reuse the hijri_offset_days / event-pill pattern from
    #     _generate_ayat_single_page() (image_generator.py:598-616).
    #   - Plain Gregorian, if it's a simple daily post (like hadith).
    if date is not None:
        date_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 38)
        date_str = f"({date.day}{self._get_ordinal_suffix(date.day)} {date.strftime('%B')}, {date.year})"
        self._draw_centered_text(draw, date_str, self.height - 100, date_font, self.text_color)

    return img


# --- Saving (this part lives in main.py, not image_generator.py) ---------
#
# images = image_gen.generate_TYPE_image(content_text, source_label, date)
# for i, page_img in enumerate(images, start=1):
#     filename = f"TYPE_<slug>.png" if len(images) == 1 else f"TYPE_<slug>_page{i}.png"
#     out_path = date_output_dir / filename
#     page_img.save(out_path, quality=95)
