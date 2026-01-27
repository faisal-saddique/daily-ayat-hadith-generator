"""Unified hadith provider supporting local database, Sunnah.com, al-hadees.com, and AI translation."""

import json
import logging
from pathlib import Path
from typing import Optional

from .database import IslamicDatabase, Hadith
from .sunnah_scraper import SunnahScraper, ScrapedHadith, SunnahScraperError
from .alhadees_scraper import AlHadeesScraper, AlHadeesScrapedHadith
from .translation_generator import TranslationGenerator

logger = logging.getLogger(__name__)


class HadithProviderConfig:
    """Configuration for hadith provider."""

    def __init__(
        self,
        mode: str = "local",
        local_db_path: Path = Path("content.sqlite3"),
        online_enabled: bool = False,
        online_collection: str = "mishkat",
        online_timeout: int = 10,
        fallback_to_local: bool = True,
        use_ai_translation: bool = False,
        ai_model: str = "gemini-1.5-flash"
    ):
        self.mode = mode
        self.local_db_path = local_db_path
        self.online_enabled = online_enabled
        self.online_collection = online_collection
        self.online_timeout = online_timeout
        self.fallback_to_local = fallback_to_local
        self.use_ai_translation = use_ai_translation
        self.ai_model = ai_model

    @classmethod
    def from_config_file(cls, config_path: Path) -> 'HadithProviderConfig':
        """Load configuration from JSON file."""
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        hadith_config = config.get('hadith_source', {})

        # Determine mode
        mode = hadith_config.get('mode', 'local')
        online_config = hadith_config.get('online', {})

        # If online mode selected but not enabled, fall back to local
        if mode == 'online' and not online_config.get('enabled', False):
            logger.warning("Online mode selected but not enabled, using local mode")
            mode = 'local'

        ai_config = hadith_config.get('ai_translation', {})

        return cls(
            mode=mode,
            local_db_path=Path(hadith_config.get('local', {}).get('database_path', 'content.sqlite3')),
            online_enabled=online_config.get('enabled', False),
            online_collection=online_config.get('collection', 'mishkat'),
            online_timeout=online_config.get('timeout', 10),
            fallback_to_local=online_config.get('fallback_to_local', True),
            use_ai_translation=ai_config.get('enabled', False),
            ai_model=ai_config.get('model', 'gemini-1.5-flash')
        )


class HadithProvider:
    """Unified provider for hadith data from multiple sources."""

    def __init__(self, config: HadithProviderConfig, db: Optional[IslamicDatabase] = None):
        """
        Initialize hadith provider.

        Args:
            config: Provider configuration
            db: Optional pre-initialized database (for Ayah access)
        """
        self.config = config
        self.db = db
        self.scraper: Optional[SunnahScraper] = None
        self.alhadees_scraper: Optional[AlHadeesScraper] = None
        self.translation_generator: Optional[TranslationGenerator] = None

        # Initialize Sunnah.com scraper if online mode
        if self.config.mode == 'online' and self.config.online_enabled:
            try:
                self.scraper = SunnahScraper(
                    collection=self.config.online_collection,
                    timeout=self.config.online_timeout
                )
                logger.info(f"Initialized Sunnah.com scraper for '{self.config.online_collection}'")
            except Exception as e:
                logger.error(f"Failed to initialize Sunnah.com scraper: {e}")
                if self.config.fallback_to_local:
                    logger.info("Falling back to local database")
                    self.config.mode = 'local'
                else:
                    raise

        # Initialize al-hadees.com scraper if online mode (as fallback)
        if self.config.mode == 'online' and self.config.online_enabled:
            try:
                self.alhadees_scraper = AlHadeesScraper(
                    collection=self.config.online_collection,
                    timeout=self.config.online_timeout
                )
                logger.info(f"Initialized al-hadees.com scraper for '{self.config.online_collection}'")
            except Exception as e:
                logger.warning(f"Failed to initialize al-hadees.com scraper: {e}")

        # Initialize AI translation if enabled
        if self.config.use_ai_translation:
            try:
                self.translation_generator = TranslationGenerator(
                    model=self.config.ai_model
                )
                logger.info(f"Initialized AI translation generator with model '{self.config.ai_model}'")
            except Exception as e:
                logger.warning(f"Failed to initialize AI translation: {e}")
                logger.warning("AI translation will not be available")

        # Ensure local database is available for fallback or local mode
        if self.db is None and (self.config.mode == 'local' or self.config.fallback_to_local):
            self.db = IslamicDatabase(self.config.local_db_path)

    def _convert_scraped_to_hadith(self, scraped: ScrapedHadith) -> Hadith:
        """
        Convert ScrapedHadith (from Sunnah.com) to Hadith dataclass.

        Gets Arabic and English from Sunnah.com, Urdu from local DB.
        """
        # Get Urdu translation from local database
        urdu_translation = ""
        if self.db:
            try:
                local_hadith = self.db.get_hadith(scraped.hadith_number)
                urdu_translation = local_hadith.urdu_translation
                logger.debug(f"Fetched Urdu translation from local DB for hadith {scraped.hadith_number}")
            except Exception as e:
                logger.warning(f"Could not fetch Urdu from local DB: {e}")

        return Hadith(
            hadith_number=scraped.hadith_number,
            arabic_text=scraped.arabic_text,
            urdu_translation=urdu_translation,
            english_translation=scraped.english_translation,
            grade=scraped.grade,
            graded_by=scraped.graded_by
        )

    def _convert_alhadees_to_hadith(self, scraped: AlHadeesScrapedHadith) -> Hadith:
        """
        Convert AlHadeesScrapedHadith (from al-hadees.com) to Hadith dataclass.

        Gets Arabic, Urdu, and grading from al-hadees.com.
        For English: tries local DB first, then AI translation if enabled.

        Note: AI translation is only generated for non-weak hadiths to preserve tokens.
        """
        english_translation = ""

        # Try to get English from local database first
        if self.db:
            try:
                local_hadith = self.db.get_hadith(scraped.hadith_number)
                if local_hadith.english_translation:
                    english_translation = local_hadith.english_translation
                    logger.debug(f"Fetched English translation from local DB for hadith {scraped.hadith_number}")
            except Exception as e:
                logger.debug(f"Could not fetch English from local DB: {e}")

        # Check if hadith is weak BEFORE generating AI translation
        # Create temporary Hadith object to check weakness
        temp_hadith = Hadith(
            hadith_number=scraped.hadith_number,
            arabic_text=scraped.arabic_text,
            urdu_translation=scraped.urdu_translation,
            english_translation=english_translation,
            grade=scraped.grade,
            graded_by=scraped.graded_by
        )

        # Only generate AI translation if:
        # 1. No English translation found in DB
        # 2. AI is enabled
        # 3. Hadith is NOT weak (to preserve tokens)
        if not english_translation and self.translation_generator:
            if self._is_weak_hadith(temp_hadith):
                logger.info(f"Skipping AI translation for weak hadith {scraped.hadith_number}: {scraped.grade}")
            else:
                try:
                    logger.info(f"Generating AI English translation for hadith {scraped.hadith_number}")
                    english_translation = self.translation_generator.get_english_translation(
                        arabic_text=scraped.arabic_text,
                        urdu_translation=scraped.urdu_translation,
                        hadith_number=scraped.hadith_number
                    )
                    logger.info(f"AI translation generated successfully for hadith {scraped.hadith_number}")
                except Exception as e:
                    logger.warning(f"AI translation failed for hadith {scraped.hadith_number}: {e}")

        return Hadith(
            hadith_number=scraped.hadith_number,
            arabic_text=scraped.arabic_text,
            urdu_translation=scraped.urdu_translation,
            english_translation=english_translation,
            grade=scraped.grade,
            graded_by=scraped.graded_by
        )

    def get_hadith(self, hadith_number: int) -> Hadith:
        """
        Get a specific hadith with fallback chain.

        Fallback chain (online mode):
        1. Sunnah.com (Arabic, English, grading) + Local DB (Urdu)
        2. al-hadees.com (Arabic, Urdu, grading) + Local DB or AI (English)
        3. Local DB (fallback)

        Args:
            hadith_number: Hadith number

        Returns:
            Hadith object with all translations and grading

        Raises:
            ValueError: If hadith cannot be retrieved from any source
        """
        # Try Sunnah.com first (if online mode)
        if self.config.mode == 'online' and self.scraper:
            try:
                scraped = self.scraper.get_hadith(hadith_number)
                logger.info(f"✓ Fetched hadith {hadith_number} from Sunnah.com")
                return self._convert_scraped_to_hadith(scraped)

            except SunnahScraperError as e:
                logger.error(f"✗ Sunnah.com failed for hadith {hadith_number}: {e}")

                # Try al-hadees.com as second option
                if self.alhadees_scraper:
                    try:
                        logger.info(f"Trying al-hadees.com for hadith {hadith_number}")
                        alhadees_scraped = self.alhadees_scraper.get_hadith(hadith_number)
                        logger.info(f"✓ Fetched hadith {hadith_number} from al-hadees.com")
                        return self._convert_alhadees_to_hadith(alhadees_scraped)

                    except Exception as alhadees_error:
                        logger.error(f"✗ al-hadees.com failed for hadith {hadith_number}: {alhadees_error}")

                # Fall back to local database if enabled
                if self.config.fallback_to_local and self.db:
                    logger.info(f"Falling back to local database for hadith {hadith_number}")
                else:
                    raise ValueError(f"Failed to fetch hadith {hadith_number} from all online sources")

        # Use local database
        if self.db:
            logger.info(f"Fetching hadith {hadith_number} from local database")
            return self.db.get_hadith(hadith_number)

        raise ValueError(f"No hadith source available to fetch hadith {hadith_number}")

    def _is_weak_hadith(self, hadith: Hadith) -> bool:
        """
        Check if a hadith has a weak (ضعیف) grading.

        Args:
            hadith: Hadith object to check

        Returns:
            True if hadith is weak, False otherwise
        """
        if not hadith.grade:
            return False  # No grading available, allow it

        # Check for weak grading indicators
        # Includes various spellings and transliterations from different sources
        weak_indicators = [
            'ضعیف',   # Arabic weak (Urdu spelling)
            'ضعيف',   # Arabic weak (Arabic spelling)
            'zaeef',  # Urdu/English transliteration (from al-hadees.com)
            "da'if",  # Arabic transliteration with apostrophe
            'daif',   # Arabic transliteration without apostrophe
            'weak',   # English
            'موضوع',  # Fabricated (Arabic)
            'mawdu',  # Fabricated (transliteration)
        ]
        grade_lower = hadith.grade.lower()

        for indicator in weak_indicators:
            if indicator in grade_lower:
                logger.warning(f"Skipping weak hadith {hadith.hadith_number}: {hadith.grade}")
                return True

        return False

    def get_next_hadith(self, current_hadith_number: int, max_attempts: int = 10) -> Hadith:
        """
        Get the next hadith in sequence, skipping weak (ضعیف) hadiths.

        Args:
            current_hadith_number: Current hadith number
            max_attempts: Maximum number of hadiths to try before giving up

        Returns:
            Next Hadith object (non-weak)
        """
        # Always use local database to determine sequence
        # This ensures consistent ordering
        if not self.db:
            raise ValueError("Local database required for sequential hadith access")

        attempts = 0
        next_number = current_hadith_number

        while attempts < max_attempts:
            # Get next in sequence
            next_hadith_meta = self.db.get_next_hadith(next_number)
            next_number = next_hadith_meta.hadith_number

            # Fetch the actual hadith using the configured source
            hadith = self.get_hadith(next_number)

            # Check if it's weak - skip if so
            if not self._is_weak_hadith(hadith):
                logger.info(f"Selected hadith {hadith.hadith_number} with grading: {hadith.grade or 'N/A'}")
                return hadith

            # Try next hadith
            attempts += 1
            logger.info(f"Trying next hadith (attempt {attempts}/{max_attempts})...")

        raise ValueError(f"Could not find non-weak hadith after {max_attempts} attempts")

    def get_source_info(self) -> dict:
        """Get information about current hadith source."""
        return {
            'mode': self.config.mode,
            'online_enabled': self.scraper is not None,
            'online_collection': self.config.online_collection if self.scraper else None,
            'local_db_available': self.db is not None,
            'fallback_enabled': self.config.fallback_to_local,
            'hybrid_mode': self.config.mode == 'online' and self.db is not None
        }

    def close(self):
        """Close connections and cleanup."""
        if self.db:
            self.db.close()
