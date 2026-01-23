"""Database module for accessing Quran and Hadith data."""

import re
import sqlite3
from pathlib import Path
from dataclasses import dataclass
from typing import List


@dataclass
class Ayah:
    """Quran verse data - single ayah."""
    surah_number: int
    ayah_number: int
    arabic_text: str
    urdu_translation: str
    english_translation: str
    surah_name: str


@dataclass
class CombinedAyah:
    """
    Combined ayah data for one or more verses.

    When multiple short ayahs are combined, this class tracks the range
    and provides formatted text with ayah number markers.
    """
    surah_number: int
    start_ayah: int
    end_ayah: int
    arabic_text: str
    urdu_translation: str
    english_translation: str
    surah_name: str
    ayah_count: int

    @property
    def reference(self) -> str:
        """Get the reference string for the ayah(s)."""
        if self.start_ayah == self.end_ayah:
            return f"{self.surah_name} {self.start_ayah}"
        return f"{self.surah_name} {self.start_ayah}-{self.end_ayah}"

    @property
    def ayah_number(self) -> int:
        """For backwards compatibility - returns the end ayah number."""
        return self.end_ayah


def _convert_to_arabic_numerals(num: int) -> str:
    """Convert integer to Arabic-Indic numerals (٠١٢٣٤٥٦٧٨٩)."""
    arabic_digits = '٠١٢٣٤٥٦٧٨٩'
    return ''.join(arabic_digits[int(d)] for d in str(num))


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

    # Ayah combining configuration
    # Short ayahs are combined to ensure visually appealing images
    MIN_CONTENT_LENGTH = 350  # Minimum combined character length before combining
    MAX_CONTENT_LENGTH = 2000  # Don't combine if result would exceed this
    MAX_AYAHS_TO_COMBINE = 3  # Maximum number of consecutive ayahs to combine

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

    def _get_ayahs_in_surah(self, surah_number: int, start_ayah: int, count: int) -> List[Ayah]:
        """Get up to 'count' consecutive ayahs starting from start_ayah in same surah."""
        cursor = self.conn.cursor()

        query = f"""
            SELECT a.SurahNumber, a.AyahNumber, a.{self.arabic_text_column} as ArabicText,
                   t.{self.urdu_translation} as Urdu, t.{self.english_translation} as English,
                   s.NameEnglish as SurahName
            FROM ayah a
            JOIN translations t ON a.SurahNumber = t.SurahNumber AND a.AyahNumber = t.AyahNumber
            JOIN surah s ON a.SurahNumber = s.SurahNumber
            WHERE a.SurahNumber = ? AND a.AyahNumber >= ?
            ORDER BY a.AyahNumber
            LIMIT ?
        """
        cursor.execute(query, (surah_number, start_ayah, count))

        rows = cursor.fetchall()
        return [
            Ayah(
                surah_number=row['SurahNumber'],
                ayah_number=row['AyahNumber'],
                arabic_text=self._clean_text(row['ArabicText']),
                urdu_translation=self._clean_text(row['Urdu']),
                english_translation=row['English'] or "",
                surah_name=row['SurahName']
            )
            for row in rows
        ]

    def _calculate_content_length(self, ayah: Ayah) -> int:
        """Calculate combined character count of all text fields."""
        return len(ayah.arabic_text) + len(ayah.urdu_translation) + len(ayah.english_translation)

    def _combine_ayahs(self, ayahs: List[Ayah]) -> CombinedAyah:
        """
        Combine multiple ayahs into a single CombinedAyah.

        For single ayah: returns as-is without numbering
        For multiple: adds ayah number markers to each verse
        """
        if not ayahs:
            raise ValueError("No ayahs to combine")

        first = ayahs[0]
        last = ayahs[-1]

        # Single ayah - return without modification
        if len(ayahs) == 1:
            return CombinedAyah(
                surah_number=first.surah_number,
                start_ayah=first.ayah_number,
                end_ayah=first.ayah_number,
                arabic_text=first.arabic_text,
                urdu_translation=first.urdu_translation,
                english_translation=first.english_translation,
                surah_name=first.surah_name,
                ayah_count=1
            )

        # Multiple ayahs - add numbered format with markers at the END
        arabic_parts = []
        urdu_parts = []
        english_parts = []

        for i, ayah in enumerate(ayahs):
            ayah_num = str(ayah.ayah_number)
            is_last = (i == len(ayahs) - 1)

            # Arabic: Use ۞ symbol at the end of each ayah (same as bismillah)
            # Don't add symbol to last ayah - image generator adds one at the end
            if is_last:
                arabic_parts.append(ayah.arabic_text)
            else:
                arabic_parts.append(f"{ayah.arabic_text} ۞")
            # Urdu/English: Put ayah number at the end
            urdu_parts.append(f"{ayah.urdu_translation} ({ayah_num})")
            english_parts.append(f"{ayah.english_translation} ({ayah_num})")

        return CombinedAyah(
            surah_number=first.surah_number,
            start_ayah=first.ayah_number,
            end_ayah=last.ayah_number,
            arabic_text=" ".join(arabic_parts),
            urdu_translation=" ".join(urdu_parts),
            english_translation=" ".join(english_parts),
            surah_name=first.surah_name,
            ayah_count=len(ayahs)
        )

    def _get_combined_ayahs(self, surah_number: int, ayah_number: int) -> CombinedAyah:
        """
        Get ayah(s) starting from position, combining if content is short.

        Rules:
        1. Only combine ayahs within the same surah
        2. Only combine consecutive ayahs
        3. Stop if combined length exceeds MAX_CONTENT_LENGTH
        4. Maximum of MAX_AYAHS_TO_COMBINE combined together
        """
        # Get potential ayahs to combine
        ayahs = self._get_ayahs_in_surah(surah_number, ayah_number, self.MAX_AYAHS_TO_COMBINE)

        if not ayahs:
            raise ValueError(f"No ayahs found at {surah_number}:{ayah_number}")

        # Start with first ayah
        combined = [ayahs[0]]
        current_length = self._calculate_content_length(ayahs[0])

        # Try to add more ayahs if too short
        for next_ayah in ayahs[1:]:
            if current_length >= self.MIN_CONTENT_LENGTH:
                break  # Already long enough

            # Verify consecutive (safety check)
            if next_ayah.ayah_number != combined[-1].ayah_number + 1:
                break

            # Check if adding would exceed max length
            next_length = self._calculate_content_length(next_ayah)
            if current_length + next_length > self.MAX_CONTENT_LENGTH:
                break

            combined.append(next_ayah)
            current_length += next_length

        return self._combine_ayahs(combined)

    def get_next_ayah(self, current_surah: int, current_ayah: int) -> CombinedAyah:
        """
        Get the next ayah(s) in sequence, combining short ayahs together.

        If the next ayah is short (combined text < MIN_CONTENT_LENGTH chars),
        it will be combined with subsequent consecutive ayahs from the same surah
        until the minimum length is reached or MAX_AYAHS_TO_COMBINE is hit.

        Args:
            current_surah: Current surah number
            current_ayah: Current ayah number

        Returns:
            CombinedAyah containing one or more verses
        """
        cursor = self.conn.cursor()

        # Find next ayah position
        cursor.execute("""
            SELECT SurahNumber, AyahNumber
            FROM ayah
            WHERE SurahNumber = ? AND AyahNumber > ?
            ORDER BY AyahNumber
            LIMIT 1
        """, (current_surah, current_ayah))

        next_row = cursor.fetchone()

        if not next_row:
            # No more ayahs in current surah, get first ayah of next surah
            cursor.execute("""
                SELECT SurahNumber, MIN(AyahNumber) as AyahNumber
                FROM ayah
                WHERE SurahNumber > ?
                GROUP BY SurahNumber
                ORDER BY SurahNumber
                LIMIT 1
            """, (current_surah,))

            next_row = cursor.fetchone()

            if not next_row:
                # End of Quran, wrap around to beginning
                return self._get_combined_ayahs(1, 1)

        return self._get_combined_ayahs(next_row['SurahNumber'], next_row['AyahNumber'])

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
