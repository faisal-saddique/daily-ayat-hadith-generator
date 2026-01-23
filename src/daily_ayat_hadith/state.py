"""State tracking for daily Ayat and Hadith generation."""

import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class DailyState:
    """State for daily generation tracking."""
    last_date: str  # ISO format date
    content_type: str  # "ayat" or "hadith"
    last_surah: int
    last_ayah: int
    last_hadith: int


class StateManager:
    """Manage state for daily generation."""

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self._load_state()

    def _load_state(self):
        """Load state from file or create default."""
        if self.state_file.exists():
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.state = DailyState(**data)
        else:
            # Default starting state: Start with first Ayat
            self.state = DailyState(
                last_date="2000-01-01",  # Old date to ensure first run works
                content_type="hadith",  # Will flip to ayat on first run
                last_surah=1,
                last_ayah=0,
                last_hadith=0
            )
            self._save_state()

    def _save_state(self):
        """Save state to file."""
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(self.state), f, indent=2, ensure_ascii=False)

    def should_generate_today(self) -> bool:
        """Check if we should generate for today."""
        today = datetime.now().date().isoformat()
        return today != self.state.last_date

    def should_generate_for_date(self, target_date) -> bool:
        """Check if we should generate for a specific date.

        Args:
            target_date: A date object or ISO format string

        Returns:
            True if the target date is after the last generated date
        """
        if hasattr(target_date, 'isoformat'):
            target_date_str = target_date.isoformat()
        else:
            target_date_str = target_date
        return target_date_str > self.state.last_date

    def get_next_content_type(self) -> str:
        """Get the content type for next generation (alternates)."""
        if self.state.content_type == "ayat":
            return "hadith"
        else:
            return "ayat"

    def update_after_generation(self, content_type: str, surah: int = None,
                               ayah: int = None, hadith: int = None,
                               target_date=None):
        """Update state after successful generation.

        Args:
            content_type: Type of content generated ("ayat", "hadith", or "both")
            surah: Surah number (for ayat content)
            ayah: Ayah number (for ayat content)
            hadith: Hadith number (for hadith content)
            target_date: The date to record (date object or ISO string). Defaults to today.
        """
        if target_date is None:
            date_str = datetime.now().date().isoformat()
        elif hasattr(target_date, 'isoformat'):
            date_str = target_date.isoformat()
        else:
            date_str = target_date

        self.state.last_date = date_str
        self.state.content_type = content_type

        if content_type == "ayat" and surah is not None and ayah is not None:
            self.state.last_surah = surah
            self.state.last_ayah = ayah
        elif content_type == "hadith" and hadith is not None:
            self.state.last_hadith = hadith
        elif content_type == "both":
            # Update both ayah and hadith
            if surah is not None and ayah is not None:
                self.state.last_surah = surah
                self.state.last_ayah = ayah
            if hadith is not None:
                self.state.last_hadith = hadith

        self._save_state()

    def get_current_state(self) -> DailyState:
        """Get current state."""
        return self.state

    def reset_state(self):
        """Reset to initial state."""
        self.state = DailyState(
            last_date="2000-01-01",
            content_type="hadith",
            last_surah=1,
            last_ayah=0,
            last_hadith=0
        )
        self._save_state()
