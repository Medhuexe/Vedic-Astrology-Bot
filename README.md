# 🌙 Vedic Astrology Automation Pipeline

> **Google Forms → Claude AI → Styled PDF → Email + WhatsApp**

---

## What This Does

```
User fills Google Form
        ↓
Script fetches new responses from linked Google Sheet
        ↓
Builds personalised Vedic astrology prompt
        ↓
Sends to Claude API → generates 5-year forecast
        ↓
Creates a beautifully themed PDF report
        ↓
Emails PDF to respondent
        ↓
Sends WhatsApp message (+ PDF link via Twilio)
```

---

## Prerequisites

- Python 3.10+
- A Google Cloud project with Sheets API enabled
- An Anthropic API key
- A Gmail account (with App Password)
- A WhatsApp messaging account (CallMeBot or Twilio)

---

## Step-by-Step Setup

### 1. Install Dependencies

```bash
pip install \
  google-auth \
  google-auth-oauthlib \
  google-api-python-client \
  anthropic \
  reportlab \
  requests \
  python-dotenv \
  twilio          # only if using Twilio WhatsApp
```

---

### 2. Configure Your Google Form

Your form **must** collect these fields (exact column names matter – edit `astrology_automation.py` if yours differ):

| Field | Column Header |
|---|---|
| Email (auto-collected) | `Email Address` |
| Full name | `Full Name` |
| Date of birth | `Date of Birth (DD/MM/YYYY)` |
| Time of birth | `Time of Birth (HH:MM AM/PM)` |
| Place of birth | `Place of Birth (City, State, Country)` |
| WhatsApp number | `WhatsApp Number (with country code, e.g. +91XXXXXXXXXX)` |
| Gender (optional) | `Gender` |

**Important:** In your Google Form settings → **Responses** → turn on **"Collect email addresses"**.

---

### 3. Link Form to Google Sheet

In Google Forms → **Responses** tab → click the green Sheets icon → **Create a new spreadsheet**. Note the Spreadsheet ID from the URL.

---

### 4. Enable Google Sheets API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or select an existing one)
3. Enable **Google Sheets API**
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
5. Application type: **Desktop app**
6. Download the JSON and save it as `credentials.json` in the same folder as `astrology_automation.py`

---

### 5. Configure `.env`

```bash
cp .env.example .env
# Edit .env with your actual values
```

Key values to fill in:

```env
ANTHROPIC_API_KEY=sk-ant-...
SPREADSHEET_ID=1abc...xyz       # From Google Sheet URL
EMAIL_SENDER=you@gmail.com
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx   # Gmail App Password (16 chars)
WHATSAPP_PROVIDER=callmebot
CALLMEBOT_API_KEY=123456         # From CallMeBot setup
```

---

### 6. WhatsApp Setup

#### Option A – CallMeBot (Free, text messages only)

1. Save `+34 644 59 97 23` to your phone contacts as "CallMeBot"
2. Send this WhatsApp message to that number: `I allow callmebot to send me messages`
3. You'll receive an API key – put it in `.env` as `CALLMEBOT_API_KEY`
4. **Note:** Each recipient's phone number needs to do this setup once.

#### Option B – Twilio (Paid, supports PDF/media)

1. Sign up at [twilio.com](https://twilio.com)
2. Activate the WhatsApp Sandbox (or apply for a dedicated number)
3. Fill in `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUM` in `.env`
4. To send PDFs, upload them to a public URL (S3, GCS, etc.) and pass the URL as `media_url`

---

### 7. Run the Script

**First run (OAuth browser authentication):**
```bash
python astrology_automation.py
```
A browser window will open asking you to authorise access to Google Sheets. After that, a `token.json` is saved and you won't need to authenticate again.

**Run once (process new responses and exit):**
```bash
python astrology_automation.py
```

**Continuous polling mode (check every 15 minutes):**
```bash
python astrology_automation.py --poll --interval 15
```

**Automate with cron (run every 30 minutes):**
```bash
crontab -e
# Add this line:
*/30 * * * * /usr/bin/python3 /path/to/astrology_automation.py >> /path/to/pipeline.log 2>&1
```

---

## Output Files

| File | Description |
|---|---|
| `reports/<Name>_<DOB>.pdf` | Beautifully themed PDF report |
| `reports/<Name>_<DOB>.txt` | Raw Claude response (debug) |
| `processed_rows.json` | Tracks processed timestamps (prevents duplicates) |
| `token.json` | Google OAuth token (auto-generated) |

---

## PDF Theme

The generated PDF features a **celestial / deep navy & gold** design:

- **Cover page** with starfield background, name, DOB, and location
- **Body pages** with cream background, gold ornamental borders
- Structured sections with colour-coded headings
- Auto page numbers and footer branding

---

## Customising Column Names

If your Google Form uses different question text, edit these constants at the top of `astrology_automation.py`:

```python
COL_TIMESTAMP   = "Timestamp"
COL_EMAIL       = "Email Address"
COL_NAME        = "Full Name"
COL_DOB         = "Date of Birth (DD/MM/YYYY)"
COL_TOB         = "Time of Birth (HH:MM AM/PM)"
COL_POB         = "Place of Birth (City, State, Country)"
COL_PHONE       = "WhatsApp Number (with country code, e.g. +91XXXXXXXXXX)"
COL_GENDER      = "Gender"
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `credentials.json not found` | Download OAuth credentials from Google Cloud Console |
| `403 Access denied` | Make sure Sheets API is enabled in Google Cloud |
| `Email authentication failed` | Use a Gmail App Password, not your account password |
| `CallMeBot not working` | Each number needs to opt-in via WhatsApp first |
| `PDF not rendering correctly` | Make sure `reportlab` is installed: `pip install reportlab` |
| `Duplicate reports` | Delete `processed_rows.json` to reprocess all rows |

---

## Security Notes

- **Never commit `.env` to git** – add it to `.gitignore`
- Store `credentials.json` and `token.json` securely
- Use Gmail App Passwords, not your account password
- Keep your Anthropic API key private

---

## Architecture Overview

```
astrology_automation.py
│
├── fetch_form_responses()     → Google Sheets API
├── build_user_prompt()        → Fills in birth details
├── call_claude()              → Anthropic API (claude-opus-4-5)
├── generate_pdf()             → ReportLab (celestial theme)
├── send_email()               → Gmail SMTP
└── send_whatsapp()            → CallMeBot or Twilio
```
