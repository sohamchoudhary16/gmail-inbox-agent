"""
Phase 3 Tests: Complete End-to-End Workflow
Tests the full pipeline: fetch → classify → reply → persist
All tests use mocks (no real Gmail/Anthropic calls)
"""

import pytest
from test_fixtures import (
    MockGmailService,
    MockClassifier,
    get_sample_email,
    get_all_sample_emails,
)
from auto_reply import AutoReplyGenerator


class TestAutoReplyGeneration:
    """Test auto-reply generation for each category."""

    def test_rfq_reply_generated(self):
        """Generate auto-reply for RFQ."""
        gen = AutoReplyGenerator()
        should_reply, reply = gen.generate_reply(
            "rfq",
            "Quote request for Shanghai to LA"
        )

        assert should_reply is True
        assert "quote request" in reply.lower()
        assert "Freight Forwarding" in reply

    def test_booking_reply_generated(self):
        """Generate auto-reply for booking request."""
        gen = AutoReplyGenerator()
        should_reply, reply = gen.generate_reply(
            "booking_request",
            "Booking request - Quote #12345"
        )

        assert should_reply is True
        assert "booking" in reply.lower()
        assert "confirmation" in reply.lower()

    def test_tracking_reply_generated(self):
        """Generate auto-reply for tracking inquiry."""
        gen = AutoReplyGenerator()
        should_reply, reply = gen.generate_reply(
            "tracking_inquiry",
            "Where is container ABC123?"
        )

        assert should_reply is True
        assert "tracking" in reply.lower()
        assert "status" in reply.lower()

    def test_documentation_reply_generated(self):
        """Generate auto-reply for documentation."""
        gen = AutoReplyGenerator()
        should_reply, reply = gen.generate_reply(
            "documentation",
            "Submitting documents"
        )

        assert should_reply is True
        assert "documents" in reply.lower()
        assert "received" in reply.lower()

    def test_general_reply_generated(self):
        """Generate auto-reply for general inquiry."""
        gen = AutoReplyGenerator()
        should_reply, reply = gen.generate_reply(
            "general_inquiry",
            "Do you offer consolidation?"
        )

        assert should_reply is True
        assert "received" in reply.lower()
        assert "response" in reply.lower()

    def test_complaint_no_reply(self):
        """No auto-reply for complaints."""
        gen = AutoReplyGenerator()
        should_reply, reply = gen.generate_reply(
            "complaint",
            "Service complaint"
        )

        assert should_reply is False
        assert reply == ""

    def test_not_relevant_no_reply(self):
        """No auto-reply for spam."""
        gen = AutoReplyGenerator()
        should_reply, reply = gen.generate_reply(
            "not_relevant",
            "FREE SHIPPING OFFER"
        )

        assert should_reply is False
        assert reply == ""


class TestCompleteWorkflow:
    """Test the complete workflow: fetch → classify → reply → persist."""

    def test_workflow_with_auto_replies(self):
        """Complete workflow with auto-reply generation."""
        # Setup
        gmail = MockGmailService(dry_run=True)
        classifier = MockClassifier()
        reply_gen = AutoReplyGenerator()

        # Simulate workflow for each email type
        emails = get_all_sample_emails()
        results = []

        for email in emails:
            # Step 1: Get email
            assert email["id"] is not None

            # Step 2: Classify
            category, classification = classifier.classify_email(
                subject=email["subject"],
                body=email["body"],
                from_email=email["from"]
            )

            # Step 3: Get label
            label = classifier.get_label_for_category(category)

            # Step 4: Apply label
            gmail.add_label(email["id"], label)

            # Step 5: Generate reply if needed
            should_reply, reply_body = reply_gen.generate_reply(
                category,
                email["subject"]
            )

            # Step 6: Mark as read
            gmail.mark_as_read(email["id"])

            # Record result
            results.append({
                "email_id": email["id"],
                "category": category,
                "label": label,
                "reply_sent": should_reply,
                "reply_length": len(reply_body) if should_reply else 0
            })

        # Verify workflow completed for all emails
        assert len(results) == 7
        assert len(gmail.labeled_emails) == 7
        assert len(gmail.marked_as_read) == 7

        # Verify replies were generated for appropriate categories
        reply_categories = {"rfq", "booking_request", "tracking_inquiry", "documentation", "general_inquiry"}
        for result in results:
            if result["category"] in reply_categories:
                assert result["reply_sent"] is True
                assert result["reply_length"] > 0
            else:
                assert result["reply_sent"] is False

    def test_workflow_idempotency_with_replies(self):
        """Workflow is idempotent even with replies."""
        gmail = MockGmailService(dry_run=True)
        classifier = MockClassifier()
        reply_gen = AutoReplyGenerator()

        email = get_sample_email("rfq")

        # Process email twice
        for iteration in range(2):
            category, _ = classifier.classify_email(
                subject=email["subject"],
                body=email["body"],
                from_email=email["from"]
            )
            label = classifier.get_label_for_category(category)
            gmail.add_label(email["id"], label)
            should_reply, reply = reply_gen.generate_reply(category, email["subject"])
            gmail.mark_as_read(email["id"])

        # Verify idempotency
        assert email["id"] in gmail.labeled_emails
        assert email["id"] in gmail.marked_as_read
        assert len(gmail.labeled_emails) == 1  # Not duplicated


class TestDryRunMode:
    """Test that dry-run mode prevents actual API calls."""

    def test_dry_run_records_without_calling(self):
        """Dry-run records actions without making API calls."""
        gmail_dry = MockGmailService(dry_run=True)

        # Simulate actions
        gmail_dry.add_label("MSG_001", "5u/rfq")
        gmail_dry.mark_as_read("MSG_001")

        # Verify recorded (not actually called)
        assert "MSG_001" in gmail_dry.labeled_emails
        assert "MSG_001" in gmail_dry.marked_as_read

        # In dry-run, these are just logged
        assert len(gmail_dry.call_log) > 0


class TestErrorHandlingPhase3:
    """Test error handling in complete workflow."""

    def test_workflow_with_missing_email(self):
        """Workflow handles missing email gracefully."""
        gmail = MockGmailService(dry_run=True)

        # Try to get non-existent email
        email = gmail.get_message("NONEXISTENT_ID")

        # Should return None, not crash
        assert email is None

    def test_workflow_with_empty_subject(self):
        """Workflow handles email with empty subject."""
        classifier = MockClassifier()
        reply_gen = AutoReplyGenerator()

        # Classify with empty subject
        category, _ = classifier.classify_email(
            subject="",
            body="Some content",
            from_email="test@example.com"
        )

        # Should still classify
        assert category in {"rfq", "booking_request", "tracking_inquiry", "documentation", "complaint", "general_inquiry", "not_relevant"}

        # Should still generate reply if appropriate
        should_reply, reply = reply_gen.generate_reply(category, "")
        if should_reply:
            assert len(reply) > 0


class TestWorkflowIntegration:
    """Integration tests for complete workflow."""

    def test_end_to_end_workflow_all_categories(self):
        """Test complete workflow for all 7 categories."""
        gmail = MockGmailService(dry_run=True)
        classifier = MockClassifier()
        reply_gen = AutoReplyGenerator()

        emails = get_all_sample_emails()
        processed = []

        for email in emails:
            # Complete workflow
            category, _ = classifier.classify_email(
                subject=email["subject"],
                body=email["body"],
                from_email=email["from"]
            )
            label = classifier.get_label_for_category(category)
            gmail.add_label(email["id"], label)
            should_reply, reply_body = reply_gen.generate_reply(category, email["subject"])
            gmail.mark_as_read(email["id"])

            processed.append({
                "id": email["id"],
                "category": category,
                "label": label,
                "reply_sent": should_reply,
                "reply_body": reply_body if should_reply else None
            })

        # Verify all processed
        assert len(processed) == 7

        # Verify correct replies sent
        rfq_reply = next((p for p in processed if p["category"] == "rfq"), None)
        assert rfq_reply is not None
        assert rfq_reply["reply_sent"] is True

        complaint_reply = next((p for p in processed if p["category"] == "complaint"), None)
        assert complaint_reply is not None
        assert complaint_reply["reply_sent"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
