---
name: dua-card-generator
description: Generate a single-page 1080x1920 "dua card" PNG from any hadith centered on a dua (supplication) — small narration prefix, large Arabic dua, large Urdu translation, small narration suffix, clean reference footer. Use this whenever asked to turn a hadith (from Fatah Al-Rabani, Mishkaat, or any other collection) into a shareable dua graphic, or to make "another one like the ghum-o-pareshani dua card." Does not touch main.py/config.json/state.json — this is a one-off/on-demand generator, not the recurring daily ayat/hadith pipeline.
---

# Dua Card Generator

Produces a single evergreen 1080x1920 PNG for a hadith whose point is a
specific dua — e.g. "whoever says X dua when afflicted by Y will have Z."
Distinct from the recurring daily ayat/hadith cards this repo generates
(see the `islamic-graphic-design` skill for that system); this is a
one-off/on-demand card type with its own settled layout, built and refined
interactively for the Fatah Al-Rabani 5576 "dua for grief and anxiety"
card. Reuses `IslamicImageGenerator`'s adaptive-sizing/drawing helpers and
this project's configured fonts, so it matches house style (1080x1920
canvas, `#F5F5F5` background, black text, RAQM shaping) without adding a
new content type to the daily pipeline.

Read `reference/generate_dua_card.py` before generating anything — it's a
working, parameterized script, not pseudocode. For a new hadith, copy it
(or edit the `CONTENT` block in place if the previous card's output isn't
needed anymore) and fill in the six text fields described below.

## The layout, top to bottom

1. **Heading** — small-medium, catchy, Urdu. One line naming what the dua
   is for (e.g. `"غم و پریشانی کی دعا"` — "Dua for Grief and Anxiety").
   Write a new one for each hadith; don't reuse a previous card's heading.
2. **Prefix** — small, muted-gray Urdu. The narration lead-in, trimmed down
   to just enough context to introduce the dua, ending in a colon right
   before it. Pattern: `"رسول اللہ ﷺ نے فرمایا: <circumstance in which one
   says this dua> اور وہ یہ دعا پڑھے:"` (or the direct-address hadith's own
   equivalent lead-in if it isn't a "whoever does X" hadith).
3. **Arabic dua** — large, main focus. **Only the dua's own words** — no
   isnad ("عَنْ فُلَانٍ قَالَ..."), no "reported that..." framing, no
   trailing "…except Allah did such-and-such" consequence clause if the
   Urdu prefix/suffix already conveys that meaning in translation.
4. **Urdu translation of the dua** — large, main focus, same visual weight
   as the Arabic. Only the dua's translation, not the surrounding
   narration's translation.
5. **Suffix** — small, muted-gray Urdu. Whatever narration follows the dua
   in the original hadith (a promised outcome, a follow-up dialogue, a
   companion's question and the Prophet's ﷺ answer, etc.). Omit this block
   entirely (don't leave an empty gap) if the source hadith has no tail
   after the dua.
6. **Reference** — small, fixed size (not scaled with the rest), one line,
   bilingual/Urdu, e.g. `"الفتح الربانی، حدیث: ۵۵۷۶ — صحیح (مسند احمد:
   ۳۷۱۲)"`. Combine collection name + hadith number + grading + a
   cross-reference in parentheses if the source cites one. No separate
   "AL-HADEES.COM"-style source-site attribution line — just the hadith
   reference itself.

The prefix and suffix are deliberately smaller (36px base vs. 62px/50px for
the dua) so the hadith reads as *context* framing the dua, while the dua +
its translation stay the thing the eye lands on — that's the whole point of
this card type. Don't even out the sizes "for consistency"; the size gap
is the design.

## Cleaning rules — going from a raw scraped hadith to the six fields

Real scraped hadith text (al-hadees.com, sunnah.com, etc.) needs cleanup
before it fits these fields. Rules verified against the Fatah Al-Rabani
5576 source used to build this card type:

- **Drop scraper artifacts**: leading hadith-number tags like `"۔ (۵۵۷۶)۔"`,
  doubled quote-parens `((...))` around the Prophet's ﷺ words, trailing
  inline cross-references like `"(مسند أحمد: ۳۷۱۲)"` — move that reference
  into the footer field instead of leaving it inline in the Arabic.
- **Split the Arabic into isnad / dua / tail** and keep only the dua for
  the Arabic field. The isnad ("عَنْ عَبْدِ اللّٰہِ رضی اللہ عنہ قَالَ: قَالَ
  رَسُولُ اللّٰہِ ﷺ...") and any tail ("قَالَ: فَقِیلَ یَا رَسُولَ اللّٰہِ...")
  are narration, not the dua — they don't belong in the large Arabic block.
  If you want that context conveyed, it's the Urdu prefix/suffix's job
  (translated/summarized in Urdu), not a second copy of the Arabic.
- **Watch for a raw-Arabic fragment embedded mid-Urdu-paragraph** — some
  sources render the dua once in Arabic inline inside the Urdu translation
  too (often abbreviated with an ellipsis, e.g. `"اَللّٰھُمَّ إِنِّی
  عَبْدُکَ……وَذَہَابَ ہَمِّی"`), followed by a parenthetical full Urdu
  translation. Drop the embedded Arabic fragment and its parentheses —
  the Arabic dua is already shown in full and at large size above; keep
  only the flowing Urdu translation text.
- **Preserve ZWNJ-joined honorifics as given** — strings like `"‌صلی ‌اللہ
  ‌علیہ ‌وآلہ ‌وسلم"` (with zero-width non-joiner characters between words)
  are how this project's source corpus formats the honorific after the
  Prophet's ﷺ name; keep them as-is rather than "cleaning" them into a
  single `ﷺ` glyph or removing the joiners — this is normal formatting for
  this content, not scraper noise.
- **Don't paraphrase the dua or its translation.** Use the source's own
  Arabic and its own Urdu translation verbatim (after trimming isnad/tail
  as above) — a dua's exact wording matters. Only the prefix/suffix
  framing text may be lightly trimmed for length.

## Arabic source text — use standard Arabic orthography, not al-hadees.com's Urdu-keyboard spelling

al-hadees.com's Arabic text is typed on an Urdu keyboard layout, so it
mixes in Urdu-specific letter variants — `ک`/`ی`/`ہ`/`ھ` (Urdu kaf/yeh/gol
heh/do-chashmi heh) — in place of standard Arabic `ك`/`ي`/`ه`. This is fine
for the Urdu translation (that's genuinely Urdu text), but it makes the
**Arabic** dua field ambiguous: it's not always obvious from the scraped
text which heh variant was "meant," and guessing wrong (or blanket-find-
replacing every `ہ` to `ھ`, which over-corrects genuine cases) produces
Arabic that doesn't match how the hadith is actually written.

**Fix: source the Arabic dua text from a standard-Arabic-orthography
edition instead** — Sunnah.com's Arabic (when reachable), an authoritative
Musnad Ahmad text, or any hadith database using plain Arabic script (`ه`
U+0647, `ك` U+0643, `ي` U+064A, `ة` U+0629, full hamza/alef variants) — and
use that verbatim for the `arabic_dua` field, rather than "fixing" the
al-hadees.com spelling letter-by-letter. Verified this session: `pdms.ttf`
(the default Arabic font, same as daily ayah generation) renders standard
Arabic Unicode correctly with RAQM — no missing-glyph boxes, proper
Nastaliq joining — so there's no need to transliterate into Urdu-keyboard
variants for this font. Only fall back to manually resolving `ک`/`ی`/`ہ`/`ھ`
in the Arabic if no standard-orthography source can be found for that
particular hadith, and in that case ask the user rather than guessing —
this project's maintainer knows the correct spelling and would rather
confirm it than have it silently over-corrected.

## Fonts

- Arabic: same font the daily ayah generator uses by default —
  `IslamicImageGenerator.arabic_font_path`, which resolves via
  `config.json`'s `fonts.arabic` (currently `"pdms"` → `fonts/pdms.ttf`).
  `DuaCardContent.arabic_font` can override this per-card by name
  (`"pdms"`, `"indopak"`, `"muhammadi"`, `"qalam"` — the same four options
  `config.json` already lists under `fonts.available_arabic_fonts`)
  without touching `config.json` itself, so switching a single card's
  Arabic style never affects the daily ayat/hadith pipeline.
- Urdu (heading, prefix, dua translation, suffix, reference): always
  `IslamicImageGenerator.urdu_font_path` (config's `fonts.urdu`, currently
  `jameelnoorinastaleeq.ttf`).
- Both are loaded with `layout_engine=LAYOUT_ENGINE` (RAQM) — required for
  correct Arabic/Urdu shaping, never optional. See the
  `islamic-graphic-design` skill's "RAQM text shaping" section for why.

## Base font sizes (pre-scaling)

| Block | Base size | Notes |
|---|---|---|
| Heading | 60px | Urdu font |
| Prefix | 36px | Urdu font, muted gray `(90,90,90)` |
| Arabic dua | 62px | Arabic font, main focus |
| Urdu dua translation | 50px | Urdu font, main focus |
| Suffix | 36px | Urdu font, muted gray `(90,90,90)` |
| Reference | 38px | Urdu font, fixed — **not** run through adaptive scaling, same convention as ayat/hadith's reference/date lines |

These were reached by iterating live with the user (started smaller, bumped
+4px across the board once the layout was confirmed) — treat them as the
current settled default, not a hardcoded constraint. All five scaled sizes
move together via `_calculate_adaptive_layout`'s single `font_scale` per
card, so the relative size gap between prefix/suffix and dua/translation is
preserved regardless of how long a given hadith's text is.

## When content doesn't fit on one page

`generate_dua_card.py` prints a warning if the adaptive layout comes back
with `font_scale < 0.7` — the single-page "small frame, large dua" layout
is too cramped at that point. Don't just let it shrink further. Two
options, in order of preference:

1. **Trim the prefix/suffix further.** They're meant to be short framing
   text, not the full narration — if a hadith's surrounding narration is
   unusually long, cut it down more aggressively before falling back to
   pagination. This is usually enough.
2. **Fall back to a 2-page layout** if the dua itself (not just the
   framing) is long: full Arabic dua on page 1, full Urdu translation +
   reference on page 2, each with a `"(Page N of 2)"` indicator and a
   `"Urdu translation on next page >>"` continuation label on page 1 —
   mirroring the existing hadith multi-page convention (one language per
   page) documented in the `islamic-graphic-design` skill. This was
   prototyped once during this card type's development before the
   single-page structure was chosen as the default; reach for it only when
   trimming isn't enough, not as the first option.

## Output location and naming

Save to `output/dua_cards/<slug>.png` — a dedicated folder separate from
the daily `output/YYYY-MM-DD/` pipeline output, since these are evergreen
on-demand cards, not date-scoped daily posts. Pick `<slug>` from the
collection + hadith number + a short topic hint, e.g.
`fatah_rabbani_5576_ghum_pareshani.png`.

## Pre-flight checklist

- [ ] Arabic field contains ONLY the dua's own words — no isnad, no tail.
- [ ] Urdu dua field is the dua's translation only, not narration.
- [ ] Prefix/suffix are visibly smaller (36px base) than the dua/translation
      (62px/50px base) in the rendered output — actually open the PNG and
      check this, don't just trust the code.
- [ ] No raw-Arabic ellipsis fragment left inside the Urdu prefix/suffix.
- [ ] Reference line reads cleanly and has no leftover scraper artifacts
      (stray `((`/`))`, a lone leading `"۔"`, etc.).
- [ ] No separate site-attribution line (e.g. "AL-HADEES.COM") — reference
      field only.
- [ ] Arabic font matches what was asked — defaults to the same font as
      daily ayah generation unless a different one was explicitly requested.
- [ ] Single page unless the pre-flight check above forced the 2-page
      fallback — and if so, that was a deliberate, noted choice.
- [ ] You opened the actual rendered PNG (not just read the code) and
      confirmed the six blocks render in the right order with correct
      RAQM shaping (no tofu boxes, no reversed text).
