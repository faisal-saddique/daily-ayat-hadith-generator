"""Al-Hadees.com scraper for fetching hadith data."""

import logging
import requests
import re
import time
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AlHadeesScrapedHadith:
    """Data class for scraped hadith from al-hadees.com."""
    hadith_number: int
    arabic_text: str
    urdu_translation: str
    grade: str = ""
    graded_by: str = ""


class AlHadeesScraper:
    """Scraper for al-hadees.com."""

    @staticmethod
    def _clean_arabic_text(text: str) -> str:
        """
        Clean Arabic text by removing unwanted characters.

        Args:
            text: Raw Arabic text

        Returns:
            Cleaned text with newlines replaced by spaces
        """
        # Replace literal \n \r \t (escaped characters as strings) with spaces
        text = text.replace('\\n', ' ').replace('\\r', ' ').replace('\\t', ' ')

        # Replace actual newlines, carriage returns, and tabs with spaces
        text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')

        # Remove any stray backslashes
        text = text.replace('\\', ' ')

        # Collapse multiple spaces into one
        import re
        text = re.sub(r'\s+', ' ', text)

        # Strip leading/trailing whitespace
        return text.strip()

    def __init__(self, collection: str = "mishkat", timeout: int = 10):
        """
        Initialize al-hadees.com scraper.

        Args:
            collection: Hadith collection name (mishkat, bukhari, muslim, etc.)
            timeout: Request timeout in seconds
        """
        self.collection = collection
        self.timeout = timeout
        self.base_url = "https://www.al-hadees.com"
        self.last_request_time = 0
        self.min_delay = 1.0  # Minimum 1 second between requests

        # Headers to mimic browser request
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Referer': 'https://www.google.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        }

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_delay:
            time.sleep(self.min_delay - time_since_last)
        self.last_request_time = time.time()

    def get_hadith(self, hadith_number: int) -> AlHadeesScrapedHadith:
        """
        Fetch a specific hadith from al-hadees.com.

        Args:
            hadith_number: Hadith number to fetch

        Returns:
            AlHadeesScrapedHadith object with Arabic, Urdu, and grading

        Raises:
            Exception: If hadith cannot be fetched or parsed
        """
        url = f"{self.base_url}/{self.collection}/{hadith_number}"

        logger.info(f"Fetching hadith from: {url}")

        # Rate limiting
        self._rate_limit()

        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            response.raise_for_status()

        except requests.Timeout:
            raise Exception(f"Request timeout while fetching hadith {hadith_number}")
        except requests.RequestException as e:
            raise Exception(f"Error fetching hadith {hadith_number}: {str(e)}")

        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract Arabic text (h4 with font-arabic2 class)
        arabic_elem = soup.find('h4', class_='font-arabic2')
        if not arabic_elem:
            raise Exception(f"Could not find Arabic text for hadith {hadith_number}")

        arabic_text = self._clean_arabic_text(arabic_elem.get_text(strip=True))

        # Extract Urdu translation
        urdu_elem = soup.find('h4', class_='font-urdu')
        if not urdu_elem:
            raise Exception(f"Could not find Urdu translation for hadith {hadith_number}")

        urdu_text = self._clean_arabic_text(urdu_elem.get_text(strip=True))

        # Extract grading (حکمِ حدیث) in Arabic
        grade = ""
        graded_by = ""

        # Look for the Status section within mb-5 divs for better accuracy
        all_mb5_divs = soup.find_all('div', class_='mb-5')
        for div in all_mb5_divs:
            # Check if this div contains a Status header
            headers = div.find_all('h5')
            has_status_header = False

            for header in headers:
                header_text = header.get_text(strip=True)
                if header_text == 'Status' or header_text == 'حکمِ حدیث':
                    has_status_header = True
                    break

            if has_status_header:
                # The grade is in the second row, right column
                rows = div.find_all('div', class_='row')
                if len(rows) >= 2:
                    content_row = rows[1]  # Second row has the actual content
                    right_col = content_row.find('div', class_='text-right')
                    if right_col:
                        # Look for span with text-success (sahih), text-danger (weak), or text-warning (hasan)
                        grade_elem = right_col.find('span', class_='text-success')
                        if not grade_elem:
                            grade_elem = right_col.find('span', class_='text-danger')
                        if not grade_elem:
                            grade_elem = right_col.find('span', class_='text-warning')

                        if grade_elem:
                            grade = grade_elem.get_text(strip=True)
                            break

        # Note: al-hadees.com has a "Status Reference" (حوالہ حکم) section, but it typically
        # contains another form of the grade (e.g., Arabic script version) rather than
        # the scholar who graded it. Unlike Sunnah.com which provides actual grader names
        # like "Al-Albani", al-hadees.com doesn't provide "graded by" information.
        # So we leave graded_by empty for al-hadees.com data.

        logger.info(f"Successfully scraped hadith {hadith_number} from al-hadees.com")
        logger.debug(f"Grade: {grade}")

        return AlHadeesScrapedHadith(
            hadith_number=hadith_number,
            arabic_text=arabic_text,
            urdu_translation=urdu_text,
            grade=grade,
            graded_by=graded_by
        )
