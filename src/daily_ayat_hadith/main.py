"""Main script for generating daily Ayat and Hadith images."""

import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta, date
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


def create_review_file(date_output_dir: Path, ayah, hadith) -> Path:
    """
    Create a review text file with ayah and hadith content for editing.

    Args:
        date_output_dir: Output directory for today's date
        ayah: Ayah object with content
        hadith: Hadith object with content

    Returns:
        Path to the created review file
    """
    review_file = date_output_dir / "content_review.txt"

    content = f"""# DAILY CONTENT REVIEW
# Edit the Arabic and Urdu text below as needed
# Press ENTER when ready to generate images
# Press ESC to cancel without generating

{'='*80}
AYAH - {ayah.reference}
{'='*80}

[AYAH_ARABIC_START]
{ayah.arabic_text}
[AYAH_ARABIC_END]

[AYAH_URDU_START]
{ayah.urdu_translation}
[AYAH_URDU_END]

[AYAH_ENGLISH_START]
{ayah.english_translation}
[AYAH_ENGLISH_END]

{'='*80}
HADITH - Mishkaat {hadith.hadith_number}
{'='*80}

[HADITH_ARABIC_START]
{hadith.arabic_text}
[HADITH_ARABIC_END]

[HADITH_URDU_START]
{hadith.urdu_translation}
[HADITH_URDU_END]

[HADITH_ENGLISH_START]
{hadith.english_translation or ''}
[HADITH_ENGLISH_END]

{'='*80}
METADATA (DO NOT EDIT)
{'='*80}
Surah: {ayah.surah_number}
Start Ayah: {ayah.start_ayah}
End Ayah: {ayah.end_ayah}
Ayah Count: {ayah.ayah_count}
Surah Name: {ayah.surah_name}
Hadith Number: {hadith.hadith_number}
Hadith Grade: {hadith.grade or 'N/A'}
Hadith Graded By: {hadith.graded_by or 'N/A'}
"""

    with open(review_file, 'w', encoding='utf-8') as f:
        f.write(content)

    return review_file


def parse_review_file(review_file: Path) -> dict:
    """
    Parse the edited review file and extract content.

    Args:
        review_file: Path to the review file

    Returns:
        Dict with ayah and hadith content and metadata
    """
    with open(review_file, 'r', encoding='utf-8') as f:
        content = f.read()

    def extract_section(text: str, start_marker: str, end_marker: str) -> str:
        """Extract text between markers."""
        start_idx = text.find(start_marker)
        end_idx = text.find(end_marker)

        if start_idx == -1 or end_idx == -1:
            return ""

        # Extract content between markers
        start_idx += len(start_marker)
        extracted = text[start_idx:end_idx].strip()
        return extracted

    # Extract all sections
    data = {
        'ayah': {
            'arabic': extract_section(content, '[AYAH_ARABIC_START]', '[AYAH_ARABIC_END]'),
            'urdu': extract_section(content, '[AYAH_URDU_START]', '[AYAH_URDU_END]'),
            'english': extract_section(content, '[AYAH_ENGLISH_START]', '[AYAH_ENGLISH_END]'),
        },
        'hadith': {
            'arabic': extract_section(content, '[HADITH_ARABIC_START]', '[HADITH_ARABIC_END]'),
            'urdu': extract_section(content, '[HADITH_URDU_START]', '[HADITH_URDU_END]'),
            'english': extract_section(content, '[HADITH_ENGLISH_START]', '[HADITH_ENGLISH_END]'),
        },
        'metadata': {}
    }

    # Extract metadata
    metadata_section = content.split("METADATA (DO NOT EDIT)")
    if len(metadata_section) > 1:
        metadata_lines = metadata_section[1].strip().split('\n')
        for line in metadata_lines:
            if ':' in line and not line.startswith('='):
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                data['metadata'][key] = value.strip()

    return data


def wait_for_user_input() -> bool:
    """
    Wait for user to press Enter or ESC.

    Returns:
        True if user pressed Enter (continue), False if ESC (cancel)
    """
    print()
    print("=" * 80)
    print("REVIEW CONTENT")
    print("=" * 80)
    print("A review file has been created. Please review and edit the content.")
    print()
    print("Options:")
    print("  - Press ENTER to continue with image generation")
    print("  - Press ESC (or Ctrl+C) to cancel without generating images")
    print("=" * 80)
    print()

    try:
        # Cross-platform input handling
        if sys.platform == 'win32':
            import msvcrt
            while True:
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b'\r':  # Enter
                        return True
                    elif key == b'\x1b':  # ESC
                        return False
        else:
            # Unix-like systems (macOS, Linux)
            import termios
            import tty

            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                while True:
                    char = sys.stdin.read(1)
                    if char == '\r' or char == '\n':  # Enter
                        return True
                    elif char == '\x1b':  # ESC
                        return False
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except KeyboardInterrupt:
        # Ctrl+C treated as cancel
        print("\n\nCancelled by user (Ctrl+C)")
        return False


def generate_for_date(
    target_date: date,
    db: IslamicDatabase,
    state_manager: StateManager,
    image_gen: IslamicImageGenerator,
    hadith_provider: HadithProvider,
    output_dir: Path,
    day_num: int = 1,
    total_days: int = 1,
    skip_review: bool = False
) -> bool:
    """
    Generate Ayah and Hadith images for a specific date.

    Args:
        target_date: The date to generate content for
        db: Database instance
        state_manager: State manager instance
        image_gen: Image generator instance
        hadith_provider: Hadith provider instance
        output_dir: Base output directory
        day_num: Current day number (for display)
        total_days: Total number of days being generated (for display)

    Returns:
        True if generation was successful, False if cancelled or skipped
    """
    # Create date-specific subfolder
    date_output_dir = output_dir / str(target_date)
    date_output_dir.mkdir(exist_ok=True)

    # Check if we should generate for this date
    if not state_manager.should_generate_for_date(target_date):
        print(f"Already generated for {target_date}! Skipping...")
        return False

    # Get current state
    current_state = state_manager.get_current_state()

    if total_days > 1:
        print()
        print("#" * 80)
        print(f"# DAY {day_num} OF {total_days}: {target_date}")
        print("#" * 80)

    print(f"\nFetching content for {target_date}...")
    print()

    # Fetch Ayah
    print("=" * 50)
    print("FETCHING AYAH")
    print("=" * 50)

    ayah = db.get_next_ayah(current_state.last_surah, current_state.last_ayah)

    print(f"\nAyah: {ayah.reference}")
    if ayah.ayah_count > 1:
        print(f"  (Combined {ayah.ayah_count} short ayahs)")
    print(f"Arabic: {ayah.arabic_text[:50]}...")
    print(f"Urdu: {ayah.urdu_translation[:50]}...")

    # Fetch Hadith
    print()
    print("=" * 50)
    print("FETCHING HADITH")
    print("=" * 50)

    hadith = hadith_provider.get_next_hadith(current_state.last_hadith)

    print(f"\nHadith: Mishkaat {hadith.hadith_number}")
    if hadith.grade:
        print(f"Grading: {hadith.grade} {hadith.graded_by}")
    print(f"Arabic: {hadith.arabic_text[:50]}...")
    print(f"Urdu: {hadith.urdu_translation[:50]}...")

    # Create review file or use content directly
    review_file = None
    if skip_review:
        # Skip review - use content directly
        print()
        print("=" * 50)
        print("GENERATING IMAGES (review skipped)")
        print("=" * 50)

        edited_content = {
            'ayah': {
                'arabic': ayah.arabic_text,
                'urdu': ayah.urdu_translation,
                'english': ayah.english_translation,
            },
            'hadith': {
                'arabic': hadith.arabic_text,
                'urdu': hadith.urdu_translation,
                'english': hadith.english_translation or '',
            }
        }
    else:
        # Normal flow with review
        print()
        print("=" * 50)
        print("CREATING REVIEW FILE")
        print("=" * 50)

        review_file = create_review_file(date_output_dir, ayah, hadith)
        print(f"\n✓ Review file created: {review_file}")
        print(f"\nYou can now edit the content in: {review_file}")

        # Wait for user input
        should_continue = wait_for_user_input()

        if not should_continue:
            # User cancelled - clean up and exit
            print("\n" + "=" * 50)
            print("CANCELLED - Cleaning up")
            print("=" * 50)

            if review_file.exists():
                review_file.unlink()
                print(f"✓ Deleted review file: {review_file}")

            print(f"\nNo images generated for {target_date}. State not updated.")
            return False

        # User pressed Enter - continue with generation
        print("\n" + "=" * 50)
        print("GENERATING IMAGES")
        print("=" * 50)

        # Parse the (possibly edited) review file
        print("\nReading edited content from review file...")
        edited_content = parse_review_file(review_file)

    # Generate Ayah image with edited content
    print()
    print("=" * 50)
    print("GENERATING AYAH IMAGE")
    print("=" * 50)

    # Create ayah reference for filename and image
    if ayah.start_ayah == ayah.end_ayah:
        ayah_ref_for_filename = str(ayah.start_ayah)
    else:
        ayah_ref_for_filename = f"{ayah.start_ayah}-{ayah.end_ayah}"

    # Use target_date for the image (converted to datetime for compatibility)
    target_datetime = datetime.combine(target_date, datetime.min.time())

    ayah_images = image_gen.generate_ayat_image(
        surah_number=ayah.surah_number,
        ayah_number=ayah.end_ayah,  # For compatibility
        arabic_text=edited_content['ayah']['arabic'],
        urdu_translation=edited_content['ayah']['urdu'],
        english_translation=edited_content['ayah']['english'],
        surah_name=ayah.surah_name,
        date=target_datetime,
        ayah_reference=ayah.reference  # Pass the full reference
    )

    # Save ayah image(s)
    print()
    for page_num, ayah_img in enumerate(ayah_images, 1):
        if len(ayah_images) == 1:
            ayah_filename = f"ayat_{ayah.surah_name.replace(' ', '_')}_{ayah_ref_for_filename}.png"
        else:
            ayah_filename = f"ayat_{ayah.surah_name.replace(' ', '_')}_{ayah_ref_for_filename}_page{page_num}.png"

        ayah_output_path = date_output_dir / ayah_filename
        ayah_img.save(ayah_output_path, quality=95)

        if len(ayah_images) == 1:
            print(f"✓ Ayah image saved: {ayah_output_path}")
        else:
            print(f"✓ Ayah page {page_num} saved: {ayah_output_path}")

    # Generate Hadith image with edited content
    print()
    print("=" * 50)
    print("GENERATING HADITH IMAGE")
    print("=" * 50)

    hadith_images = image_gen.generate_hadith_image(
        hadith_number=hadith.hadith_number,
        arabic_text=edited_content['hadith']['arabic'],
        urdu_translation=edited_content['hadith']['urdu'],
        english_translation=edited_content['hadith']['english'],
        date=target_datetime,
        grade=hadith.grade,
        graded_by=hadith.graded_by
    )

    # Save hadith image(s)
    print()
    for page_num, hadith_img in enumerate(hadith_images, 1):
        if len(hadith_images) == 1:
            hadith_filename = f"hadith_mishkaat_{hadith.hadith_number}.png"
        else:
            hadith_filename = f"hadith_mishkaat_{hadith.hadith_number}_page{page_num}.png"

        hadith_output_path = date_output_dir / hadith_filename
        hadith_img.save(hadith_output_path, quality=95)

        if len(hadith_images) == 1:
            print(f"✓ Hadith image saved: {hadith_output_path}")
        else:
            print(f"✓ Hadith page {page_num} saved: {hadith_output_path}")

    # Delete review file (if it was created)
    if review_file:
        print()
        print("=" * 50)
        print("CLEANING UP")
        print("=" * 50)

        if review_file.exists():
            review_file.unlink()
            print(f"✓ Deleted review file: {review_file}")

    # Update state with both (use end_ayah so next generation continues from correct position)
    # Pass target_date so state reflects the date we generated for
    state_manager.update_after_generation(
        content_type="both",
        surah=ayah.surah_number,
        ayah=ayah.end_ayah,
        hadith=hadith.hadith_number,
        target_date=target_date
    )

    print()
    print("=" * 50)
    print(f"✓ Done! Generated both Ayah and Hadith for {target_date}")
    print("=" * 50)

    return True


def main():
    """Main entry point."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Generate daily Ayah and Hadith images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s              Generate for today only
  %(prog)s --days 3     Generate for today and next 2 days
  %(prog)s -d 7         Generate for a week (today + 6 days)
"""
    )
    parser.add_argument(
        '-d', '--days',
        type=int,
        default=1,
        metavar='N',
        help='Number of days to generate (default: 1 for today only)'
    )
    parser.add_argument(
        '--skip-review',
        action='store_true',
        help='Skip content review step and generate images directly'
    )
    args = parser.parse_args()

    num_days = args.days
    if num_days < 1:
        print("Error: Number of days must be at least 1")
        sys.exit(1)

    # Setup paths
    project_root = Path(__file__).parent.parent.parent
    db_path = project_root / "content.sqlite3"
    fonts_dir = project_root / "fonts"
    output_dir = project_root / "output"
    state_file = project_root / "state.json"
    config_file = project_root / "config.json"

    # Ensure output directory exists
    output_dir.mkdir(exist_ok=True)

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

    # Generate dates to process
    today = datetime.now().date()
    dates_to_generate = [today + timedelta(days=i) for i in range(num_days)]

    if num_days > 1:
        print(f"Generating content for {num_days} days:")
        for d in dates_to_generate:
            print(f"  - {d}")
        print()

    # Track results
    successful = 0
    skipped = 0
    cancelled = False

    try:
        for day_num, target_date in enumerate(dates_to_generate, 1):
            success = generate_for_date(
                target_date=target_date,
                db=db,
                state_manager=state_manager,
                image_gen=image_gen,
                hadith_provider=hadith_provider,
                output_dir=output_dir,
                day_num=day_num,
                total_days=num_days,
                skip_review=args.skip_review
            )

            if success:
                successful += 1
            else:
                # Check if it was skipped (already generated) or cancelled
                if state_manager.should_generate_for_date(target_date):
                    # Still needs generation, so user cancelled
                    cancelled = True
                    break
                else:
                    skipped += 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        cancelled = True
    finally:
        # Close connections
        hadith_provider.close()

    # Print summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Days requested: {num_days}")
    print(f"Successfully generated: {successful}")
    print(f"Skipped (already generated): {skipped}")
    if cancelled:
        print(f"Remaining (cancelled): {num_days - successful - skipped}")
    print("=" * 80)


if __name__ == "__main__":
    main()
