import os
import json
import requests
import smtplib
import subprocess
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

TOKEN = os.environ.get("YANDEX_TOKEN")
EMAIL_FROM = os.environ.get("EMAIL_FROM")
EMAIL_TO = os.environ.get("EMAIL_TO", "").split(",")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.yandex.ru")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 465))
FOLDER_PATH = os.environ.get("FOLDER_PATH")

def list_all_items(path):
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    headers = {"Authorization": f"OAuth {TOKEN}"}
    items = []

    def recurse(current_path):
        params = {"path": current_path}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        embedded = data.get("_embedded", {})
        for item in embedded.get("items", []):
            entry = {
                "name": item["name"],
                "modified": item["modified"],
                "path": item["path"],
                "etag": item.get("etag", ""),
                "type": item["type"]
            }
            items.append(entry)
            if item["type"] == "dir":
                recurse(item["path"])
    recurse(path)
    return items

def send_email(subject, body):
    message = MIMEMultipart()
    message["From"] = EMAIL_FROM
    message["To"] = ", ".join(EMAIL_TO)
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.send_message(message)

def load_state(filename):
    if os.path.exists(filename):
        with open(filename) as f:
            return json.load(f)
    return []

def save_state(filename, state):
    with open(filename, "w") as f:
        json.dump(state, f, indent=2)

def build_index(data):
    return {item["path"]: item for item in data}

def describe_change(change_type, item):
    label = "Файл" if item["type"] != "dir" else "Папка"
    gender = "м" if label == "Файл" else "ж"
    endings = {
        "added":   {"м": "добавлен",   "ж": "добавлена"},
        "removed": {"м": "удалён",     "ж": "удалена"},
        "changed": {"м": "изменён",    "ж": "изменена"}
    }
    emoji = {
        "added": "➕",
        "removed": "➖",
        "changed": "✏️"
    }
    return f"{emoji[change_type]} {label} {endings[change_type][gender]}: {item['path']}"

def detect_differences(prev_list, curr_list):
    prev = build_index(prev_list)
    curr = build_index(curr_list)

    added = [curr[p] for p in curr if p not in prev]
    removed = [prev[p] for p in prev if p not in curr]
    changed = [
        curr[p] for p in curr if p in prev and (
            curr[p]["etag"] != prev[p]["etag"] or curr[p]["modified"] != prev[p]["modified"]
        )
    ]

    return added, removed, changed

def git_commit_and_push(files):
    subprocess.run(["git", "config", "--global", "user.email", "bot@example.com"])
    subprocess.run(["git", "config", "--global", "user.name", "GitHub Bot"])
    subprocess.run(["git", "add"] + files)
    subprocess.run(["git", "commit", "-m", "Update notification state"], check=False)
    subprocess.run(["git", "push"], check=False)

try:
    current = list_all_items(FOLDER_PATH)
    previous = load_state("previous_state.json")

    added, removed, changed = detect_differences(previous, current)

    messages = []
    for item in added:
        messages.append(describe_change("added", item))
    for item in removed:
        messages.append(describe_change("removed", item))
    for item in changed:
        messages.append(describe_change("changed", item))

    if messages:
        body = "\n".join(messages)
        send_email("📝 Изменения в Яндекс.Диске", body)

    save_state("previous_state.json", current)
    git_commit_and_push(["previous_state.json"])

except Exception as e:
    print("Ошибка:", e)
