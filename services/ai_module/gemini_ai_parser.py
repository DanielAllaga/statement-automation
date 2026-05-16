from google import genai
from datetime import datetime
import re, os
import time

class GeminiAIParser:

    def run(self, redacted_text_list: list) -> list:

        # 'gemini-2.5-flash' is the stable free-tier model for 2026
        client = genai.Client(api_key=os.getenv("GEN_AI_API_KEY"))
        cleaned_response_list = []
        current_date = datetime.now().strftime("%Y-%m-%d")

        for redacted_text in enumerate(redacted_text_list):
            # Create the prompt
            prompt = f"""
                From the sanitized credit card statement text below, extract these fields:
                
                - due_date
                - total_balance
                - credit_card_type
                - minimum_amount
                - bank_name
                
                Rules:
                1. Return ONLY a valid JSON object with exactly these keys:
                   {{
                     "due_date": "",
                     "total_balance": "",
                     "credit_card_type": "",
                     "minimum_amount": "",
                     "bank_name": ""
                   }}
                
                2. If a value cannot be found, use null.
                
                3. due_date rules:
                   - Output format must be strictly YYYY-MM-DD.
                   - Use the CURRENT DATE as reference when validating the year.
                   - The due_date must NOT be in the past.
                   - If the statement shows a month/day without a year, infer the correct future year based on the current date.
                   - If multiple years appear in the text, choose the due date that is closest upcoming future date.
                   - Ignore old statement dates, transaction dates, posting dates, and previous billing periods.
                   - Never return a due_date from a previous year if the current date is already later than that date.
                   - If no valid future due date can be confidently determined, return null.
                
                4. total_balance and minimum_amount:
                   - Format must be exactly: ₱1234.56
                   - Include the peso sign.
                   - Do not include extra text.
                
                5. Do not include markdown, explanations, code blocks, or extra text.
                
                Current Date:
                {current_date}
                
                Sanitized Text:
                {redacted_text}
            """

            max_retries = 5
            delay = 2  # seconds

            for attempt in range(max_retries):

                try:
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt
                    )
                    break  # success
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                        delay *= 2  # exponential backoff
                    else:
                        raise e

            print("Gemini's response:")
            print(response.text)
            cleaned_response = re.sub(r"^```[a-zA-Z]*|```$", "", response.text).strip()

            cleaned_response_list.append(cleaned_response)

        return cleaned_response_list