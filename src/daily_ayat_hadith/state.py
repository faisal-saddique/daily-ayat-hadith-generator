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

    def get_next_content_type(self) -> str:
        """Get the content type for next generation (alternates)."""
        if self.state.content_type == "ayat":
            return "hadith"
        else:
            return "ayat"

    def update_after_generation(self, content_type: str, surah: int = None,
                               ayah: int = None, hadith: int = None):
        """Update state after successful generation."""
        today = datetime.now().date().isoformat()

        self.state.last_date = today
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
