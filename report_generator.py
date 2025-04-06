import json
import yfinance as yf
import openai
import smtplib, ssl
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

# Load secrets
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# Load portfolio
with open("portfolio.json", "r") as f:
    portfolio = json.load(f)

# Step 1: 주가 데이터 수집
report_lines = []
tickers = list(portfolio.keys())
data = yf.download(tickers, period="2d", interval="1d")["Close"]
yesterday = data.iloc[-2]
today = data.iloc[-1]

for ticker in tickers:
    shares = portfolio[ticker]["shares"]
    avg_price = portfolio[ticker]["avg_price"]
    prev = yesterday[ticker]
    curr = today[ticker]
    change = ((curr - prev) / prev) * 100
    profit = (curr - avg_price) * shares
    report_lines.append(f"{ticker}: {curr:.2f} USD ({change:+.2f}%), 평가손익: ${profit:,.2f}")

stock_summary = "\n".join(report_lines)

# Step 2: GPT에게 분석 요청
prompt = f"""
너는 미국 주식 분석가야.
다음은 사용자의 포트폴리오 종목별 변동 및 수익률이야:

{stock_summary}

아래 항목을 요약해서 HTML로 보고서를 만들어줘.
1. 주요 특징 요약 (섹터/ETF별 정리)
2. 주가 변동에 따른 코멘트
3. 금리, 환율, 뉴스 요약 (추정 기반)
4. 리스크 요인 및 전략 제안
"""

response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": prompt}]
)
gpt_html = response.choices[0].message.content

# Step 3: 이메일 보내기
msg = MIMEMultipart("alternative")
msg["Subject"] = "📈 오늘의 미국 주식 GPT 리포트"
msg["From"] = EMAIL_USER
msg["To"] = EMAIL_RECEIVER
part = MIMEText(gpt_html, "html")
msg.attach(part)

context = ssl.create_default_context()
with smtplib.SMTP_SSL("smtp.naver.com", 465, context=context) as server:
    server.login(EMAIL_USER, EMAIL_PASS)
    server.sendmail(EMAIL_USER, EMAIL_RECEIVER, msg.as_string())

# Step 4: 텔레그램 전송
requests.post(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
    data={"chat_id": TELEGRAM_CHAT_ID, "text": "📬 미국 주식 GPT 리포트가 도착했어요!\n메일함을 확인해보세요 ✉️"}
)
