from google import genai
import PIL.Image
import time
import re
import json
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class MarketAnalyzer:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    def _safe_generate_content(self, model, contents):
        """지수 백오프를 적용한 안전한 AI 호출"""
        return self.client.models.generate_content(model=model, contents=contents)

    def generate_analysis(self, market_data, report_type="opening", trade_info=None):
        indices_summary = "".join([f"- {n}: {i['price']} ({i['change_pct']}% / BB신호: {i.get('bb_signal')})\n" for n, i in market_data.get('indices', {}).items()])
        portfolio_data = market_data.get('portfolio', {})
        sentiment_score = market_data.get('market_sentiment', 50.0)
        total_value = sum(info.get('current_value', 0) for info in portfolio_data.values())
        
        portfolio_details = ""
        for name, info in portfolio_data.items():
            weight = (info.get('current_value', 0) / total_value * 100) if total_value > 0 else 0
            hist = ", ".join([f"{d}: {p}" for d, p in info.get('history', {}).items()])
            portfolio_details += f"- {name}: 현재가 {info['price']} (평단 {info['avg_price']}), 수익률 {info['roi']}%, 비중 {round(weight, 1)}%\n"
            portfolio_details += f"  [기술지표]: RSI({info.get('rsi')}), MACD({info.get('macd')}), BB({info.get('bb_lower')} ~ {info.get('bb_upper')})\n"
            portfolio_details += f"  [신호]: BB {info.get('bb_signal')}, MACD Signal({info.get('macd_signal')})\n"
            portfolio_details += f"  [1개월 히스토리]: {hist}\n"

        # 1. 시스템 역할 및 기본 지침
        system_context = "당신은 전문 금융 분석가 Stocky입니다. 제공된 데이터를 바탕으로 통찰력 있는 주식 리포트를 작성하세요."

        # 2. 시장 데이터 섹션
        data_context = f"""
        [시장 지수 정보]
        {indices_summary}

        [사용자 포트폴리오 현황]
        {portfolio_details}
        """

        # 3. 실행 모드별 특화 지침
        if report_type == "trade_eval" and trade_info:
            task_instruction = f"""
            [매매 진단 요청]
            - 종목: {trade_info['ticker']} ({trade_info['category']})
            - 작업: {trade_info['action']}
            - 사유: {trade_info['reason']}
            데이터를 기반으로 이 매매 결정이 적절한지 분석하고, 기술적 지표를 활용해 목표가와 손절가를 제시하세요.
            """
        elif report_type == "closing":
            task_instruction = "미국 증시 마감 상황을 분석하고, 보유 종목에 미칠 영향과 내일의 대응 전략을 수립하세요."
        else:
            task_instruction = "오늘 한국 증시 개장 전 체크해야 할 주요 포인트와 포트폴리오 종목별 기술적 관점을 정리하세요."

        # 4. 출력 형식 및 제약 조건
        format_instruction = """
        [출력 가이드라인]
        1. 요약본과 상세본을 [SPLIT] 구분자로 나누어 작성하세요.
        2. 리포트 서두(첫 문장)는 반드시 현재 '시장 심리 지수'를 반영하여 시장의 전반적인 온도감을 묘사하며 시작하세요.
        3. 요약본: 텔레그램 메시지용. 핵심 요점 3가지를 불렛포인트로 작성 (HTML <b> 태그 사용 가능).
        4. 상세본: 전문적인 톤으로 섹션별 상세 분석. 
        5. 적정 주가 분석: 각 종목에 대해 현재 기술적 지표(RSI, MACD, 볼린저 밴드 돌파 여부)와 히스토리를 바탕으로 단기적 '적정 주가(Fair Value)' 범위를 추론하여 제시하세요. 특히 볼린저 밴드 상/하단 이탈 시의 기술적 의미를 분석에 포함하세요.
        6. 이모지 활용: 각 섹션 제목에는 시장 상황(상승, 하락, 횡보)에 어울리는 이모지를 동적으로 사용하세요.
        7. HTML 태그: <b>, <pre> 태그만 사용하여 가독성을 높이세요.
        """

        prompt = f"{system_context}\n\n{data_context}\n\n{task_instruction}\n\n{format_instruction}"

        models_to_try = ['gemini-3.5-flash', 'gemini-2.5-flash']
        analysis_result = None

        for model_name in models_to_try:
            try:
                analysis_result = self._safe_generate_content(model=model_name, contents=prompt).text
                break
            except Exception as e:
                if "API_KEY_INVALID" in str(e) or "400" in str(e):
                    return f"❌ {model_name} 인증 실패: API 키가 유효하지 않습니다. .env 파일을 확인하세요."
                
                if "429" in str(e): continue
                print(f"❌ {model_name} 오류: {e}")

        if analysis_result is None:
            return "모든 모델의 할당량이 초과되었습니다."

        # 요약본 길이 체크 및 단축 재시도 로직
        MAX_SUMMARY_LENGTH_TARGET = 800
        MAX_SUMMARY_RETRY = 2

        current_summary = ""
        details = ""
        if "[SPLIT]" in analysis_result:
            current_summary, details = analysis_result.split("[SPLIT]", 1)
        else:
            current_summary = analysis_result
            details = ""

        original_analysis_result = analysis_result
        retry_count = 0

        while len(current_summary) > MAX_SUMMARY_LENGTH_TARGET and retry_count < MAX_SUMMARY_RETRY:
            print(f"⚠️ 요약본이 너무 깁니다 ({len(current_summary)}자). Gemini에게 다시 요약을 요청합니다. (시도 {retry_count + 1}/{MAX_SUMMARY_RETRY})")
            retry_count += 1
            
            content_to_summarize = current_summary if details else original_analysis_result
            summarize_prompt = f"""
            다음 텍스트를 {MAX_SUMMARY_LENGTH_TARGET}자 이내로 핵심 요약해 주세요.
            HTML 태그(<b>, <pre>)는 유지하되, 내용이 잘리지 않도록 주의해 주세요.
            ---
            {content_to_summarize}
            ---
            """
            
            try:
                summarization_model = 'gemini-2.0-flash' # 최신 모델 권장
                new_summary_response = self._safe_generate_content(model=summarization_model, contents=summarize_prompt).text
                current_summary = new_summary_response.strip()
                
                if details:
                    analysis_result = f"{current_summary}[SPLIT]{details}"
                else:
                    analysis_result = current_summary
            except Exception as e:
                print(f"❌ 요약 재시도 중 오류 발생: {e}")
                break

        return analysis_result

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
            결과는 반드시 다른 설명 없이 [{"name": "...", "ticker": "...", "avg_price": 0, "deposit": 0}] 형식의 JSON 배열만 보내세요.
            """
            response = self._safe_generate_content(model='gemini-3.5-flash', contents=[prompt, img])
            return self._validate_and_clean_json(response.text)
        except Exception as e:
            return json.dumps({"error": f"이미지 분석 실패: {str(e)}"})

    def _validate_and_clean_json(self, raw_text):
        """AI 응답에서 JSON만 추출하고 데이터 유효성 검증"""
        try:
            # 1. 정규식을 이용해 JSON 배열 부분([ ... ])만 추출
            match = re.search(r'\[\s*\{.*\}\s*\]', raw_text, re.DOTALL)
            if not match:
                return "[]"
            
            json_str = match.group()
            data = json.loads(json_str)
            
            # 2. 필수 필드 및 데이터 타입 검증
            validated_data = []
            required_keys = ['name', 'ticker', 'avg_price', 'deposit']
            
            for item in data:
                if all(key in item for key in required_keys):
                    # 숫자형 데이터 정제 (콤마 제거 등)
                    item['avg_price'] = float(str(item['avg_price']).replace(',', ''))
                    item['deposit'] = float(str(item['deposit']).replace(',', ''))
                    validated_data.append(item)
            
            return json.dumps(validated_data, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ JSON 검증 중 오류: {e}")
            return "[]"
