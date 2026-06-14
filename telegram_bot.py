import requests
import json

class TelegramNotifier:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id

    def send_message(self, text, reply_markup=None):
        """텔레그램 메시지 전송"""
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
        return requests.post(url, json=payload)

    def send_photo(self, photo_path):
        """텔레그램 사진 전송"""
        url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
        with open(photo_path, 'rb') as photo:
            return requests.post(url, data={"chat_id": self.chat_id}, files={"photo": photo})