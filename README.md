# AI-Powered Email Assistant Dashboard

This is a smart Flask application that acts as an automated, intelligent email assistant for your Gmail account. It uses **Google Gemini 2.0 Flash** to read incoming emails, understand the context, and draft human-like, professional responses automatically.

## Key Features

-   **🤖 AI Auto-Response**: Automatically replies to new emails using **Gemini 2.0 Flash**. Responses are crafted to sound natural and professional, not robotic.
-   **🧠 Intelligent CRM**:
    -   **Summarization**: Instantly summarizes every incoming email into a single sentence.
    -   **Contact Profiles**: Builds a dynamic profile for every person who emails you, tracking who they are and their relationship to you based on your history.
-   **🛡️ Smart Filtering**: detects and ignores "no-reply", "newsletter", and subscription emails to avoid spamming.
-   **📊 Live Dashboard**: A real-time dashboard to monitor:
    -   Sent responses, skipped emails, and errors.
    -   Live feed of incoming email summaries and AI responses.
    -   CRM view of your contacts.
-   **Background Processing**: Runs a dedicated background thread to check for emails every 10 seconds without blocking the web interface.

## Prerequisites

1.  **Python 3.10+**
2.  **Gmail Account** with 2-Step Verification enabled.
3.  **App Password** for Gmail (Required for IMAP/SMTP access).
4.  **Google Gemini API Key** (Get it from [Google AI Studio](https://aistudio.google.com/)).

## Setup & Installation

1.  **Clone/Download the project**.

2.  **Create a Virtual Environment** (Optional but recommended):
    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate
    ```

3.  **Install Dependencies**:
    ```powershell
    pip install -r requirements.txt
    ```

4.  **Configure Environment**:
    Open the `.env` file and fill in your credentials:
    ```env
    EMAIL_USER=your_email@gmail.com
    EMAIL_PASS=your_gmail_app_password
    GEMINI_API_KEY=your_gemini_api_key
    ```
    *Note: `EMAIL_PASS` must be the 16-character App Password, not your login password.*

5.  **Run the Application**:
    Double-click `run.ps1` or run via terminal:
    ```powershell
    .\run.ps1
    ```

6.  **Access the Dashboard**:
    Open your browser and navigate to:
    [http://127.0.0.1:5000/dashboard](http://127.0.0.1:5000/dashboard)

## Project Structure

-   `app.py`: Logic for Flask web server, background email polling, AI generation, and database management.
-   `email_bot.db`: SQLite database storing logs, contact profiles, and conversation history.
-   `templates/dashboard.html`: The frontend interface.
-   `requirements.txt`: Python dependencies (`Flask`, `google-genai`, `python-dotenv`).

## Customization

-   **Prompt Tuning**: You can modify the `generate_ai_reply` function in `app.py` to change the persona or tone of the AI (e.g., make it more casual or more formal).
-   **Model**: Currently uses `gemini-2.0-flash`. You can switch to `gemini-1.5-pro` or others in `app.py` if your API key supports it.

## Troubleshooting

-   **"Authentication Failed"**: Check your `.env` file. Ensure you are using an **App Password** and not your regular Gmail password.
-   **"Gemini API Error"**: Ensure your API key is valid and has access to the `gemini-2.0-flash` model.
-   **No Auto-Replies**: The bot ignores "no-reply" addresses and bulk mail headers. Send an email from a real personal account to test.
