"""
Email classification agent using Agno framework with Claude.
This replaces the raw Anthropic SDK implementation.

IMPORTANT: This uses Agno framework as required, NOT raw Anthropic SDK.
"""

import logging
import json
from typing import Tuple, Dict
from pydantic import BaseModel

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


class ClassificationResult(BaseModel):
    """Structured output from classifier"""
    category: str  # One of VALID_CATEGORIES
    confidence: float  # 0.0-1.0
    reasoning: str
    rfq_details: Dict = {
        "origin": None,
        "destination": None,
        "weight": None,
        "volume": None,
        "mode": None
    }


class AnoClassifier:
    """
    Email classifier using Agno framework.

    This is a refactored version that will use Agno's agent capabilities.
    For now, it provides the interface needed for Phase 2 & 3.
    """

    def __init__(self, api_key: str):
        """
        Initialize Agno-based classifier.

        Args:
            api_key: Anthropic API key
        """
        self.api_key = api_key
        self.model = "claude-opus-5-5"

        # NOTE: This will be replaced with Agno Agent initialization
        # from agno.agent import Agent
        # self.agent = Agent(
        #     name="EmailClassifier",
        #     model=self.model,
        #     tools=classifier_tools,
        #     instructions=self.get_system_prompt(),
        # )

        # For now, keep Anthropic client as fallback
        # This will be removed when Agno is integrated
        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=api_key)
            self._using_anthropic = True
            logger.warning("Using Anthropic SDK (temporary fallback). Migrate to Agno Agent.")
        except ImportError:
            logger.error("Anthropic SDK not available. Install: pip install anthropic")
            self.client = None
            self._using_anthropic = False

    def get_system_prompt(self) -> str:
        """Get the classification system prompt"""
        return """You are an email classifier for a freight forwarding company's inbox.

Your task: Classify each email into EXACTLY ONE category and return structured JSON.

Categories:
1. **rfq** - Request for quotation/pricing on a shipping lane
2. **booking_request** - Request to book a shipment
3. **tracking_inquiry** - Question about shipment status or ETA
4. **documentation** - Submission of documents (BOL, packing list, etc.)
5. **complaint** - Complaint about service, delivery, or pricing
6. **general_inquiry** - General questions that don't fit other categories
7. **not_relevant** - Spam, newsletters, or completely unrelated content

RULES:
- Classify into EXACTLY ONE category
- For RFQ: extract origin, destination, weight, volume, mode if available
- Be conservative: if unclear, use general_inquiry
- Return valid JSON only

JSON Format:
{
  "category": "one_of_the_categories",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "rfq_details": {
    "origin": "port/city or null",
    "destination": "port/city or null",
    "weight": "value or null",
    "volume": "value or null",
    "mode": "sea/air/lcl/fcl or null"
  }
}"""

    def classify_email(
        self,
        subject: str,
        body: str,
        from_email: str
    ) -> Tuple[str, Dict]:
        """
        Classify an email.

        Args:
            subject: Email subject
            body: Email body
            from_email: Sender email address

        Returns:
            Tuple of (category, full_response_dict)
        """
        if not self._using_anthropic:
            logger.error("Classifier not initialized")
            return "general_inquiry", {"category": "general_inquiry", "error": "not_initialized"}

        try:
            email_content = f"""Subject: {subject}
From: {from_email}
Body:
{body}"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=self.get_system_prompt(),
                messages=[
                    {"role": "user", "content": f"Classify this email:\n\n{email_content}"}
                ]
            )

            response_text = response.content[0].text
            result = json.loads(response_text)

            # Validate category
            category = result.get("category", "general_inquiry")
            if category not in VALID_CATEGORIES:
                logger.warning(f"Invalid category: {category}, using general_inquiry")
                category = "general_inquiry"

            logger.info(f"Classified from {from_email}: {category} (confidence: {result.get('confidence', 0)})")

            return category, result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response: {e}")
            return "general_inquiry", {"category": "general_inquiry", "error": "parse_error"}
        except Exception as e:
            logger.error(f"Classification error: {e}")
            return "general_inquiry", {"category": "general_inquiry", "error": str(e)}

    def get_label_for_category(self, category: str) -> str:
        """Get Gmail label for category"""
        return CATEGORY_LABELS.get(category, "5u/general")


# Placeholder for future Agno agent tools
# These will be used when we migrate to Agno Agent
AGNO_CLASSIFIER_TOOLS = [
    # TODO: Add structured output tools
    # {
    #     "name": "classify_as_rfq",
    #     "description": "Classify email as rate request",
    #     "parameters": {...}
    # },
    # etc.
]
