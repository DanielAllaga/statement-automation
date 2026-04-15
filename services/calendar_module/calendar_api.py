
from googleapiclient.discovery import build
import json
from datetime import datetime
from services.email_module.email_reader import EmailService
from services.email_module.email_sender import GmailSender
import os

class CalendarAPI:

    def run(self, cleaned_response):

        for response in cleaned_response:

            try:
                card_info = json.loads(response)
                due_date_str = card_info.get("due_date")  # expected format: "YYYY-MM-DD"
                card_type = card_info.get("credit_card_type") or "Credit Card"
                bank_name = card_info.get("bank_name") or ""
                total_amount = card_info.get("total_balance") or "Check statement"
            except Exception as e:
                print(f"❌ Failed to parse Gemini response: {e}")
                due_date_str = None

            if due_date_str:
                # Convert string to datetime
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
                readable_due_date = self.convert_date_readable_format(due_date_str)
                # Event start and end (30-min block)
                start_dt = due_date.replace(hour=9, minute=0)
                end_dt = due_date.replace(hour=9, minute=30)

                # Creating instance of email_module service to get the credential
                email = EmailService()
                creds = email.authenticate()

                # Authenticate Calendar API
                calendar_service = build('calendar', 'v3', credentials=creds)

                event = {
                    'summary': f'[{bank_name}] -  {card_type} (Payment Due: {readable_due_date})',
                    'description': f' Hi! This is your CreditCardBot AI reminder. \n Please ensure payment of {total_amount} '
                                   f'on or before {readable_due_date} to avoid any penalties.',
                    'start': {
                        'dateTime': start_dt.isoformat(),
                        'timeZone': 'Asia/Manila',
                    },
                    'end': {
                        'dateTime': end_dt.isoformat(),
                        'timeZone': 'Asia/Manila',
                    },
                    'attendees': [
                        {'email': os.getenv("TARGET_EMAIL")},  # This sends an invite to robert@gmail.com
                    ],
                    'reminders': {
                        'useDefault': False,
                        'overrides': [
                            {'method': 'email', 'minutes': 120 * 60},  # 5 days before
                            {'method': 'email', 'minutes': 48 * 60},  # 5 days before
                            {'method': 'popup', 'minutes': 60},
                            {'method': 'popup', 'minutes': 180},
                        ],
                    }
                }

                created_event = calendar_service.events().insert(
                    calendarId="primary",
                    body=event,
                    sendUpdates='all'
                ).execute()

                print(f"✅ Credit card due date event created: {created_event.get('htmlLink')}")
                sender = GmailSender()
                sender.send_message(
                    recipient=os.getenv("TARGET_EMAIL"),
                    message=(
                        f"Event successfully created! {bank_name} ({card_type}). "
                        f"Due on {readable_due_date} with a total amount of {total_amount}."
                    ),
                    subject = "[Notification] Credit Card Payment Reminder"
                )

                # Invoking email reader service to move the statement to processed_statement label
                email_reader = EmailService()
                email_reader.move_email_to_processed_statements()

            else:
                print("⚠️ No due date found. Skipping calendar event creation.")

    def convert_date_readable_format(self, date_str: str) -> str:

        # Convert to datetime object
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")

        # Format to desired output
        formatted_date = date_obj.strftime("%b %d, %Y")

        return formatted_date