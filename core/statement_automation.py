
from services.calendar_module.calendar_api import CalendarAPI
from services.email_module.email_reader import EmailService
from services.pdf_processor.extract_pdf import PDFProcessor
from services.ai_module.gemini_ai_parser import GeminiAIParser
from pathlib import Path

def run():
    # Workflow 1: Access the email_module and download the attached pdf file
    email_service = EmailService()
    pdf_path = email_service.fetch_latest_pdf()

    # Workflow 2: Parse the pdf in the attachment folder
    project_root = Path(__file__).resolve().parent
    pdf_processor = PDFProcessor(project_root)
    pdf_processor_result = pdf_processor.run(pdf_path)

    print(pdf_processor_result)
    # Workflow 3: Send the redacted text to Gemini for text analysis
    gemini_ai_parser = GeminiAIParser()
    gemini_ai_parser_result = gemini_ai_parser.run(pdf_processor_result)

    # Workflow 4: Google Calendar API
    calendar_api = CalendarAPI()
    calendar_api.run(gemini_ai_parser_result)



if __name__ == "__main__":
    run()


