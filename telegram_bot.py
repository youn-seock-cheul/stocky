import requests
import json
import re

class TelegramNotifier:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id

    def send_message(self, text, reply_markup=None):
        """텔레그램 메시지 전송"""
        max_length = 4000
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        
        # 정교한 HTML 안전 분할 로직 호출
        chunks = self._split_html_safe(text, max_length)
        last_response = None

        for i, chunk in enumerate(chunks):
            is_last = (i == len(chunks) - 1)
            payload = {
                "chat_id": self.chat_id,
                "text": chunk,
                "parse_mode": "HTML"
            }
            
            # 마지막 청크에만 버튼(reply_markup) 추가
            if is_last and reply_markup:
                payload["reply_markup"] = reply_markup
                
            res = requests.post(url, json=payload)
            if is_last:
                last_response = res
        
        return last_response

    def _split_html_safe(self, text, limit):
        """HTML 태그 파손을 방지하며 메시지를 분할"""
        if len(text) <= limit:
            return [text]

        chunks = []
        lines = text.split('\n')
        current_chunk = ""
        # 현재 추적 중인 태그 (b, pre 등)
        active_tags = []

        for line in lines:
            # 새 라인을 추가했을 때 제한을 넘는지 확인
            if len(current_chunk) + len(line) + 1 > limit - 20: # 여유 공간 확보
                # 현재 청크에서 닫히지 않은 태그들을 닫아줌
                closing_tags = "".join([f"</{tag}>" for tag in reversed(active_tags)])
                chunks.append(current_chunk + closing_tags)
                
                # 다음 청크 시작 시 이전의 태그들을 다시 열어줌
                current_chunk = "".join([f"<{tag}>" for tag in active_tags])

            current_chunk += line + '\n'
            
            # 라인 내의 태그 상태 업데이트 (간이 파싱)
            for tag in ['b', 'pre']:
                open_count = len(re.findall(f'<{tag}>', line))
                close_count = len(re.findall(f'</{tag}>', line))
                balance = open_count - close_count
                
                if balance > 0:
                    for _ in range(balance): active_tags.append(tag)
                elif balance < 0:
                    for _ in range(abs(balance)):
                        if tag in active_tags: active_tags.remove(tag)

        if current_chunk.strip():
            closing_tags = "".join([f"</{tag}>" for tag in reversed(active_tags)])
            chunks.append(current_chunk + closing_tags)
            
        return chunks

    def send_photo(self, photo_path):
        """텔레그램 사진 전송"""
        url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
        with open(photo_path, 'rb') as photo:
            return requests.post(url, data={"chat_id": self.chat_id}, files={"photo": photo})