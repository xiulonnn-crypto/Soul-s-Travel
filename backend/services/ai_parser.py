import json
import os
from anthropic import Anthropic

SYSTEM_PROMPT = """You are a travel itinerary parser. Extract structured trip data from the user's text.

Return a JSON object with this exact structure:
{
  "trip": {
    "title": "string",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "traveler_count": number,
    "description": "string",
    "status": "completed"
  },
  "legs": [
    {
      "order_index": number,
      "city": "string (Chinese name)",
      "country": "string (Chinese name)",
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD",
      "days": [
        {
          "day_number": number,
          "date": "YYYY-MM-DD",
          "description": "string",
          "highlights": "string or null",
          "activities": ["string"],
          "transport": ["string with flight/train number and time if available"],
          "accommodation": "string or null"
        }
      ]
    }
  ],
  "expenses": [
    {
      "date": "YYYY-MM-DD",
      "category": "交通|住宿|餐饮|门票|购物|其他",
      "amount": number,
      "currency": "CNY",
      "description": "string"
    }
  ]
}

Rules:
- Extract all dates, cities, activities, transport, accommodation, and expenses you can find.
- If a day spans two cities (transfer day), assign it to the departure city's leg.
- For expenses, record total amounts. Note quantity in the description (e.g. "机票 2人").
- If information is unclear, use "[待确认]" as the value.
- Return ONLY valid JSON, no markdown fences, no explanation."""


def parse_text(text: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )

    response_text = message.content[0].text.strip()
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    return json.loads(response_text)
