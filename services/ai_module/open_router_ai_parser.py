from google import genai
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv
import re, os
import time
import json

load_dotenv()
open_router_key = os.getenv("OPEN_ROUTER_KEY")
open_router_url = os.getenv("BASE_URL")


class OpenRouterAIParser:

    def run(self, redacted_text_list: list) -> list:

        client = OpenAI(
            base_url=open_router_url,
            api_key=open_router_key,
        )

        models= [
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "minimax/minimax-m3:free"
        ]

        cleaned_response_list = []
        current_date = datetime.now().strftime("%Y-%m-%d")

        for redacted_text in redacted_text_list:
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
                   
                5. bank_name normalization rules:
                
                   Extract the bank/card issuer from the statement and normalize it to EXACTLY one of the following values when a matching indicator is found.
                
                   Matching must be case-insensitive.
                
                   - If the text contains "metropolitan", "Metropolitan Bank", or "Metropolitan Bank and Trust Company":
                     → bank_name = "Metrobank"
                
                   - If the text contains "BDO":
                     → bank_name = "BDO"
                
                   - If the text contains "RCBC Visa":
                     → bank_name = "RCBC Flex Visa"
                
                   - If the text contains "BPI":
                     → bank_name = "BPI"
                
                   - If the text contains "Maya":
                     → bank_name = "Maya Bank Visa"
                
                   - If the text "UnionBank" or standalone "UB" appears → "Unionbank"":
                     → bank_name = "Unionbank"
                
                   Important:
                   - Return ONLY the normalized value listed above.
                   - Do not return the original bank name from the statement.
                   - Do not infer a bank from unrelated text.
                   - Do not guess based on the credit card type alone.
                   - If none of the indicators above are found with reasonable confidence, return null.
                   - If multiple indicators are present, use the most specific match.
                   - "RCBC Visa" must take precedence over a generic "Visa" reference.
                   - "UB" should only be treated as Unionbank when it clearly refers to the bank/issuer, not when "ub" appears as part of another word.
                  
                  6. Do not include markdown, explanations, code blocks, or extra text.
                
                Current Date:
                {current_date}
                
                Sanitized Text:
                {redacted_text}
            """

            response = None
            last_error = None
            selected_model = None

            for model in models:
                max_retries = 5
                delay = 2  # seconds

                for attempt in range(max_retries):

                    try:
                        response = client.chat.completions.create(
                            model=model,
                            messages=[{"role": "user","content": prompt}],
                            temperature=0,
                        )

                        result = response.choices[0].message.content

                        json.loads(result)
                        selected_model = model
                        # Successful response
                        break

                    except Exception as e:
                        last_error = e
                        if attempt < max_retries - 1:
                            time.sleep(delay)
                            delay *= 2  # exponential backoff
                        else:
                            raise e

                if response is not None:
                    break

            if response is None:
                raise last_error

            cleaned_response = response.choices[0].message.content

            print("OpenRouter Response:")
            print(cleaned_response)
            print("Model:", selected_model)

            # Remove accidental markdown fences
            cleaned_response = re.sub(
                r"^```(?:json)?\s*|\s*```$",
                "",
                cleaned_response.strip(),
                flags=re.IGNORECASE
            )

            cleaned_response_list.append(cleaned_response)

        return cleaned_response_list