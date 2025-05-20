import requests
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Путь к config.json
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_PATH) as f:
    cfg = json.load(f)

TOKEN = cfg["yandex_token"]
EMAIL_FROM = cfg["email_from"]
EMAIL_TO = cfg["email_to"]
EMAIL_PASS = cfg["email_password"]
SMTP_SERVER = cfg["smtp_server"]
SMTP_PORT = cfg["smtp_port"]
FOLDER_PATH = cfg["folder_path"]

def get_folder_files():
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    headers = {"Authorization": f"OAuth {TOKEN}"}
    params = {"path": FOLDER_PATH}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()
    return [{
        "name": item["name"],
        "modified": item["modified"],
        "path": item["path"],
        "etag": item.get("etag", "")
    } for item in data.get("_embedded", {}).get("items", []) if item["type"] == "file"]

def send_email(subject, body):
    message = MIMEMultipart()
    message["From"] = EMAIL_FROM
    message["To"] = ", ".join(EMAIL_TO)
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.send_message(message)

def load_previous_state():
    state_path = os.path.join(BASE_DIR, "previous_state.json")
    if os.path.exists(state_path):
        with open(state_path) as f:
            return json.load(f)
    return []

def save_current_state(state):
    state_path = os.path.join(BASE_DIR, "previous_state.json")
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)

def detect_changes(prev, curr):
    changes = []
    prev_dict = {f["path"]: f for f in prev}
    for file in curr:
        old = prev_dict.get(file["path"])
        if not old or old["etag"] != file["etag"]:
            changes.append(file)
    return changes

# Один запуск
try:
    current_state = get_folder_files()
    previous_state = load_previous_state()
    changed_files = detect_changes(previous_state, current_state)
    if changed_files:
        for f in changed_files:
            body = f"📄 Изменён файл: {f['name']}\nПуть: {f['path']}\nДата: {f['modified']}"
            send_email("⚠️ Обновление файла в Яндекс.Диске", body)
    save_current_state(current_state)
except Exception as e:
    print("Ошибка:", e)
