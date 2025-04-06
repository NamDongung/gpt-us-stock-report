import json
import yfinance as yf
import openai
import smtplib, ssl
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import os

# 환경 변수 불러오기
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# 1. 포트폴리오 로드
with open("portfolio.json", "r") as f:
    portfolio = json.load(f)

# 2. 주가 데이터 수집
print("\U0001F4E5 주가 데이터 수집 중...")
tickers = list(portfolio.keys())
data = yf.download(tickers, period="2d", interval="1d")["Close"]
yesterday = data.iloc[-2]
today = data.iloc[-1]

stock_table_rows = []
total_value = 0
stock_summary_lines = []

for ticker in tickers:
    avg_price = portfolio[ticker]["avg_price"]
    shares = portfolio[ticker]["shares"]
    curr = today[ticker]
    value = curr * shares
    total_value += value
    pnl_pct = ((curr - avg_price) / avg_price) * 100
    pnl_color = "red" if pnl_pct >= 0 else "blue"
    stock_table_rows.append(
        f"<tr><td>{ticker}</td><td>${avg_price:.2f}</td><td>${curr:.2f}</td><td>{shares}</td><td>${value:,.2f}</td><td class=\"{pnl_color}\">{pnl_pct:+.1f}%</td></tr>"
    )
    stock_summary_lines.append(f"{ticker}: 현재가 ${curr:.2f}, 평균단가 ${avg_price:.2f}, 수익률 {pnl_pct:.2f}%")

stock_table = """
<table>
  <thead><tr><th>Ticker</th><th>평균단가</th><th>현재가</th><th>수량</th><th>평가금액</th><th>수익률</th></tr></thead>
  <tbody>
""" + "\n".join(stock_table_rows) + "\n  </tbody></table>"

stock_summary = "\n".join(stock_summary_lines)

# GPT 프롬프트 구성
prompt = f"""
“지금부터 너는 너는 미국 주식 애널리스트이며, 정해진 템플릿 양식대로만 HTML을 출력하는 프로그램이야”
다음은 사용자의 포트폴리오 종목별 정보야:

{stock_summary}

아래 항목을 반드시 각각 [key]와 [/key] 태그 안에 HTML 형식으로 작성해줘. 각 항목은 다음과 같아:

[market_index_table]
S&P500, NASDAQ, 다우존스, 코스피, 코스닥, USD/KRW 등 주요 지수 요약 테이블 (전일 등락률, 시가/종가, 52주 고저 포함)
[/market_index_table]

[market_analysis]
시장 변동 요인 (뉴스 5개 이상 기반, 금리, 전쟁, 경제지표 등) — 5줄 이상 분석 + 출처 포함
[/market_analysis]

[strategy_table]
VIX, Fear & Greed Index, 10Y 금리, 달러인덱스 DXY 등 핵심 지표 요약 테이블 + 수치 + 출처 링크
[/strategy_table]

[indicator_insight]
각 지표에 대한 상세 해석 및 내 포트폴리오 전략 관점에서의 의미 (배당주/성장주/방어주 등 중심으로)
[/indicator_insight]

[today_strategy_comment]
오늘의 리스크/기회 요약 전략 코멘트 (1줄)
[/today_strategy_comment]

[stock_analysis_sections]
JEPI, JEPQ, SCHD, QQQM, O, NVDA, TSLA, CONY 종목에 대한 상세 분석. 각 항목은 <details>로 토글 구성. 시장 해석은 5개 이상 기사 교차 검증된 분석으로 작성.
[/stock_analysis_sections]
"""

print("[DEBUG] GPT에 보낼 프롬프트:\n", prompt)

# GPT 요청
response = openai.ChatCompletion.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}]
)

print("[DEBUG] GPT 응답 전체:\n", response)

try:
    gpt_content = response.choices[0].message.content
    print("[DEBUG] GPT 응답 본문:\n", gpt_content)
except Exception as e:
    print("[ERROR] GPT 응답 파싱 실패:", str(e))
    gpt_content = "<p>⚠️ GPT 응답 오류 - 리포트를 생성하지 못했습니다.</p>"

# 4. 템플릿 로드 및 채우기
with open("report_template.html", "r", encoding="utf-8") as f:
    template = f.read()

report_html = template.replace("{{ report_date }}", datetime.today().strftime("%Y.%m.%d"))
report_html = report_html.replace("{{ total_value }}", f"${total_value:,.2f}")
report_html = report_html.replace("{{ stock_table }}", stock_table)

for key in ["market_index_table", "market_analysis", "strategy_table", "indicator_insight", "today_strategy_comment", "stock_analysis_sections"]:
    placeholder = f"{{{{ {key} }}}}"
    extracted = gpt_content.split(f"[{key}]")[1].split(f"[/{key}]")[0].strip() if f"[{key}]" in gpt_content else "(데이터 없음)"
    report_html = report_html.replace(placeholder, extracted)

# 5. 이메일 발송
msg = MIMEMultipart("alternative")
msg["Subject"] = "\U0001F4C8 오늘의 GPT 주식 리포트"
msg["From"] = EMAIL_USER
msg["To"] = EMAIL_RECEIVER
part = MIMEText(report_html, "html")
msg.attach(part)

context = ssl.create_default_context()
with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
    server.login(EMAIL_USER, EMAIL_PASS)
    server.sendmail(EMAIL_USER, EMAIL_RECEIVER, msg.as_string())

# 6. 텔레그램 전송
requests.post(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
    data={"chat_id": TELEGRAM_CHAT_ID, "text": "\U0001F4EC GPT 주식 리포트가 발송되었습니다! ✉️"}
)

print("✅ 리포트 전송 완료")
