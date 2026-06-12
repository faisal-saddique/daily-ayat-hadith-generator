"""
TTS comparison test: ElevenLabs vs Gemini
Content from:
  - ayat_Aal-i-Imraan_135.png
  - hadith_mishkaat_4737.png

Run: uv run python test_tts_comparison.py
Output: test_tts_output/
"""

import io
import os
import sys
import time
import wave
import logging
from pathlib import Path

# Load .env
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Content from the two images ──────────────────────────────────────────────

AYAT_ARABIC = (
    "وَالَّذِينَ إِذَا فَعَلُوا فَاحِشَةً أَوْ ظَلَمُوا أَنفُسَهُمْ ذَكَرُوا اللَّهَ "
    "فَاسْتَغْفَرُوا لِذُنُوبِهِمْ وَمَن يَغْفِرُ الذُّنُوبَ إِلَّا اللَّهُ وَلَمْ يُصِرُّوا "
    "عَلَى مَا فَعَلُوا وَهُمْ يَعْلَمُونَ"
)
AYAT_URDU = (
    "اور جن کا حال یہ ہے کہ اگر کبھی کوئی فحش کام ان سے سرزد ہو جاتا ہے "
    "یا کسی گناہ کا ارتکاب کر کے وہ اپنے اوپر ظلم کر بیٹھتے ہیں تو معاً اللہ انہیں یاد "
    "آجاتا ہے اور اس سے اپنے قصوروں کی معافی مانگتے ہیں، کیونکہ اللہ کے سوا اور کون ہے "
    "جو گناہ معاف کر سکتا ہو؟ اور وہ دیدہ و دانستہ اپنے کیے پر اصرار نہیں کرتے۔"
)
AYAT_ENGLISH = (
    "These are the ones who, when they commit any indecency and wrong against themselves, "
    "instantly remember Allah and implore forgiveness for their sins - "
    "for who will forgive sins save Allah? - "
    "and who do not wilfully persist in the wrong they did. (Aal-i-Imraan 135)"
)

HADITH_ARABIC = (
    "وَعَنْ أَبِي سَعِيدٍ الْخُدْرِيِّ أَنَّ رَسُولَ اللَّهِ صَلَّى اللَّهُ عَلَيْهِ وَسَلَّمَ قَالَ: "
    "إِذَا تَثَاءَبَ أَحَدُكُمْ فَلْيُمْسِكْ بِيَدِهِ عَلَى فَمِهِ فَإِنَّ الشَّيْطَانَ يَدْخُلُ. "
    "رَوَاهُ مُسْلِمٌ"
)
HADITH_URDU = (
    "ابوسعید خدری سے روایت ہے کہ رسول اللہ صلی اللہ علیہ وسلم نے فرمایا: "
    "جب تم میں سے کسی کو جمائی آئے تو وہ اپنا ہاتھ اپنے منہ پر رکھے "
    "کیونکہ شیطان (منہ میں) داخل ہو جاتا ہے۔ رواہ مسلم۔"
)
HADITH_ENGLISH = (
    "Abu Sa'id al-Khudri reported that Allah's Messenger (peace be upon him) said: "
    "\"When one of you yawns, he should place his hand over his mouth, "
    "for indeed Shaytan enters.\" Narrated by Muslim. (Mishkaat 4737)"
)

# ── Test cases ────────────────────────────────────────────────────────────────

TESTS = [
    ("ayat_english",  AYAT_ENGLISH,   "english"),
    ("ayat_arabic",   AYAT_ARABIC,    "arabic"),
    ("ayat_urdu",     AYAT_URDU,      "urdu"),
    ("hadith_english", HADITH_ENGLISH, "english"),
    ("hadith_arabic",  HADITH_ARABIC,  "arabic"),
    ("hadith_urdu",    HADITH_URDU,    "urdu"),
]

OUT_DIR = Path("test_tts_output")


def pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000) -> bytes:
    """Wrap raw PCM bytes in a proper WAV container (mono, 16-bit)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def run_gemini(tests):
    """Run all tests with Gemini TTS."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.error("google-genai not installed")
        return

    raw_key = os.environ.get("GEMINI_API_KEY", "")
    # Support comma-separated key rotation — use first key
    api_keys = [k.strip() for k in raw_key.split(",") if k.strip()]
    if not api_keys:
        logger.error("GEMINI_API_KEY not set — skipping Gemini tests")
        return

    model = "gemini-2.5-flash-preview-tts"
    # Use Puck for English, Charon for Arabic (deeper tone), Aoede for Urdu
    voice_map = {"english": "Puck", "arabic": "Charon", "urdu": "Aoede"}

    logger.info("\n=== Gemini TTS ===")
    key_idx = 0
    for i, (name, text, lang) in enumerate(tests):
        voice = voice_map[lang]
        out_path = OUT_DIR / "gemini" / f"{name}_{voice}.wav"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Rotate keys on rate limit; also space requests slightly
        if i > 0:
            time.sleep(1)

        for attempt in range(len(api_keys)):
            client = genai.Client(api_key=api_keys[key_idx % len(api_keys)])
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=text,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice
                                )
                            )
                        ),
                    ),
                )
                inline = response.candidates[0].content.parts[0].inline_data
                audio_bytes: bytes = inline.data  # SDK returns bytes directly
                mime_type: str = inline.mime_type or ""

                # Gemini outputs raw PCM — wrap in proper WAV headers
                if "pcm" in mime_type or "L16" in mime_type:
                    rate = 24000
                    if "rate=" in mime_type:
                        try:
                            rate = int(mime_type.split("rate=")[1].split(";")[0])
                        except (ValueError, IndexError):
                            pass
                    audio_bytes = pcm_to_wav(audio_bytes, sample_rate=rate)
                elif "mp3" in mime_type or "mpeg" in mime_type:
                    out_path = out_path.with_suffix(".mp3")

                out_path.write_bytes(audio_bytes)
                logger.info(f"  ✓ {out_path}  ({len(audio_bytes):,} bytes)  [{mime_type}]")
                break  # success
            except Exception as e:
                err = str(e)
                if "429" in err or "RESOURCE_EXHAUSTED" in err:
                    key_idx += 1
                    if attempt + 1 < len(api_keys):
                        logger.warning(f"  Rate limit on key {key_idx}, rotating...")
                        time.sleep(2)
                        continue
                logger.error(f"  ✗ {name}: {e}")
                break


def run_elevenlabs(tests):
    """Run English tests with ElevenLabs TTS (multilingual model)."""
    try:
        from elevenlabs.client import ElevenLabs
        from elevenlabs import VoiceSettings
    except ImportError:
        logger.error("elevenlabs not installed")
        return

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        logger.error("ELEVENLABS_API_KEY not set — skipping ElevenLabs tests")
        return

    client = ElevenLabs(api_key=api_key)
    # George voice — calm narrator
    voice_id = "JBFqnCBsd6RMkjVDRZzb"
    settings = VoiceSettings(stability=0.85, similarity_boost=0.75, style=0.0,
                              use_speaker_boost=True, speed=0.85)

    logger.info("\n=== ElevenLabs TTS ===")
    for name, text, lang in tests:
        out_path = OUT_DIR / "elevenlabs" / f"{name}.mp3"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            audio = client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
                voice_settings=settings,
            )
            with open(out_path, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            size = out_path.stat().st_size
            logger.info(f"  ✓ {out_path}  ({size:,} bytes)")
        except Exception as e:
            logger.error(f"  ✗ {name}: {e}")


if __name__ == "__main__":
    OUT_DIR.mkdir(exist_ok=True)

    provider = sys.argv[1] if len(sys.argv) > 1 else "both"

    if provider in ("gemini", "both"):
        run_gemini(TESTS)

    if provider in ("elevenlabs", "both"):
        run_elevenlabs(TESTS)

    print(f"\nOutput saved to: {OUT_DIR.resolve()}/")
    print("  gemini/      — WAV files")
    print("  elevenlabs/  — MP3 files")
