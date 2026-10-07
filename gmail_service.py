from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.api_python_client import build
from config import get_settings
import pickle
import os
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


class GmailService:
    def __init__(self):
        self.settings = get_settings()
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Gmail API using OAuth2"""
        creds = None
        token_file = self.settings.gmail_token_file

        # Check if token exists
        if os.path.exists(token_file):
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)

        # If no valid credentials, request new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Use credentials.json from interview-soham
                credentials_file = "../interview-soham/credentials.json"
                if not os.path.exists(credentials_file):
                    credentials_file = "../interview-soham/credentials-desktop.json"

                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save token for next run
            os.makedirs(os.path.dirname(token_file), exist_ok=True)
            with open(token_file, 'wb') as token:
                pickle.dump(creds, token)

        self.service = build('gmail', 'v1', credentials=creds)
        logger.info("Gmail service authenticated successfully")

    def get_unread_emails(self, max_results: int = 10) -> List[Dict]:
        """Fetch unread emails from inbox"""
        try:
            results = self.service.users().messages().list(
                userId='me',
                q='is:unread',
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])
            emails = []

            for msg in messages:
                email_data = self.get_message(msg['id'])
                if email_data:
                    emails.append(email_data)

            return emails
        except Exception as e:
            logger.error(f"Error fetching unread emails: {e}")
            return []

    def get_message(self, message_id: str) -> Optional[Dict]:
        """Get a specific message by ID"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            headers = message['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            from_email = next((h['value'] for h in headers if h['name'] == 'From'), '')

            body = self._get_message_body(message['payload'])

            return {
                'id': message_id,
                'threadId': message['threadId'],
                'subject': subject,
                'from': from_email,
                'body': body,
                'timestamp': int(message['internalDate'])
            }
        except Exception as e:
            logger.error(f"Error getting message {message_id}: {e}")
            return None

    def _get_message_body(self, payload) -> str:
        """Extract body from message payload"""
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data', '')
                    if data:
                        import base64
                        return base64.urlsafe_b64decode(data).decode('utf-8')
        else:
            data = payload['body'].get('data', '')
            if data:
                import base64
                return base64.urlsafe_b64decode(data).decode('utf-8')
        return ""

    def add_label(self, message_id: str, label_name: str) -> bool:
        """Add a label to a message"""
        try:
            # Get or create label
            label_id = self._get_or_create_label(label_name)

            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': [label_id]}
            ).execute()

            logger.info(f"Added label {label_name} to message {message_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding label: {e}")
            return False

    def _get_or_create_label(self, label_name: str) -> str:
        """Get label ID or create it if it doesn't exist"""
        try:
            labels = self.service.users().labels().list(userId='me').execute()

            for label in labels.get('labels', []):
                if label['name'] == label_name:
                    return label['id']

            # Create new label
            label_object = {
                'name': label_name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }

            created_label = self.service.users().labels().create(
                userId='me',
                body=label_object
            ).execute()

            return created_label['id']
        except Exception as e:
            logger.error(f"Error getting/creating label: {e}")
            return None

    def send_reply(self, message_id: str, thread_id: str, reply_body: str) -> bool:
        """Send a reply to a message in the same thread"""
        try:
            original = self.get_message(message_id)
            if not original:
                return False

            # Create reply message
            message = self._create_message(
                to=original['from'],
                subject=f"Re: {original['subject']}",
                message_text=reply_body,
                thread_id=thread_id
            )

            self.service.users().messages().send(
                userId='me',
                body=message
            ).execute()

            logger.info(f"Sent reply to message {message_id}")
            return True
        except Exception as e:
            logger.error(f"Error sending reply: {e}")
            return False

    def _create_message(self, to: str, subject: str, message_text: str, thread_id: str = None) -> Dict:
        """Create a MIME message"""
        import base64
        from email.mime.text import MIMEText

        message = MIMEText(message_text)
        message['to'] = to
        message['subject'] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        result = {'raw': raw}
        if thread_id:
            result['threadId'] = thread_id

        return result

    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read"""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Error marking as read: {e}")
            return False
