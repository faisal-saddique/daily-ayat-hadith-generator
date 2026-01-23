# Daily Ayat and Hadith Generator

An automated system that generates beautiful Islamic graphics featuring daily Quran verses (Ayat) and Hadith from authentic sources. Creates high-quality, shareable images with Arabic text, Urdu and English translations, and Islamic calendar dates.

## Features

- **Daily Content Generation**: Automatically generates both Ayat and Hadith every day
- **Multi-Day Generation**: Generate content for multiple days in advance with `--days` argument
- **Content Review Workflow**: Edit Arabic/Urdu text before image generation for quality control
- **Beautiful Image Output**: Creates 1080x1920 PNG images optimized for social media sharing
- **Multi-Language Support**:
  - Arabic (source text with 4 font variants)
  - Urdu (12 translator options)
  - English (8 translator options)
- **Multi-Source Hadith System**: Hybrid architecture with automatic fallback
  - Primary: Sunnah.com (Arabic + English)
  - Secondary: Al-hadees.com (Arabic + Urdu)
  - Fallback: Local database
- **AI-Powered Translation**: Uses Google Gemini/OpenAI to generate missing English translations
- **Quality Assurance**: Automatically filters weak hadiths, showing only authentic traditions
- **Smart Ayah Combining**: Automatically combines short consecutive ayahs for better visual layout
- **Islamic Calendar**: Displays Hijri dates with configurable offset
- **Proper Text Rendering**: Supports complex Arabic/Urdu typography with adaptive layouts
- **State Management**: Tracks progress and prevents duplicate generations

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) - Fast Python package manager
- Required fonts (included in `fonts/` directory)
- SQLite database with Quran and Hadith content (`content.sqlite3`)
- API keys for AI translation (optional but recommended)

## Installation

1. **Install uv** (Python package manager)
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or using pip
pip install uv
```

2. **Clone the repository**
```bash
git clone https://github.com/faisal-saddique/daily-ayat-hadith-generator.git
cd daily-ayat-hadith-generator
```

3. **Install dependencies**
```bash
uv sync
```

This will create a virtual environment in `.venv` and install all required dependencies.

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env and add your API keys:
# GEMINI_API_KEY=your_gemini_api_key_here
# OPENAI_API_KEY=your_openai_api_key_here  # Optional alternative
```

5. **Verify required files**
- Ensure `content.sqlite3` database exists
- Ensure fonts are in the `fonts/` directory
- Ensure `config.json` and `state.json` are present

## Usage

### Basic Usage

**Generate for today (default)**
```bash
uv run python -m src.daily_ayat_hadith.main
```

**Generate for multiple days in advance**
```bash
# Generate for today and the next 2 days (3 total)
uv run python -m src.daily_ayat_hadith.main --days 3

# Generate for a full week
uv run python -m src.daily_ayat_hadith.main -d 7
```

### Command Line Options

```
usage: main.py [-h] [-d N]

options:
  -h, --help    show this help message and exit
  -d, --days N  Number of days to generate (default: 1 for today only)
```

### Content Review Workflow

When you run the generator, it follows an interactive workflow:

1. **Fetch Content**: Retrieves the next Ayah and Hadith from configured sources
2. **Create Review File**: Saves content to `output/YYYY-MM-DD/content_review.txt`
3. **Wait for Input**: Pauses for you to review/edit the content
   - Press **ENTER** to continue with image generation
   - Press **ESC** or **Ctrl+C** to cancel (no images generated, state unchanged)
4. **Generate Images**: Creates PNG files using the (possibly edited) content
5. **Cleanup**: Deletes the review file and updates state

This workflow allows you to:
- Fix typos or punctuation in Arabic/Urdu text
- Review content before publishing
- Cancel if the content isn't suitable

When generating multiple days, this workflow repeats for each day.

### Alternative: Activate venv first

```bash
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python -m src.daily_ayat_hadith.main
```

### Automated Daily Execution

**Using Cron (Linux/Mac)**:
```bash
# Open crontab editor
crontab -e

# Add this line to run daily at 8 AM
0 8 * * * cd /path/to/daily-ayat-hadith-generator && /path/to/.local/bin/uv run python -m src.daily_ayat_hadith.main
```

**Using Task Scheduler (Windows)**:
- Create a new task
- Set trigger: Daily at desired time
- Set action: Run `uv.exe` with arguments `run python -m src.daily_ayat_hadith.main`
- Set start in: Project directory path

**Using GitHub Actions** (for automated cloud execution):
Create `.github/workflows/daily-generation.yml` to run on a schedule.

## Configuration

### `config.json`

Customize the generator behavior:

```json
{
  "hijri_offset_days": -1,           // Adjust Islamic date (±days)
  "translations": {
    "urdu": "Maududi",               // Choose Urdu translator
    "english": "MaududiEn"           // Choose English translator
  },
  "fonts": {
    "arabic": "pdms",                // Arabic font variant
    "urdu": "jameelnoorinastaleeq"   // Urdu font variant
  },
  "hadith_source": {
    "mode": "online",                // "online" or "local"
    "online": {
      "enabled": true,
      "collection": "mishkat",       // Hadith collection name
      "timeout": 10,
      "fallback_to_local": true      // Enable fallback chain
    },
    "ai_translation": {
      "enabled": true,
      "model": "gemini-2.5-flash"    // Or "openai"
    }
  }
}
```

**Available Urdu Translators**: Maududi, Jalandhary, Junagarhi, Taqi, AhmadRaza, TahirulQadri, AbdusSalam, Kilani, Islahi, Majid, Israr, Riffat

**Available English Translators**: MaududiEn, Mubarakpuri, Pickthall, SaheehInternational, Sarwar, Shakir, YousufAli, TaqiEnglish

**Available Arabic Fonts**: pdms, indopak, muhammadi, qalam

**Available Urdu Fonts**: jameelnoorinastaleeq, noto

### `state.json`

Tracks generation progress (auto-managed):
```json
{
  "last_date": "2026-01-17",    // Last generation date
  "content_type": "both",       // Content types generated
  "last_surah": 3,              // Last Surah processed
  "last_ayah": 71,              // Last Ayah processed
  "last_hadith": 4636           // Last Hadith processed
}
```

## Project Structure

```
daily_ayat_and_hadith/
├── main.py                     # Entry point
├── config.json                 # Configuration file
├── state.json                  # State tracking
├── content.sqlite3             # Quran & Hadith database (~426MB)
├── .env                        # API keys (not in git)
├── .env.example                # Environment template
├── fonts/                      # Arabic & Urdu fonts
├── output/                     # Generated images by date
│   └── YYYY-MM-DD/
│       ├── content_review.txt  # Temporary review file (deleted after generation)
│       ├── ayat_SurahName_AyahNumber.png
│       └── hadith_mishkaat_HadithNumber.png
└── src/daily_ayat_hadith/
    ├── main.py                 # Main generation logic
    ├── state.py                # State management
    ├── database.py             # Database access
    ├── hadith_provider.py      # Multi-source hadith system
    ├── sunnah_scraper.py       # Sunnah.com scraper
    ├── alhadees_scraper.py     # Al-hadees.com scraper
    ├── translation_generator.py # AI translation
    └── image_generator.py      # Image generation
```

## How It Works

### Multi-Source Hadith System

The generator uses a smart fallback chain:

1. **Sunnah.com** (Primary): Arabic text + English translation + grading
2. **Al-hadees.com** (Secondary): Arabic text + Urdu translation + grading
3. **Local Database** (Fallback): Pre-stored hadith from local SQLite

If a source fails or times out, it automatically tries the next source in the chain.

### AI Translation

When a hadith lacks an English translation:
- Uses Google Gemini or OpenAI to generate one
- Provides scholarly translation with Islamic terminology
- Uses Urdu translation as reference for accuracy
- Includes confidence level assessment

### Image Generation Process

1. Fetches content (Ayat and Hadith) from database/online sources
2. Creates review file for manual editing opportunity
3. Waits for user approval (ENTER to continue, ESC to cancel)
4. Parses edited content from review file
5. Converts Gregorian date to Hijri (Islamic) date for Ayat images
6. Measures text and calculates optimal font sizes
7. Renders Arabic/Urdu text with proper text shaping (RAQM)
8. Applies adaptive layout to fit content beautifully
9. Saves high-quality PNG to dated output directory
10. Cleans up review file and updates state

### Quality Control

- **Weak Hadith Filtering**: Automatically skips hadiths graded as weak (ضَعِيفٌ)
- **Error Handling**: Graceful degradation with comprehensive logging
- **Rate Limiting**: 1-second delays between scraper requests
- **Timeout Protection**: 10-second timeout per online request

## Output Examples

Generated images include:
- Opening prayers (A'oodhu billah, Bismillah)
- Arabic text with proper calligraphy
- Urdu translation
- English translation
- Hadith grading status (Sahih/Hasan)
- Date (Hijri for Ayat, Gregorian for Hadith)
- Source reference (Surah:Ayah or Hadith number)

Images are saved as:
- `output/2026-01-17/ayat_Aal-i-Imraan_71.png` (Surah Aal-i-Imraan, Ayah 71)
- `output/2026-01-17/ayat_Aal-i-Imraan_74-77.png` (Combined short ayahs 74-77)
- `output/2026-01-17/hadith_mishkaat_4636.png` (Mishkaat Hadith 4636)

## Dependencies

```
beautifulsoup4>=4.14.3    # Web scraping
hijridate>=2.3.0          # Islamic calendar conversion
pillow>=12.1.0            # Image generation
requests>=2.31.0          # HTTP requests
pydantic-ai>=0.0.14       # AI translation framework
python-dotenv>=1.0.0      # Environment management
```

## Technical Details

- **Database**: SQLite with complete Quran (multiple translations) and Mishkaat hadith collection
- **Image Format**: PNG (1080x1920 resolution, 95% quality)
- **Text Engine**: Pillow with RAQM for complex text shaping
- **AI Framework**: Pydantic AI with structured output
- **State Persistence**: JSON-based state tracking

## Troubleshooting

**Images not generating**:
- Verify fonts exist in `fonts/` directory
- Check database file `content.sqlite3` exists
- Ensure output directory has write permissions

**AI translation not working**:
- Verify API keys in `.env` file
- Check API quota/billing status
- Review logs for specific error messages

**Hadith scraping fails**:
- Check internet connection
- Verify hadith collection name in config
- Enable local fallback in configuration

**Arabic/Urdu text rendering incorrectly**:
- Ensure RAQM library is installed (usually comes with Pillow)
- Verify font files are not corrupted
- Try different font variants in config

## License

MIT License - Feel free to use and modify for your own Islamic content generation needs.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## Acknowledgments

- Quran translations from various scholars
- Hadith from Mishkaat ul-Masabih collection
- Sunnah.com and Al-hadees.com for online hadith sources
- Font creators for beautiful Arabic and Urdu typography
