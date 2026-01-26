"""AI-powered translation generator for hadith using Pydantic AI."""

import logging
import os
from typing import Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class HadithTranslation(BaseModel):
    """Structured output for hadith translation."""
    english_translation: str = Field(
        description="Accurate English translation of the Arabic hadith text"
    )
    confidence: str = Field(
        description="Confidence level: high, medium, or low",
        pattern="^(high|medium|low)$"
    )


class TranslationGenerator:
    """AI-powered translation generator using Pydantic AI."""

    def __init__(self, model: str = "gemini-1.5-flash", api_key: Optional[str] = None):
        """
        Initialize translation generator.

        Args:
            model: Model to use (gemini-1.5-flash, gemini-1.5-pro, openai:gpt-4, etc.)
            api_key: API key for the model (defaults to GEMINI_API_KEY or OPENAI_API_KEY from env)
        """
        self.model = model

        # Get API key from parameter or environment
        if api_key is None:
            if model.startswith("gemini"):
                api_key = os.getenv("GEMINI_API_KEY")
            elif model.startswith("openai"):
                api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError(
                f"API key required for model '{model}'. "
                "Set GEMINI_API_KEY or OPENAI_API_KEY in .env file"
            )

        # Create Pydantic AI agent with structured output
        self.agent = Agent(
            model,
            output_type=HadithTranslation,
            instructions="""You are an expert Islamic scholar and translator specializing in hadith translation.
Your task is to provide ACCURATE and AUTHENTIC English translations of Arabic hadith texts.

CRITICAL REQUIREMENTS:
1. This is a SACRED religious text - accuracy is paramount
2. PRIORITY: When Urdu translation is provided, use it as your PRIMARY GUIDE for understanding the meaning, context, and tone
   - The Urdu translation captures contextual meaning, intent, and Islamic nuances
   - Follow the Urdu interpretation closely - it's been prepared by Islamic scholars
   - The Arabic is the source text, but the Urdu shows how scholars interpret its meaning
3. Capture the INTENT and MEANING, not just literal word-for-word translation
   - If the Urdu shows prescriptive/instructive tone (should, must), reflect that in English
   - If the Urdu conveys ethical guidance or etiquette, maintain that tone
   - Preserve the prophetic wisdom and practical application shown in Urdu
4. Use formal, respectful language appropriate for prophetic traditions
5. When the Prophet Muhammad ﷺ is mentioned, use "Allah's Messenger" or "the Messenger of Allah"
6. Preserve Islamic terminology (use transliterations where appropriate)
7. ALWAYS use proper transliteration with MACRONS for Arabic names and terms:
   - Use macrons (ā, ī, ū) to indicate long vowels in Arabic transliterations
   - Examples: Abū (أبو), Salām (سلام), Dāwūd (داود), ʿĀʾishah (عائشة), Ḥadīth (حديث)
   - Common terms: Salāh (صلاة), Zakāh (زكاة), Ṣaḥābah (صحابة), Sunnah (سنة)
   - Narrator names: Abū Hurayrah, Ibn ʿUmar, ʿAbdullāh, Muḥammad
   - Use ʿ (ʿayn) and ʾ (hamzah) for proper transliteration when appropriate
   - This ensures proper pronunciation and scholarly accuracy
8. Translate the COMPLETE text provided, including:
   - The prophetic statement or narration
   - Narrator attributions (رواه، أخرجه، etc.)
   - Chain of transmission references
   - Any contextual notes that are part of the original text
9. Do NOT translate modern scholarly grading/authentication unless it's part of the original Arabic

TRANSLATION APPROACH:
1. Read the Arabic text carefully
2. Study the Urdu translation to understand the meaning, tone, and context
3. Translate to English following the Urdu interpretation
4. Ensure your English conveys the same meaning and tone as the Urdu

If you're uncertain about any part of the translation, indicate "medium" or "low" confidence.
Only mark as "high" confidence if you're completely certain of the accuracy.

This translation will be shared publicly, so it MUST be accurate and authentic."""
        )

    def generate_translation(
        self,
        arabic_text: str,
        urdu_translation: Optional[str] = None,
        hadith_number: Optional[int] = None
    ) -> HadithTranslation:
        """
        Generate English translation for Arabic hadith text.

        Args:
            arabic_text: Arabic text of the hadith
            urdu_translation: Optional Urdu translation for reference
            hadith_number: Optional hadith number for logging

        Returns:
            HadithTranslation object with translation and confidence level

        Raises:
            Exception: If translation generation fails
        """
        prompt_parts = [
            "Translate the following Arabic hadith text to English:\n",
            f"Arabic: {arabic_text}"
        ]

        if urdu_translation:
            prompt_parts.append(
                f"\nUrdu translation (for reference): {urdu_translation}"
            )

        prompt = "\n".join(prompt_parts)

        log_context = f"hadith {hadith_number}" if hadith_number else "hadith"
        logger.info(f"Generating AI translation for {log_context} using {self.model}")

        try:
            result = self.agent.run_sync(prompt)
            translation = result.output

            logger.info(
                f"AI translation generated for {log_context} "
                f"(confidence: {translation.confidence})"
            )

            if translation.confidence != "high":
                logger.warning(
                    f"AI translation has {translation.confidence} confidence for {log_context}. "
                    "Manual review recommended."
                )

            return translation

        except Exception as e:
            logger.error(f"Failed to generate AI translation for {log_context}: {e}")
            raise Exception(f"AI translation failed: {str(e)}")

    def get_english_translation(
        self,
        arabic_text: str,
        urdu_translation: Optional[str] = None,
        hadith_number: Optional[int] = None
    ) -> str:
        """
        Convenience method to get just the English translation string.

        Args:
            arabic_text: Arabic text of the hadith
            urdu_translation: Optional Urdu translation for reference
            hadith_number: Optional hadith number for logging

        Returns:
            English translation string
        """
        result = self.generate_translation(arabic_text, urdu_translation, hadith_number)
        return result.english_translation
