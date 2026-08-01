import os
import requests
import logging

logger = logging.getLogger(__name__)

class AlertSystem:
    def __init__(self):
        self.telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    def send_alert(self, title: str, message: str):
        full_msg = f"*{title}*\n\n{message}"
        
        # 1. Console Log (Evitando errores Unicode en Windows)
        safe_title = title.encode('ascii', 'ignore').decode('ascii')
        safe_message = message.encode('ascii', 'ignore').decode('ascii')
        print(f"\n{'='*40}")
        print(f"ALERTA: {safe_title}")
        print(f"{'-'*40}")
        print(safe_message)
        print(f"{'='*40}\n")
        
        # 2. Telegram (Si está configurado)
        if self.telegram_token and self.telegram_chat_id:
            try:
                url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                payload = {
                    "chat_id": self.telegram_chat_id,
                    "text": full_msg,
                    "parse_mode": "Markdown"
                }
                requests.post(url, json=payload, timeout=5)
            except Exception as e:
                logger.error(f"Error enviando alerta Telegram: {e}")
