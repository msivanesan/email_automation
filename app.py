from flask import Flask, render_template, request, redirect, url_for, flash
import smtplib
import imaplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parseaddr
import os
import threading
import time
import sqlite3
from datetime import datetime
import sqlite3
from datetime import datetime
from google import genai
from dotenv import load_dotenv
import rag_engine

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Change this in production!

DATABASE = 'email_bot.db'

# Configuration from .env
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
IMAP_SERVER = 'imap.gmail.com'

# Branding Config
ORG_NAME = os.getenv('ORG_NAME', 'the business')
ORG_TYPE = os.getenv('ORG_TYPE', 'professional service')
CONTACT_DETAILS = os.getenv('CONTACT_DETAILS', 'our team')

# Configure Gemini
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
    # model = genai.GenerativeModel('gemini-1.5-flash') # Not needed in new SDK style, we pass model name in call
else:
    print("Warning: GEMINI_API_KEY not found. AI replies will be disabled.")
    client = None

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Existing logs table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS auto_reply_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT NOT NULL,
            subject TEXT,
            status TEXT NOT NULL,
            details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # New table: Contact Profiles
    conn.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            email TEXT PRIMARY KEY,
            name TEXT,
            summary TEXT,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # New table: Interaction History (Summaries)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS email_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            subject TEXT,
            incoming_summary TEXT,
            response_content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def log_event(recipient, subject, status, details=None):
    try:
        conn = get_db_connection()
        conn.execute('INSERT INTO auto_reply_logs (recipient, subject, status, details) VALUES (?, ?, ?, ?)',
                     (recipient, subject, status, details))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Logging error: {e}")

# Configuration from .env
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
IMAP_SERVER = 'imap.gmail.com'

def send_email(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        text = msg.as_string()
        server.sendmail(EMAIL_USER, to_email, text)
        server.quit()
        return True, "Email sent successfully!"
    except Exception as e:
        return False, str(e)




@app.route('/')
def index():
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    logs = conn.execute('SELECT * FROM auto_reply_logs ORDER BY timestamp DESC LIMIT 50').fetchall()
    
    # Fetch Contacts
    contacts = conn.execute('SELECT * FROM contacts ORDER BY last_updated DESC LIMIT 20').fetchall()
    
    # Fetch Detailed Interactions
    interactions = conn.execute('SELECT * FROM email_interactions ORDER BY timestamp DESC LIMIT 20').fetchall()
    
    # Calculate stats
    stats = {}
    stats['sent'] = conn.execute("SELECT COUNT(*) FROM auto_reply_logs WHERE status = 'sent'").fetchone()[0]
    stats['skipped'] = conn.execute("SELECT COUNT(*) FROM auto_reply_logs WHERE status = 'skipped'").fetchone()[0]
    stats['errors'] = conn.execute("SELECT COUNT(*) FROM auto_reply_logs WHERE status = 'error'").fetchone()[0]
    
    conn.close()
    return render_template('dashboard.html', logs=logs, stats=stats, contacts=contacts, interactions=interactions)

def generate_ai_reply(sender, subject, body):
    """Generates a reply using Gemini Flash."""
    if not client:
        return "Thank you for your email. This is an automated response."

    try:
        # --- RAG: Fetch Context ---
        context = rag_engine.query_knowledge_base(body)
        
        prompt = f"""
        You are the AI assistant for {ORG_NAME}, a {ORG_TYPE}.
        Please draft a natural, human-like, and professional reply to the following email.
        
        KNOWLEDGE BASE CONTEXT (Use this to answer accurately):
        {context if context else "No specific documents found for this query. Answer generally or ask for clarification based on business common sense."}
        
        Sender: {sender}
        Subject: {subject}
        Content:
        {body}
        
        Guidelines:
        1. Be concise and professional.
        2. If the context contains the answer, use it. 
        3. If you don't know the answer, politely mention they can contact {CONTACT_DETAILS}.
        4. Do NOT sound like a bot.
        5. Sign off with "Best regards, \n{ORG_NAME} Team".
        """
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return "Thank you for your email. We have received it and will get back to you shortly."

def summarize_content(text):
    """Summarizes text using AI."""
    if not client: return "No AI model available."
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=f"Please summarize the following email content in one sentence:\n\n{text}"
        )
        return response.text.strip()
    except Exception as e:
        print(f"Summary Error: {e}")
        return "Summary generation failed."

def update_contact_profile(email_addr, name, new_content):
    """Updates the profile of a contact based on new interaction."""
    if not client: return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch existing profile
    cursor.execute("SELECT summary, name FROM contacts WHERE email = ?", (email_addr,))
    row = cursor.fetchone()
    
    current_summary = row['summary'] if row else "New contact."
    current_name = row['name'] if row and row['name'] else name
    
    prompt = f"""
    You are managing a CRM database.
    
    Current Profile Summary for {email_addr} ({current_name}):
    "{current_summary}"
    
    New Email Interaction:
    "{new_content}"
    
    Please update the profile summary to include relevant new information from this interaction. 
    Keep it concise (under 50 words). Focus on who they are and their relationship/business with us.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt
        )
        new_summary = response.text.strip()
        
        cursor.execute("""
            INSERT INTO contacts (email, name, summary, last_updated) 
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(email) DO UPDATE SET 
                summary = excluded.summary,
                last_updated = CURRENT_TIMESTAMP,
                name = COALESCE(contacts.name, excluded.name)
        """, (email_addr, current_name, new_summary))
        conn.commit()
    except Exception as e:
        print(f"Profile update error: {e}")
    finally:
        conn.close()

def auto_reply_task():
    """Background task to check for unseen emails and auto-reply."""
    print("Starting auto-reply background task...")
    while True:
        try:
            # Connect to IMAP
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)
            mail.login(EMAIL_USER, EMAIL_PASS)
            mail.select("inbox")
            
            # Search for UNSEEN emails
            status, messages = mail.search(None, 'UNSEEN')
            email_ids = messages[0].split()
            
            if email_ids:
                print(f"Found {len(email_ids)} new emails. Processing...")

            for e_id in email_ids:
                # Fetch the email (Fetching RFC822 implies marking as \\Seen, which is what we want here)
                res, msg_data = mail.fetch(e_id, '(RFC822)')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        # Get Subject
                        subject_header = msg["Subject"]
                        if subject_header:
                            subject, encoding = decode_header(subject_header)[0]
                            if isinstance(subject, bytes):
                                subject = subject.decode(encoding if encoding else "utf-8")
                        else:
                            subject = "(No Subject)"
                        
                        # Get Sender
                        from_header = msg.get("From")
                        real_name, return_path = parseaddr(from_header)
                        
                        # Safety check
                        if not return_path or return_path == EMAIL_USER:
                            continue
                        
                        # Filter out no-reply and subscription emails
                        excluded_keywords = ['no-reply', 'noreply', 'donotreply', 'mailer-daemon', 'postmaster', 'subscription', 'newsletter', 'marketing', 'alert', 'notification']
                        if any(keyword in return_path.lower() for keyword in excluded_keywords):
                            print(f"Skipping auto-reply to {return_path} (Excluded keyword)")
                            log_event(return_path, subject, 'skipped', 'Excluded keyword/address')
                            continue

                        # Check generic auto-generated headers
                        if (msg.get('List-Unsubscribe') or 
                            msg.get('Auto-Submitted') == 'auto-generated' or 
                            msg.get('Precedence') in ['bulk', 'list', 'junk'] or
                            msg.get('X-Auto-Response-Suppress')):
                             print(f"Skipping auto-reply to {return_path} (Automated/Bulk mail detected)")
                             log_event(return_path, subject, 'skipped', 'Automated/Bulk headers detected')
                             continue
                            
                        # Extract Body for AI Context
                        email_body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))
                                if content_type == "text/plain" and "attachment" not in content_disposition:
                                    try:
                                        email_body = part.get_payload(decode=True).decode()
                                    except:
                                        pass
                                    break 
                        else:
                            try:
                                email_body = msg.get_payload(decode=True).decode()
                            except:
                                pass
                        
                        # Fallback if body decode fails
                        if not email_body:
                            email_body = "(No content)"

                        print(f"Auto-replying to: {return_path}")
                        
                        # Generate AI Content
                        reply_content = generate_ai_reply(return_path, subject, email_body)
                        
                        # Send Reply
                        start_time = time.time()
                        send_success, send_msg = send_email(
                            return_path, 
                            f"Re: {subject}", 
                            reply_content
                        )
                        
                        if send_success:
                            print(f"Reply sent to {return_path}")
                            log_event(return_path, subject, 'sent', 'AI Auto-reply sent successfully')
                            
                            # --- New: Database Logic ---
                            
                            # 1. Summarize Incoming
                            incoming_summary = summarize_content(email_body)
                            
                            # 2. Update Contact Profile
                            update_contact_profile(return_path, real_name, email_body)
                            
                            # 3. Log Interaction
                            try:
                                db = get_db_connection()
                                db.execute("INSERT INTO email_interactions (email, subject, incoming_summary, response_content) VALUES (?, ?, ?, ?)",
                                           (return_path, subject, incoming_summary, reply_content))
                                db.commit()
                                db.close()
                            except Exception as e:
                                print(f"DB Error: {e}")
                            
                            # ---------------------------
                        else:
                            print(f"Failed to send reply to {return_path}: {send_msg}")
                            log_event(return_path, subject, 'error', f"Failed: {send_msg}")


            mail.close()
            mail.logout()
            
        except Exception as e:
            # print(f"Auto-reply error: {e}") # Reduce noise
            pass
        
        # Wait before next check
        time.sleep(10)

if __name__ == '__main__':
    # Initialize DB (run once on startup logic)
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
         # Only run init_db in the main process manager, 
         # but actually create tables safely
         pass

    # Ensure tables and RAG index exist
    init_db()
    try:
        rag_engine.process_pdfs()
    except Exception as e:
        print(f"RAG Indexing Error: {e}")

    # Start the background thread ONLY if we are in the main reloader process
    # WERKZEUG_RUN_MAIN is set by Flask when it spawns the child process
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        thread = threading.Thread(target=auto_reply_task)
        thread.daemon = True
        thread.start()
        
    app.run(debug=True)
