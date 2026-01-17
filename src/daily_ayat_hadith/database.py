"""Database module for accessing Quran and Hadith data."""

import re
import sqlite3
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Ayah:
    """Quran verse data."""
    surah_number: int
    ayah_number: int
    arabic_text: str
    urdu_translation: str
    english_translation: str
    surah_name: str


@dataclass
class Hadith:
    """Hadith data."""
    hadith_number: int
    arabic_text: str
    urdu_translation: str
    english_translation: str = ""  # Optional English translation
    grade: str = ""  # e.g., "صَحِيحٌ"
    graded_by: str = ""  # e.g., "(الألباني)"


class IslamicDatabase:
    """Interface to the Islamic database."""

    # Map font names to their corresponding database columns
    FONT_COLUMN_MAP = {
        'indopak': 'AyahTextIndoPakForIOS',
        'muhammadi': 'AyahTextMuhammadi',
        'pdms': 'AyahTextPdms',
        'qalam': 'AyahTextQalam',
    }

    def __init__(self, db_path: Path, arabic_font: str = 'pdms', urdu_translation: str = 'Maududi', english_translation: str = 'MaududiEn'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.arabic_font = arabic_font
        self.arabic_text_column = self.FONT_COLUMN_MAP.get(arabic_font, 'AyahTextPdms')
        self.urdu_translation = urdu_translation
        self.english_translation = english_translation

    def _clean_text(self, text: str) -> str:
        """Clean text by removing HTML entities and escape sequences."""
        if not text:
            return text

        # Replace literal \n with space
        text = text.replace('\\n', ' ')

        # Replace actual newlines with space (for multiline database entries)
        text = text.replace('\n', ' ')

        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)

        # Trim whitespace
        text = text.strip()

        return text

    def get_ayah(self, surah_number: int, ayah_number: int) -> Ayah:
        """Get a specific ayah with translations."""
        cursor = self.conn.cursor()

        # Get Arabic text and surah name from joined tables using selected font
        query = f"""
            SELECT a.SurahNumber, a.AyahNumber, a.{self.arabic_text_column} as ArabicText, s.NameEnglish
            FROM ayah a
            JOIN surah s ON a.SurahNumber = s.SurahNumber
            WHERE a.SurahNumber = ? AND a.AyahNumber = ?
        """
        cursor.execute(query, (surah_number, ayah_number))

        ayah_row = cursor.fetchone()
        if not ayah_row:
            raise ValueError(f"Ayah not found: {surah_number}:{ayah_number}")

        # Get translations using configured translation columns
        query = f"""
            SELECT {self.urdu_translation}, {self.english_translation}
            FROM translations
            WHERE SurahNumber = ? AND AyahNumber = ?
        """
        cursor.execute(query, (surah_number, ayah_number))

        trans_row = cursor.fetchone()
        if not trans_row:
            raise ValueError(f"Translations not found: {surah_number}:{ayah_number}")

        return Ayah(
            surah_number=ayah_row['SurahNumber'],
            ayah_number=ayah_row['AyahNumber'],
            arabic_text=self._clean_text(ayah_row['ArabicText']),
            urdu_translation=self._clean_text(trans_row[self.urdu_translation]),
            english_translation=trans_row[self.english_translation],
            surah_name=ayah_row['NameEnglish']
        )

    def get_next_ayah(self, current_surah: int, current_ayah: int) -> Ayah:
        """Get the next ayah in sequence."""
        cursor = self.conn.cursor()

        # Try next ayah in same surah first
        cursor.execute("""
            SELECT SurahNumber, AyahNumber
            FROM ayah
            WHERE SurahNumber = ? AND AyahNumber > ?
            ORDER BY AyahNumber
            LIMIT 1
        """, (current_surah, current_ayah))

        next_ayah = cursor.fetchone()

        if next_ayah:
            return self.get_ayah(next_ayah['SurahNumber'], next_ayah['AyahNumber'])

        # If no more ayahs in current surah, get first ayah of next surah
        cursor.execute("""
            SELECT SurahNumber, MIN(AyahNumber) as AyahNumber
            FROM ayah
            WHERE SurahNumber > ?
            GROUP BY SurahNumber
            ORDER BY SurahNumber
            LIMIT 1
        """, (current_surah,))

        next_ayah = cursor.fetchone()

        if next_ayah:
            return self.get_ayah(next_ayah['SurahNumber'], next_ayah['AyahNumber'])

        # If we've reached the end, start from the beginning
        return self.get_ayah(1, 1)

    def get_hadith(self, hadith_number: int) -> Hadith:
        """Get a specific hadith from Mishkaat."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT HadithNumber, Arabic, Urdu
            FROM mishkaat
            WHERE HadithNumber = ?
        """, (hadith_number,))

        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Hadith not found: {hadith_number}")

        # Generate simple English translation
        english = self._generate_hadith_english(row['HadithNumber'], row['Urdu'])

        return Hadith(
            hadith_number=row['HadithNumber'],
            arabic_text=self._clean_text(row['Arabic']),
            urdu_translation=self._clean_text(row['Urdu']),
            english_translation=english
        )

    def _generate_hadith_english(self, hadith_number: int, urdu_text: str) -> str:
        """Generate or retrieve English translation for hadith."""
        # Manual translations for specific hadiths (can be expanded)
        translations = {
            4629: 'Abdullah ibn Amr narrated that a man asked Allah\'s Messenger ﷺ, "Which characteristic of Islam is best?" He said, "You should feed food and should greet not only those you know but also those whom you do not know."',
            4631: 'Abu Hurayrah narrated that Allah\'s Messenger ﷺ said, "You shall not enter paradise until you believe, and you shall not be perfect in belief unless you love each other. Shall I not guide you to that, which if you practice, you shall love each other? Spread salaam among yourselves (offering salaam to acquaintances and strangers alike)."',
        }

        return translations.get(hadith_number, "")

    def get_next_hadith(self, current_hadith_number: int) -> Hadith:
        """Get the next hadith in Mishkaat."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT HadithNumber
            FROM mishkaat
            WHERE HadithNumber > ?
            ORDER BY HadithNumber
            LIMIT 1
        """, (current_hadith_number,))

        next_hadith = cursor.fetchone()

        if next_hadith:
            return self.get_hadith(next_hadith['HadithNumber'])

        # If we've reached the end, start from the beginning
        cursor.execute("""
            SELECT MIN(HadithNumber) as HadithNumber
            FROM mishkaat
        """)

        first_hadith = cursor.fetchone()
        return self.get_hadith(first_hadith['HadithNumber'])

    def get_total_ayahs(self) -> int:
        """Get total number of ayahs."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM ayah")
        return cursor.fetchone()['count']

    def get_total_hadiths(self) -> int:
        """Get total number of hadiths in Mishkaat."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM mishkaat")
        return cursor.fetchone()['count']

    def close(self):
        """Close database connection."""
        self.conn.close()
