"""Quran.com API client for fetching Quran verses and translations."""

import re
import time
import logging
import requests
from requests.auth import HTTPBasicAuth
from typing import Optional, List

from .database import Ayah, CombinedAyah

logger = logging.getLogger(__name__)


class QuranAPIError(Exception):
    pass


class QuranAPI:
    """Client for the Quran.com API (api.quran.com/api/v4)."""

    BASE_URL = "https://api.quran.com/api/v4"
    TOKEN_URL = "https://oauth2.quran.foundation/oauth2/token"

    # Translation IDs on quran.com
    URDU_TRANSLATION_IDS = {
        'Maududi': 97,       # Tafheem e Qur'an - Syed Abu Ali Maududi
        'Jalandhary': 234,   # Fatah Muhammad Jalandhari
        'Junagarhi': 54,     # Maulana Muhammad Junagarhi
        'Israr': 158,        # Dr. Israr Ahmad - Bayan-ul-Quran
    }

    ENGLISH_TRANSLATION_IDS = {
        'MaududiEn': 95,             # Sayyid Abul Ala Maududi
        'Pickthall': 19,             # Mohammed Marmaduke Pickthall
        'YousufAli': 22,             # Abdullah Yusuf Ali
        'SaheehInternational': 20,   # Saheeh International
        'TaqiEnglish': 84,           # Mufti Taqi Usmani
    }

    # Map font config names to API Arabic text fields
    ARABIC_FIELD_MAP = {
        'indopak': 'text_indopak',
        'pdms': 'text_indopak',
        'muhammadi': 'text_uthmani',
        'qalam': 'text_uthmani',
    }

    MIN_CONTENT_LENGTH = 600
    MAX_CONTENT_LENGTH = 2000
    MAX_AYAHS_TO_COMBINE = 3

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        urdu_translation: str = 'Maududi',
        english_translation: str = 'MaududiEn',
        arabic_font: str = 'pdms',
        timeout: int = 15,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self.arabic_field = self.ARABIC_FIELD_MAP.get(arabic_font, 'text_indopak')

        self._urdu_id = self.URDU_TRANSLATION_IDS.get(urdu_translation)
        self._english_id = self.ENGLISH_TRANSLATION_IDS.get(english_translation)
        self._translation_ids = [i for i in [self._urdu_id, self._english_id] if i is not None]

        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

        if self._urdu_id is None:
            logger.warning(
                f"Urdu translator '{urdu_translation}' has no quran.com API ID — "
                "will fall back to local DB for Urdu."
            )
        if self._english_id is None:
            logger.warning(
                f"English translator '{english_translation}' has no quran.com API ID — "
                "will fall back to local DB for English."
            )

    def has_translation_ids(self) -> bool:
        """Return True if at least the Urdu translation ID is configured."""
        return self._urdu_id is not None

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token

        resp = requests.post(
            self.TOKEN_URL,
            auth=HTTPBasicAuth(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        token: str = data["access_token"]
        self._token = token
        self._token_expiry = time.time() + data.get("expires_in", 3600)
        return token

    @staticmethod
    def _clean_text(text: str) -> str:
        """Strip HTML footnote tags, HTML tags, entities, and extra whitespace."""
        # Remove <sup ...>...</sup> footnote elements entirely
        text = re.sub(r'<sup[^>]*>.*?</sup>', '', text, flags=re.DOTALL)
        # Remove any remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode common HTML entities
        text = (
            text.replace('&amp;', '&')
                .replace('&lt;', '<')
                .replace('&gt;', '>')
                .replace('&nbsp;', ' ')
        )
        return re.sub(r'\s+', ' ', text).strip()

    def _get_headers(self) -> dict:
        try:
            return {"Authorization": f"Bearer {self._get_token()}"}
        except Exception as e:
            logger.debug(f"Could not get auth token, proceeding without: {e}")
            return {}

    def _fetch_verse(self, surah: int, ayah: int) -> Optional[Ayah]:
        """Fetch a single verse from the API. Returns None if not found."""
        params: dict = {"fields": self.arabic_field}
        if self._translation_ids:
            params["translations"] = ",".join(str(i) for i in self._translation_ids)

        resp = requests.get(
            f"{self.BASE_URL}/verses/by_key/{surah}:{ayah}",
            headers=self._get_headers(),
            params=params,
            timeout=self.timeout,
        )

        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        verse = resp.json()["verse"]
        arabic_text = verse.get(self.arabic_field) or verse.get("text_uthmani", "")

        urdu = ""
        english = ""
        for t in verse.get("translations", []):
            rid = t["resource_id"]
            if rid == self._urdu_id:
                urdu = self._clean_text(t["text"])
            elif rid == self._english_id:
                english = self._clean_text(t["text"])

        return Ayah(
            surah_number=surah,
            ayah_number=ayah,
            arabic_text=arabic_text,
            urdu_translation=urdu,
            english_translation=english,
            surah_name="",  # filled in by caller
        )

    def _fetch_verses(self, surah: int, start_ayah: int, count: int) -> List[Ayah]:
        """Fetch up to count consecutive verses from the same surah."""
        verses = []
        for i in range(count):
            try:
                v = self._fetch_verse(surah, start_ayah + i)
                if v is None:
                    break
                verses.append(v)
            except Exception as e:
                logger.warning(f"Failed to fetch {surah}:{start_ayah + i} from API: {e}")
                break
        return verses

    @staticmethod
    def _content_length(ayah: Ayah) -> int:
        return len(ayah.arabic_text) + len(ayah.urdu_translation) + len(ayah.english_translation)

    def get_combined_ayahs(
        self, surah_number: int, ayah_number: int, surah_name: str = ""
    ) -> CombinedAyah:
        """
        Fetch ayah(s) starting at surah_number:ayah_number, combining short ayahs
        using the same rules as IslamicDatabase._get_combined_ayahs().

        Args:
            surah_number: Surah (chapter) number 1-114
            ayah_number: Starting ayah number
            surah_name: Surah name to embed in result (provided by caller from local DB)

        Returns:
            CombinedAyah ready for image generation

        Raises:
            QuranAPIError: If no verses could be fetched
        """
        ayahs = self._fetch_verses(surah_number, ayah_number, self.MAX_AYAHS_TO_COMBINE)

        if not ayahs:
            raise QuranAPIError(f"No verses returned for {surah_number}:{ayah_number}")

        # Apply combining logic (mirrors IslamicDatabase._get_combined_ayahs)
        combined = [ayahs[0]]
        current_length = self._content_length(ayahs[0])

        for next_ayah in ayahs[1:]:
            if current_length >= self.MIN_CONTENT_LENGTH:
                break
            if next_ayah.ayah_number != combined[-1].ayah_number + 1:
                break
            next_len = self._content_length(next_ayah)
            if current_length + next_len > self.MAX_CONTENT_LENGTH:
                break
            combined.append(next_ayah)
            current_length += next_len

        first = combined[0]
        last = combined[-1]

        if len(combined) == 1:
            return CombinedAyah(
                surah_number=first.surah_number,
                start_ayah=first.ayah_number,
                end_ayah=first.ayah_number,
                arabic_text=first.arabic_text,
                urdu_translation=first.urdu_translation,
                english_translation=first.english_translation,
                surah_name=surah_name,
                ayah_count=1,
            )

        arabic_parts: List[str] = []
        urdu_parts: List[str] = []
        english_parts: List[str] = []

        for i, ayah in enumerate(combined):
            is_last = i == len(combined) - 1
            arabic_parts.append(ayah.arabic_text if is_last else f"{ayah.arabic_text} ۞")
            urdu_parts.append(ayah.urdu_translation)
            english_parts.append(ayah.english_translation)

        return CombinedAyah(
            surah_number=first.surah_number,
            start_ayah=first.ayah_number,
            end_ayah=last.ayah_number,
            arabic_text=" ".join(arabic_parts),
            urdu_translation=" ".join(urdu_parts),
            english_translation=" ".join(english_parts),
            surah_name=surah_name,
            ayah_count=len(combined),
        )
