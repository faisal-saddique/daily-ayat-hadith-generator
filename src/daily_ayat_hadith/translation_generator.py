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
    """AI-powered translation generator using Pydantic AI with automatic API key rotation."""

    def __init__(self, model: str = "gemini-1.5-flash", api_key: Optional[str] = None):
        """
        Initialize translation generator.

        Args:
            model: Model to use (gemini-1.5-flash, gemini-1.5-pro, openai:gpt-4, etc.)
            api_key: API key for the model (defaults to GEMINI_API_KEY or OPENAI_API_KEY from env)
                    Can be a single key or comma-separated keys for rotation
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

        # Parse multiple API keys (comma-separated)
        self.api_keys = [key.strip() for key in api_key.split(",") if key.strip()]
        self.current_key_index = 0

        if len(self.api_keys) > 1:
            logger.info(f"Loaded {len(self.api_keys)} API keys for rotation")

        # Store instructions for reuse when creating agents
        self.instructions = """You are an expert Islamic scholar and translator specializing in hadith translation.
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

        # Create initial agent with first API key
        self.agent = Agent(
            model,
            output_type=HadithTranslation,
            instructions=self.instructions
        )

    def _get_current_api_key(self) -> str:
        """Get the current API key being used."""
        return self.api_keys[self.current_key_index]

    def _rotate_api_key(self) -> bool:
        """
        Rotate to the next API key.

        Returns:
            True if rotation successful, False if all keys exhausted
        """
        self.current_key_index += 1
        if self.current_key_index >= len(self.api_keys):
            return False  # All keys exhausted

        logger.info(
            f"Rotating to API key {self.current_key_index + 1}/{len(self.api_keys)}"
        )
        return True

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if the error is a rate limit error (429)."""
        error_str = str(error).lower()
        return "429" in error_str or "rate limit" in error_str or "quota exceeded" in error_str

    def _create_agent_with_key(self, api_key: str) -> Agent:
        """Create a new agent instance with the specified API key."""
        # Temporarily set the API key in the environment
        old_key = None
        env_var = "GEMINI_API_KEY" if self.model.startswith("gemini") else "OPENAI_API_KEY"

        if env_var in os.environ:
            old_key = os.environ[env_var]

        os.environ[env_var] = api_key

        try:
            agent = Agent(
                self.model,
                output_type=HadithTranslation,
                instructions=self.instructions
            )
            return agent
        finally:
            # Restore old key if it existed
            if old_key is not None:
                os.environ[env_var] = old_key
            elif env_var in os.environ:
                del os.environ[env_var]

    def generate_translation(
        self,
        arabic_text: str,
        urdu_translation: Optional[str] = None,
        hadith_number: Optional[int] = None
    ) -> HadithTranslation:
        """
        Generate English translation for Arabic hadith text with automatic API key rotation.

        Args:
            arabic_text: Arabic text of the hadith
            urdu_translation: Optional Urdu translation for reference
            hadith_number: Optional hadith number for logging

        Returns:
            HadithTranslation object with translation and confidence level

        Raises:
            Exception: If translation generation fails with all API keys
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

        # Try all API keys in sequence
        last_error = None
        for attempt in range(len(self.api_keys)):
            current_key = self._get_current_api_key()

            try:
                # Create agent with current API key
                agent = self._create_agent_with_key(current_key)
                result = agent.run_sync(prompt)
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
                last_error = e

                # Check if it's a rate limit error
                if self._is_rate_limit_error(e):
                    logger.warning(
                        f"Rate limit hit for API key {self.current_key_index + 1}/{len(self.api_keys)}: {e}"
                    )

                    # Try to rotate to next key
                    if self._rotate_api_key():
                        logger.info(f"Retrying with next API key...")
                        continue
                    else:
                        logger.error(f"All {len(self.api_keys)} API keys exhausted due to rate limits")
                        raise Exception(f"All API keys exhausted: {str(e)}")
                else:
                    # Not a rate limit error, don't retry
                    logger.error(f"Failed to generate AI translation for {log_context}: {e}")
                    raise Exception(f"AI translation failed: {str(e)}")

        # If we get here, all attempts failed
        logger.error(f"Failed to generate AI translation for {log_context} after {len(self.api_keys)} attempts")
        raise Exception(f"AI translation failed: {str(last_error)}")

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
