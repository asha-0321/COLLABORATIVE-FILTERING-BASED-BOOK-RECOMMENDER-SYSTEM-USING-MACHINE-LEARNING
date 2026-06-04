from transformers import pipeline
from googletrans import Translator

translator = Translator()

summarizer = pipeline(
    "summarization",
    model="facebook/bart-large-cnn",
    framework="pt"
)

def multilingual_summary(text, language):

    if not text:
        return "Summary not available."

    try:
        # 🔥 Map dataset language → code
        lang_map = {
            "English": "en",
            "Telugu": "te",
            "Hindi": "hi",
            "Tamil": "ta",
            "Kannada": "kn",
            "Malayalam": "ml"
        }

        target_lang = lang_map.get(language, "en")

        # ✅ If English → direct summary
        if target_lang == "en":
            result = summarizer(
                text,
                max_length=300,
                min_length=150,
                do_sample=False
            )
            return result[0]["summary_text"]

        # 🔁 Step 1: Translate to English (safe even if already English)
        translated = translator.translate(text, dest='en').text

        # 🧠 Step 2: Summarize
        result = summarizer(
            translated,
            max_length=300,
            min_length=150,
            do_sample=False
        )

        summary_en = result[0]["summary_text"]

        # 🔁 Step 3: Translate to TARGET language
        final_summary = translator.translate(summary_en, dest=target_lang).text

        return final_summary

    except Exception as e:
        print("Summary Error:", e)
        return "Could not generate summary."