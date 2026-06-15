from google import genai
import PIL.Image
import time

class MarketAnalyzer:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)

    def generate_analysis(self, market_data, report_type="opening", trade_info=None):
        indices_summary = "".join([f"- {n}: {i['price']} ({i['change_pct']}%)\n" for n, i in market_data.get('indices', {}).items()])
        portfolio_data = market_data.get('portfolio', {})
        total_value = sum(info.get('current_value', 0) for info in portfolio_data.values())
        
        portfolio_summary = ""
        for name, info in portfolio_data.items():
            weight = (info.get('current_value', 0) / total_value * 100) if total_value > 0 else 0
            hist = ", ".join([f"{d}: {p}" for d, p in info.get('history', {}).items()])
            portfolio_summary += f"- {name}: 현재가 {info['price']} (평단 {info['avg_price']}), 수익률 {info['roi']}%, 비중 {round(weight, 1)}%\n"
            portfolio_summary += f"  [기술지표]: RSI({info.get('rsi')}), MACD({info.get('macd')}), Signal({info.get('macd_signal')})\n"
            portfolio_summary += f"  [1개월 히스토리]: {hist}\n"

        # (전략: trade_info, closing, opening에 따른 프롬프트 구성 - 이전과 동일하게 유지하되 요청된 이모지 로직 추가)
        # ... (이하 프롬프트 로직은 이전 답변에서 완성된 고도화 버전을 적용합니다) ...
        # [생략된 부분: 이전 답변의 상세 프롬프트 내용들]
        
        prompt = f"위 데이터를 바탕으로 분석하세요. 상세 리포트 섹션 제목에는 시장 상황에 맞는 이모지를 동적으로 사용하세요." 
        # (실제 구현 시에는 이전 단계에서 완성한 긴 프롬프트를 이곳에 통합합니다)

        models_to_try = ['gemini-2.0-flash', 'gemini-2.5-flash', 'gemini-3.0-flash', 'gemini-3.5-flash']
        for model_name in models_to_try:
            try:
                return self.client.models.generate_content(model=model_name, contents=prompt).text
            except Exception as e:
                if "429" in str(e): continue
                print(f"❌ {model_name} 오류: {e}")
        return "모든 모델의 할당량이 초과되었습니다."

    def extract_portfolio_from_image(self, image_path):
        try:
            img = PIL.Image.open(image_path)
            prompt = """
            당신은 한국 증권사(MTS) 잔고 스크린샷 분석 전문가입니다. 이미지에서 주식 및 ETF 잔고 정보를 추출하여 JSON 배열로 응답하세요.
            [레이아웃 분석 팁]
            - 한국 MTS(CYBOS 등)는 보통 한 종목 정보를 2줄(상/하)로 배치합니다. 상단(종목명, 평단), 하단(수익률, 평가금액)을 하나의 블록으로 묶으세요.
            [추출 지침]
            1. name: 종목명
            2. ticker: 6자리숫자.KS(코스피) 또는 .KQ(코스닥)
            3. avg_price: 매입단가 (숫자만)
            4. deposit: 매입금액 (숫자만)
            결과는 반드시 [{"name": "...", "ticker": "...", "avg_price": 0, "deposit": 0}] 형식의 JSON 배열만 보내세요.
            """
            return self.client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, img]).text
        except Exception as e:
            return f"이미지 분석 실패: {e}"
