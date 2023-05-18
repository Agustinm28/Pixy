import requests
from colorama import Fore

with open('./data/BOT_CREDENTIALS.txt', 'r') as f:
    token = str(f.read())

def send_message(chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message}
        response = requests.post(url, data=data)
    except requests.exceptions.RequestException as e:
        print(f"[{Fore.RED}ERROR{Fore.RESET}]Error sending the message: {e}")

def send_file(file_path, filetype, chat_id):
    try:
        url = f"https://api.telegram.org/bot{token}/sendDocument"
        files = {"document": open(file_path, "rb")}
        data = {"chat_id": chat_id, "disable_content_type_detection": True}
        if filetype.startswith('video/'):
            send_message(chat_id, "Downloading upscaled video...")
        elif filetype.startswith('image/'):
            send_message(chat_id, "Downloading upscaled image...")
        response = requests.post(url, files=files, data=data)
        print(f'[{Fore.YELLOW}RESPONSE{Fore.RESET}] {response}')
        print(f'[{Fore.GREEN}SENDING{Fore.RESET}] File sended')
    except requests.exceptions.RequestException as e:
        print(f"[{Fore.RED}ERROR{Fore.RESET}] Error sending the file: {e}")
        send_message(chat_id, "There was an error sending the file")