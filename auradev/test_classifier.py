"""
Unit tests for the Claude classifier module.

Covers:
- Valid API response parsing
- Malformed JSON handling
- Invalid state rejection
- Missing field fallback
- API error fallback
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import classifier as classifier_module
import config as config_module
from config import STATES


class DummyContent:
    def __init__(self, text):
        self.text = text


class DummyMessage:
    def __init__(self, text):
        self.content = [DummyContent(text)]


class TestCognitiveClassifier(unittest.TestCase):

    # ------------------------------------------------------------------
    # 1. Valid response
    # ------------------------------------------------------------------
    def test_valid_response(self):
        """Classifier returns the exact state / confidence / reason Claude provides."""
        valid_response = {
            "state": "flow",
            "confidence": 0.91,
            "reason": "Steady typing with minimal interruptions."
        }
        mock_client = MagicMock()
        mock_client.messages.create.return_value = DummyMessage(json.dumps(valid_response))

        with patch.object(classifier_module, "ANTHROPIC_API_KEY", "test-key"):
            with patch.object(classifier_module, "Anthropic") as mock_anthropic:
                mock_anthropic.return_value = mock_client
                clf = classifier_module.CognitiveClassifier()

        metrics = {
            "wpm": 55.0,
            "backspace_ratio": 0.10,
            "active_window": "VS Code",
            "window_switches": 0,
            "mouse_distance": 150.0,
            "cpu_percent": 25.0,
            "idle_seconds": 2.0,
        }
        result = clf.classify_state(metrics)

        self.assertEqual(result["state"], "flow")
        self.assertEqual(result["confidence"], 0.91)
        self.assertEqual(result["reason"], "Steady typing with minimal interruptions.")
        self.assertEqual(clf.last_state, "flow")

    # ------------------------------------------------------------------
    # 2. Malformed JSON
    # ------------------------------------------------------------------
    def test_malformed_json(self):
        """Classifier falls back when Claude returns unparseable JSON."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = DummyMessage("not-json-at-all")

        with patch.object(classifier_module, "ANTHROPIC_API_KEY", "test-key"):
            with patch.object(classifier_module, "Anthropic") as mock_anthropic:
                mock_anthropic.return_value = mock_client
                clf = classifier_module.CognitiveClassifier()
                clf.last_state = "debugging"  # simulate previous state

        metrics = {"wpm": 10.0, "backspace_ratio": 0.4}
        result = clf.classify_state(metrics)

        self.assertEqual(result["state"], "debugging")  # keeps previous
        self.assertEqual(result["confidence"], 0.5)
        self.assertIn("Fallback", result["reason"])

    # ------------------------------------------------------------------
    # 3. Invalid state
    # ------------------------------------------------------------------
    def test_invalid_state(self):
        """Classifier rejects a state not in the supported STATES list."""
        invalid_response = {
            "state": "daydreaming",
            "confidence": 0.8,
            "reason": "Mind wandered off."
        }
        mock_client = MagicMock()
        mock_client.messages.create.return_value = DummyMessage(json.dumps(invalid_response))

        with patch.object(classifier_module, "ANTHROPIC_API_KEY", "test-key"):
            with patch.object(classifier_module, "Anthropic") as mock_anthropic:
                mock_anthropic.return_value = mock_client
                clf = classifier_module.CognitiveClassifier()

        metrics = {"wpm": 5.0, "backspace_ratio": 0.5}
        result = clf.classify_state(metrics)

        self.assertEqual(result["state"], "reviewing")  # no previous state → reviewing
        self.assertEqual(result["confidence"], 0.5)
        self.assertIn("Fallback", result["reason"])

    # ------------------------------------------------------------------
    # 4. Missing fields
    # ------------------------------------------------------------------
    def test_missing_fields(self):
        """Classifier falls back when required keys are absent."""
        incomplete_response = {"state": "flow", "confidence": 0.9}  # missing 'reason'
        mock_client = MagicMock()
        mock_client.messages.create.return_value = DummyMessage(json.dumps(incomplete_response))

        with patch.object(classifier_module, "ANTHROPIC_API_KEY", "test-key"):
            with patch.object(classifier_module, "Anthropic") as mock_anthropic:
                mock_anthropic.return_value = mock_client
                clf = classifier_module.CognitiveClassifier()
                clf.last_state = "stuck"

        metrics = {"wpm": 0.0, "backspace_ratio": 0.0}
        result = clf.classify_state(metrics)

        self.assertEqual(result["state"], "stuck")  # previous state preserved
        self.assertEqual(result["confidence"], 0.5)
        self.assertIn("Fallback", result["reason"])

    # ------------------------------------------------------------------
    # 5. API error
    # ------------------------------------------------------------------
    def test_api_error(self):
        """Classifier falls back when the API raises an exception."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Connection timeout")

        with patch.object(classifier_module, "ANTHROPIC_API_KEY", "test-key"):
            with patch.object(classifier_module, "Anthropic") as mock_anthropic:
                mock_anthropic.return_value = mock_client
                clf = classifier_module.CognitiveClassifier()

        metrics = {"wpm": 30.0, "backspace_ratio": 0.2}
        result = clf.classify_state(metrics)

        self.assertEqual(result["state"], "reviewing")  # no previous state
        self.assertEqual(result["confidence"], 0.5)
        self.assertIn("Fallback", result["reason"])

    # ------------------------------------------------------------------
    # 6. Confidence validation edge-cases
    # ------------------------------------------------------------------
    def test_confidence_out_of_range_high(self):
        """Confidence > 1.0 triggers fallback."""
        bad_conf = {"state": "flow", "confidence": 1.5, "reason": "Too confident."}
        mock_client = MagicMock()
        mock_client.messages.create.return_value = DummyMessage(json.dumps(bad_conf))

        with patch.object(classifier_module, "ANTHROPIC_API_KEY", "test-key"):
            with patch.object(classifier_module, "Anthropic") as mock_anthropic:
                mock_anthropic.return_value = mock_client
                clf = classifier_module.CognitiveClassifier()
                clf.last_state = "flow"

        result = clf.classify_state({"wpm": 60.0})
        self.assertEqual(result["state"], "flow")  # fallback keeps last_state
        self.assertEqual(result["confidence"], 0.5)

    def test_confidence_out_of_range_low(self):
        """Confidence < 0.0 triggers fallback."""
        bad_conf = {"state": "debugging", "confidence": -0.2, "reason": "Negative."}
        mock_client = MagicMock()
        mock_client.messages.create.return_value = DummyMessage(json.dumps(bad_conf))

        with patch.object(classifier_module, "ANTHROPIC_API_KEY", "test-key"):
            with patch.object(classifier_module, "Anthropic") as mock_anthropic:
                mock_anthropic.return_value = mock_client
                clf = classifier_module.CognitiveClassifier()
                clf.last_state = "debugging"

        result = clf.classify_state({"wpm": 20.0})
        self.assertEqual(result["state"], "debugging")
        self.assertEqual(result["confidence"], 0.5)

    # ------------------------------------------------------------------
    # 7. Init without API key
    # ------------------------------------------------------------------
    def test_init_missing_api_key(self):
        """Constructor raises ValueError when ANTHROPIC_API_KEY is missing."""
        with patch.object(classifier_module, "ANTHROPIC_API_KEY", None):
            with self.assertRaises(ValueError) as ctx:
                classifier_module.CognitiveClassifier()
            self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))

    # ------------------------------------------------------------------
    # 8. Real API call (skipped if no real key present)
    # ------------------------------------------------------------------
    def test_real_api_call(self):
        """
        Sends metrics to the *real* Claude API.
        Skipped unless ANTHROPIC_API_KEY is present in the environment.
        """
        real_key = os.environ.get("ANTHROPIC_API_KEY")
        if not real_key or real_key == "test-key":
            self.skipTest("No real ANTHROPIC_API_KEY in environment")

        clf = classifier_module.CognitiveClassifier()
        metrics = {
            "wpm": 45.0,
            "backspace_ratio": 0.12,
            "active_window": "VS Code",
            "window_switches": 1,
            "mouse_distance": 200.0,
            "cpu_percent": 30.0,
            "idle_seconds": 3.0,
        }
        result = clf.classify_state(metrics)

        self.assertIn(result["state"], STATES)
        self.assertIsInstance(result["confidence"], float)
        self.assertTrue(0.0 <= result["confidence"] <= 1.0)
        self.assertIsInstance(result["reason"], str)
        self.assertTrue(len(result["reason"]) > 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
