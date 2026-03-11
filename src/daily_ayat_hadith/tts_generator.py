"""ElevenLabs TTS generator for ayah and hadith audio output."""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TTSConfig:
    """Configuration for TTS generation."""

    def __init__(self, config: dict):
        tts = config.get("tts", {})
        self.enabled: bool = tts.get("enabled", False)
        self.english_voice_id: str = tts.get("english_voice_id", "JBFqnCBsd6RMkjVDRZzb")
        self.urdu_voice_id: str = tts.get("urdu_voice_id", "JBFqnCBsd6RMkjVDRZzb")
        self.model: str = tts.get("model", "eleven_multilingual_v2")
        self.output_format: str = tts.get("output_format", "mp3_44100_128")
        vs = tts.get("voice_settings", {})
        self.stability: float = vs.get("stability", 0.85)
        self.similarity_boost: float = vs.get("similarity_boost", 0.75)
        self.style: float = vs.get("style", 0.0)
        self.use_speaker_boost: bool = vs.get("use_speaker_boost", True)
        self.speed: float = vs.get("speed", 0.85)
        generate = tts.get("generate", {})
        self.ayah_english: bool = generate.get("ayah_english", True)
        self.ayah_urdu: bool = generate.get("ayah_urdu", False)
        self.hadith_english: bool = generate.get("hadith_english", True)
        self.hadith_urdu: bool = generate.get("hadith_urdu", False)

    @classmethod
    def from_config_file(cls, config_file: Path) -> "TTSConfig":
        import json
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                return cls(json.load(f))
        return cls({})


class TTSGenerator:
    """Generates MP3 audio files from text using ElevenLabs TTS."""

    def __init__(self, config: TTSConfig):
        self.config = config
        self._client = None

        if config.enabled:
            self._init_client()

    def _init_client(self):
        try:
            from elevenlabs.client import ElevenLabs
            api_key = os.environ.get("ELEVENLABS_API_KEY")
            if not api_key:
                logger.warning("ELEVENLABS_API_KEY not set — TTS disabled")
                self.config.enabled = False
                return
            self._client = ElevenLabs(api_key=api_key)
            logger.info("ElevenLabs TTS client initialized")
        except ImportError:
            logger.warning("elevenlabs package not installed — TTS disabled")
            self.config.enabled = False

    def _generate(self, text: str, voice_id: str, output_path: Path) -> bool:
        """Generate audio for text and save to output_path. Returns True on success."""
        if not self._client or not text.strip():
            return False
        try:
            from elevenlabs import VoiceSettings
            settings = VoiceSettings(
                stability=self.config.stability,
                similarity_boost=self.config.similarity_boost,
                style=self.config.style,
                use_speaker_boost=self.config.use_speaker_boost,
                speed=self.config.speed,
            )
            audio = self._client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id=self.config.model,
                output_format=self.config.output_format,
                voice_settings=settings,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            logger.info(f"TTS saved: {output_path}")
            return True
        except Exception as e:
            logger.error(f"TTS generation failed for {output_path.name}: {e}")
            return False

    def generate_ayah_english(self, text: str, output_path: Path) -> Optional[Path]:
        if not self.config.enabled or not self.config.ayah_english:
            return None
        success = self._generate(text, self.config.english_voice_id, output_path)
        return output_path if success else None

    def generate_ayah_urdu(self, text: str, output_path: Path) -> Optional[Path]:
        if not self.config.enabled or not self.config.ayah_urdu:
            return None
        success = self._generate(text, self.config.urdu_voice_id, output_path)
        return output_path if success else None

    def generate_hadith_english(self, text: str, output_path: Path) -> Optional[Path]:
        if not self.config.enabled or not self.config.hadith_english:
            return None
        success = self._generate(text, self.config.english_voice_id, output_path)
        return output_path if success else None

    def generate_hadith_urdu(self, text: str, output_path: Path) -> Optional[Path]:
        if not self.config.enabled or not self.config.hadith_urdu:
            return None
        success = self._generate(text, self.config.urdu_voice_id, output_path)
        return output_path if success else None
