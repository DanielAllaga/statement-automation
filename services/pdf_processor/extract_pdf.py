import sys, os
from pathlib import Path
import pdfplumber
from pdf2image import convert_from_path
import cv2
import numpy as np
from pypdf import PdfReader, PdfWriter
from dotenv import load_dotenv
from typing import List, Optional, Dict
import pytesseract
import re
from pathlib import Path

load_dotenv()

TESSERACT_PATH = os.getenv("TESSERACT_PATH")
POPPLER_PATH = os.getenv("POPPLER_PATH")

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

FULL_NAME = os.getenv("FULL_NAME")
USER_ADDRESS = os.getenv("USER_ADDRESS")

PASSWORD_MAP: Dict[str, Optional[str]] = {
    "maya": os.getenv("PASSWORD_MAYA"),
    "jcb": os.getenv("PASSWORD_JCB"),
    "flex": os.getenv("PASSWORD_FLEX"),
    "bdo": os.getenv("PASSWORD_BDO"),
    "bpi": os.getenv("PASSWORD_BPI"),
    "metrobank": os.getenv("PASSWORD_METROBANK"),
    "ub": os.getenv("PASSWORD_UB"),
}


class PDFProcessor:

    def __init__(self, base_dir):
        self.project_dir = Path(base_dir)
        self.attachments_dir = self.project_dir / "data" / "attachments"
        self.decrypted_dir = self.project_dir / "data" / "decrypted"
        self.decrypted_dir.mkdir(parents=True, exist_ok=True)


    # ---- Public Method ----
    def run(self, email_subject, pdf_path: Path = None) -> List[str]:

        if pdf_path and isinstance(pdf_path, str):
            pdf_path = Path(pdf_path)

        redacted_text_list = []

        pdf_files = [pdf_path] if pdf_path else list(self.attachments_dir.glob("*.pdf"))

        if not pdf_files:
            print("No pdf files found in the directory")
            sys.exit(0)

        for pdf in pdf_files:
            try:
                password = self.get_password(pdf.name, email_subject)

                decrypted_pdf = self.decrypt_pdf_if_needed(
                    pdf,
                    password,
                    self.decrypted_dir
                )

                raw_text = self.extract_pdf_text(decrypted_pdf, email_subject)
                redacted_text = self.sanitize_text(raw_text)

                print(f"\n✅ Processed: {pdf.name}")
                redacted_text_list.append(redacted_text)

            except Exception as e:
                print(f"\n❌ Failed: {pdf.name}")
                print(f"Error: {e}")

        return redacted_text_list

    def preprocess(self,pil_img):
        img = np.array(pil_img)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        _, thresh = cv2.threshold(blur, 150, 255, cv2.THRESH_BINARY)

        return thresh

    def ocr_pdf(self, file_path: str) -> str:
        images = convert_from_path(
            file_path,
            poppler_path=POPPLER_PATH,
            dpi=300  # 🔥 improves accuracy
        )

        results = []

        for i, img in enumerate(images):
            print(f"Processing page {i + 1}...")

            processed = self.preprocess(img)

            text = pytesseract.image_to_string(
                processed,
                config="--oem 3 --psm 6"
            )

            results.append(text)

        return "\n".join(results)

    def extract_pdf_text(self, pdf_path: Path, email_subject: str) -> str:

        if "BPI" in str(pdf_path):
            # Custom logic for BPI Credit Card Statement
            # To not include transaction history - limit of 8000 indexes applied
            extracted_text = self.ocr_pdf(str(pdf_path))
            return extracted_text[:8000]

        if "metrobank" in email_subject.lower():
            extracted_text = self.ocr_pdf(str(pdf_path))
            return extracted_text[:8000]

        else:
            chunks: List[str] = []
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page in pdf.pages:
                    chunks.append(page.extract_text() or "")
            return "\n".join(chunks).strip()

    def decrypt_pdf_if_needed(self, pdf_path: Path, password: Optional[str], output_dir: Path) -> Path:
        reader = PdfReader(str(pdf_path))

        if not reader.is_encrypted:
            return pdf_path

        if not password:
            raise ValueError(f"No password found for: {pdf_path.name}")

        if reader.decrypt(password) == 0:
            raise ValueError(f"Wrong password for: {pdf_path.name}")

        output_dir.mkdir(parents=True, exist_ok=True)
        decrypted_path = output_dir / f"decrypted_{pdf_path.name}"

        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        with decrypted_path.open("wb") as f:
            writer.write(f)

        if pdf_path.exists():
            pdf_path.unlink()
            print("PDF successfully decrypted, file will be deleted in the attachment folder")

        else:
            print("No PDF detected in the attachment folder")

        return decrypted_path

    def get_password(self, filename: str, email_subject: str) -> Optional[str]:
        filename_lower = filename.lower()
        email_subject_lower = email_subject.lower()
        pdf_password = ""

        # To get the password based on its filename
        for key, password in PASSWORD_MAP.items():
            if key in filename_lower:
                pdf_password = password
                return pdf_password

        # To get the password based on its email subject
        if not pdf_password:
            for key, password in PASSWORD_MAP.items():
                if key in email_subject_lower:
                    pdf_password = password
                    return pdf_password

        return None

    def redact_sensitive_information(self, text: str) -> str:

        # 🔹 Pattern 0: Masked card numbers like 4404-53**-****-8376
        pattern_masked_card = r'\b\d{4}-[\d\*]{4}-[\d\*]{4}-\d{4}\b'

        # 🔹 Pattern 1: Standard card formats (with spaces or dashes)
        pattern_cards = r'\b(?:\d{4}[- ]?){3}\d{4}\b'

        # 🔹 Pattern 2: Continuous digits with length >= 16
        pattern_long_numbers = r'\b\d{16,}\b'

        # 🔹 Pattern 3: Numbers with optional prefix like *, #
        pattern_prefixed_numbers = r'[\*\#]?\d{16,}'

        # 🔹 Pattern 4: Limit amounts (PHP or ₱ with commas)
        pattern_limit = r'Limit\s+(?:PHP|₱)\s+[\d,]+'

        # 🔹 Pattern 5: Remove Available points
        pattern_points = r'Available\s+Points[:\s]*[\d,]*'

        # 🔹 Pattern 6: Remove Customer number
        pattern_customer_number = r'Customer\s+Number[:\s]*[\d-]+'

        # 🔹 Pattern 8: Remove reference number
        pattern_dashed_numbers = r'§?\d{3,}(?:-\d{1,}){2,}'

        # 🔹 Pattern 8: Remove Bill reference number
        pattern_reference_no = r'Reference\s+No\.?[:\s]*[A-Za-z0-9-]+'

        # 🔹 Pattern 9: Remove BPI credit limit
        pattern_credit_limit = r'CREDIT\s+LIMIT[:\s]*[\d,]+\.\d{2}'

        # 🔹 Pattern 10: Remove UB credit limit
        ub_credit_limit = r'Credit\s*Limit\s*:\s*(?:PHP|₱)\s*[\d,]+\.\d{2}'

        # 🔹 Pattern 11: Masked name + trailing digits (MB use case)
        pattern_masked_name_digits = r'\b[A-Z][A-Z\*\™]+\s+[A-Z]+\s+\d{2}\s+\d{4}\b'

        # ✅ Apply redactions (order matters)
        text = re.sub(pattern_masked_card, '[REDACTED]', text)
        text = re.sub(pattern_cards, '[REDACTED]', text)
        text = re.sub(pattern_prefixed_numbers, '[REDACTED]', text)
        text = re.sub(pattern_long_numbers, '[REDACTED]', text)
        text = re.sub(pattern_dashed_numbers, '[REDACTED]', text)
        text = re.sub(pattern_limit, '[REDACTED]', text, flags=re.IGNORECASE)
        text = re.sub(pattern_points, '[REDACTED]', text, flags=re.IGNORECASE)
        text = re.sub(pattern_customer_number, '[REDACTED]', text, flags=re.IGNORECASE)
        text = re.sub(pattern_reference_no, '[REDACTED]', text, flags=re.IGNORECASE)
        text = re.sub(pattern_credit_limit, '[REDACTED]', text, flags=re.IGNORECASE)
        text = re.sub(ub_credit_limit, '[REDACTED]', text, flags=re.IGNORECASE)
        text = re.sub(pattern_masked_name_digits, '[REDACTED]', text)


        return text

    # 🔹 Convert full string into keywords
    def get_keywords(self, value: Optional[str]) -> List[str]:
        if not value:
            return []
        return [word.lower() for word in value.split()]

    def redact_keywords_partial(self, text: str, keywords: List[str], label: str) -> str:
        for keyword in keywords:
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            text = pattern.sub(f"[{label}]", text)
        return text

    # 🔹 Main sanitizer
    def sanitize_text(self, text: str) -> str:
        text = self.redact_sensitive_information(text)

        name_keywords = self.get_keywords(FULL_NAME)
        address_keywords = self.get_keywords(USER_ADDRESS)

        text = self.redact_keywords_partial(text, name_keywords, "REDACTED")
        text = self.redact_keywords_partial(text, address_keywords, "REDACTED")

        return text