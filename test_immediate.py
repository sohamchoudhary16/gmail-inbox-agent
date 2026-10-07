"""
IMMEDIATE TESTS - Run RIGHT NOW without any external services.
Tests the full workflow: Gmail → Classify → Label → Store

Run with: pytest test_immediate.py -v
"""

import pytest
import json
from test_fixtures import (
    MockGmailService,
    MockClassifier,
    SAMPLE_EMAILS,
    get_sample_email,
    get_all_sample_emails,
    get_mock_gmail_service,
    get_mock_classifier
)


class TestMockGmailService:
    """Test the mock Gmail service."""

    def test_get_unread_emails(self):
        """Mock Gmail returns sample emails."""
        gmail = MockGmailService()
        emails = gmail.get_unread_emails(max_results=10)

        assert len(emails) == 7  # 7 sample categories
        assert all('id' in e for e in emails)
        assert all('threadId' in e for e in emails)

    def test_get_specific_email(self):
        """Mock Gmail can fetch specific email."""
        gmail = MockGmailService()
        email = gmail.get_message("MSG_RFQ_001")

        assert email is not None
        assert email["id"] == "MSG_RFQ_001"
        assert email["subject"] == "Quote request - Shanghai to Los Angeles"

    def test_add_label_records_action(self):
        """Mock Gmail records labels added."""
        gmail = MockGmailService(dry_run=True)
        result = gmail.add_label("MSG_RFQ_001", "5u/rfq")

        assert result is True
        assert "MSG_RFQ_001" in gmail.labeled_emails
        assert gmail.labeled_emails["MSG_RFQ_001"] == "5u/rfq"

    def test_mark_as_read_records_action(self):
        """Mock Gmail records messages marked as read."""
        gmail = MockGmailService(dry_run=True)
        result = gmail.mark_as_read("MSG_RFQ_001")

        assert result is True
        assert "MSG_RFQ_001" in gmail.marked_as_read

    def test_call_log_tracks_all_operations(self):
        """Mock Gmail logs all operations."""
        gmail = MockGmailService(dry_run=True)

        gmail.get_unread_emails(max_results=5)
        gmail.get_message("MSG_RFQ_001")
        gmail.add_label("MSG_RFQ_001", "5u/rfq")
        gmail.mark_as_read("MSG_RFQ_001")

        assert len(gmail.call_log) == 4
        assert gmail.call_log[0][0] == "get_unread_emails"
        assert gmail.call_log[1][0] == "get_message"
        assert gmail.call_log[2][0] == "add_label"
        assert gmail.call_log[3][0] == "mark_as_read"


class TestMockClassifier:
    """Test the mock classifier."""

    def test_classify_rfq(self):
        """Classify quote request correctly."""
        classifier = MockClassifier()
        category, result = classifier.classify_email(
            subject="Quote request",
            body="Need pricing for Shanghai to LA",
            from_email="buyer@example.com"
        )

        assert category == "rfq"
        assert result["category"] == "rfq"

    def test_classify_booking(self):
        """Classify booking request correctly."""
        classifier = MockClassifier()
        category, result = classifier.classify_email(
            subject="Booking request",
            body="Please book the following shipment",
            from_email="booking@example.com"
        )

        assert category == "booking_request"

    def test_classify_tracking(self):
        """Classify tracking inquiry correctly."""
        classifier = MockClassifier()
        category, result = classifier.classify_email(
            subject="Where is my shipment?",
            body="Can you provide status and tracking",
            from_email="ops@example.com"
        )

        assert category == "tracking_inquiry"

    def test_get_label_for_category(self):
        """Get correct label for category."""
        classifier = MockClassifier()

        assert classifier.get_label_for_category("rfq") == "5u/rfq"
        assert classifier.get_label_for_category("booking_request") == "5u/booking-request"
        assert classifier.get_label_for_category("tracking_inquiry") == "5u/tracking"
        assert classifier.get_label_for_category("documentation") == "5u/documentation"
        assert classifier.get_label_for_category("complaint") == "5u/complaint"
        assert classifier.get_label_for_category("general_inquiry") == "5u/general"
        assert classifier.get_label_for_category("not_relevant") == "5u/not-relevant"


class TestSampleEmails:
    """Test sample email data."""

    def test_all_categories_have_samples(self):
        """All 7 categories have sample emails."""
        categories = {
            "rfq",
            "booking_request",
            "tracking_inquiry",
            "documentation",
            "complaint",
            "general_inquiry",
            "not_relevant"
        }

        for category in categories:
            assert category in SAMPLE_EMAILS
            email = SAMPLE_EMAILS[category]
            assert email["expected_category"] == category

    def test_sample_email_has_required_fields(self):
        """Sample emails have all required fields."""
        required_fields = ["id", "threadId", "subject", "from", "body", "timestamp"]

        for email in SAMPLE_EMAILS.values():
            for field in required_fields:
                assert field in email

    def test_get_sample_email(self):
        """Can retrieve sample email by category."""
        email = get_sample_email("rfq")

        assert email["expected_category"] == "rfq"
        assert "Quote" in email["subject"] or "quote" in email["body"]


class TestFullWorkflow:
    """Test complete workflow: fetch → classify → label."""

    def test_workflow_rfq(self):
        """Complete workflow for RFQ email."""
        # Setup
        gmail = MockGmailService(dry_run=True)
        classifier = MockClassifier()

        # Step 1: Fetch unread emails
        emails = gmail.get_unread_emails(max_results=1)
        assert len(emails) > 0
        email = emails[0]

        # Step 2: Classify
        category, result = classifier.classify_email(
            subject=email["subject"],
            body=email["body"],
            from_email=email["from"]
        )
        assert category in {
            "rfq", "booking_request", "tracking_inquiry",
            "documentation", "complaint", "general_inquiry", "not_relevant"
        }

        # Step 3: Get label
        label = classifier.get_label_for_category(category)
        assert label.startswith("5u/")

        # Step 4: Apply label
        result = gmail.add_label(email["id"], label)
        assert result is True

        # Step 5: Mark as read
        result = gmail.mark_as_read(email["id"])
        assert result is True

        # Verify
        assert email["id"] in gmail.labeled_emails
        assert email["id"] in gmail.marked_as_read

    def test_workflow_all_categories(self):
        """Workflow works for all 7 categories."""
        gmail = MockGmailService(dry_run=True)
        classifier = MockClassifier()

        all_emails = get_all_sample_emails()

        for email in all_emails:
            # Classify
            category, _ = classifier.classify_email(
                subject=email["subject"],
                body=email["body"],
                from_email=email["from"]
            )

            # Get label
            label = classifier.get_label_for_category(category)

            # Apply label
            gmail.add_label(email["id"], label)
            gmail.mark_as_read(email["id"])

        # Verify all were processed
        assert len(gmail.labeled_emails) == 7
        assert len(gmail.marked_as_read) == 7

    def test_idempotency_check(self):
        """Idempotency: can check if email already processed."""
        processed_ids = set()

        gmail = MockGmailService(dry_run=True)
        emails = gmail.get_unread_emails(max_results=10)

        for email in emails:
            email_id = email["id"]

            # First pass: process
            if email_id not in processed_ids:
                gmail.add_label(email_id, "5u/rfq")
                processed_ids.add(email_id)

            # Second pass: skip (already processed)
            if email_id in processed_ids:
                continue

        # Verify: all processed
        assert len(processed_ids) == len(emails)
        assert len(gmail.labeled_emails) == len(emails)


class TestDryRunMode:
    """Test dry-run mode prevents external calls."""

    def test_dry_run_records_but_doesnt_call(self):
        """Dry-run records actions without making API calls."""
        gmail_dry = MockGmailService(dry_run=True)

        # Add label (in dry-run, should just record)
        gmail_dry.add_label("MSG_001", "5u/rfq")

        # Verify recorded
        assert "MSG_001" in gmail_dry.labeled_emails

        # Verify no actual API call would be made
        # (In dry-run=True, we just log the action)
        assert len(gmail_dry.call_log) > 0


class TestErrorHandling:
    """Test error handling."""

    def test_missing_email_returns_none(self):
        """Request for non-existent email returns None."""
        gmail = MockGmailService()
        email = gmail.get_message("NONEXISTENT_ID")

        assert email is None

    def test_classifier_handles_empty_body(self):
        """Classifier handles emails with empty body."""
        classifier = MockClassifier()
        category, result = classifier.classify_email(
            subject="Subject only",
            body="",
            from_email="test@example.com"
        )

        # Should still classify into some category
        assert category in {
            "rfq", "booking_request", "tracking_inquiry",
            "documentation", "complaint", "general_inquiry", "not_relevant"
        }


class TestIntegration:
    """Integration tests combining mocks."""

    def test_end_to_end_workflow(self):
        """Full end-to-end workflow test."""
        # Setup mocks
        gmail = get_mock_gmail_service(dry_run=True)
        classifier = get_mock_classifier()

        # Simulate polling and processing
        unread = gmail.get_unread_emails(max_results=10)

        results = {
            "processed": 0,
            "errors": 0,
            "labels_applied": 0
        }

        for email in unread:
            try:
                # Classify
                category, _ = classifier.classify_email(
                    subject=email["subject"],
                    body=email["body"],
                    from_email=email["from"]
                )

                # Get label
                label = classifier.get_label_for_category(category)

                # Apply label (in dry-run, just records)
                if gmail.add_label(email["id"], label):
                    results["labels_applied"] += 1

                # Mark as read (in dry-run, just records)
                gmail.mark_as_read(email["id"])

                results["processed"] += 1
            except Exception as e:
                results["errors"] += 1

        # Verify results
        assert results["processed"] > 0
        assert results["errors"] == 0
        assert results["labels_applied"] == results["processed"]
        assert len(gmail.labeled_emails) == results["processed"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
