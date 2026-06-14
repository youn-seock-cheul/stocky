from google import genai
import time

class MarketAnalyzer:
    def __init__(self, api_key):
        # 최신 Gemini SDK 클라이언트 설정
        self.client = genai.Client(api_key=api_key)

    def generate_analysis(self, market_data, report_type="opening"):
        """수집된 데이터를 기반으로 AI 분석 리포트 생성"""
        
        # 1. 데이터를 AI용 텍스트로 변환
        data_summary = ""
        for name, info in market_data.items():
            data_summary += f"- {name}: 현재가 {info['price']}, 등락률 {info['change_pct']}%\n"

        # 2. 리포트 유형에 따른 차별화된 프롬프트 구성
        if report_type == "closing":
            prompt = f"""
            당신은 글로벌 매크로 분석 전문가입니다. 미국 증시 마감 상황을 요약하여 한국 투자자들에게 전달하세요.

            [최신 시장 데이터]
            {data_summary}

            [요청 사항]
            1. **미국 증시 마감 요약**: 간밤 뉴욕 증시의 핵심 변동 원인과 흐름을 설명해줘.
            2. **주요 종목 동향**: 테크주(빅테크, 반도체 등)의 눈에 띄는 움직임 분석.
            3. **글로벌 지표 점검**: 환율, 금리 등의 변화가 주는 시사점.
            """
        else:
            prompt = f"""
            당신은 실전 투자 전략가입니다. 한국 증시 개장 직전, 투자자가 즉각 참고할 전략 리포트를 작성하세요.

            [최신 시장 데이터]
            {data_summary}

            [요청 사항]
            1. **오늘의 장전 관전 포인트**: 개장 직후 가장 주목해야 할 핵심 변수.
            2. **한국 증시 예상 흐름**: 미국장 결과를 반영한 코스피/코스닥 시초가 분위기 예측.
            3. **실전 대응 가이드**: 오늘 시장에서 취해야 할 매매 포지션(적극 매수, 관망 등).
            4. **오늘의 주도 섹터**: 수급이 몰릴 것으로 예상되는 섹터 2개와 구체적 이유.
            """

        # 요약과 상세 내용을 나누기 위한 지시사항 추가
        prompt += """
        
        **중요 지시사항**:
        1. 보고서 시작 부분에 전체 내용을 3줄 이내로 요약한 **'오늘의 핵심 요약'**을 작성하세요.
        2. 요약이 끝난 후 반드시 `[SPLIT]` 이라는 단어만 포함된 줄을 삽입하세요.
        3. 그 다음 이어서 상세 분석 내용을 작성하세요.
        4. 전문적이면서도 투자자가 행동에 옮길 수 있도록 구체적인 한국어로 작성해주세요.
        """

        # 시도할 모델 순서 (최신 모델 -> 안정화 모델)
        models_to_try = ['gemini-2.0-flash', 'gemini-2.5-flash', 'gemini-3.0-flash', 'gemini-3.5-flash']
        
        for model_name in models_to_try:
            for attempt in range(2):  # 모델당 최대 2회 시도
                try:
                    response = self.client.models.generate_content(model=model_name, contents=prompt)
                    return response.text
                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg:
                        print(f"⚠️ {model_name} 할당량 초과. 20초 후 재시도합니다... (시도 {attempt + 1}/2)")
                        time.sleep(20)  # 에러 메시지의 권장 대기 시간 반영
                        continue
                    else:
                        print(f"❌ {model_name} 호출 중 오류 발생: {error_msg}")
                        break  # 다음 모델로 넘어가거나 종료

        return f"AI 분석 중 오류가 발생했습니다 ({report_type}): 모든 가용 모델의 할당량이 초과되었습니다."