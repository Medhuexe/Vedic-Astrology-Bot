"""
╔══════════════════════════════════════════════════════════════════╗
║         VEDIC ASTROLOGY AUTOMATION PIPELINE                     ║
║  Google Forms → Gemini AI → PDF → Email + WhatsApp             ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import re
import json
import time
import smtplib
import requests
import logging
import urllib.request
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, Spacer, HRFlowable, PageBreak, Image as RLImage
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, NextPageTemplate
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from google import genai

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
SPREADSHEET_ID      = os.getenv("SPREADSHEET_ID", "")
SHEET_NAME          = os.getenv("SHEET_NAME", "Form responses 1")

SMTP_HOST           = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT           = int(os.getenv("SMTP_PORT", "587"))
EMAIL_SENDER        = os.getenv("EMAIL_SENDER", "your@gmail.com")
EMAIL_PASSWORD      = os.getenv("EMAIL_PASSWORD", "your_app_password")

WHATSAPP_PROVIDER   = os.getenv("WHATSAPP_PROVIDER", "callmebot")
TWILIO_ACCOUNT_SID  = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_NUM = os.getenv("TWILIO_WHATSAPP_NUM", "whatsapp:+14155238886")
CALLMEBOT_API_KEY   = os.getenv("CALLMEBOT_API_KEY", "")

OUTPUT_DIR          = os.getenv("OUTPUT_DIR", "reports")
PROCESSED_LOG       = os.getenv("PROCESSED_LOG", "processed_rows.json")

COL_TIMESTAMP   = "Timestamp"
COL_EMAIL       = "Email Address"
COL_NAME        = "Full Name"
COL_DOB         = "Date of Birth"
COL_TOB         = "Time of Birth"
COL_POB         = "Place of Birth (City, State/Province, Country)"
COL_PHONE       = "Contact Number"

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

FONT_URLS = {
    "CormorantGaramond-Regular":   "https://github.com/CatharsisFonts/Cormorant/raw/refs/heads/master/fonts/ttf/CormorantGaramond-Regular.ttf",
    "CormorantGaramond-Bold":      "https://github.com/CatharsisFonts/Cormorant/raw/refs/heads/master/fonts/ttf/CormorantGaramond-Bold.ttf",
    "CormorantGaramond-Italic":    "https://github.com/CatharsisFonts/Cormorant/raw/refs/heads/master/fonts/ttf/CormorantGaramond-Italic.ttf",
    "EBGaramond-Regular":          "https://github.com/octaviopardo/EBGaramond12/raw/master/fonts/EBGaramond12-Regular.ttf",
    "EBGaramond-Bold":             "https://github.com/octaviopardo/EBGaramond12/raw/master/fonts/EBGaramond12-Italic.ttf",
    "EBGaramond-Italic":           "https://github.com/octaviopardo/EBGaramond12/raw/master/fonts/EBGaramond12-Italic.ttf",
}

def setup_fonts():
    """Download and register custom fonts. Falls back to Helvetica if download fails."""
    os.makedirs(FONT_DIR, exist_ok=True)
    fonts_ok = True
    for font_name, url in FONT_URLS.items():
        path = os.path.join(FONT_DIR, f"{font_name}.ttf")
        if not os.path.exists(path):
            log.info(f"Downloading font {font_name}...")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    with open(path, "wb") as f:
                        f.write(resp.read())
                log.info(f"  Downloaded: {font_name}")
            except Exception as e:
                log.warning(f"  Could not download {font_name}: {e}")
                fonts_ok = False

    try:
        pdfmetrics.registerFont(TTFont("CormorantGaramond", os.path.join(FONT_DIR, "CormorantGaramond-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("CormorantGaramond-Bold", os.path.join(FONT_DIR, "CormorantGaramond-Bold.ttf")))
        pdfmetrics.registerFont(TTFont("CormorantGaramond-Italic", os.path.join(FONT_DIR, "CormorantGaramond-Italic.ttf")))
        pdfmetrics.registerFont(TTFont("EBGaramond", os.path.join(FONT_DIR, "EBGaramond-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("EBGaramond-Bold", os.path.join(FONT_DIR, "EBGaramond-Bold.ttf")))
        pdfmetrics.registerFont(TTFont("EBGaramond-Italic", os.path.join(FONT_DIR, "EBGaramond-Italic.ttf")))
        pdfmetrics.registerFontFamily(
            "CormorantGaramond",
            normal="CormorantGaramond",
            bold="CormorantGaramond-Bold",
            italic="CormorantGaramond-Italic",
            boldItalic="CormorantGaramond-Italic"
        )
        pdfmetrics.registerFontFamily(
            "EBGaramond",
            normal="EBGaramond",
            bold="EBGaramond-Bold",
            italic="EBGaramond-Italic",
            boldItalic="EBGaramond-Italic"
        )
        log.info("Custom fonts registered successfully.")
        return True
    except Exception as e:
        log.warning(f"Font registration failed, falling back to Helvetica: {e}")
        return False

DEEP_NAVY   = colors.HexColor("#0B1929")
GOLD        = colors.HexColor("#C9A84C")
LIGHT_GOLD  = colors.HexColor("#E8CC7E")
CREAM       = colors.HexColor("#FDFAF4")
RUST_RED    = colors.HexColor("#8B2500")
SLATE       = colors.HexColor("#2C3E50")
LIGHT_SLATE = colors.HexColor("#8899AA")
WHITE       = colors.white



SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

def get_google_creds():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return creds

def fetch_form_responses():
    creds   = get_google_creds()
    service = build("sheets", "v4", credentials=creds)
    result  = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Form responses 1",
    ).execute()
    rows = result.get("values", [])
    if not rows:
        log.info("No data found in sheet.")
        return []
    headers = rows[0]
    return [dict(zip(headers, row)) for row in rows[1:]]

def load_processed():
    if os.path.exists(PROCESSED_LOG):
        with open(PROCESSED_LOG) as f:
            return set(json.load(f))
    return set()

def save_processed(processed):
    with open(PROCESSED_LOG, "w") as f:
        json.dump(list(processed), f)



SYSTEM_PROMPT = """Act as a master Vedic astrologer with decades of experience in Jyotish shastra, chart analysis, and predictive astrology.
Your task is to generate a comprehensive, highly specific 5-year Vedic astrology forecast (covering 2026-2031) focused primarily on career and wealth.
CRITICAL INSTRUCTION: You must execute this analysis and provide the full, completed report immediately in your response. Do not ask any follow-up questions, do not ask for clarification, do not offer a menu of options, and do not express doubts. Assume standard Lahiri Ayanamsa for all calculations.
Deliver the analysis directly, using clear headings, bullet points, and authoritative, professional astrological terminology explained simply."""

def build_user_prompt(row: dict) -> str:
    name = row.get(COL_NAME, "the querent")
    dob  = row.get(COL_DOB, "DD/MM/YYYY")
    tob  = row.get(COL_TOB, "HH:MM AM/PM")
    pob  = row.get(COL_POB, "City, State, Country")

    return f"""Here are the birth details for {name}:

* Date of Birth: {dob}
* Time of Birth: {tob}
* Place of Birth: {pob}

Please structure your response meticulously using the following sections:

### 1. Birth Chart Foundation
* Calculate the planetary positions and explicitly state the Ascendant (Lagna), Moon sign (Rashi), Sun sign, and Nakshatra.
* Map out the key placements in the Rashi (D1) and Navamsa (D9) charts.
* Detail the positions and dignity (exalted, debilitated, own sign, friendly) of planets governing career (10th lord, Saturn, Sun) and wealth (2nd & 11th lords, Jupiter, Venus).
* Identify the current Vimshottari Mahadasha and Antardasha periods, including exact dates.

### 2. 5-Year Career Forecast (2026-2031)
* Provide year-by-year chronological predictions for career growth, job transitions, or business ventures.
* Highlight specific timeframes (months/years) for major career breakthroughs, promotions, or shifts in professional direction.
* Analyze professional challenges, workplace dynamics, and favorable periods for taking risks.
* Suggest the most suitable industries, roles, or career paths based on the 10th house, Amatyakaraka, and D10 (Dasamsa) indications.

### 3. 5-Year Wealth & Finance Forecast (2026-2031)
* Project income growth potential and financial stability patterns over the next 5 years.
* Pinpoint the most favorable periods for investments, savings, and major purchases.
* Identify any planetary yogas (Dhana Yogas) indicating windfalls, unexpected gains, or wealth accumulation.
* Outline potential financial pitfalls or periods of high expenditure to watch out for.

### 4. Supporting Life Areas
* Health: Highlight specific transits or dashas requiring extra care and areas of the body to protect.
* Relationships/Family: Provide a brief overview of family harmony and relationship milestones.
* Spiritual/Life Themes: Summarize the overarching karmic lessons of this 5-year period.

### 5. Practical Guidance & Remedies
* Recommend 1-2 specific gemstones based on functional benefics for the Lagna (include carat weight and which finger to wear them on). Give the astrological reasoning.
* Provide powerful mantras or specific daily remedies to propitiate weak or challenging planets.
* Suggest favorable dates or upcoming transit periods to initiate important career or financial moves."""



def call_gemini(user_prompt: str) -> str:
    log.info("Calling Gemini API ...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=SYSTEM_PROMPT + "\n\n" + user_prompt
    )
    return response.text



SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PDF = os.path.join(SCRIPT_DIR, "Astraveda_PDF_format.pdf")


def _get_font(base: str, variant: str = "normal") -> str:
    """Return registered font name or fallback Helvetica."""
    mapping = {
        ("CormorantGaramond", "normal"):  "CormorantGaramond",
        ("CormorantGaramond", "bold"):    "CormorantGaramond-Bold",
        ("CormorantGaramond", "italic"):  "CormorantGaramond-Italic",
        ("EBGaramond",        "normal"):  "EBGaramond",
        ("EBGaramond",        "bold"):    "EBGaramond-Bold",
        ("EBGaramond",        "italic"):  "EBGaramond-Italic",
    }
    fallback = {
        "normal": "Helvetica",
        "bold":   "Helvetica-Bold",
        "italic": "Helvetica-Oblique",
    }
    name = mapping.get((base, variant))
    if name:
        try:
            pdfmetrics.getFont(name)
            return name
        except Exception:
            pass
    return fallback.get(variant, "Helvetica")


def _draw_cover_page(c, doc, name: str, dob: str, pob: str):
    """
    Page 1 — use the cover from Astraveda_PDF_format.pdf as background,
    then overlay the recipient's name/dob/pob.
    Falls back to a programmatic dark cover if the template is missing.
    """
    w, h = A4
    c.saveState()

    if os.path.exists(TEMPLATE_PDF):
        from reportlab.lib.utils import ImageReader
        from pdf2image import convert_from_path
        try:
            imgs = convert_from_path(TEMPLATE_PDF, dpi=150, first_page=1, last_page=1)
            import io
            buf = io.BytesIO()
            imgs[0].save(buf, format="PNG")
            buf.seek(0)
            c.drawImage(ImageReader(buf), 0, 0, width=w, height=h)
        except Exception as e:
            log.warning(f"Could not render template cover: {e}")
            _draw_fallback_cover(c, w, h)
    else:
        _draw_fallback_cover(c, w, h)

    # Overlay recipient details at the bottom of the cover
    box_y = h * 0.13
    c.setFillColor(colors.HexColor("#0B1929CC"))  # semi-transparent navy
    c.roundRect(2*cm, box_y - 2.2*cm, w - 4*cm, 2.5*cm, 6, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.8)
    c.roundRect(2*cm, box_y - 2.2*cm, w - 4*cm, 2.5*cm, 6, fill=0, stroke=1)

    c.setFillColor(LIGHT_GOLD)
    c.setFont(_get_font("CormorantGaramond", "bold"), 15)
    c.drawCentredString(w / 2, box_y + 0.05*cm, name)

    c.setFillColor(WHITE)
    c.setFont(_get_font("EBGaramond", "normal"), 10)
    c.drawCentredString(w / 2, box_y - 0.65*cm, f"Born: {dob}   |   {pob}")

    c.setFillColor(LIGHT_SLATE)
    c.setFont(_get_font("EBGaramond", "italic"), 8)
    c.drawCentredString(w / 2, box_y - 1.35*cm,
        f"Report prepared on {datetime.now().strftime('%d %B %Y')}")

    c.restoreState()


def _draw_fallback_cover(c, w, h):
    """Plain dark cover used when template PDF is unavailable."""
    import random
    c.setFillColor(colors.HexColor("#0D1B2A"))
    c.rect(0, 0, w, h, fill=1, stroke=0)
    random.seed(42)
    c.setFillColor(WHITE)
    for _ in range(80):
        x = random.uniform(0, w)
        y = random.uniform(h * 0.25, h)
        c.circle(x, y, random.uniform(0.5, 1.8), fill=1, stroke=0)
    c.setFillColor(LIGHT_GOLD)
    c.setFont(_get_font("CormorantGaramond", "bold"), 28)
    c.drawCentredString(w / 2, h * 0.72, "ASTRAVEDA")
    c.setFont(_get_font("EBGaramond", "normal"), 14)
    c.setFillColor(WHITE)
    c.drawCentredString(w / 2, h * 0.67, "ANCIENT WISDOM. FUTURE CLARITY.")
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(3*cm, h * 0.65, w - 3*cm, h * 0.65)


def _draw_body_page(c, doc):
    """
    Pages 2+ — Astraveda header banner at the top, cream body, gold footer.
    The header image is taken from page 2 of the template PDF.
    """
    w, h = A4
    c.saveState()

    c.setFillColor(CREAM)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    HEADER_HEIGHT = 5.8 * cm   # matches the banner in your template
    if os.path.exists(TEMPLATE_PDF):
        from reportlab.lib.utils import ImageReader
        from pdf2image import convert_from_path
        try:
            imgs = convert_from_path(TEMPLATE_PDF, dpi=150, first_page=2, last_page=2)
            img  = imgs[0]
            iw, ih = img.size
            # Crop only the top banner portion
            crop_bottom = int(ih * 0.72)   # keep top 28%
            banner = img.crop((0, 0, iw, crop_bottom))
            import io
            buf = io.BytesIO()
            banner.save(buf, format="PNG")
            buf.seek(0)
            c.drawImage(ImageReader(buf), 0, h - HEADER_HEIGHT,
                        width=w, height=HEADER_HEIGHT, mask="auto")
        except Exception as e:
            log.warning(f"Header render failed: {e}")
            _draw_fallback_header(c, w, h, HEADER_HEIGHT)
    else:
        _draw_fallback_header(c, w, h, HEADER_HEIGHT)

    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(1.5*cm, h - HEADER_HEIGHT, w - 1.5*cm, h - HEADER_HEIGHT)

    c.setFillColor(GOLD)
    c.rect(0, 1.8*cm, 3, h - HEADER_HEIGHT - 1.8*cm, fill=1, stroke=0)
    c.rect(w - 3, 1.8*cm, 3, h - HEADER_HEIGHT - 1.8*cm, fill=1, stroke=0)

    c.setFillColor(DEEP_NAVY)
    c.rect(0, 0, w, 1.8*cm, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(0, 1.8*cm, w, 1.8*cm)

    c.setFillColor(LIGHT_GOLD)
    c.setFont(_get_font("EBGaramond", "normal"), 8)
    c.drawCentredString(w / 2, 0.9*cm, f"— {doc.page} —")

    c.setFillColor(LIGHT_SLATE)
    c.setFont(_get_font("EBGaramond", "italic"), 7)
    c.drawCentredString(w / 2, 0.4*cm,
        "Astraveda  •  Ancient Wisdom. Future Clarity.  •  Confidential")

    c.restoreState()


def _draw_fallback_header(c, w, h, header_height):
    """Simple navy header used when template PDF is not found."""
    c.setFillColor(DEEP_NAVY)
    c.rect(0, h - header_height, w, header_height, fill=1, stroke=0)
    c.setFillColor(LIGHT_GOLD)
    c.setFont(_get_font("CormorantGaramond", "bold"), 22)
    c.drawCentredString(w / 2, h - header_height * 0.45, "ASTRAVEDA")
    c.setFont(_get_font("EBGaramond", "normal"), 9)
    c.setFillColor(LIGHT_SLATE)
    c.drawCentredString(w / 2, h - header_height * 0.72,
        "ANCIENT WISDOM. FUTURE CLARITY.")


def safe_paragraph(content: str, style) -> Paragraph:
    """Strip raw HTML from Gemini output, convert markdown, build Paragraph safely."""
    content = re.sub(r'<[^>]+>', '', content)
    content = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', content)
    content = re.sub(r'\*(.+?)\*',    r'<i>\1</i>', content)
    content = re.sub(r'&(?!amp;|lt;|gt;|quot;|#)', '&amp;', content)
    try:
        return Paragraph(content, style)
    except Exception:
        plain = re.sub(r'<[^>]+>', '', content)
        return Paragraph(plain, style)


def parse_report_text(text: str, fonts_loaded: bool) -> list:
    """Convert Gemini markdown to ReportLab story using Astraveda fonts & colours."""
    H_FONT  = "CormorantGaramond" if fonts_loaded else "Helvetica"
    H_BOLD  = "CormorantGaramond-Bold" if fonts_loaded else "Helvetica-Bold"
    B_FONT  = "EBGaramond" if fonts_loaded else "Helvetica"
    B_BOLD  = "EBGaramond-Bold" if fonts_loaded else "Helvetica-Bold"
    B_ITAL  = "EBGaramond-Italic" if fonts_loaded else "Helvetica-Oblique"

    styles = getSampleStyleSheet()

    h1 = ParagraphStyle("AH1", parent=styles["Normal"],
        fontName=H_BOLD, fontSize=18, textColor=DEEP_NAVY,
        spaceAfter=6, spaceBefore=18, leading=22)

    h2 = ParagraphStyle("AH2", parent=styles["Normal"],
        fontName=H_BOLD, fontSize=14, textColor=RUST_RED,
        spaceAfter=5, spaceBefore=14, leading=18)

    h3 = ParagraphStyle("AH3", parent=styles["Normal"],
        fontName=H_FONT, fontSize=12, textColor=SLATE,
        spaceAfter=4, spaceBefore=10, leading=15)

    body = ParagraphStyle("ABody", parent=styles["Normal"],
        fontName=B_FONT, fontSize=11, textColor=SLATE,
        leading=17, spaceAfter=6, alignment=TA_JUSTIFY)

    bullet = ParagraphStyle("ABullet", parent=body,
        leftIndent=18, bulletIndent=6, spaceAfter=4)

    story = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            story.append(Spacer(1, 4))
            continue
        if s.startswith("### "):
            story.append(safe_paragraph(s[4:], h3))
        elif s.startswith("## "):
            story.append(HRFlowable(width="100%", thickness=0.5,
                                    color=LIGHT_GOLD, spaceAfter=3))
            story.append(safe_paragraph(s[3:], h2))
        elif s.startswith("# "):
            story.append(Spacer(1, 6))
            story.append(safe_paragraph(s[2:], h1))
            story.append(HRFlowable(width="100%", thickness=1.5,
                                    color=GOLD, spaceAfter=5))
        elif s.startswith(("* ", "- ", "• ")):
            story.append(safe_paragraph(f"• {s[2:]}", bullet))
        elif s[:2] in [f"{i}." for i in range(1, 20)] or (len(s) > 2 and s[0].isdigit() and s[1] == "."):
            content = s.split(".", 1)[-1].strip()
            story.append(safe_paragraph(f"• {content}", bullet))
        else:
            story.append(safe_paragraph(s, body))
    return story


def generate_pdf(report_text: str, name: str, dob: str, pob: str,
                 output_path: str, fonts_loaded: bool) -> str:
    """Build and save the Astraveda-branded PDF."""
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    w, h = A4
    HEADER_H = 5.8 * cm
    FOOTER_H = 1.8 * cm
    MARGIN_X = 1.8 * cm

    class AstravedeDoc(BaseDocTemplate):
        def __init__(self, filename, **kwargs):
            BaseDocTemplate.__init__(self, filename, **kwargs)
            # Page 1: full-bleed cover (no frame needed, drawn by onPage)
            cover_frame = Frame(0, 0, w, h, id="cover",
                                leftPadding=0, rightPadding=0,
                                topPadding=0, bottomPadding=0)
            # Pages 2+: content below header, above footer
            body_frame = Frame(
                MARGIN_X,
                FOOTER_H + 0.3*cm,
                w - 2 * MARGIN_X,
                h - HEADER_H - FOOTER_H - 0.6*cm,
                id="body",
                leftPadding=0.3*cm,
                rightPadding=0.3*cm,
            )
            self.addPageTemplates([
                PageTemplate(
                    id="Cover",
                    frames=[cover_frame],
                    onPage=lambda c, d: _draw_cover_page(c, d, name, dob, pob),
                ),
                PageTemplate(
                    id="Body",
                    frames=[body_frame],
                    onPage=_draw_body_page,
                ),
            ])

    doc = AstravedeDoc(output_path, pagesize=A4,
                       title=f"Astraveda Report – {name}")

    story = [
        NextPageTemplate("Body"),
        PageBreak(),   # Cover = page 1; content starts page 2
    ]
    story += parse_report_text(report_text, fonts_loaded)
    doc.build(story)

    log.info(f"PDF saved → {output_path}")
    return output_path



def send_email(recipient_email: str, name: str, pdf_path: str):
    msg = MIMEMultipart()
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = recipient_email
    msg["Subject"] = f"Your Astraveda Vedic Astrology Report, {name.split()[0]}"

    body_html = f"""
    <html><body style="font-family:Georgia,serif;background:#FDF6E3;color:#2C3E50;padding:30px;">
      <div style="max-width:600px;margin:auto;border:1px solid #C9A84C;border-radius:8px;
                  padding:30px;background:#fff;">
        <h2 style="color:#0B1929;text-align:center;">ASTRAVEDA</h2>
        <p style="text-align:center;color:#C9A84C;font-style:italic;margin-top:-10px;">
          Ancient Wisdom. Future Clarity.</p>
        <hr style="border:1px solid #C9A84C;"/>
        <p>Namaste, <strong>{name}</strong>,</p>
        <p>Your personalised <strong>5-Year Vedic Astrology Report</strong> is ready and attached
        to this email as a PDF.</p>
        <p>The report covers:</p>
        <ul>
          <li>Your complete Vedic birth chart (Rashi &amp; Navamsa)</li>
          <li>Year-by-year career predictions (2026-2031)</li>
          <li>Wealth &amp; investment timing</li>
          <li>Gemstone &amp; mantra recommendations</li>
          <li>Mahadasha &amp; Antardasha analysis</li>
        </ul>
        <p style="color:#8B2500;font-style:italic;font-size:13px;">
          This report is confidential and prepared exclusively for you. Predictions are based
          on Vedic astrological calculations and should be used as spiritual guidance.
        </p>
        <hr style="border:1px solid #C9A84C;"/>
        <p style="font-size:11px;color:#999;text-align:center;">
          Generated on {datetime.now().strftime("%d %B %Y")} &nbsp;|&nbsp; Astraveda
        </p>
      </div>
    </body></html>
    """
    msg.attach(MIMEText(body_html, "html"))

    with open(pdf_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition",
                    f'attachment; filename="{os.path.basename(pdf_path)}"')
    msg.attach(part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, recipient_email, msg.as_string())

    log.info(f"Email sent → {recipient_email}")



def _whatsapp_message_text(name: str) -> str:
    first = name.split()[0]
    return (
        f"Namaste {first}!\n\n"
        f"Your personalised *Vedic Astrology 5-Year Report* from *Astraveda* is ready!\n\n"
        f"What's inside:\n"
        f"• Complete Rashi & Navamsa birth chart\n"
        f"• Year-by-year career & wealth forecast (2026-2031)\n"
        f"• Mahadasha timeline & key periods\n"
        f"• Gemstone & mantra recommendations\n\n"
        f"The full PDF has been sent to your registered email address.\n\n"
        f"_May the stars illuminate your path!_\n"
        f"— Astraveda"
    )

def send_whatsapp_callmebot(phone: str, name: str, pdf_path: str):
    msg    = _whatsapp_message_text(name)
    url    = "https://api.callmebot.com/whatsapp.php"
    params = {
        "phone":  phone.replace("+", "").replace(" ", ""),
        "text":   msg,
        "apikey": CALLMEBOT_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=15)
    if resp.ok:
        log.info(f"WhatsApp (CallMeBot) sent → {phone}")
    else:
        log.warning(f"CallMeBot error {resp.status_code}: {resp.text[:200]}")

def send_whatsapp_twilio(phone: str, name: str, pdf_path: str):
    from twilio.rest import Client
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    client.messages.create(
        body=_whatsapp_message_text(name),
        from_=TWILIO_WHATSAPP_NUM,
        to=f"whatsapp:{phone}",
    )
    log.info(f"WhatsApp (Twilio) sent → {phone}")

def send_whatsapp(phone: str, name: str, pdf_path: str):
    if not phone:
        log.warning("No phone number – skipping WhatsApp.")
        return
    if WHATSAPP_PROVIDER == "twilio":
        send_whatsapp_twilio(phone, name, pdf_path)
    else:
        send_whatsapp_callmebot(phone, name, pdf_path)



def process_row(row: dict, fonts_loaded: bool):
    name      = row.get(COL_NAME, "Friend").strip()
    email     = row.get(COL_EMAIL, "").strip()
    dob       = row.get(COL_DOB, "").strip()
    tob       = row.get(COL_TOB, "").strip()
    pob       = row.get(COL_POB, "").strip()
    phone     = row.get(COL_PHONE, "").strip()
    timestamp = row.get(COL_TIMESTAMP, str(time.time()))

    log.info(f"Processing: {name} | {email} | DOB: {dob}")

    prompt      = build_user_prompt(row)
    report_text = call_gemini(prompt)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_name     = "".join(c for c in name if c.isalnum() or c in " _-").strip()
    base_filename = f"{safe_name}_{dob.replace('/', '-')}"

    txt_path = os.path.join(OUTPUT_DIR, f"{base_filename}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    pdf_path = os.path.join(OUTPUT_DIR, f"{base_filename}.pdf")
    generate_pdf(report_text, name, dob, pob, pdf_path, fonts_loaded)

    if email:
        try:
            send_email(email, name, pdf_path)
        except Exception as e:
            log.error(f"Email failed: {e}")
    else:
        log.warning(f"No email for {name} – skipping.")

    try:
        send_whatsapp(phone, name, pdf_path)
    except Exception as e:
        log.error(f"WhatsApp failed: {e}")

    return timestamp


def run_pipeline(once: bool = True, poll_interval_minutes: int = 15):
    fonts_loaded = setup_fonts()
    while True:
        log.info("Fetching form responses ...")
        try:
            responses = fetch_form_responses()
            processed = load_processed()
            new_rows  = [r for r in responses
                         if r.get(COL_TIMESTAMP) not in processed]
            log.info(f"Total: {len(responses)}  |  New: {len(new_rows)}")
            for row in new_rows:
                try:
                    ts = process_row(row, fonts_loaded)
                    processed.add(ts)
                    save_processed(processed)
                    time.sleep(2)
                except Exception as e:
                    log.exception(f"Row error: {e}")
        except Exception as e:
            log.exception(f"Pipeline error: {e}")

        if once:
            break
        log.info(f"Sleeping {poll_interval_minutes} min ...")
        time.sleep(poll_interval_minutes * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Astraveda Automation Pipeline")
    parser.add_argument("--poll", action="store_true")
    parser.add_argument("--interval", type=int, default=15)
    args = parser.parse_args()
    run_pipeline(once=not args.poll, poll_interval_minutes=args.interval)
