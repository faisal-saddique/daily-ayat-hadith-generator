"""Main script for generating daily Ayat and Hadith images."""

import sys
import logging
from pathlib import Path
from datetime import datetime
import json

from .database import IslamicDatabase
from .state import StateManager
from .image_generator import IslamicImageGenerator
from .hadith_provider import HadithProvider, HadithProviderConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    """Main entry point."""
    # Setup paths
    project_root = Path(__file__).parent.parent.parent
    db_path = project_root / "content.sqlite3"
    fonts_dir = project_root / "fonts"
    output_dir = project_root / "output"
    state_file = project_root / "state.json"
    config_file = project_root / "config.json"

    # Ensure output directory exists
    output_dir.mkdir(exist_ok=True)

    # Create date-specific subfolder for today's output
    today_date = datetime.now().date()
    date_output_dir = output_dir / str(today_date)
    date_output_dir.mkdir(exist_ok=True)

    # Load configuration
    arabic_font = 'pdms'  # default
    urdu_translation = 'Maududi'  # default
    english_translation = 'MaududiEn'  # default

    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            arabic_font = config.get('fonts', {}).get('arabic', 'pdms')
            urdu_translation = config.get('translations', {}).get('urdu', 'Maududi')
            english_translation = config.get('translations', {}).get('english', 'MaududiEn')

    # Initialize components
    db = IslamicDatabase(
        db_path,
        arabic_font=arabic_font,
        urdu_translation=urdu_translation,
        english_translation=english_translation
    )
    state_manager = StateManager(state_file)
    image_gen = IslamicImageGenerator(fonts_dir)

    # Initialize hadith provider with configuration
    hadith_config = HadithProviderConfig.from_config_file(config_file)
    hadith_provider = HadithProvider(hadith_config, db=db)

    # Display hadith source info
    source_info = hadith_provider.get_source_info()
    print(f"Hadith Source: {source_info['mode'].upper()}")
    if source_info['online_enabled']:
        print(f"  Collection: {source_info['online_collection']}")
        print(f"  Mode: Hybrid (Sunnah.com + Local DB)")
        print(f"  Fallback: {'Enabled' if source_info['fallback_enabled'] else 'Disabled'}")
    print()

    # Check if we should generate today
    if not state_manager.should_generate_today():
        print("Already generated for today!")
        current_state = state_manager.get_current_state()
        print(f"Last generated: {current_state.last_date}")
        return

    # Generate BOTH Ayah and Hadith daily
    current_state = state_manager.get_current_state()
    today = datetime.now()

    print(f"Generating daily content for {today.date()}...")
    print()

    # Generate Ayah
    print("=" * 50)
    print("GENERATING AYAH")
    print("=" * 50)

    ayah = db.get_next_ayah(current_state.last_surah, current_state.last_ayah)

    print(f"\nAyah: {ayah.surah_name} {ayah.ayah_number}")
    print(f"Arabic: {ayah.arabic_text[:50]}...")
    print(f"Urdu: {ayah.urdu_translation[:50]}...")
    print(f"English: {ayah.english_translation[:50]}...")

    # Generate ayah image(s) - returns a list (single-page or multi-page)
    ayah_images = image_gen.generate_ayat_image(
        surah_number=ayah.surah_number,
        ayah_number=ayah.ayah_number,
        arabic_text=ayah.arabic_text,
        urdu_translation=ayah.urdu_translation,
        english_translation=ayah.english_translation,
        surah_name=ayah.surah_name,
        date=today
    )

    # Save ayah image(s)
    print()
    for page_num, ayah_img in enumerate(ayah_images, 1):
        if len(ayah_images) == 1:
            # Single page ayah
            ayah_filename = f"ayat_{ayah.surah_name.replace(' ', '_')}_{ayah.ayah_number}.png"
        else:
            # Multi-page ayah
            ayah_filename = f"ayat_{ayah.surah_name.replace(' ', '_')}_{ayah.ayah_number}_page{page_num}.png"

        ayah_output_path = date_output_dir / ayah_filename
        ayah_img.save(ayah_output_path, quality=95)

        if len(ayah_images) == 1:
            print(f"✓ Ayah image saved: {ayah_output_path}")
        else:
            print(f"✓ Ayah page {page_num} saved: {ayah_output_path}")

    # Generate Hadith
    print()
    print("=" * 50)
    print("GENERATING HADITH")
    print("=" * 50)

    hadith = hadith_provider.get_next_hadith(current_state.last_hadith)

    print(f"\nHadith: Mishkaat {hadith.hadith_number}")
    if hadith.grade:
        print(f"Grading: {hadith.grade} {hadith.graded_by}")
    print(f"Arabic: {hadith.arabic_text[:50]}...")
    print(f"Urdu: {hadith.urdu_translation[:50]}...")
    if hadith.english_translation:
        print(f"English: {hadith.english_translation[:50]}...")

    # Generate hadith image(s) - returns a list (single-page or multi-page)
    hadith_images = image_gen.generate_hadith_image(
        hadith_number=hadith.hadith_number,
        arabic_text=hadith.arabic_text,
        urdu_translation=hadith.urdu_translation,
        english_translation=hadith.english_translation,
        date=today,
        grade=hadith.grade,
        graded_by=hadith.graded_by
    )

    # Save hadith image(s)
    print()
    for page_num, hadith_img in enumerate(hadith_images, 1):
        if len(hadith_images) == 1:
            # Single page hadith
            hadith_filename = f"hadith_mishkaat_{hadith.hadith_number}.png"
        else:
            # Multi-page hadith
            hadith_filename = f"hadith_mishkaat_{hadith.hadith_number}_page{page_num}.png"

        hadith_output_path = date_output_dir / hadith_filename
        hadith_img.save(hadith_output_path, quality=95)

        if len(hadith_images) == 1:
            print(f"✓ Hadith image saved: {hadith_output_path}")
        else:
            print(f"✓ Hadith page {page_num} saved: {hadith_output_path}")

    # Update state with both
    state_manager.update_after_generation(
        content_type="both",
        surah=ayah.surah_number,
        ayah=ayah.ayah_number,
        hadith=hadith.hadith_number
    )

    print()
    print("=" * 50)
    print("✓ Done! Generated both Ayah and Hadith for today")
    print("=" * 50)

    # Close connections
    hadith_provider.close()


if __name__ == "__main__":
    main()
