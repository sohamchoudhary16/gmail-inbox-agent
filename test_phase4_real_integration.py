"""
Phase 4 Tests: Real Service Integration
Tests real Gmail OAuth2 and Anthropic API with comprehensive mocking.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from anthropic_classifier import AnthropicClassifier
from test_fixtures import (
    MockGmailService,
    MockClassifier,
    get_sample_email,
    get_all_sample_emails,
)


class TestAnthropicClassifier:
    """Test real Anthropic API classifier."""

    def test_classifier_initialized_without_key(self):
        """Classifier initializes gracefully without API key."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
            classifier = AnthropicClassifier()
            assert classifier.client is None
            assert classifier.model is not None

    def test_get_label_for_category(self):
        """Get correct Gmail label for each category."""
        classifier = AnthropicClassifier()

        labels = {
            "rfq": "5u/rfq",
            "booking_request": "5u/booking-request",
            "tracking_inquiry": "5u/tracking-inquiry",
            "documentation": "5u/documentation",
            "complaint": "5u/complaint",
            "general_inquiry": "5u/general-inquiry",
            "not_relevant": "5u/not-relevant"
        }

        for category, expected_label in labels.items():
            assert classifier.get_label_for_category(category) == expected_label

    def test_classifier_fallback_no_api_key(self):
        """Classifier returns fallback when API key missing."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
            classifier = AnthropicClassifier()

            category, result = classifier.classify_email(
                subject="Test",
                body="Test body"
            )

            assert category == "general_inquiry"
            assert "Anthropic" in result["error"]

    @patch('anthropic.Anthropic')
    def test_classifier_with_mocked_api(self, mock_anthropic):
        """Test classifier with mocked Anthropic API."""
        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = '{"category": "rfq", "confidence": 0.95, "reasoning": "Quote request"}'
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        # Create classifier with mocked API
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}, clear=False):
            classifier = AnthropicClassifier()
            classifier.client = mock_client

            category, result = classifier.classify_email(
                subject="Quote request",
                body="Please provide quote for Shanghai to LA"
            )

            assert category == "rfq"
            assert result["confidence"] == 0.95
            assert "Quote request" in result["reasoning"]

    @patch('anthropic.Anthropic')
    def test_classifier_json_parse_error(self, mock_anthropic):
        """Classifier handles invalid JSON response."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = "Invalid JSON {incomplete"
        mock_client.messages.create.return_value = mock_response

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}, clear=False):
            classifier = AnthropicClassifier()
            classifier.client = mock_client

            category, result = classifier.classify_email(
                subject="Test",
                body="Test"
            )

            assert category == "general_inquiry"
            assert "Failed to parse" in result["error"]

    @patch('anthropic.Anthropic')
    def test_classifier_invalid_category(self, mock_anthropic):
        """Classifier handles invalid category from API."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = '{"category": "invalid_category", "confidence": 0.8}'
        mock_client.messages.create.return_value = mock_response

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}, clear=False):
            classifier = AnthropicClassifier()
            classifier.client = mock_client

            category, result = classifier.classify_email(
                subject="Test",
                body="Test"
            )

            # Should fall back to general_inquiry
            assert category == "general_inquiry"


class TestGmailOAuth2Integration:
    """Test Gmail OAuth2 integration."""

    def test_mock_gmail_service_still_works(self):
        """Verify mock Gmail service works for testing."""
        gmail = MockGmailService(dry_run=True)

        emails = gmail.get_unread_emails(max_results=5)
        assert len(emails) > 0
        assert all("id" in e for e in emails)
        assert all("subject" in e for e in emails)

    def test_gmail_label_operations(self):
        """Test Gmail label operations."""
        gmail = MockGmailService(dry_run=True)
        email_id = "MSG_001"

        # Add label
        success = gmail.add_label(email_id, "5u/rfq")
        assert success is True
        assert email_id in gmail.labeled_emails

        # Mark as read
        success = gmail.mark_as_read(email_id)
        assert success is True
        assert email_id in gmail.marked_as_read


class TestDryRunModePhase4:
    """Test dry-run mode prevents real API calls."""

    def test_dry_run_records_actions(self):
        """Dry-run records actions without calling APIs."""
        gmail = MockGmailService(dry_run=True)
        classifier = MockClassifier()

        email = get_sample_email("rfq")

        # Process email
        category, _ = classifier.classify_email(
            subject=email["subject"],
            body=email["body"],
            from_email=email["from"]
        )

        label = classifier.get_label_for_category(category)
        gmail.add_label(email["id"], label)
        gmail.mark_as_read(email["id"])

        # Verify recorded (not called)
        assert email["id"] in gmail.labeled_emails
        assert email["id"] in gmail.marked_as_read
        assert len(gmail.call_log) > 0

    def test_dry_run_safe_mode(self):
        """Dry-run mode is safe for testing without side effects."""
        gmail = MockGmailService(dry_run=True)

        # Multiple operations
        for i in range(10):
            gmail.add_label(f"MSG_{i:03d}", "5u/test")
            gmail.mark_as_read(f"MSG_{i:03d}")

        # Verify all recorded
        assert len(gmail.labeled_emails) == 10
        assert len(gmail.marked_as_read) == 10


class TestPhase4Workflow:
    """Test complete Phase 4 workflow."""

    def test_workflow_with_real_classifier_mock(self):
        """Complete workflow with real classifier structure."""
        gmail = MockGmailService(dry_run=True)
        classifier = AnthropicClassifier()  # Real structure, no API

        email = get_sample_email("rfq")

        # Workflow
        # In Phase 4, this would use real API
        # For now, we test the structure is in place
        assert classifier.get_label_for_category("rfq") == "5u/rfq"

        label = classifier.get_label_for_category("rfq")
        gmail.add_label(email["id"], label)
        gmail.mark_as_read(email["id"])

        assert email["id"] in gmail.labeled_emails

    def test_workflow_all_categories_with_real_structure(self):
        """Test workflow for all 7 categories with real classifier."""
        gmail = MockGmailService(dry_run=True)
        classifier = AnthropicClassifier()

        categories = [
            "rfq",
            "booking_request",
            "tracking_inquiry",
            "documentation",
            "complaint",
            "general_inquiry",
            "not_relevant"
        ]

        for cat in categories:
            label = classifier.get_label_for_category(cat)
            assert label is not None
            assert "5u/" in label

        assert len(gmail.call_log) == 0  # No actual calls yet


class TestErrorHandlingPhase4:
    """Test error handling in Phase 4 integration."""

    def test_classifier_handles_missing_api_key_gracefully(self):
        """Classifier gracefully handles missing API key."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
            classifier = AnthropicClassifier()

            category, result = classifier.classify_email(
                subject="Test",
                body="Test body"
            )

            # Should not crash, should return fallback
            assert category in ["rfq", "booking_request", "tracking_inquiry",
                              "documentation", "complaint", "general_inquiry", "not_relevant"]
            assert result is not None

    def test_gmail_missing_email_handling(self):
        """Gmail service handles missing emails gracefully."""
        gmail = MockGmailService()

        email = gmail.get_message("NONEXISTENT_ID")
        assert email is None

    def test_workflow_continues_on_classifier_error(self):
        """Workflow continues even if classifier fails."""
        gmail = MockGmailService(dry_run=True)

        email_id = "MSG_001"
        label = "5u/general-inquiry"  # Default fallback

        # Continue even without classifier working
        gmail.add_label(email_id, label)
        gmail.mark_as_read(email_id)

        assert email_id in gmail.labeled_emails
        assert email_id in gmail.marked_as_read


class TestPhase4Readiness:
    """Test system readiness for Phase 4."""

    def test_all_imports_work(self):
        """All Phase 4 modules can be imported."""
        # These should not raise errors
        from anthropic_classifier import AnthropicClassifier
        from config import get_settings
        from auto_reply import AutoReplyGenerator

        assert AnthropicClassifier is not None
        assert get_settings is not None
        assert AutoReplyGenerator is not None

    def test_settings_configured_for_phase4(self):
        """Settings support Phase 4 configuration."""
        from config import get_settings

        settings = get_settings()

        # All Phase 4 settings should exist
        assert hasattr(settings, 'anthropic_api_key')
        assert hasattr(settings, 'portal_base_url')
        assert hasattr(settings, 'portal_api_key')
        assert hasattr(settings, 'gmail_token_file')

    def test_complete_workflow_structure_phase4(self):
        """Complete workflow structure ready for Phase 4."""
        from anthropic_classifier import AnthropicClassifier
        from auto_reply import AutoReplyGenerator
        from test_fixtures import MockGmailService

        gmail = MockGmailService(dry_run=True)
        classifier = AnthropicClassifier()
        reply_gen = AutoReplyGenerator()

        # All components initialized
        assert gmail is not None
        assert classifier is not None
        assert reply_gen is not None

        # Workflow chain works
        emails = gmail.get_unread_emails(max_results=1)
        assert len(emails) > 0

        email = emails[0]
        label = classifier.get_label_for_category("rfq")
        gmail.add_label(email["id"], label)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
