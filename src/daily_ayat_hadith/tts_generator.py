"""Multi-provider TTS generator (ElevenLabs + Gemini) for ayah and hadith audio output."""

import io
import logging
import os
import wave
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TTSConfig:
    """Configuration for TTS generation."""

    def __init__(self, config: dict):
        tts = config.get("tts", {})
        self.enabled: bool = tts.get("enabled", False)
        self.provider: str = tts.get("provider", "elevenlabs")  # "elevenlabs" | "gemini"

        generate = tts.get("generate", {})
        self.ayah_english: bool = generate.get("ayah_english", True)
        self.ayah_urdu: bool = generate.get("ayah_urdu", False)
        self.hadith_english: bool = generate.get("hadith_english", True)
        self.hadith_urdu: bool = generate.get("hadith_urdu", False)

        # ElevenLabs config (nested under "elevenlabs" key)
        el = tts.get("elevenlabs", {})
        self.el_english_voice_id: str = el.get("english_voice_id", "JBFqnCBsd6RMkjVDRZzb")
        self.el_urdu_voice_id: str = el.get("urdu_voice_id", "JBFqnCBsd6RMkjVDRZzb")
        self.el_model: str = el.get("model", "eleven_multilingual_v2")
        self.el_output_format: str = el.get("output_format", "mp3_44100_128")
        vs = el.get("voice_settings", {})
        self.stability: float = vs.get("stability", 0.85)
        self.similarity_boost: float = vs.get("similarity_boost", 0.75)
        self.style: float = vs.get("style", 0.0)
        self.use_speaker_boost: bool = vs.get("use_speaker_boost", True)
        self.speed: float = vs.get("speed", 0.85)

        # Gemini config (nested under "gemini" key)
        gm = tts.get("gemini", {})
        self.gemini_model: str = gm.get("model", "gemini-2.5-flash-preview-tts")
        self.gemini_english_voice: str = gm.get("english_voice", "Sadaltager")
        self.gemini_urdu_voice: str = gm.get("urdu_voice", "Sadaltager")
        self.gemini_style_instruction: str = gm.get("style_instruction", "")

    @classmethod
    def from_config_file(cls, config_file: Path) -> "TTSConfig":
        import json
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                return cls(json.load(f))
        return cls({})


class _ElevenLabsProvider:
    """ElevenLabs TTS backend."""

    def __init__(self, config: TTSConfig):
        self.config = config
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            from elevenlabs.client import ElevenLabs
            api_key = os.environ.get("ELEVENLABS_API_KEY")
            if not api_key:
                logger.warning("ELEVENLABS_API_KEY not set — ElevenLabs TTS unavailable")
                return
            self._client = ElevenLabs(api_key=api_key)
            logger.info("ElevenLabs TTS client initialized")
        except ImportError:
            logger.warning("elevenlabs package not installed — ElevenLabs TTS unavailable")

    def is_available(self) -> bool:
        return self._client is not None

    def generate(self, text: str, voice_id: str, output_path: Path) -> bool:
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
                model_id=self.config.el_model,
                output_format=self.config.el_output_format,
                voice_settings=settings,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            logger.info(f"ElevenLabs TTS saved: {output_path}")
            return True
        except Exception as e:
            logger.error(f"ElevenLabs TTS failed for {output_path.name}: {e}")
            return False


class _GeminiProvider:
    """Gemini TTS backend with API key rotation (outputs WAV)."""

    def __init__(self, config: TTSConfig):
        self.config = config
        self._api_keys: list[str] = []
        self._key_index: int = 0
        self._genai = None
        self._init_keys()

    def _init_keys(self):
        try:
            from google import genai as _genai
            self._genai = _genai
        except ImportError:
            logger.warning("google-genai package not installed — Gemini TTS unavailable")
            return

        raw = os.environ.get("GEMINI_API_KEY", "")
        self._api_keys = [k.strip() for k in raw.split(",") if k.strip()]
        if not self._api_keys:
            logger.warning("GEMINI_API_KEY not set — Gemini TTS unavailable")
            return
        if len(self._api_keys) > 1:
            logger.info(f"Gemini TTS: {len(self._api_keys)} API keys loaded for rotation")
        else:
            logger.info("Gemini TTS client initialized")

    def is_available(self) -> bool:
        return self._genai is not None and bool(self._api_keys)

    def _client_for(self, index: int):
        return self._genai.Client(api_key=self._api_keys[index])

    @staticmethod
    def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000) -> bytes:
        """Wrap raw PCM bytes in a proper WAV container (mono, 16-bit)."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)
        return buf.getvalue()

    @staticmethod
    def _is_rate_limit(e: Exception) -> bool:
        s = str(e)
        return "429" in s or "RESOURCE_EXHAUSTED" in s or "quota" in s.lower()

    def generate(self, text: str, voice_name: str, output_path: Path) -> bool:
        if not self.is_available() or not text.strip():
            return False

        from google.genai import types

        instruction = self.config.gemini_style_instruction
        prompt = f"{instruction}\n\n{text}" if instruction else text

        for attempt in range(len(self._api_keys)):
            idx = (self._key_index + attempt) % len(self._api_keys)
            client = self._client_for(idx)
            try:
                response = client.models.generate_content(
                    model=self.config.gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice_name
                                )
                            )
                        ),
                    ),
                )
                inline = response.candidates[0].content.parts[0].inline_data
                audio_bytes: bytes = inline.data
                mime_type: str = inline.mime_type or ""

                if "pcm" in mime_type or "L16" in mime_type:
                    rate = 24000
                    if "rate=" in mime_type:
                        try:
                            rate = int(mime_type.split("rate=")[1].split(";")[0])
                        except (ValueError, IndexError):
                            pass
                    audio_bytes = self._pcm_to_wav(audio_bytes, sample_rate=rate)
                    out_path = output_path.with_suffix(".wav")
                elif "mp3" in mime_type or "mpeg" in mime_type:
                    out_path = output_path.with_suffix(".mp3")
                else:
                    out_path = output_path.with_suffix(".wav")

                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(audio_bytes)
                self._key_index = idx  # remember last working key
                logger.info(f"Gemini TTS saved: {out_path}")
                return True

            except Exception as e:
                if self._is_rate_limit(e) and len(self._api_keys) > 1:
                    logger.warning(
                        f"Gemini TTS rate limit on key {idx + 1}/{len(self._api_keys)}, rotating..."
                    )
                    continue
                logger.error(f"Gemini TTS failed for {output_path.name}: {e}")
                return False

        logger.error(f"Gemini TTS: all {len(self._api_keys)} keys exhausted for {output_path.name}")
        return False


class TTSGenerator:
    """Generates audio files from text using the configured TTS provider."""

    def __init__(self, config: TTSConfig):
        self.config = config
        self._provider = None

        if not config.enabled:
            return

        if config.provider == "gemini":
            self._provider = _GeminiProvider(config)
        else:
            self._provider = _ElevenLabsProvider(config)

        if not self._provider.is_available():
            logger.warning(f"TTS provider '{config.provider}' is not available")
            self.config.enabled = False

    def _generate(self, text: str, voice: str, output_path: Path) -> bool:
        if not self._provider:
            return False
        return self._provider.generate(text, voice, output_path)

    def _english_voice(self) -> str:
        if self.config.provider == "gemini":
            return self.config.gemini_english_voice
        return self.config.el_english_voice_id

    def _urdu_voice(self) -> str:
        if self.config.provider == "gemini":
            return self.config.gemini_urdu_voice
        return self.config.el_urdu_voice_id

    def generate_ayah_english(self, text: str, output_path: Path) -> Optional[Path]:
        if not self.config.enabled or not self.config.ayah_english:
            return None
        success = self._generate(text, self._english_voice(), output_path)
        return output_path if success else None

    def generate_ayah_urdu(self, text: str, output_path: Path) -> Optional[Path]:
        if not self.config.enabled or not self.config.ayah_urdu:
            return None
        success = self._generate(text, self._urdu_voice(), output_path)
        return output_path if success else None

    def generate_hadith_english(self, text: str, output_path: Path) -> Optional[Path]:
        if not self.config.enabled or not self.config.hadith_english:
            return None
        success = self._generate(text, self._english_voice(), output_path)
        return output_path if success else None

    def generate_hadith_urdu(self, text: str, output_path: Path) -> Optional[Path]:
        if not self.config.enabled or not self.config.hadith_urdu:
            return None
        success = self._generate(text, self._urdu_voice(), output_path)
        return output_path if success else None
