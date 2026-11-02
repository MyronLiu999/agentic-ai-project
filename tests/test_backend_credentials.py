"""Reject malformed credentials before sending them or exposing them in errors."""

import os
import unittest
from dataclasses import replace
from unittest.mock import patch

from harness.backends import OpenAICompatibleBackend
from harness.settings import load_settings


class CredentialTest(unittest.TestCase):
    def test_malformed_keys_never_reach_sdk_and_are_not_logged(self):
        settings = replace(load_settings(), api_key_env="TEST_MODEL_KEY")
        for value in ("sk-test\x16secret", " sk-test", "sk-test\n", "sk-test\x7f", "sk-tést"):
            with self.subTest(value=repr(value)), patch.dict(os.environ, TEST_MODEL_KEY=value):
                with patch("openai.OpenAI") as client:
                    with self.assertRaisesRegex(RuntimeError, "Invalid TEST_MODEL_KEY") as caught:
                        OpenAICompatibleBackend(settings)
                    client.assert_not_called()
                    self.assertNotIn(value, str(caught.exception))

    def test_valid_custom_key_reaches_sdk_unchanged(self):
        settings = replace(load_settings(), api_key_env="TEST_MODEL_KEY")
        with patch.dict(os.environ, TEST_MODEL_KEY="test-only-key"), patch("openai.OpenAI") as client:
            OpenAICompatibleBackend(settings)
            client.assert_called_once_with(api_key="test-only-key", base_url=settings.base_url or None)
