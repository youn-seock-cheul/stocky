from google import genai
import time

class MarketAnalyzer:
    def __init__(self, api_key):
        # 최신 Gemini SDK 클라이언트 설정
        self.client = genai.Client(api_key=api_key)

    def generate_analysis(self, market_data, report_type="opening", trade_info=None):
        """수집된 데이터를 기반으로 AI 분석 리포트 생성"""
        
        # 1. 지수 데이터 및 포트폴리오 데이터를 각각 텍스트로 변환
        indices_data = market_data.get('indices', {})
        portfolio_data = market_data.get('portfolio', {})
        
        indices_summary = ""
        for name, info in indices_data.items():
            indices_summary += f"- {name}: 현재가 {info['price']}, 등락률 {info['change_pct']}%\n"
            
        portfolio_summary = ""
        for name, info in portfolio_data.items():
            portfolio_summary += f"- {name}: 현재가 {info['price']}, 등락률 {info['change_pct']}%\n"

        # 2. 매매 판단 요청인 경우 (trade_info 존재 시)
        if trade_info:
            ticker_data = trade_info['data']
            prompt = f"""
            당신은 개인 투자자의 매매 결정을 돕는 수석 투자 컨설턴트입니다.
            
            [사용자 요청]
            - 투자 유형: {trade_info['category']}
            - 수행 작업: {trade_info['action']}
            - 대상 종목: {trade_info['ticker']} (현재가: {ticker_data['price']}, 등락률: {ticker_data['change_pct']}%)
            - 매매 사유: {trade_info['reason']}
            
            [최근 시장 맥락]
            {indices_summary}

            [요청 사항]
            1. **판단 결과**: 이 매매가 현재 시장 상황과 종목 흐름상 '적절'한지 '주의'가 필요한지 결론을 내주세요.
            2. **매도/추매 시점 예측**: 이 거래를 실행한다면, 수익 실현을 위한 1차 목표가(매도 시점)와 물타기 또는 비중 확대를 위한 2차 매수가를 가격 숫자로 제시하세요.
            3. **유형별 조언**: {trade_info['category']} 특성에 맞는 리스크 관리 방안(예: 환율 고려, 배당락, 지수 추종성 등)을 설명하세요.
            """
            report_type = "trade_eval"

        # 2. 리포트 유형에 따른 차별화된 프롬프트 구성
        elif report_type == "closing":
            prompt = f"""
            당신은 글로벌 매크로 분석 전문가입니다. 미국 증시 마감 상황을 요약하여 한국 투자자들에게 전달하세요.

            [최신 시장 데이터]
            {indices_summary}
            
            [나의 보유 종목]
            {portfolio_summary}

            [요청 사항]
            1. **미국 증시 마감 요약**: 간밤 뉴욕 증시의 핵심 변동 원인과 흐름을 설명해줘.
            2. **주요 종목 동향**: 테크주(빅테크, 반도체 등)의 눈에 띄는 움직임 분석.
            3. **보유 종목 영향 분석**: 미국 시장의 흐름이 [나의 보유 종목]에 미칠 긍정적/부정적 요인 분석.
            4. **글로벌 지표 점검**: 환율, 금리 등의 변화가 주는 시사점.
            """
        else:
            prompt = f"""
            당신은 실전 투자 전략가입니다. 한국 증시 개장 직전, 투자자가 즉각 참고할 전략 리포트를 작성하세요.

            [최신 시장 데이터]
            {indices_summary}
            
            [나의 보유 종목]
            {portfolio_summary}

            [요청 사항]
            1. **오늘의 장전 관전 포인트**: 개장 직후 가장 주목해야 할 핵심 변수.
            2. **한국 증시 예상 흐름**: 미국장 결과를 반영한 코스피/코스닥 시초가 분위기 예측.
            3. **보유 종목별 투자 전략**: [나의 보유 종목] 각각에 대해 차트와 시장 상황을 고려한 구체적 대응(홀딩, 추가 매수, 비중 축소 등) 및 예상 가격대를 제안하세요.
            4. **실전 대응 가이드**: 오늘 시장 전반에서 취해야 할 포지션.
            5. **오늘의 주도 섹터**: 수급이 몰릴 것으로 예상되는 섹터 2개와 구체적 이유.
            """

        # 요약과 상세 내용을 나누기 위한 지시사항 추가
        prompt += """
        
        **중요 지시사항**:
        1. 보고서 시작 부분에 **'오늘의 핵심 요약'**을 3줄 이내로 작성하세요.
        2. 요약 바로 아래에 시장 상황을 한눈에 볼 수 있는 **'마크다운 요약 표'**를 포함하세요.
        2. 요약 바로 아래에 시장 상황 요약 표를 작성하세요. 
           텔레그램 가독성을 위해 반드시 <pre> 태그로 표 전체를 감싸고, 내부 컬럼 간격을 공백으로 맞춰 정렬하세요.
           (예: <pre>| 지수 | 현재가 | 등락 |\n| KOSPI| 2,500 | +0.5%|</pre>)
        3. 표가 끝난 후 반드시 `[SPLIT]` 이라는 단어만 포함된 줄을 삽입하세요.
        4. 상세 분석 내용에도 가능한 한 항목별로 표를 사용하여 가독성을 높이세요.
        5. 전문적이면서도 투자자가 행동에 옮길 수 있도록 구체적인 한국어로 작성해주세요.
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