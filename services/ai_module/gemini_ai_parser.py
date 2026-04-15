from google import genai
import re, os
import time

class GeminiAIParser:

    def run(self, redacted_text_list: list) -> list:

        # 'gemini-2.5-flash' is the stable free-tier model for 2026
        client = genai.Client(api_key=os.getenv("GEN_AI_API_KEY"))
        cleaned_response_list = []

        for redacted_text in enumerate(redacted_text_list):
            # Create the prompt
            prompt = f"""
            From the sanitized text below, extract the following fields: 
            - due_date (the expected format must be: "YYYY-MM-DD")
            - total_balance (the expected format must be ₱ amount_here)
            - credit_card_type
            - minimum_amount (the expected format must be ₱ amount_here)
            - bank_name
    
            Return strictly a JSON object with these keys. 
            If any value is not found, use null for that field. 
            Do not include any extra text, explanations, or formatting outside of the JSON.
    
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