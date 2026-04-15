from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import os
import base64
from googleapiclient.discovery import build

from services.email_module.email_sender import GmailSender

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar.events'
]

SOURCE_LABEL = 'Credit Card Statement'
TARGET_LABEL = 'Processed Statements'
DOWNLOAD_DIR = 'data/attachments'

class EmailService:

    def authenticate(self):
        creds = None
        # 1. Try to load existing token
        if os.path.exists('token.json'):
            try:
                creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            except Exception as e:
                print(f"⚠️ Token file corrupted, deleting... {e}")
                os.remove('token.json')

        # 2. Check validity
        if not creds or not creds.valid:
            try:
                if creds and creds.expired and creds.refresh_token:
                    print("🔄 Refreshing expired token...")
                    creds.refresh(Request())
                else:
                    raise Exception("No refresh token available")
            except Exception:
                print("🔑 Fresh login required...")
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)

            # 3. Save the new token
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
                print("✅ New token.json created!")

        return creds

    def process_statement(self, service):
        if not os.path.exists(DOWNLOAD_DIR):
            os.makedirs(DOWNLOAD_DIR)

        # 1. Get Label IDs
        source_id = self.get_label_id(service, SOURCE_LABEL)
        target_id = self.get_label_id(service, TARGET_LABEL)

        # 2. Search for the latest message in the source label
        results = service.users().messages().list(userId='me', q=f'label:"{SOURCE_LABEL}"').execute()
        messages = results.get('messages', [])

        if not messages:
            print(f"📭 No new messages in '{SOURCE_LABEL}'.")
            sender = GmailSender()
            sender.send_message(
                recipient=os.getenv("TARGET_EMAIL"),
                message=(
                    f"No new messages found in '{SOURCE_LABEL}'. "
                    f"Execution completed successfully."
                ),
                subject="[Notification] Credit Card Payment Reminder"
            )

            return None

        msg_id = messages[0]['id']
        message = service.users().messages().get(userId='me', id=msg_id).execute()

        # 3. Extract PDF
        pdf_path_process_statement = None
        parts = message.get('payload', {}).get('parts', [])
        for part in parts:
            filename = part.get('filename')
            if filename and filename.lower().endswith('.pdf'):
                att_id = part['body'].get('attachmentId')
                attachment = service.users().messages().attachments().get(
                    userId='me', messageId=msg_id, id=att_id).execute()

                file_data = base64.urlsafe_b64decode(attachment.get('data').encode('UTF-8'))
                pdf_path_process_statement = os.path.join(DOWNLOAD_DIR, filename)

                with open(pdf_path_process_statement, 'wb') as f:
                    f.write(file_data)
                break

        # 4. If download succeeded, move the label immediately
        if pdf_path_process_statement:
            print(f"✅ Downloaded: {pdf_path_process_statement}")

            return pdf_path_process_statement

        return None

    def get_label_id(self, service, label_name):
        results = service.users().labels().list(userId='me').execute()
        for label in results.get('labels', []):
            if label['name'] == label_name:
                return label['id']
        return None

    def fetch_latest_pdf(self) -> str | None:
        """
        Authenticate, connect to Gmail, and fetch the latest PDF from SOURCE_LABEL.
        Returns the local PDF path if successful, else None.
        """
        # 1️⃣ Authenticate
        creds = self.authenticate()
        gmail_service = build('gmail', 'v1', credentials=creds)

        # 2️⃣ Process the latest statement
        pdf_path = self.process_statement(service=gmail_service)

        if pdf_path:
            print(f"📄 Latest PDF ready: {pdf_path}")
        else:
            print("📭 No PDF found.")

        return pdf_path

    def move_email_to_processed_statements(self):
        creds = self.authenticate()
        gmail_service = build('gmail', 'v1', credentials=creds)

        source_id = self.get_label_id(gmail_service, SOURCE_LABEL)
        target_id = self.get_label_id(gmail_service, TARGET_LABEL)

        # 2. Search for the latest message in the source label
        results = gmail_service.users().messages().list(userId='me', q=f'label:"{SOURCE_LABEL}"').execute()
        messages = results.get('messages', [])
        msg_id = messages[0]['id']

        # Move logic: Remove source label, add target label
        mods = {'removeLabelIds': [source_id]}
        if target_id:
            mods['addLabelIds'] = [target_id]

        gmail_service.users().messages().modify(userId='me', id=msg_id, body=mods).execute()
        print(f"🏷️ Moved email to '{TARGET_LABEL}' to prevent duplicate processing.")

        return None