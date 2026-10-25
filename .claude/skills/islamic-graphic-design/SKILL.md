---
name: islamic-graphic-design
description: Design-system and implementation reference for this repository's 1080x1920 PNG Islamic graphics (the Ayat/Hadith cards produced by src/daily_ayat_hadith/image_generator.py). Use this skill whenever asked to generate a new graphic type, add a poster/card for a new content category (poetry, scholar quotes, event announcements, dua collections, etc.), design a new on-brand image, wire a new content type into the daily generator, or otherwise extend this project's visual output while staying consistent with its existing plain, centered, whitespace-heavy aesthetic. Also use it when asked to explain or audit the existing adaptive text-sizing algorithm, the event-pill badge component, or the Hijri-date footer convention.
---

# Islamic Graphic Design System

This document is the distilled design system for the PNG graphics produced by
this repository (`daily_ayat_and_hadith`). It exists so that an agent with
**zero prior context on this codebase** can produce a new, visually
consistent 1080x1920 graphic for a content type that doesn't exist yet
(poetry, scholar quotes, event announcements, dua collections, etc.)
without re-deriving the design system from scratch by reading 1200+ lines of
`image_generator.py`.

Everything below was verified against the actual implementation
(`src/daily_ayat_hadith/image_generator.py`, `config.json`, `state.py`,
`main.py`, `islamic_events.json`) and against real rendered samples in
`output/2026-01-13/` and `output/2026-09-03/` — not inferred from
docstrings alone. File:line references point at the canonical
implementation so you can go verify a detail yourself rather than trust a
paraphrase.

**Read this framing before the tables below:** everything documented here —
colors, "always centered," "no borders," "always has a date footer" — is
the specific set of choices the *existing* ayat/hadith generators happen to
make for a plain, minimal daily-verse aesthetic. None of it is a technical
constraint of the codebase or of Pillow. A new content type is free to need
a date-free layout, a border/frame, its own accent color, a different
canvas aspect ratio, or left-aligned pull quotes — see **"Deviating from
house style"** below for how to make those calls deliberately instead of
either (a) blindly copying ayat/hadith's choices onto content that doesn't
need them, or (b) bolting on decoration without the same care ayat/hadith's
own restraint reflects. Treat every rule below as "this is what the current
two generators do, and why it works for them" — not "this is the only
allowed way to make a graphic in this repo."

## Quick-reference token table

| Token | Value | Source |
|---|---|---|
| Canvas size | 1080 x 1920 px (portrait, phone-story format) | `image_generator.py:25-26` |
| Background color | `#F5F5F5` — `(245, 245, 245)` | `image_generator.py:27` |
| Text color | pure black `#000000` — `(0, 0, 0)` | `image_generator.py:28` |
| Muted/meta text color | `(100, 100, 100)` gray — page indicators, "Continued >>" labels | e.g. `image_generator.py:678` |
| Output format | PNG, `quality=95` (hardcoded at every `img.save()` call site in `main.py`, e.g. lines 340, 368, 675, 707) | — |
| Arabic font (selectable) | `pdms.ttf` (default), or `indopak.ttf`, `muhammadi.ttf`, `qalam.ttf` | `config.json` → `fonts.arabic` |
| Urdu font (selectable) | `jameelnoorinastaleeq.ttf` (default), or `NotoNastaliqUrdu-Regular.ttf` | `config.json` → `fonts.urdu` |
| Latin/English font | hardcoded `/System/Library/Fonts/Helvetica.ttc` — **macOS-only path, not config-driven** | `image_generator.py:143, 566, 567, 568...` (every English/date/reference font load) |
| Text shaping engine | RAQM — `ImageFont.Layout.RAQM`, always passed as `layout_engine=LAYOUT_ENGINE` when loading Arabic/Urdu fonts | `image_generator.py:11` |
| Top margin (start Y) | 80px | e.g. `image_generator.py:570` |
| Footer date baseline | fixed `self.height - 100` (= y 1820) unless an event pill is drawn, in which case `pill_bottom + 14` | `image_generator.py:614-616` |
| Event pill reserved space | `EVENT_PILL_RESERVE = 90` px, unconditionally reserved on every ayat image whether or not a pill renders that day | `image_generator.py:21` |
| Alignment | **everything is horizontally centered** — Arabic, Urdu, English, references, dates, page indicators alike | `_draw_centered_text` / `_draw_multiline_centered`, used uniformly |
| Decoration | **none**, except one component: the rounded, gradient-filled "pill" badge used for Islamic-event footers | `_draw_event_pill`, `image_generator.py:122-202` |

## Verified visual character (from real samples)

Opened and visually inspected `output/2026-09-03/ayat_Al-Maaida_20.png`,
`output/2026-09-03/hadith_mishkaat_5007.png`,
`output/2026-01-13/ayat_Aal-i-Imraan_67.png`, and
`output/2026-01-13/hadith_mishkaat_4632.png`. Confirmed:

- Flat, uniform off-white background, no texture, no vignette.
- All text pure black, no color variation between Arabic/Urdu/English blocks.
- Every block — including Urdu, which in most other contexts is set
  right-aligned as a paragraph — is horizontally **centered**, not
  right-aligned or justified. This is a deliberate, verified simplification;
  do not "fix" it to be right-aligned in a new content type.
- Generous negative space: the last text block (translation or grading) ends
  well above the vertical midpoint of the lower half of the canvas, then
  nothing until a small `(Reference)` line, then the date line near the very
  bottom. This huge reserved whitespace before a small footer is a
  signature, not empty/broken layout.
- No borders, rules, dividers, icons, drop shadows, or background imagery
  anywhere in either sample.
- Neither sample happened to have an active Islamic-event pill (none of the
  events in `islamic_events.json` matched those two Hijri dates), so the
  gradient pill wasn't observed directly in a rendered sample this session —
  it was verified from the `_draw_event_pill` source instead (see below).
  The hadith sample does show the grading line (`حكم : صحیح`) rendered in the
  Arabic font just above the `(Mishkaat 5007)` reference — confirms the
  grading convention.

## The adaptive text-sizing algorithm

Implemented in `_calculate_adaptive_layout()`,
`image_generator.py:383-497`. This is the single most important mechanism
in the system — it's what lets one piece of code handle a two-word ayah and
a 40-line hadith without either looking sparse or overflowing.

**Inputs:** a list of "content blocks", each a dict:
```python
{'text': str, 'font_size': int, 'font_path': Path|str,
 'type': 'single' | 'multi', 'line_spacing': int (multi only),
 'margin': int (multi only, wrap width = canvas_width - margin),
 'spacing_after': int}
```
`type: 'single'` = one line, never wrapped (headers, references, grading).
`type: 'multi'` = wrapped via `_wrap_text()` (naive word-boundary wrap
against `font.getbbox` width, `image_generator.py:295-316`) and stacked with
`line_spacing` between lines.

**Algorithm:**
1. Compute `base_height` = total rendered height of all blocks at
   `font_scale=1.0, spacing_scale=1.0`, plus a fixed 220px buffer for the
   reference/date footer (`image_generator.py:417`).
2. **If content is short** (`base_height < 90%` of the available height):
   scale **up**. Walk an increasing list of scale increments
   `[0.1, 0.15, ... up to 2.0]`, testing `font_scale = 1.0 + increment` and
   `spacing_scale = 1.0 + increment*0.9` at each step. Accept a step only if
   the resulting height fits within 97% of available height **and** every
   `type: 'single'` block still fits within `canvas_width - 40`. Stop at the
   first step that fails (greedy). Final scale is capped at
   `font_scale <= 3.0`, `spacing_scale <= 2.5`. Target: fill 88-97% of the
   available vertical space — short content should look intentionally
   large, not lonely at the default size.
3. **If content fits as-is** (`base_height <= max_height`): use
   `font_scale = spacing_scale = 1.0` unchanged.
4. **If content is too long**: scale **down** over up to 10 attempts.
   Attempts 0-2 shrink `spacing_scale` only (−0.12/attempt, preserves
   readability by tightening whitespace before touching font size).
   Attempts 3-5 shrink both `font_scale` and `spacing_scale` by −0.05/attempt.
   Attempts 6-9 shrink both by −0.04/attempt. Floors:
   `font_scale >= 0.57`, `spacing_scale >= 0.40`.
5. **Multi-page fallback**: if the resulting `font_scale < 0.75`, the
   content is judged too cramped for one page and the caller switches to a
   multi-page layout instead of accepting a tiny font
   (`image_generator.py:533-538` for ayat, `:806-811` for hadith). Hadith
   goes further: if even the 2-page split still needs Urdu below 38px or
   Arabic below 42px (`MIN_URDU_FONT`/`MIN_ARABIC_FONT`,
   `image_generator.py:923-935`), it escalates to a 3-page "one language per
   page, fixed comfortable size" layout (`_generate_hadith_threepage`,
   `image_generator.py:1099-1207`) that paginates via `_paginate_lines()`
   rather than ever shrinking below a readable floor.

**Practical takeaway for a new content type:** never hardcode a single font
size and hope it fits. Build a `content_blocks` list the same way, pick a
`max_content_height` (canvas height minus your fixed top/footer reserves),
call `_calculate_adaptive_layout`, and multiply every base font size and
every spacing value by the returned `font_scale`/`spacing_scale` respectively
when you actually draw. Provide a multi-page (or paginated) escape hatch for
when `font_scale` comes back very small, exactly as ayat/hadith do.

### Base font sizes actually used (pre-scaling)

These are the literal numbers baked into the two existing generators — a
useful sanity anchor for choosing sizes for a new content type of similar
weight (e.g. a scholar-quote card is closer to the hadith numbers; a single
short line of poetry closer to the ayat header).

| Block | Ayat (`image_generator.py:522-527`) | Hadith (`:789-801`) |
|---|---|---|
| Header (A'oodhu billah + Bismillah) | 54px, Arabic font, single | 54px, Arabic font, single |
| Primary script body | 75px, Arabic font, multi, line_spacing 20, margin 100 | 60px, Arabic font, multi, line_spacing 18, margin 100 |
| Urdu translation | 60px, multi, line_spacing 15, margin 120 | 55px, multi, line_spacing 15, margin 120 |
| English translation | 52px, Helvetica, multi, line_spacing 12, margin 150 | 46px, Helvetica, multi, line_spacing 12, margin 150 |
| Grading (hadith only) | — | 38px, Arabic font, single, text `"حكم : {grade}"` |
| Reference line | 40px, Helvetica, fixed (not scaled) | 40px, Helvetica, fixed (not scaled) |
| Date line | 38px, Helvetica, fixed (not scaled) | 38px, Helvetica, fixed (not scaled) |
| Page indicator (multi-page) | 32px, Helvetica, gray, fixed | same |
| Continuation label (multi-page) | 36px, Helvetica, gray, fixed | same |

Note reference/date/page-indicator/continuation fonts are **never** run
through the scaling factor — they stay at a fixed size regardless of how
much the main content shrinks or grows. Only the header/body/translation/
grading fonts scale.

`max_content_height` used per page type:
- Ayat single page: `height - 160 - EVENT_PILL_RESERVE` = 1920−160−90 = **1670px** (`:529`)
- Hadith single page: `height - 160` = **1760px** (`:803`, no event-pill reserve — events never render on hadith images)
- Ayat page 2 (English, multi-page): `height - 200 - EVENT_PILL_RESERVE` (`:723`)
- Hadith 2-page attempt: `height - 140 - 250` (`RESERVED_SPACE_TOP`/`RESERVED_SPACE_BOTTOM`, `:904-905, 918`)

## RAQM text shaping — required, not optional

`LAYOUT_ENGINE = ImageFont.Layout.RAQM` (`image_generator.py:11`) is passed
as `layout_engine=LAYOUT_ENGINE` on **every** `ImageFont.truetype(...)` call
that loads an Arabic or Urdu font. RAQM handles Arabic/Urdu glyph shaping
(joining forms) and bidirectional text ordering automatically — you draw the
raw logical-order Unicode string and it renders correctly shaped and
right-to-left.

`_get_display_text(text, use_raqm=True)` (`image_generator.py:204-216`) is
called at **every single call site in the codebase** with
`use_raqm=True` — grep confirms this; there are zero call sites passing
`use_raqm=False` in the shipped code. When `use_raqm=True` the function is a
no-op passthrough. The `else` branch (manual `arabic_reshaper.reshape()` +
`get_display()`) is **dead code**: neither `arabic_reshaper` nor
`get_display` is imported anywhere in the file, so that branch would raise
`NameError` if ever reached. **Conclusion for a new content type:** always
load Arabic/Urdu fonts with `layout_engine=LAYOUT_ENGINE` and draw the raw
string directly — never attempt manual reshaping/bidi, and don't rely on the
`use_raqm=False` path existing (it's broken).

English/Latin text has the opposite problem: Helvetica doesn't have Arabic
glyphs, so any Arabic honorific symbols embedded in English translation text
(ﷺ, رضي الله عنه, etc.) are stripped/replaced by
`_replace_arabic_symbols_for_english()` (`image_generator.py:218-293`)
before rendering — e.g. `ﷺ` → `"(peace be upon him)"`. If a new content
type mixes Arabic honorifics into an English/Latin block, reuse this helper
rather than drawing raw Arabic glyphs in the Helvetica font (they render as
tofu boxes).

## Alignment rules per block type

There are no per-script alignment rules — that's the point. `_draw_centered_text`
and `_draw_multiline_centered` (`image_generator.py:318-335`) are used for
literally every text block in every generator function: Arabic, Urdu,
English, references, dates, grading, page indicators, continuation labels.
Everything is centered horizontally against the full 1080px canvas width.
Do not introduce left- or right-alignment for a new content type unless you
have a specific, deliberate reason to break from the house style — and if
you do, note it explicitly as an intentional departure.

**One deliberate, named exception: Urdu/Arabic poetry.** Plain per-line
centering (each line's own midpoint pinned to canvas center, independent of
every other line's width) is wrong for poetry specifically, because verse
lines vary a lot in length line-to-line and plain centering leaves short
lines floating with ragged, uneven edges next to long ones — it reads as
sparse/unbalanced rather than as a composed stanza. Poetry content types
must use the **justified-misra** convention instead — see "Poetry alignment
— justified misra convention" below. This is the one case in the whole
system where "just center it like everything else" is the wrong default.

## Poetry alignment — justified misra convention

Applies to any content type whose primary body is verse (a sher/couplet, a
nazm/ghazal stanza, a multi-line poem excerpt) in Arabic or Urdu — e.g. a
poetry card. Does **not** apply to ayat/hadith (they stay plain-centered as
documented above); this is a per-content-type deviation, made deliberately
for the reason below, not a global change to `_draw_centered_text`.

**The problem it fixes:** classical Urdu/Arabic verse is printed in couplets
(sher) of two lines (misra), and misra lengths vary — one line might be 8
words, the next 5. Centering each line independently (the ayat/hadith
default) leaves the shorter line looking small and adrift under/over the
longer one, with no shared edge to anchor the eye. Printed diwans and
poetry typesetting avoid this by giving every line in the stanza the same
rendered width — the short lines are stretched (via extra inter-word
spacing, not letter-spacing) so every line's left and right edges line up
into one clean block, which then sits centered on the canvas as a unit.

**Chosen target width (confirmed with the user for this repo): the widest
line in the whole poem/excerpt**, not each couplet's own partner line. Every
line — regardless of which couplet it's in — gets justified out to that one
shared width, so the entire stanza reads as a single uniform column, not a
sequence of independently-sized couplet blocks.

**Algorithm — `_draw_justified_poetry_block` (new helper, not in
`image_generator.py` yet; add it alongside `_draw_multiline_centered`):**

1. Split the poem into its lines (already split by the caller — one string
   per misra, in the order they should render top to bottom).
2. At the final scaled font size, measure the natural rendered width of
   every line (RAQM-shaped, full string, `font.getbbox`/`getlength`) and take
   `target_width = max(line_widths)`.
3. For each line, split on whitespace into words (safe: Arabic/Urdu letter
   joining happens *within* a word, never across a space, so splitting on
   spaces and redrawing each word separately never breaks glyph joining —
   only inter-word gaps change, never intra-word shaping).
4. Compute justification for that line:
   - `natural_width` = sum of each word's rendered width + `(word_count - 1)
     * space_width` (space_width = the font's normal space-glyph advance).
   - `extra_total = target_width - natural_width`.
   - `extra_per_gap = extra_total / (word_count - 1)` when `word_count > 1`.
   - **Single-word lines can't be word-spaced** — there's no internal gap to
     stretch. Leave a lone-word line plain-centered within the target block
     rather than trying to letter-space it (letter-spacing an Arabic/Urdu
     word breaks RAQM's joining forms — never do this).
   - Optional sanity floor: skip justification (fall back to centered) for
     a line if `extra_per_gap` would exceed a few times the normal
     space width — very short lines with only 1-2 words stretched to match
     a much longer line produce ugly, cavernous gaps rather than a
     "nicely balanced" look. Pick a threshold by eye against real content,
     not a guessed constant.
5. Draw each justified line RTL-correctly: since these are pure Arabic/Urdu
   lines (no embedded Latin/digits needing bidi reordering), the word order
   on screen is just the logical word order laid right-to-left. Compute the
   block's shared left/right edges from `target_width` centered on the
   canvas (`left_x = (canvas_width - target_width) / 2`,
   `right_x = left_x + target_width`), then walk words in logical order
   starting a screen cursor at `right_x`: draw each word so its right edge
   sits at the cursor, decrement the cursor by that word's width, then by
   `space_width + extra_per_gap` before the next word. This makes every
   line's right edge *and* left edge land on the same `right_x`/`left_x` as
   every other line — that shared edge alignment is what actually produces
   the "looks nice" balanced-column effect, not the stretching by itself.
6. The justified block as a whole is still horizontally **centered on the
   canvas** (via `left_x`/`right_x` above) — this convention replaces
   per-line centering with per-block edge alignment, it doesn't turn poetry
   into a left- or right-margin-pinned layout.

**Integration with the rest of the system:** this is purely a drawing-stage
change to how one `content_blocks` entry gets rendered — it doesn't change
`_calculate_adaptive_layout` at all. Feed the poem in as a normal
`type: 'multi'` block for sizing purposes (wrap/line-count/height
estimation can stay as-is, since wrapping should generally be avoided for
poetry anyway — verse lines are meant to break exactly where the poet broke
them, not at whatever width `_wrap_text` picks; treat each supplied misra as
already-final, one array entry per screen line, not a paragraph to
re-wrap). Once `scaling['font_scale']`/`spacing_scale` come back, load the
font at the scaled size and call `_draw_justified_poetry_block` instead of
`_draw_multiline_centered` for that one block; everything else (adaptive
sizing, multi-page fallback, footer/date conventions) works unchanged.

## Quote/aphorism cards — default convention

Applies to any short, evergreen prose saying attributed to a person — a
scholar/writer quote, an aphorism, a maxim — as opposed to a Quran ayah,
hadith, or verse (poetry uses the justified-misra convention above
instead). Verified by building and visually checking a real sample this
session (`output/2026-09-05/quote_badi_neki.png`, an Urdu Wasif Ali Wasif
quote). Treat this as the **default** layout for this content type — start
here rather than re-deriving a quote layout from scratch, and only deviate
with a reason.

**Structure, top to bottom:**

1. **Big opening-quote glyph**, centered, in a reserved top band
   (`top_reserve` ≈ 340px worked well on the 1080x1920 canvas). Use
   `"“"` (U+201C, curly opening double quote) set in **Georgia Bold**
   (`/System/Library/Fonts/Supplemental/Georgia Bold.ttf`) at a large size
   (~260px) and a light gray fill (`(205, 205, 205)` — lighter than the
   `(100,100,100)` muted-meta gray used elsewhere, since this is pure
   decoration, not a meta-text label). Georgia's `"` renders as a bold
   serif curl (the classic "66"-shaped quotation mark look) — Helvetica's
   is a plain straight-ish mark and doesn't read the same way; don't
   substitute it. This is the one new decoration primitive introduced for
   this content type, on top of the existing event-pill — keep it to just
   this one mark, not a full quote-box/frame treatment.
2. **Quote body**, plain centered (not justified-misra — this is prose,
   not verse), vertically centered in the space between the top glyph band
   and the bottom byline band. Prioritize **balanced line count over
   maximum size**: search font sizes from large downward and pick the
   largest size whose natural word-wrap still produces a small number of
   balanced lines (3 was the right target for a one-sentence aphorism) —
   don't just take the first size that fits the height budget, since a
   bigger size that wraps into 4-5 ragged, mid-clause-broken lines looks
   worse than a slightly smaller 3-line version. This is a deliberate
   refinement on top of `_calculate_adaptive_layout`'s plain
   fits-height-first greedy behavior, worth carrying over: for short,
   single-sentence content, filter candidate sizes by resulting line count
   before filtering by height.
3. **Author byline**, fixed near the bottom (`HEIGHT - 170` worked well),
   in the same muted gray as ayat/hadith's meta text `(100, 100, 100)`,
   set in the Urdu font (RAQM, `layout_engine=LAYOUT_ENGINE`) at a modest
   size (~44px) — a name/pen-name, not a reference citation, so it doesn't
   need the `(Reference)`-style parenthesization ayat/hadith use.

**No date footer.** A quote/aphorism is evergreen, not tied to today's
Gregorian or Hijri date — omit the date block entirely (see "Deviating
from house style" below on this) and don't try to wedge the byline into
the fixed `height - 100` date baseline; give it its own reserved band
instead (see next point).

**Reserved-space discipline still applies**: both the top glyph band and
the bottom byline band should be reserved unconditionally in the height
budget used to size the quote body, exactly like `EVENT_PILL_RESERVE` — so
the body's font size doesn't shift depending on incidental factors. Don't
attribute a quote to a person unless the user actually named one; if no
author is given, drop the byline band entirely rather than leaving an
empty gray line or guessing an attribution.

## The pill/badge component (`_draw_event_pill`)

The **only** reusable decoration primitive in the whole system, and the most
likely thing a new content type would want to borrow (e.g. a "category"
badge, a date-range badge for event announcements). Implementation:
`image_generator.py:122-202`.

Mechanics, verified from source (no live sample rendered this session, but
every value below is read directly off the code, not inferred):

- **Bilingual layout**: English text, then a separator `"   •   "`, then
  Urdu text, drawn left-to-right in that run order on one row.
- **Shrink-to-fit**: starts at `font_size=28` (English, Helvetica) with the
  Urdu font at `font_size+8` (so 36 initially — Urdu needs to run larger to
  read at the same visual weight). Both step down together by 2px per
  iteration, floor `min_font_size=18`, until combined content width
  (`en_width + separator_width + ur_width`) fits within
  `max_content_width = canvas_width - 160` = **920px**.
- **Shape**: a rounded rectangle built via an `ImageDraw` mask with
  `radius = box_h // 2` — i.e. fully pill-shaped (semicircular ends), not
  a rounded-corner rectangle with small radius.
- **Padding**: `pad_x=26, pad_y=8` around the text content.
- **Fill — the one gradient in the whole system**: a horizontal left-to-right
  gradient computed from the event's own `bg_color` hex:
  `gradient_start = lighten(base_rgb, 0.18)`,
  `gradient_end = darken(base_rgb, 0.14)`. Built by drawing 1px-wide vertical
  color columns across the box width, then masked to the rounded shape.
- **Text color**: the event's own `text_color` hex, drawn directly (not
  auto-contrasted — the event config author is responsible for choosing a
  readable pair).
- **Vertical centering**: each of the three runs (EN text, separator, UR
  text) is centered individually against the row's content height rather
  than all three sharing one baseline — needed because the bullet
  separator's glyph bounding box is much shorter than the surrounding text,
  and naive baseline alignment would leave it sitting visibly high.
- **Placement**: horizontally centered on the canvas; called with
  `top_y = self.height - 175` (only on **ayat** images — hadith images never
  draw a pill). Returns `pill_bottom` (the box's bottom Y), and the date
  line is then drawn at `pill_bottom + 14` instead of the usual fixed
  `height - 100`.
- **Trigger**: `_get_event_for_date(hijri_month, hijri_day)`
  (`image_generator.py:95-107`) looks up `islamic_events.json` for a
  matching Hijri month/day; `hijri_month: null` in the event config means
  "matches every month" (used for the recurring Ayyam al-Beed white days).
  Events can be individually toggled via `enabled: false` without deleting
  them.

If a new content type wants a badge (e.g. "Poetry" category tag, an event
countdown), reuse `_draw_event_pill`'s shape/gradient/shrink-to-fit approach
rather than inventing a new decoration style — this keeps the "one
decoration primitive" rule intact.

## Hijri date / footer conventions

Two different date conventions exist depending on content type — don't
conflate them:

- **Ayat images**: show the **Hijri (Islamic) date**, computed via
  `hijridate.Gregorian(...).to_hijri()` after applying `hijri_offset_days`
  from `config.json` (a signed integer day offset for regional calendar
  correction, e.g. `-1` in the current `config.json`). Format:
  `"({day}{ordinal} {HijriMonthName}, {year}AH)"`, e.g.
  `"(20th Rabi' al-Awwal, 1448AH)"`. An optional `islamic_date_override`
  string can substitute the *displayed* text, but the Hijri month/day are
  **still computed** underneath so the event-pill lookup keeps working
  regardless of the override (`image_generator.py:598-601`).
- **Hadith images**: show the plain **Gregorian date**, no Hijri conversion,
  no event pill. Format: `"({day}{ordinal} {MonthName}, {year})"`, e.g.
  `"(3rd September, 2026)"` (`image_generator.py:878`).

Both sit at the same fixed footer baseline `self.height - 100` unless
displaced by a pill (ayat only). A new content type should pick one of
these two conventions deliberately (Hijri if the content is inherently
Islamic-calendar-anchored like an event announcement; Gregorian if it's a
simple daily post like a quote) and say so explicitly rather than silently
picking one.

## config.json and state.json plug-in pattern

`config.json` is the single source of runtime configuration. Observed
pattern for every configurable choice: a `selected` key plus a sibling
`available_*` dict/list of choices, e.g.:

```json
"fonts": {
  "arabic": "pdms",
  "urdu": "jameelnoorinastaleeq",
  "available_arabic_fonts": { "indopak": "fonts/indopak.ttf", "muhammadi": "fonts/muhammadi.ttf", "pdms": "fonts/pdms.ttf", "qalam": "fonts/qalam.ttf" },
  "available_urdu_fonts": { "jameelnoorinastaleeq": "fonts/jameelnoorinastaleeq.ttf", "noto": "fonts/NotoNastaliqUrdu-Regular.ttf" }
}
```
and similarly `translations.urdu`/`translations.english` with
`available_urdu`/`available_english` lists. A brand-new content type that
needs its own font or source selection should add a new top-level block
following this exact shape (`<content_type>_source`, or a new key under
`fonts`/`translations` if it genuinely reuses the same script choices) —
don't repurpose the existing `fonts.arabic`/`fonts.urdu` keys for an
unrelated content type, since those are read specifically by the
ayat/hadith generators and changing them would affect existing output.

Note: `config.json` declares `output.image_quality: 95`, but
`image_generator.py`/`main.py` don't actually read that value — every
`img.save()` call hardcodes `quality=95` directly at the call site. They
happen to agree today; if you add a new save call, either hardcode `95` to
match the existing convention or take the opportunity to wire it through
`config.json` properly (and note that you did).

`state.json` / `state.py` (`StateManager`, `DailyState` dataclass) tracks:
`last_date`, `content_type` (`"ayat"`, `"hadith"`, or in current practice
also `"both"` — see live `state.json`), `last_surah`, `last_ayah`,
`last_hadith`. `get_next_content_type()` currently just alternates
`ayat ⇄ hadith`. For a new content type, extend `DailyState` with a new
field (e.g. `last_<type>_id` or a reference string) and either:
- fold it into the existing alternation (extend `content_type` to a 3-way
  or N-way rotation), if it should replace daily runs, or
- track it independently with its own cadence (its own "last generated"
  date field) if it runs on a different schedule from the ayat/hadith pair.

Either way, update `update_after_generation()` to accept and persist the new
field, mirroring how it currently branches on `content_type == "ayat"` vs
`"hadith"` vs `"both"` (`state.py:75-110`).

## Fonts directory inventory

`fonts/` (all paths relative to project root):

| File | Used by current code? | Role |
|---|---|---|
| `pdms.ttf` | yes — default Arabic (`fonts.arabic`) | Arabic Quran/hadith script |
| `indopak.ttf` | yes — selectable Arabic | Arabic alt style |
| `muhammadi.ttf` | yes — selectable Arabic | Arabic alt style |
| `qalam.ttf` | yes — selectable Arabic | Arabic alt style |
| `jameelnoorinastaleeq.ttf` | yes — default Urdu (`fonts.urdu`) | Urdu Nastaliq script |
| `NotoNastaliqUrdu-Regular.ttf` | yes — selectable Urdu | Urdu alt style |
| `indopak_old.ttf` | **no** — present but not referenced in `config.json` or code | unused/legacy |
| `indopak-nastaleeq-v4.ttf` / `.woff2` | **no** — not referenced | unused |
| `UthmanicHafs1Ver18.ttf` / `.woff2` | **no** — not referenced | unused |

English/Latin text is not drawn from any file in `fonts/` — it always uses
the hardcoded macOS system path `/System/Library/Fonts/Helvetica.ttc`. If
you're generating on a non-macOS box, this path won't resolve; that's a
pre-existing limitation of the codebase, not something to silently "fix" by
swapping in a bundled font unless asked.

## Output naming convention

```
output/
  └── YYYY-MM-DD/
        ├── content_review.txt        (temporary, deleted after generation)
        ├── content.json              (finalized record of that day's content)
        ├── ayat_<SurahName>_<AyahNum>.png            (or _page{N}.png if multi-page)
        └── hadith_mishkaat_<HadithNum>.png            (or _page{N}.png if multi-page)
```
Underscores replace spaces in the slug portion (e.g. `Al-Maaida`,
`Aal-i-Imraan` keep their hyphens but spaces become `_`). A new content
type should follow the same shape:
`output/YYYY-MM-DD/<type>_<slug-or-id>.png`, with a `_page{N}` suffix
appended before `.png` if it spills to multiple pages.

## How to add a new content-type generator — step by step

1. **Add a new method to `IslamicImageGenerator`** in `image_generator.py`,
   named `generate_<type>_image(...)`, mirroring `generate_ayat_image()`
   (`:499-545`) or `generate_hadith_image()` (`:780-817`):
   - Build the raw text strings for your content (any Arabic/Urdu
     honorifics run through `_get_display_text(text, use_raqm=True)`; any
     English text with embedded Arabic symbols run through
     `_replace_arabic_symbols_for_english()`).
   - Build a `content_blocks` list (see algorithm section above) with your
     chosen base font sizes, `type: 'single'|'multi'`, `line_spacing`,
     `margin`, `spacing_after`.
   - Pick `max_content_height = self.height - <your fixed top/footer
     reserve>` and call `self._calculate_adaptive_layout(content_blocks,
     max_content_height)`.
   - If `scaling['font_scale'] < 0.75`, branch to a multi-page variant
     instead of accepting a cramped single page (see `_generate_ayat_multipage`
     `:620-642` and `_generate_hadith_multipage`/`_generate_hadith_threepage`
     `:883-1207` for the pattern of splitting content across pages with
     `_paginate_lines`).
   - Otherwise call a private `_generate_<type>_single_page(...)` that
     actually builds the `Image`, loads fonts at `int(base_size *
     scaling['font_scale'])` with `layout_engine=LAYOUT_ENGINE` for
     Arabic/Urdu fonts, draws each block via `_draw_centered_text` /
     `_draw_multiline_centered` starting at `y = 80`, and finishes with a
     `(Reference)` line and a footer date line at the fixed baseline
     described above. Return the `Image`.
   - A ready-to-copy skeleton for this is in
     `reference/generator_template.py` in this skill directory — copy it in
     and fill in your specific content/fonts/reference format rather than
     starting from a blank file.

2. **Wire it into `main.py`**: follow the existing ayat/hadith fetch → review
   → generate → save pattern (`main.py` around lines 480-780). Fetch/prepare
   your content, call your new `generate_<type>_image(...)`, iterate the
   returned `list[Image.Image]` (single or multi-page), and save each with
   `img.save(out_path, quality=95)` using the naming convention above
   (`_page{N}` suffix when `len(images) > 1`, matching lines 336-344 and
   364-372 for the existing types).

3. **Extend `config.json`** with a new top-level block for any new
   font/source/translation choices your content type needs, following the
   `selected key + available_* dict` pattern shown above. Don't reuse
   `fonts.arabic`/`fonts.urdu` unless you deliberately want to inherit the
   same script choice as ayat/hadith.

4. **Extend `state.py`'s `DailyState`** with whatever new field tracks your
   content's sequencing (a numeric id, a reference string, or its own
   `last_<type>_date`), and update `update_after_generation()` /
   `get_next_content_type()` (or add an independent scheduling check) to
   persist and consume it — mirroring the existing `last_surah`/`last_ayah`
   vs `last_hadith` branching.

5. **Save to `output/YYYY-MM-DD/<type>_<slug>.png`** as described above.

## Deviating from house style — a decision menu

Ayat/hadith cards are one point in a design space, not the whole space. Before
building a new content type, go through this menu and decide each row on
purpose — "same as ayat/hadith" is a fine answer as often as not, but it
should be a choice, not an accident from copy-pasting.

| Element | Ayat/hadith's current choice | When a new content type should deviate |
|---|---|---|
| Canvas size | 1080x1920 (phone story format) | Keep this if the output is going to the same story/status placement. A feed post, print flyer, or square graphic legitimately wants a different size — 1080x1080, A4, etc. Change `self.width`/`self.height` for that generator's own image creation call; don't touch the shared class defaults if ayat/hadith must stay exactly as they are. |
| Palette | 3 grays only (`245,245,245` bg / `0,0,0` text / `100,100,100` muted), + the event pill's per-event color as the sole scoped exception | A content type can have its own restrained accent (1-2 colors, used deliberately — e.g. a poetry card's ink color, a themed border) if that's genuinely part of its identity. Restraint is the actual house value, not "gray only" — don't jump to a busy multi-color palette, but don't feel bound to black-on-gray either. |
| Border / frame | None anywhere | A poetry card, certificate-style announcement, or event poster can legitimately want a frame — that's a real, common design need the current minimal cards just don't have. If you add one: pick a single treatment (a hairline rule, or a frame, not both plus a shadow plus an icon), reserve a consistent inset margin for it so text never sits flush against it, and keep the border itself restrained (thin line or simple geometric frame, not an ornate flourish) unless the content specifically calls for more. |
| Gradient/fill effects | One gradient exists (the event pill) | Fine to have your own if a badge/background element calls for it — keep it to one considered effect, not stacked shadows + gradients + glows. |
| Alignment | Everything centered | Centering is the default that reads cleanest for short-to-medium verse/hadith text. Poetry specifically should use the **justified-misra** convention (see "Poetry alignment — justified misra convention" above), not plain per-line centering. Other longer-form content (an editorial-style pull quote) may read better left-aligned as a ragged block, or with a deliberate asymmetric layout — that's a legitimate call, not a mistake, as long as it's consistent within the piece. |
| Date/footer | Always present — Hijri (ayat) or Gregorian (hadith) | A date is only useful if the content is time-anchored (a daily post, a calendar event). An evergreen quote, a poem excerpt, or a scholar-quote card has no obligation to carry a date at all — omit the block entirely and reclaim that reserved vertical space rather than leaving it as unexplained empty margin sized for a date that never renders. |
| Badge/pill | Used only for Islamic-event names and hadith grading | The pill *mechanic* (rounded shape, shrink-to-fit, optional gradient) is reusable for any short label — a poet's name, a category tag, a "new" marker. Reuse the mechanic; the colors and copy are yours to set. |
| Decoration reserve | `EVENT_PILL_RESERVE = 90`, unconditional | Whatever optional element you add (border inset, badge, decorative rule), reserve its space unconditionally in your `max_content_height` calculation — this is the one pattern worth carrying over verbatim regardless of what you're building, because it's what keeps font scaling stable whether or not the optional element renders for a given piece of content. |

The one thing that *is* effectively a hard constraint, not a style choice:
RAQM shaping for any Arabic/Urdu text (see below) — that's a correctness
requirement, not an aesthetic one, and applies no matter how the rest of the
graphic looks.

## House rules — what the current codebase actually does, and why

These describe the ayat/hadith generators' own restraint — useful as a
calibration reference for "how much is too much," not as a ban list for
other content types. Use the deviation menu above to decide what applies to
what you're building.

- The current system uses exactly 3 colors and 1 gradient (the event pill)
  precisely because ayat/hadith content wants to disappear behind the text —
  no branding, no ornamentation competing with scripture. That reasoning
  doesn't automatically transfer to, say, an event-announcement poster,
  whose whole job might be to catch the eye. Match the restraint level to
  what the content actually needs, not to ayat/hadith by default.
- **Do** always load Arabic/Urdu fonts with `layout_engine=LAYOUT_ENGINE`
  (RAQM) and draw raw logical-order text, for *any* content type that
  includes Arabic/Urdu script. **Don't** use the
  `_get_display_text(..., use_raqm=False)` path — it's dead/broken code
  (missing imports). This one is a correctness rule, not a style rule.
- **Do** run any adaptive font sizing through `_calculate_adaptive_layout`
  rather than a hand-picked constant, and provide a multi-page/pagination
  fallback for when content doesn't fit even at the minimum scale — this
  generalizes cleanly to any amount of text, regardless of how the page
  looks otherwise.
- **Do** reserve fixed vertical (or horizontal) space unconditionally for
  any optional element — border inset, badge, date block — so the main
  content's font scale doesn't visibly shift depending on whether that
  element happens to render for a given piece of content. This is the
  single most load-bearing pattern in the codebase and applies regardless
  of what decoration you do or don't add.
- **Do** save as PNG. `quality=95` and 1080x1920 are today's values for
  story-format output — carry them over if you're targeting the same
  placement; pick deliberately (and note it) if you're not.
- **Don't** claim a new graphic is "done" without actually opening the
  rendered PNG and eyeballing it — reading the code is not sufficient
  verification, as this skill's own research process demonstrated (the
  event pill's exact behavior could only be fully confirmed from source
  since no sample this session happened to have an active event).

## Pre-flight checklist before calling a new graphic "done"

- [ ] You went through the "Deviating from house style" menu above and made
      a deliberate call on canvas size, palette, border/frame, alignment,
      date/footer, and badge — not a default carried over unexamined.
- [ ] If this content type is poetry/verse, body lines use the
      justified-misra convention (justified to the widest line in the
      poem, not plain per-line centering) — see "Poetry alignment" above.
- [ ] If this content type is a quote/aphorism (not verse), it uses the
      default quote-card convention — big gray Georgia-Bold `"` glyph on
      top, plain-centered body picked for balanced line count, muted
      byline at bottom, no date — see "Quote/aphorism cards" above.
- [ ] Any Arabic/Urdu font is loaded with `layout_engine=LAYOUT_ENGINE`.
- [ ] Font sizes and spacing come from `_calculate_adaptive_layout`, not hardcoded constants, and a multi-page/pagination fallback exists for low `font_scale`.
- [ ] Any optional element (border, badge, date, decorative rule) has its space reserved unconditionally, so layout doesn't shift depending on whether it renders.
- [ ] If you added something beyond ayat/hadith's plain style (a color, a border, a different aspect ratio), it's a considered, restrained choice — and you left a comment saying why, not just that you did it.
- [ ] New `config.json` keys follow the `selected + available_*` pattern and don't clobber existing `fonts`/`translations` keys.
- [ ] `state.json`/`DailyState` was extended (or deliberately left alone) with a clear rationale for how this content type sequences.
- [ ] Output was saved to `output/YYYY-MM-DD/<type>_<slug>.png` (with `_page{N}` if multi-page) at the quality/format you settled on.
- [ ] You actually opened the generated PNG with the Read tool (or equivalent) and visually assessed it against what this content type is supposed to look like — not just read the code that produced it.
