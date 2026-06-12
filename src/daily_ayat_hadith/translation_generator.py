"""AI-powered translation generator for hadith using Pydantic AI."""

import logging
import os
from typing import Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.builtin_tools import WebSearchTool
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
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


class FixedTexts(BaseModel):
    """Structured output for batched punctuation correction across all translations."""
    ayah_urdu: str = Field(
        description="Fixed Urdu translation of the Quran verse with proper Urdu punctuation marks"
    )
    ayah_english: str = Field(
        description="Fixed English translation of the Quran verse with proper punctuation and Arabic diacritics"
    )
    hadith_urdu: str = Field(
        description="Fixed Urdu translation of the Hadith with proper Urdu punctuation marks"
    )
    hadith_english: Optional[str] = Field(
        default=None,
        description="Fixed English translation of the Hadith, or null if not provided"
    )


class WhatsAppCaptions(BaseModel):
    """WhatsApp-formatted captions for ayah and hadith posts."""
    ayah_caption: str = Field(
        description=(
            "Engaging WhatsApp caption for the Quran verse post. "
            "Urdu section first, then a visual divider, then English. "
            "Uses WhatsApp markdown: *bold*, _italic_, > quotes, - bullets."
        )
    )
    hadith_caption: str = Field(
        description=(
            "Engaging WhatsApp caption for the Hadith post. "
            "Urdu section first, then a visual divider, then English. "
            "Uses WhatsApp markdown: *bold*, _italic_, > quotes, - bullets."
        )
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

        # OpenRouter as final fallback (when all primary keys are exhausted)
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.openrouter_models = ["anthropic/claude-sonnet-4-5"]
        if self.openrouter_api_key:
            logger.info(f"OpenRouter fallback available ({', '.join(self.openrouter_models)})")

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
        """Check if the error is retryable (rate limit 429 or service unavailable 503)."""
        error_str = str(error).lower()
        return (
            "429" in error_str or
            "rate limit" in error_str or
            "quota exceeded" in error_str or
            "503" in str(error) or
            "unavailable" in error_str
        )

    def _create_openrouter_agent(self, output_type, model_name: str) -> Agent:
        """Create an agent using OpenRouter as fallback provider."""
        model = OpenRouterModel(
            model_name,
            provider=OpenRouterProvider(api_key=self.openrouter_api_key)
        )
        return Agent(model, output_type=output_type, instructions=self.instructions,
                     model_settings={"max_tokens": 2000})

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
        for _ in range(len(self.api_keys)):
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
                        logger.warning(f"All {len(self.api_keys)} Gemini keys exhausted, trying OpenRouter fallback")
                        break
                else:
                    # Not a rate limit error, don't retry
                    logger.warning(f"Non-retryable error for {log_context}, trying OpenRouter fallback: {e}")
                    break

        # All primary keys failed — try OpenRouter models in sequence as final fallback
        if self.openrouter_api_key:
            for or_model in self.openrouter_models:
                try:
                    logger.info(f"Attempting OpenRouter fallback ({or_model}) for {log_context}")
                    agent = self._create_openrouter_agent(HadithTranslation, or_model)
                    result = agent.run_sync(prompt)
                    translation = result.output
                    logger.info(f"OpenRouter fallback succeeded ({or_model}) for {log_context} (confidence: {translation.confidence})")
                    return translation
                except Exception as e:
                    last_error = e
                    logger.warning(f"OpenRouter fallback failed ({or_model}) for {log_context}: {e}")

        raise Exception(f"AI translation failed (all providers exhausted): {str(last_error)}")

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

    def fix_all_punctuation(
        self,
        ayah_urdu: str,
        ayah_english: str,
        hadith_urdu: str,
        hadith_english: Optional[str] = None
    ) -> FixedTexts:
        """
        Fix punctuation and diacritics for all translations in a single API call.

        Urdu texts: Replaces Latin punctuation with proper Urdu marks (۔ ، ؟).
        English texts: Fixes punctuation and adds Arabic transliteration diacritics (macrons).

        Args:
            ayah_urdu: Urdu translation of the Quran verse
            ayah_english: English translation of the Quran verse
            hadith_urdu: Urdu translation of the Hadith
            hadith_english: English translation of the Hadith, or None to skip

        Returns:
            FixedTexts with corrected translations. On failure, returns originals unchanged.
        """
        instructions = """You are an expert Islamic scholar and editor fluent in both Urdu and English.
Fix punctuation and diacritics in the provided Islamic translations.

CRITICAL: You MUST return the COMPLETE text for each field. Do NOT truncate, summarize, or shorten any text. Every word of the input must appear in the output.

FOR URDU TEXTS:
1. Use proper Urdu/Arabic punctuation marks only:
   - ۔ for full stop (never Latin .)
   - ، for comma (never Latin ,)
   - ؟ for question mark (never Latin ?)
2. Fix spacing around punctuation marks
3. Do NOT change any wording or meaning
4. Return the FULL text - do not cut it short even if it seems long

FOR ENGLISH TEXTS:
1. Fix broken words caused by line-break artifacts:
   - Join words split by a hyphen (e.g., "Resur-rection" → "Resurrection", "nig-gardly" → "niggardly")
   - Join words split by an errant space mid-word (e.g., "niggardli ness" → "niggardliness")
2. Fix any punctuation mistakes (missing commas, periods, misplaced punctuation, etc.)
3. Add proper Arabic transliteration diacritics where Arabic names/terms appear:
   - Long vowels: ā (alif), ī (ya), ū (waw)
   - Examples: Abū, Muḥammad, Ḥadīth, Salāh, Zakāh, Ṣaḥābah, ʿĀʾishah, Dāwūd
   - Use ʿ for ʿayn (ع) and ʾ for hamzah (ء) where appropriate
3. Do NOT change any wording or meaning
4. Return the FULL text - do not cut it short even if it seems long

Return each corrected text in its corresponding output field. The output length should be similar to the input length."""

        prompt_parts = [
            "Fix the punctuation and diacritics in these Islamic translations:\n",
            f"--- AYAH (Quran verse) - Urdu ---\n{ayah_urdu}\n",
            f"--- AYAH (Quran verse) - English ---\n{ayah_english}\n",
            f"--- HADITH - Urdu ---\n{hadith_urdu}\n",
        ]
        if hadith_english:
            prompt_parts.append(f"--- HADITH - English ---\n{hadith_english}\n")
        else:
            prompt_parts.append("No Hadith English translation provided — set hadith_english to null.")

        prompt = "\n".join(prompt_parts)

        logger.info("Fixing punctuation for all translations in a single call")

        env_var = "GEMINI_API_KEY" if self.model.startswith("gemini") else "OPENAI_API_KEY"

        def _guard(original: str, fixed: str, field: str) -> str:
            """Return fixed text only if it's not significantly shorter than original."""
            if not original:
                return fixed or original
            ratio = len(fixed) / len(original) if fixed else 0
            if ratio < 0.85:
                logger.warning(
                    f"Punctuation fixer truncated {field} "
                    f"({len(original)} -> {len(fixed)} chars, {ratio:.0%}). Using original."
                )
                return original
            return fixed

        # Try all API keys in sequence (same rotation logic as generate_translation)
        saved_index = self.current_key_index
        self.current_key_index = 0
        last_error = None

        for _ in range(len(self.api_keys)):
            api_key = self._get_current_api_key()
            old_key = os.environ.get(env_var)
            os.environ[env_var] = api_key
            try:
                agent = Agent(self.model, output_type=FixedTexts, instructions=instructions)
                result = agent.run_sync(prompt)
                fixed = result.output
                logger.info("Punctuation fixed for all translations")
                return FixedTexts(
                    ayah_urdu=_guard(ayah_urdu, fixed.ayah_urdu, "ayah_urdu"),
                    ayah_english=_guard(ayah_english, fixed.ayah_english, "ayah_english"),
                    hadith_urdu=_guard(hadith_urdu, fixed.hadith_urdu, "hadith_urdu"),
                    hadith_english=_guard(hadith_english or "", fixed.hadith_english or "", "hadith_english") or None,
                )
            except Exception as e:
                last_error = e
                if self._is_rate_limit_error(e):
                    logger.warning(f"Punctuation fix: retryable error on key {self.current_key_index + 1}: {e}")
                    if not self._rotate_api_key():
                        break
                else:
                    break
            finally:
                if old_key is not None:
                    os.environ[env_var] = old_key
                elif env_var in os.environ:
                    del os.environ[env_var]

        self.current_key_index = saved_index

        # All primary keys failed — try OpenRouter models in sequence as final fallback
        if self.openrouter_api_key:
            for or_model in self.openrouter_models:
                try:
                    logger.info(f"Attempting OpenRouter fallback for punctuation fixing ({or_model})")
                    agent = self._create_openrouter_agent(FixedTexts, or_model)
                    result = agent.run_sync(prompt)
                    fixed = result.output
                    logger.info(f"Punctuation fixed via OpenRouter fallback ({or_model})")
                    return FixedTexts(
                        ayah_urdu=_guard(ayah_urdu, fixed.ayah_urdu, "ayah_urdu"),
                        ayah_english=_guard(ayah_english, fixed.ayah_english, "ayah_english"),
                        hadith_urdu=_guard(hadith_urdu, fixed.hadith_urdu, "hadith_urdu"),
                        hadith_english=_guard(hadith_english or "", fixed.hadith_english or "", "hadith_english") or None,
                    )
                except Exception as e:
                    last_error = e
                    logger.warning(f"OpenRouter fallback failed ({or_model}) for punctuation fixing: {e}")

        logger.warning(f"Punctuation fixing failed on all providers, using originals: {last_error}")
        return FixedTexts(
            ayah_urdu=ayah_urdu,
            ayah_english=ayah_english,
            hadith_urdu=hadith_urdu,
            hadith_english=hadith_english
        )

    def generate_whatsapp_captions(
        self,
        ayah_arabic: str,
        ayah_urdu: str,
        ayah_english: str,
        ayah_reference: str,
        hadith_arabic: str,
        hadith_urdu: str,
        hadith_english: str,
        hadith_reference: str,
        hadith_grade: Optional[str] = None,
    ) -> WhatsAppCaptions:
        """
        Generate engaging WhatsApp captions for the ayah and hadith posts.

        Each caption contains Urdu first, then English, with WhatsApp markdown formatting.
        Includes context, key takeaways, practical action points, and a closing reflection.

        Returns:
            WhatsAppCaptions with ayah_caption and hadith_caption strings.
            On failure, raises an exception.
        """
        instructions = """You are an Islamic scholar and community educator who crafts WhatsApp posts for Muslim communities. You write like a knowledgeable, warm friend — not a formal lecturer.

TASK: Create two WhatsApp captions — one for a Quran verse post and one for a Hadith post.

Each caption has TWO PARTS: Urdu first, then English, separated by this exact divider:

─────────────────────────

WHATSAPP FORMATTING RULES (these are literal characters that render in WhatsApp):
- *text* → bold (use for headings, key terms, the opening hook)
- _text_ → italic (use for duas, Arabic terms, and the closing inspirational line)
- > text → quote block (use for the central message or a key phrase)
- - item → bullet point (use for action items)
- Use line breaks generously — short paragraphs read better on mobile

CAPTION STRUCTURE (apply identically for both the Urdu and English sections):

1. *Opening hook* — One punchy line that makes someone STOP scrolling. Frame it as a question, a bold statement, or a relatable observation. Do NOT start with "Today's verse/hadith is..."

2. Brief context (1-3 sentences max) — only if genuinely needed to understand the content. Skip if the meaning is self-evident.

3. > The core message — quote the most powerful phrase or the key lesson directly from the content.

4. Reflection (2-4 sentences) — connect this ancient wisdom to real, everyday modern life. Be specific. Give an example of how this applies to someone's day.

5. *آج کا عمل:* / *Today's Action:*
   - 1 to 2 specific, immediately doable actions. Concrete, not vague. ("Read this dua before sleeping" not "reflect on this verse".)

6. _Closing line_ — a short, warm dua or motivation. End on something that lingers.

TONE RULES:
- Warm, direct, relatable — not preachy
- If the content is a warning, frame it with compassion, not fear
- Connect to everyday scenarios: workplace, family, social media, daily routines
- Avoid academic vocabulary; aim for a Year 10 reading level
- Use occasional transliterated Arabic terms (_iman_, _tawbah_, _sabr_) where they add depth

LANGUAGE RULES:
- Urdu: Natural, conversational Urdu. Proper Urdu punctuation (۔ ، ؟). Not overly formal.
- English: Modern, accessible. Occasional transliterated Arabic with _italics_.
- Do NOT retranslate the ayah or hadith — use the provided translations only to understand the meaning.
- Do NOT include the full Arabic text in the caption.

OUTPUT: Return exactly two fields — ayah_caption and hadith_caption. Each field contains both the Urdu and English sections separated by the divider shown above.

WEB SEARCH: You have access to a web search tool. Use it only when you genuinely need a fact you are uncertain about — for example, the background of a narrator, the historical context of an event, the meaning of a specific Arabic term, or scholarly commentary on this particular verse or hadith. Do not search for things you already know confidently. When you do search, prefer established Islamic scholarship sites (sunnah.com, islamqa.info, seekersguidance.org, islamweb.net)."""

        grade_note = f"\nHadith Grade: {hadith_grade}" if hadith_grade else ""

        prompt = f"""Generate WhatsApp captions for today's Islamic content.

--- AYAH ---
Reference: {ayah_reference}
Arabic: {ayah_arabic}
Urdu: {ayah_urdu}
English: {ayah_english}

--- HADITH ---
Reference: {hadith_reference}{grade_note}
Arabic: {hadith_arabic}
Urdu: {hadith_urdu}
English: {hadith_english}"""

        logger.info("Generating WhatsApp captions for ayah and hadith")

        env_var = "GEMINI_API_KEY" if self.model.startswith("gemini") else "OPENAI_API_KEY"

        saved_index = self.current_key_index
        self.current_key_index = 0
        last_error = None

        for _ in range(len(self.api_keys)):
            api_key = self._get_current_api_key()
            old_key = os.environ.get(env_var)
            os.environ[env_var] = api_key
            try:
                agent = Agent(self.model, output_type=WhatsAppCaptions, instructions=instructions, builtin_tools=[WebSearchTool()])
                result = agent.run_sync(prompt)
                logger.info("WhatsApp captions generated successfully")
                return result.output
            except Exception as e:
                last_error = e
                if self._is_rate_limit_error(e):
                    logger.warning(f"Caption gen: rate limit on key {self.current_key_index + 1}: {e}")
                    if not self._rotate_api_key():
                        break
                else:
                    break
            finally:
                if old_key is not None:
                    os.environ[env_var] = old_key
                elif env_var in os.environ:
                    del os.environ[env_var]

        self.current_key_index = saved_index

        # OpenRouter fallback — use local instructions (not self.instructions which is for hadith translation)
        if self.openrouter_api_key:
            for or_model in self.openrouter_models:
                try:
                    logger.info(f"Attempting OpenRouter fallback for captions ({or_model})")
                    model_obj = OpenRouterModel(
                        or_model,
                        provider=OpenRouterProvider(api_key=self.openrouter_api_key)
                    )
                    agent = Agent(model_obj, output_type=WhatsAppCaptions, instructions=instructions, builtin_tools=[WebSearchTool()])
                    result = agent.run_sync(prompt)
                    logger.info(f"WhatsApp captions generated via OpenRouter ({or_model})")
                    return result.output
                except Exception as e:
                    last_error = e
                    logger.warning(f"OpenRouter caption fallback failed ({or_model}): {e}")

        raise Exception(f"WhatsApp caption generation failed (all providers exhausted): {str(last_error)}")
