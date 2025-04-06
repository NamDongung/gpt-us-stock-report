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
print("📥 주가 데이터 수집 중...")
tickers = list(portfolio.keys())
data = yf.download(tickers, period="2d", interval="1d")["Close"]
yesterday = data.iloc[-2]
today = data.iloc[-1]

stock_table_rows = []
total_value = 0

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

stock_table = """
<table>
  <thead><tr><th>Ticker</th><th>평균단가</th><th>현재가</th><th>수량</th><th>평가금액</th><th>수익률</th></tr></thead>
  <tbody>
""" + "\n".join(stock_table_rows) + "\n  </tbody></table>"

# 3. GPT 프롬프트 구성
stock_summary = "\n".join([
    f"{ticker}: 현재가 ${today[ticker]:.2f}, 평균단가 ${portfolio[ticker]['avg_price']:.2f}, 수익률 {((today[ticker] - portfolio[ticker]['avg_price']) / portfolio[ticker]['avg_price']) * 100:.2f}%"
    for ticker in tickers
])

prompt = f"""
너는 금융 애널리스트야. 아래는 사용자 포트폴리오 요약이야:

{stock_summary}

이 포트폴리오를 기준으로 아래 항목들을 분석해줘:
1. 시장 요약 테이블 (S&P500, Nasdaq, Kospi 등)
2. 시장 분석 요약 (뉴스 기반)
3. 심리지표 요약 (Fear&Greed, VIX 등) + 전략 코멘트
4. 종목별 분석 (JEPI, JEPQ 등)

결과를 각각 아래 변수에 맞춰 HTML 조각으로 반환해:
- market_index_table
- market_analysis
- strategy_table
- indicator_insight
- today_strategy_comment
- stock_analysis_sections
"""

response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": prompt}]
)

content = response.choices[0].message.content

# 4. 템플릿 로드 및 채우기
with open("report_template.html", "r", encoding="utf-8") as f:
    template = f.read()

report_html = template.replace("{{ report_date }}", datetime.today().strftime("%Y.%m.%d"))
report_html = report_html.replace("{{ total_value }}", f"${total_value:,.2f}")
report_html = report_html.replace("{{ stock_table }}", stock_table)

# GPT 결과를 변수별로 나누기 (간단한 구조 가정)
for key in ["market_index_table", "market_analysis", "strategy_table", "indicator_insight", "today_strategy_comment", "stock_analysis_sections"]:
    placeholder = f"{{{{ {key} }}}}"
    # 키별 구분자 사용 시 적절히 파싱 필요
    extracted = content.split(f"[{key}]")[1].split(f"[/{key}]")[0].strip() if f"[{key}]" in content else "(데이터 없음)"
    report_html = report_html.replace(placeholder, extracted)

# 5. 이메일 발송
msg = MIMEMultipart("alternative")
msg["Subject"] = "📈 오늘의 GPT 주식 리포트"
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
    data={"chat_id": TELEGRAM_CHAT_ID, "text": "📬 GPT 주식 리포트가 발송되었습니다! ✉️"}
)

print("✅ 리포트 전송 완료")
