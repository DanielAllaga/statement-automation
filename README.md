# Credit Card Statement Automation

This project downloads credit card statement PDFs from Gmail, decrypts them with a password map, redacts sensitive numbers, sends the redacted text to Gemini for JSON extraction, and creates Google Calendar reminders 5 days before the due date.

## What it does

1. Reads Gmail messages that match a query such as `label:"credit card statements" has:attachment filename:pdf`.
2. Downloads PDF attachments to `data/attachments/`.
3. Decrypts password-protected PDFs using rules in `config.json`.
4. Extracts text from the PDF and redacts likely credit card numbers before sending the text to Gemini.
5. Requests strict JSON with `due_date`, `total_amount`, and `email_sender`.
6. Validates the JSON in code before creating a Google Calendar event with a reminder 5 days before the due date.

## Gemini note

This version uses the Gemini API with `gemini-2.0-flash` as the default model. Google currently documents a free tier for Gemini API usage, but it comes with limits and different data handling than the paid tier.

## Setup

1. Install Python 3.11+.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. In Google Cloud Console, enable:
   - Gmail API
   - Google Calendar API
4. Create OAuth client credentials for a Desktop app.
5. Save the downloaded OAuth file as `credentials.json` in this project folder.
6. Copy `.env.example` to `.env` and set your Gemini API key:

```bash
GEMINI_API_KEY=your_api_key_here
```

7. Copy `config.example.json` to `config.json` and fill in your password lookup rules.
8. Run the script:

```bash
python statement_automation.py
```

## Output files

- `data/attachments/`: downloaded original PDFs
- `data/decrypted/`: decrypted PDFs
- `data/extracted_statements.json`: extracted structured data
- `data/state.json`: processed Gmail IDs and created calendar event IDs

## Security notes

- The script redacts likely card numbers before sending text to Gemini.
- Gmail and Calendar use Google APIs because they must interact with your Google account.
- Gemini is still a cloud API, so this version is not local-only.
