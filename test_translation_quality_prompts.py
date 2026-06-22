from __future__ import annotations

import unittest
from unittest.mock import patch

import proofreader
import qa
import translator


def _captured_user_prompt(mocked_call) -> str:
    if "user_prompt" in mocked_call.call_args.kwargs:
        return mocked_call.call_args.kwargs["user_prompt"]
    return mocked_call.call_args.args[1]


class TranslationQualityPromptTests(unittest.TestCase):
    def test_translation_prompt_includes_quality_requirements(self):
        with patch("translator.ask_openai", return_value="Prevod.") as mocked:
            translator.translate_text("Hello world.", "Translate from English to Slovenian.")

        user_prompt = _captured_user_prompt(mocked)
        self.assertIn("Translation quality requirements", user_prompt)
        self.assertIn("silently check for omissions", user_prompt)
        self.assertIn("Source text:\nHello world.", user_prompt)

    def test_proofreading_prompt_includes_quality_requirements(self):
        with patch("proofreader.ask_openai", return_value="Lepo besedilo.") as mocked:
            proofreader.proofread_translation("Lepo besedilo", "Slovenian", "General")

        user_prompt = _captured_user_prompt(mocked)
        self.assertIn("Proofreading quality requirements", user_prompt)
        self.assertIn("no paragraph or segment has been lost", user_prompt)

    def test_qa_prompt_includes_quality_checklist(self):
        with patch("qa.ask_openai", return_value="No issues.") as mocked:
            qa.run_qa_check("Hello.", "Pozdravljeni.", "English", "Slovenian", "General")

        user_prompt = _captured_user_prompt(mocked)
        self.assertIn("Quality checks to perform especially carefully", user_prompt)
        self.assertIn("Omitted or untranslated paragraphs", user_prompt)


if __name__ == "__main__":
    unittest.main()
