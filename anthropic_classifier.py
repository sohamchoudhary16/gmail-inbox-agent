"""
Real Anthropic API integration for email classification.
Uses Claude to classify emails into 7 categories.
"""

import json
import logging
from typing import Tuple, Dict, Optional
import anthropic
from config import get_settings

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {
    "rfq",
    "booking_request",
    "tracking_inquiry",
    "documentation",
    "complaint",
    "general_inquiry",
    "not_relevant"
}

CATEGORY_LABELS = {
    "rfq": "5u/rfq",
    "booking_request": "5u/booking-request",
    "tracking_inquiry": "5u/tracking-inquiry",
    "documentation": "5u/documentation",
    "complaint": "5u/complaint",
    "general_inquiry": "5u/general-inquiry",
    "not_relevant": "5u/not-relevant"
}

CLASSIFICATION_PROMPT = """You are an email classification system for a freight forwarding company.
Classify the following email into ONE of these 7 categories:

1. "rfq" - Quote/pricing requests for shipping services
2. "booking_request" - Requests to book/reserve shipment space
3. "tracking_inquiry" - Questions about shipment status or location
4. "documentation" - Submission or request for shipping documents
5. "complaint" - Complaints about service, delays, or issues
6. "general_inquiry" - General questions about services or company
7. "not_relevant" - Spam, unrelated content, or irrelevant emails

Email Subject: {subject}
Email Body: {body}

Respond in JSON format:
{{
    "category": "<ONE category from list above>",
    "confidence": 0.0-1.0,
    "reasoning": "<brief explanation>"
}}

Only respond with valid JSON. Category must be one of the 7 listed above."""


class AnthropicClassifier:
    """Classify emails using Claude API."""

    def __init__(self):
        """Initialize Anthropic classifier."""
        self.settings = get_settings()

        if not self.settings.anthropic_api_key:
            logger.warning("ANTHROPIC_API_KEY not set - classifier will fail")
            self.client = None
        else:
            self.client = anthropic.Anthropic(
                api_key=self.settings.anthropic_api_key
            )

        self.model = "claude-3-5-sonnet-20241022"

    def classify_email(
        self,
        subject: str,
        body: str,
        from_email: str = ""
    ) -> Tuple[str, Dict]:
        """
        Classify email using Claude API.

        Args:
            subject: Email subject
            body: Email body
            from_email: Sender email (for context)

        Returns:
            Tuple of (category, result_dict)
        """
        if not self.client:
            logger.error("Anthropic client not initialized")
            return "general_inquiry", {
                "category": "general_inquiry",
                "confidence": 0.0,
                "error": "Anthropic API not configured"
            }

        try:
            # Prepare prompt
            prompt = CLASSIFICATION_PROMPT.format(
                subject=subject,
                body=body[:2000]  # Limit body to 2000 chars
            )

            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=256,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Parse response
            response_text = message.content[0].text
            result = json.loads(response_text)

            # Validate category
            category = result.get("category", "general_inquiry").lower()
            if category not in VALID_CATEGORIES:
                logger.warning(f"Invalid category from API: {category}")
                category = "general_inquiry"

            logger.info(
                f"Classified email from {from_email}: {category} "
                f"(confidence: {result.get('confidence', 0)})"
            )

            return category, result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse API response: {e}")
            return "general_inquiry", {
                "category": "general_inquiry",
                "confidence": 0.0,
                "error": "Failed to parse classification"
            }
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            return "general_inquiry", {
                "category": "general_inquiry",
                "confidence": 0.0,
                "error": f"API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error classifying email: {e}")
            return "general_inquiry", {
                "category": "general_inquiry",
                "confidence": 0.0,
                "error": str(e)
            }

    def get_label_for_category(self, category: str) -> str:
        """Get Gmail label for email category."""
        return CATEGORY_LABELS.get(category, "5u/general-inquiry")


def get_anthropic_classifier() -> AnthropicClassifier:
    """Get classifier instance."""
    return AnthropicClassifier()
