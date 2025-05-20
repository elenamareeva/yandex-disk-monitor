import os
import json
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Загрузка конфигурации из переменных окружения
TOKEN = os.environ.get("YANDEX_TOKEN")
EMAIL_FROM = os.environ.get("EMAIL_FROM")
EMAIL_TO = os.environ.get("EMAIL_TO", "").split(",")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.yandex.ru")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 465))
FOLDER_PATH = os.environ.get("FOLDER_PATH")

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
    if os.path.exists("previous_state.json"):
        with open("previous_state.json") as f:
            return json.load(f)
    return []

def save_current_state(state):
    with open("previous_state.json", "w") as f:
        json.dump(state, f, indent=2)

def detect_changes(prev, curr):
    changes = []
    prev_dict = {f["path"]: f for f in prev}
    for file in curr:
        old = prev_dict.get(file["path"])
        if not old or old["etag"] != file["etag"]:
            changes.append(file)
    return changes

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
