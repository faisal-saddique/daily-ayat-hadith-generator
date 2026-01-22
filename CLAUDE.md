# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Daily Ayat and Hadith Generator - An automated system that generates beautiful Islamic graphics (1080x1920 PNG) featuring daily Quran verses (Ayat) and Hadith from authentic sources. The system supports multi-language output (Arabic, Urdu, English) with complex text rendering and includes an intelligent multi-source hadith system with automatic fallback.

## Development Setup

**Prerequisites:**
- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- SQLite database `content.sqlite3` (426MB) with Quran and Mishkaat hadith collection
- Fonts in `fonts/` directory (included in repo)
- API keys for AI translation (optional)

**Installation:**
```bash
# Install dependencies
uv sync

# Set up environment variables
cp .env.example .env
# Add GEMINI_API_KEY or OPENAI_API_KEY to .env
```

**Running the generator:**
```bash
# Option 1: Using uv (recommended)
uv run python -m src.daily_ayat_hadith.main

# Option 2: With activated venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m src.daily_ayat_hadith.main

# Alternative entry point
python main.py
```

## Architecture

### Core Components

**1. Multi-Source Hadith System (`hadith_provider.py`)**
- Primary architecture: intelligent fallback chain for hadith retrieval
- Sources (in priority order):
  1. **Sunnah.com** (primary): Arabic text + English translation + grading
  2. **Al-hadees.com** (secondary): Arabic text + Urdu translation + grading
  3. **Local SQLite database** (fallback): Pre-stored hadith
- When Sunnah.com succeeds: Urdu is fetched from local DB to complete the hadith
- When al-hadees.com succeeds: English is fetched from local DB or generated via AI
- Quality control: Automatically skips weak (ضعیف) hadiths
- Configuration: `HadithProviderConfig` loaded from `config.json`

**2. Database Layer (`database.py`)**
- SQLite interface with two main tables: `ayah` (Quran verses) and `mishkaat` (hadith)
- Supports 4 Arabic font variants via column mapping: indopak, muhammadi, pdms, qalam
- Supports 12 Urdu translators and 8 English translators
- Sequential navigation: `get_next_ayah()` and `get_next_hadith()` handle progression
- Text cleaning: Removes HTML entities, normalizes newlines and whitespace

**3. State Management (`state.py`)**
- JSON-based persistence in `state.json`
- Tracks: last generation date, content type (ayat/hadith/both), last surah/ayah, last hadith
- `should_generate_today()` prevents duplicate daily runs
- State updates only after successful image generation

**4. Image Generation (`image_generator.py`)**
- Uses Pillow with RAQM layout engine for complex Arabic/Urdu text shaping
- Image specs: 1080x1920 PNG, 95% quality
- Key features:
  - Adaptive text sizing based on content length
  - Automatic line wrapping with proper word boundaries
  - Hijri (Islamic) calendar integration with configurable offset
  - Handles special Islamic symbols (ﷺ, etc.)
  - Separate generators: `generate_ayat_image()` and `generate_hadith_image()`

**5. Web Scrapers (`sunnah_scraper.py`, `alhadees_scraper.py`)**
- Fetch hadith from online sources with timeout protection (default 10s)
- Extract Arabic text, translations, and scholarly grading
- Rate limiting: 1-second delays between requests
- Error handling with structured exceptions (`SunnahScraperError`)

**6. AI Translation (`translation_generator.py`)**
- Uses Pydantic AI framework with Google Gemini or OpenAI
- Generates scholarly English translations when not available from sources
- References Urdu translation for accuracy
- Includes confidence level assessment in output

### Data Flow

```
main.py
  ↓
StateManager checks if generation needed today
  ↓
For Ayah: Database.get_next_ayah()
  ↓
For Hadith: HadithProvider.get_next_hadith()
  ├─ Try Sunnah.com (Arabic + English) + Local DB (Urdu)
  ├─ Fallback: al-hadees.com (Arabic + Urdu) + Local DB or AI (English)
  └─ Final fallback: Local DB only
  ↓
Create review file: content_review.txt (Arabic + Urdu for both)
  ↓
Wait for user input
  ├─ ESC/Ctrl+C → Delete review file → Exit (state NOT updated)
  └─ ENTER → Continue
      ↓
  Parse review file (read edited content)
      ↓
  ImageGenerator (uses edited content) → Save PNG files
      ↓
  Delete review file
      ↓
  StateManager updates state
```

## Configuration

**`config.json`** controls all behavior:
- `hijri_offset_days`: Adjust Islamic calendar (±days)
- `translations.urdu`: Choose from 12 Urdu translators
- `translations.english`: Choose from 8 English translators
- `fonts.arabic`: Select Arabic font variant (pdms, indopak, muhammadi, qalam)
- `fonts.urdu`: Select Urdu font (jameelnoorinastaleeq, noto)
- `hadith_source.mode`: "online" or "local"
- `hadith_source.online.collection`: Hadith collection name (e.g., "mishkat")
- `hadith_source.online.fallback_to_local`: Enable/disable fallback chain
- `hadith_source.ai_translation.enabled`: Enable AI English translation
- `hadith_source.ai_translation.model`: "gemini-2.5-flash" or "openai"

**`state.json`** is auto-managed - do not edit manually unless resetting state.

## Output Structure

```
output/
  └── YYYY-MM-DD/
      ├── content_review.txt (temporary - created for review, deleted after generation)
      ├── ayat_SurahName_AyahNumber.png
      └── hadith_mishkaat_HadithNumber.png
```

**Note:** `content_review.txt` is a temporary file created before image generation. It contains the ayah and hadith content for manual review/editing. After you press ENTER to continue or ESC to cancel, this file is automatically deleted.

## Key Implementation Details

### Text Rendering
- RAQM layout engine handles Arabic/Urdu text shaping automatically
- No manual bidi/reshaping needed when using RAQM
- English text: Arabic symbols replaced with equivalents (e.g., ﷺ → "(peace be upon him)")

### Font Selection
- Arabic fonts mapped to specific database columns (see `FONT_COLUMN_MAP` in database.py)
- Font paths resolved from `config.json` relative to project root
- Default fallbacks if config missing

### Hadith Quality Control
- Weak hadith indicators: 'ضعیف', 'ضعيف', 'da\'if', 'weak'
- `get_next_hadith()` automatically skips weak hadiths (max 10 attempts)
- Grading displayed on hadith images when available

### Date Handling
- Islamic calendar conversion via `hijridate` library
- Configurable offset (`hijri_offset_days`) for regional calendar differences
- Both Gregorian and Hijri dates displayed on images

## Dependencies

```
beautifulsoup4>=4.14.3    # Web scraping (BeautifulSoup4)
hijridate>=2.3.0          # Islamic calendar conversion
pillow>=12.1.0            # Image generation with RAQM support
requests>=2.31.0          # HTTP requests for scrapers
pydantic-ai>=0.0.14       # AI translation framework
python-dotenv>=1.0.0      # Environment variable management
```

## Common Tasks

**Run with content review:**
```bash
uv run python -m src.daily_ayat_hadith.main
```
The generator will:
1. Fetch ayah and hadith content
2. Create a review file: `output/YYYY-MM-DD/content_review.txt`
3. Pause and wait for your input:
   - Press **ENTER** to continue with image generation (uses edited content)
   - Press **ESC** or **Ctrl+C** to cancel (deletes review file, doesn't update state)
4. If you continue: generates images, updates state, deletes review file

**Content Review Workflow:**
1. When prompted, open `output/YYYY-MM-DD/content_review.txt`
2. Edit Arabic/Urdu text as needed (fix punctuation, etc.)
3. Save the file
4. Return to terminal and press **ENTER**
5. Images will be generated with your edited content

**Force regeneration (reset state):**
Edit `state.json` and change `last_date` to a past date, or delete the file entirely.

**Change hadith source:**
Edit `config.json` → `hadith_source.mode` to "online" or "local"

**Test with different fonts/translations:**
Modify `config.json` → `fonts` and `translations` sections

**Debug AI translation:**
Check `.env` for valid API keys, review logs for error messages

## Git Operations

**Commit Message Guidelines:**
- Keep commit messages simple and short
- Use conventional format: "Add feature", "Fix bug", "Update config"
- Do NOT include references to Claude, AI assistance, or co-authorship
- Focus on what changed, not how it was created

Examples:
- ✓ "Add support for new Arabic font"
- ✓ "Fix hadith scraper timeout handling"
- ✓ "Update translation configuration"
- ✗ "Add feature with Claude assistance"
- ✗ "Co-authored by Claude"

## Important Notes

- **Database dependency**: `content.sqlite3` must exist - it contains all Quran verses and hadith
- **Font dependency**: Font files in `fonts/` are required for text rendering
- **State persistence**: State updates only after successful PNG saves - prevents state corruption on failures
- **Scraper etiquette**: 1-second delays between requests, 10-second timeouts
- **Image quality**: Always save at 95% quality to preserve Arabic text clarity
- **Entry points**: Both `main.py` (root) and `src.daily_ayat_hadith.main` work identically
