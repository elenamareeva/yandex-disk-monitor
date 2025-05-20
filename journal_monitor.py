import os
import json
import requests
from datetime import datetime

TOKEN = os.environ.get("YANDEX_TOKEN")
EMAIL_FROM = os.environ.get("EMAIL_FROM")
EMAIL_TO = os.environ.get("EMAIL_TO", "").split(",")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.yandex.ru")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 465))
FOLDER_PATH = os.environ.get("FOLDER_PATH")
USER_MAP_PATH = "user_map.json"

JOURNAL_FILE = "last_journal_id.json"

def send_email(subject, body):
    from smtplib import SMTP_SSL
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    message = MIMEMultipart()
    message["From"] = EMAIL_FROM
    message["To"] = ", ".join(EMAIL_TO)
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))
    with SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.send_message(message)

def get_last_journal_id():
    if os.path.exists(JOURNAL_FILE):
        with open(JOURNAL_FILE) as f:
            return json.load(f).get("last_journal_id", 0)
    return 0

def save_last_journal_id(journal_id):
    with open(JOURNAL_FILE, "w") as f:
        json.dump({"last_journal_id": journal_id}, f, indent=2)

def load_user_map():
    if os.path.exists(USER_MAP_PATH):
        with open(USER_MAP_PATH) as f:
            return json.load(f)
    return {}

def fetch_journal_events(from_id):
    url = "https://cloud-api.yandex.net/v1/disk/journal"
    headers = {"Authorization": f"OAuth {TOKEN}"}
    params = {"limit": 100, "since": from_id}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def is_under_folder(path):
    return path.startswith(FOLDER_PATH.replace("disk:", "/disk"))

def format_event(e, user_map):
    action = e.get("event")
    path = e.get("path", "")
    resource_type = e.get("resource_type")
    uid = e.get("user_id", "")
    who = user_map.get(str(uid), f"user_id: {uid}")
    ts = e.get("timestamp", "")

    ts_fmt = ts.replace("T", " ").replace("Z", "") if ts else ""

    if action == "create":
        symbol = "➕"
    elif action == "delete":
        symbol = "➖"
    else:
        symbol = "❓"

    type_label = "папка" if resource_type == "dir" else "файл"
    return f"{symbol} {type_label.capitalize()}: {path}\nДата: {ts_fmt}\nСделал: {who}"

def main():
    try:
        user_map = load_user_map()
        last_id = get_last_journal_id()
        journal = fetch_journal_events(last_id)
        events = journal.get("items", [])
        new_last_id = journal.get("last_journal_record_id", last_id)

        filtered = [e for e in events if is_under_folder(e.get("path", ""))]

        if filtered:
            lines = [format_event(e, user_map) for e in filtered]
            body = "\n\n".join(lines)
            send_email("🗂 Изменения в папке на Яндекс.Диске", body)

        save_last_journal_id(new_last_id)
    except Exception as e:
        print("Ошибка:", e)

if __name__ == "__main__":
    main()
