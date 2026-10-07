"""
Email classification agent using Agno framework and Claude.
Classifies incoming emails into predefined categories.
"""

import logging
from typing import Optional, Tuple
from anthropic import Anthropic

logger = logging.getLogger(__name__)

# Valid classification categories
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
    "tracking_inquiry": "5u/tracking",
    "documentation": "5u/documentation",
    "complaint": "5u/complaint",
    "general_inquiry": "5u/general",
    "not_relevant": "5u/not-relevant"
}

SYSTEM_PROMPT = """You are an email classifier for a freight forwarding company's inbox automation system.

Classify each email into EXACTLY ONE of these categories:

1. **rfq** - Request for quotation/pricing on a shipping lane. Includes origin, destination, weight, volume, or mode.
2. **booking_request** - Request to book a shipment that has already been quoted or is a repeat booking.
3. **tracking_inquiry** - Question about where a shipment currently is, its status, or ETA.
4. **documentation** - Submission of documents (bill of lading, packing list, customs forms, etc.).
5. **complaint** - Complaint about service, delivery, pricing, or quality.
6. **general_inquiry** - General questions not fitting other categories (company info, capabilities, etc.).
7. **not_relevant** - Spam, newsletter, automated notifications, or completely unrelated content.

IMPORTANT RULES:
- Classify into EXACTLY ONE category only
- For RFQ emails: extract key information (origin, destination, weight, volume, mode if mentioned)
- Be conservative: if unclear, prefer general_inquiry over incorrect specific category
- Tracking inquiries usually mention a container number, shipment reference, or "track/where is" language
- Complaints have emotional language, describe problems, or request refunds/compensation

You will respond with ONLY valid JSON in this exact format:
{
  "category": "<one of: rfq, booking_request, tracking_inquiry, documentation, complaint, general_inquiry, not_relevant>",
  "confidence": <0.0-1.0>,
  "reasoning": "<brief explanation of why this category>",
  "rfq_details": {
    "origin": "<port/city or null>",
    "destination": "<port/city or null>",
    "weight": "<weight value or null>",
    "volume": "<volume value or null>",
    "mode": "<sea/air/lcl/fcl or null>"
  }
}
"""


class ClassifierAgent:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-opus-5-5"  # Using latest Claude for accuracy

    def classify_email(
        self,
        subject: str,
        body: str,
        from_email: str
    ) -> Tuple[str, dict]:
        """
        Classify an email and extract relevant information.

        Args:
            subject: Email subject line
            body: Email body text
            from_email: Sender's email address

        Returns:
            Tuple of (category, full_response_dict)
        """
        try:
            email_content = f"""
Subject: {subject}
From: {from_email}
Body:
{body}
"""

            message = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": f"Classify this email:\n\n{email_content}"
                    }
                ]
            )

            response_text = message.content[0].text

            # Parse JSON response
            import json
            result = json.loads(response_text)

            # Validate category
            category = result.get("category", "general_inquiry")
            if category not in VALID_CATEGORIES:
                logger.warning(f"Invalid category returned: {category}, using general_inquiry")
                category = "general_inquiry"

            logger.info(f"Classified email from {from_email}: {category} (confidence: {result.get('confidence', 0)})")

            return category, result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse classification response: {e}")
            return "general_inquiry", {"category": "general_inquiry", "error": "parse_error"}
        except Exception as e:
            logger.error(f"Classification error: {e}")
            return "general_inquiry", {"category": "general_inquiry", "error": str(e)}

    def get_label_for_category(self, category: str) -> str:
        """Get Gmail label name for a category"""
        return CATEGORY_LABELS.get(category, "5u/general")
