"""Simple web scraper for Sunnah.com to fetch hadith content."""

import re
import time
import logging
from typing import Optional
from dataclasses import dataclass

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

logger = logging.getLogger(__name__)


@dataclass
class ScrapedHadith:
    """Hadith data scraped from Sunnah.com."""
    hadith_number: int
    arabic_text: str
    english_translation: str
    collection: str = "mishkat"
    grade: str = ""  # e.g., "صَحِيحٌ"
    graded_by: str = ""  # e.g., "(الألباني)"


class SunnahScraperError(Exception):
    """Exception raised when scraping fails."""
    pass


class SunnahScraper:
    """Simple scraper to fetch hadith from Sunnah.com website."""

    def __init__(self, collection: str = "mishkat", timeout: int = 10):
        """
        Initialize Sunnah scraper.

        Args:
            collection: Hadith collection (e.g., 'mishkat', 'bukhari', 'muslim')
            timeout: Request timeout in seconds
        """
        if requests is None or BeautifulSoup is None:
            raise ImportError(
                "requests and beautifulsoup4 are required. "
                "Install with: uv add requests beautifulsoup4"
            )

        self.collection = collection
        self.timeout = timeout
        self.base_url = "https://sunnah.com"

        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 1.0  # 1 second between requests

    def _get_headers(self) -> dict:
        """Get request headers to mimic a real browser."""
        return {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36'
        }

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        if not text:
            return ""

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        return text

    def get_hadith(self, hadith_number: int) -> ScrapedHadith:
        """
        Fetch a hadith from Sunnah.com.

        Args:
            hadith_number: Hadith number in the collection

        Returns:
            ScrapedHadith object with Arabic and English text

        Raises:
            SunnahScraperError: If scraping fails
        """
        url = f"{self.base_url}/{self.collection}:{hadith_number}"

        try:
            # Rate limit
            self._rate_limit()

            # Make request
            logger.info(f"Fetching hadith from: {url}")
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=self.timeout
            )

            if response.status_code == 404:
                raise SunnahScraperError(f"Hadith {hadith_number} not found in {self.collection}")

            if response.status_code != 200:
                raise SunnahScraperError(
                    f"Failed to fetch hadith: HTTP {response.status_code}"
                )

            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract English text
            english_text = ""
            english_div = soup.find('div', class_='english_hadith_full')
            if english_div:
                text_div = english_div.find('div', class_='text_details')
                if text_div:
                    english_text = self._clean_text(text_div.get_text())

            # Extract Arabic text
            arabic_text = ""
            arabic_span = soup.find('span', class_='arabic_text_details')
            if arabic_span:
                arabic_text = self._clean_text(arabic_span.get_text())

            # Extract grading information
            grade = ""
            graded_by = ""
            grade_table = soup.find('table', class_='gradetable')
            if grade_table:
                arabic_grade_cells = grade_table.find_all('td', class_='arabic_grade')
                # The grade is usually in the cell with the actual grade text (not the "حكم :" label)
                for cell in arabic_grade_cells:
                    cell_text = self._clean_text(cell.get_text())
                    # Skip the "حكم :" cell
                    if cell_text and 'حكم' not in cell_text or (cell_text and len(cell_text) > 10):
                        # Extract grade (bold text) and scholar (in parentheses)
                        # Format: "صَحِيحٌ (الألباني)"
                        match = re.match(r'([^\(]+)(\([^\)]+\))?', cell_text)
                        if match:
                            grade = match.group(1).strip()
                            graded_by = match.group(2).strip() if match.group(2) else ""
                        break

            # Validate we got the data
            if not arabic_text:
                raise SunnahScraperError("Could not extract Arabic text from page")

            if not english_text:
                logger.warning(f"No English translation found for hadith {hadith_number}")

            if grade:
                logger.info(f"Successfully scraped hadith {hadith_number} - Grade: {grade} {graded_by}")
            else:
                logger.info(f"Successfully scraped hadith {hadith_number} - No grading found")

            return ScrapedHadith(
                hadith_number=hadith_number,
                arabic_text=arabic_text,
                english_translation=english_text,
                collection=self.collection,
                grade=grade,
                graded_by=graded_by
            )

        except requests.Timeout:
            raise SunnahScraperError(f"Request timeout while fetching hadith {hadith_number}")

        except requests.RequestException as e:
            raise SunnahScraperError(f"Network error: {e}")

        except Exception as e:
            raise SunnahScraperError(f"Error scraping hadith {hadith_number}: {e}")
