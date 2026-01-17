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
        self.base_url = "https://al-hadees.com"
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

        # Look for the Status section
        status_sections = soup.find_all('div', class_='row')
        for section in status_sections:
            # Find the section with "Status" or "حکمِ حدیث"
            headers = section.find_all('h5')
            for header in headers:
                if 'Status' in header.get_text() or 'حکمِ حدیث' in header.get_text():
                    # Get the Arabic grade (صحیح) from the Arabic column
                    # Look for text-success span in the right column
                    cols = section.find_all('div', class_='col-6')
                    for col in cols:
                        # Find the Arabic grade (second col with text-right)
                        if 'text-right' in col.get('class', []):
                            grade_elem = col.find('span', class_='text-success')
                            if grade_elem:
                                grade = grade_elem.get_text(strip=True)
                                break

        # Get Status Reference (حوالہ حکم) - the Arabic reference like (متفق علیہ)
        ref_headers = soup.find_all('h5')
        for header in ref_headers:
            if 'Status Reference' in header.get_text() or 'حوالہ حکم' in header.get_text():
                parent = header.find_parent('div', class_='mb-5')
                if parent:
                    # Get all rows in this section
                    ref_rows = parent.find_all('div', class_='row')
                    # The second row (after the header row) contains the actual reference
                    if len(ref_rows) >= 2:
                        content_row = ref_rows[1]  # Second row has the content
                        right_col = content_row.find('div', class_='text-right')
                        if right_col:
                            ref_elem = right_col.find('h3', class_='font-arabic2')
                            if ref_elem:
                                graded_by_text = ref_elem.get_text(strip=True)
                                # Only keep the actual grading reference like (متفق علیہ)
                                if graded_by_text and graded_by_text != grade:
                                    # Filter out ترقیم and numbers
                                    if 'ترقیم' not in graded_by_text:
                                        graded_by = graded_by_text
                                    else:
                                        # Extract only parentheses content
                                        match = re.search(r'\([^)]+\)', graded_by_text)
                                        if match:
                                            graded_by = match.group(0)

        logger.info(f"Successfully scraped hadith {hadith_number} from al-hadees.com")
        logger.debug(f"Grade: {grade}, Graded by: {graded_by}")

        return AlHadeesScrapedHadith(
            hadith_number=hadith_number,
            arabic_text=arabic_text,
            urdu_translation=urdu_text,
            grade=grade,
            graded_by=graded_by
        )
