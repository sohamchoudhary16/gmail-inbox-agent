"""
Auto-reply generation for each email category.
Professional, freight-appropriate responses.
"""

from typing import Dict, Tuple


class AutoReplyGenerator:
    """Generate professional auto-replies based on email category."""

    def __init__(self):
        """Initialize reply generator."""
        self.templates = {
            "rfq": self._generate_rfq_reply,
            "booking_request": self._generate_booking_reply,
            "tracking_inquiry": self._generate_tracking_reply,
            "documentation": self._generate_documentation_reply,
            "complaint": None,  # No auto-reply for complaints
            "general_inquiry": self._generate_general_reply,
            "not_relevant": None,  # No auto-reply for spam
        }

    def should_reply(self, category: str) -> bool:
        """Check if category gets auto-reply."""
        return self.templates.get(category) is not None

    def generate_reply(self, category: str, original_subject: str, **kwargs) -> Tuple[bool, str]:
        """
        Generate auto-reply for email category.

        Args:
            category: Email category
            original_subject: Original email subject
            **kwargs: Additional context (RFQ details, tracking info, etc.)

        Returns:
            Tuple of (should_send, reply_body)
        """
        generator = self.templates.get(category)

        if generator is None:
            return False, ""

        reply = generator(original_subject, **kwargs)
        return True, reply

    def _generate_rfq_reply(self, original_subject: str, **kwargs) -> str:
        """Generate RFQ acknowledgment reply."""
        return f"""Hello,

Thank you for your quote request regarding "{original_subject}".

We have received your inquiry and our quotations team is reviewing the details:
- Origin and destination
- Weight and volume
- Service requirements

We will process your request and send you a detailed quote as soon as possible.
If we need any additional information, we will reach out to you.

Best regards,
Freight Forwarding Automation System"""

    def _generate_booking_reply(self, original_subject: str, **kwargs) -> str:
        """Generate booking acknowledgment reply."""
        return f"""Hello,

Thank you for your booking request regarding "{original_subject}".

We have received your booking details and our operations team is now processing your request.
We will confirm the booking details and provide you with:
- Booking reference number
- Pickup/collection details
- Estimated transit time
- Documentation requirements

You will receive a confirmation email shortly.

Best regards,
Freight Forwarding Automation System"""

    def _generate_tracking_reply(self, original_subject: str, **kwargs) -> str:
        """Generate tracking inquiry reply."""
        return f"""Hello,

Thank you for your tracking inquiry regarding "{original_subject}".

We are currently retrieving the latest status and location information for your shipment.
We will send you a detailed update with:
- Current status
- Current location
- Estimated time of arrival
- Recent shipping events

Please expect a tracking update shortly.

Best regards,
Freight Forwarding Automation System"""

    def _generate_documentation_reply(self, original_subject: str, **kwargs) -> str:
        """Generate documentation receipt reply."""
        return f"""Hello,

Thank you for submitting your documents regarding "{original_subject}".

We have received your documentation submission and will process it as part of your shipment.
Our team will review the documents for:
- Completeness
- Accuracy
- Customs compliance

If any corrections or additional documents are needed, we will contact you immediately.

Best regards,
Freight Forwarding Automation System"""

    def _generate_general_reply(self, original_subject: str, **kwargs) -> str:
        """Generate general inquiry acknowledgment reply."""
        return f"""Hello,

Thank you for your inquiry regarding "{original_subject}".

We have received your message and a member of our team will review your request.
We will provide you with a detailed response as soon as possible.

If your inquiry is urgent, please feel free to contact us directly.

Best regards,
Freight Forwarding Automation System"""


def get_reply_generator() -> AutoReplyGenerator:
    """Get auto-reply generator instance."""
    return AutoReplyGenerator()
