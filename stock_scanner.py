import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import re
from ta.momentum import StochasticOscillator

st.set_page_config(page_title="台股飆股掃描器", layout="wide")

@st.cache_data(ttl=86400)
def get_all_stocks():
    codes = []
    for mode in ["2", "4"]:
        try:
            url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}"
            res = requests.get(url, timeout=10)
            df = pd.read_html(res.text)[0]
            for item in df.iloc[:, 0]:
                match = re.match(r'^(\d{4})\s+', str(item))
                if match: codes.append(f"{match.group(1)}.TW")
        except: continue
    return list(set(codes))

def scan_all():
    stocks = get_all_stocks()
    # 掃描前 300 檔避免雲端記憶體溢出
    target_stocks = stocks[:300] 
    results = []
    
    progress_bar = st.progress(0)
    for i, s in enumerate(target_stocks):
        progress_bar.progress(i / len(target_stocks))
        try:
            # 改為單檔下載，避開合併錯誤 (No objects to concatenate)
            df = yf.download(s, period="2mo", interval="1d", progress=False)
            if df.empty or len(df) < 30: continue
            
            # 指標計算
            vol5 = df['Volume'].rolling(5).mean().iloc[-1]
            vol20 = df['Volume'].rolling(20).mean().iloc[-1]
            if vol20 == 0: continue
            
            vol_ratio = vol5 / vol20
            close_now = df['Close'].iloc[-1]
            close_3 = df['Close'].iloc[-4]
            return3 = (close_now - close_3) / close_3
            
            limit_up_sum = (df['Close'].pct_change() >= 0.098).rolling(3).sum().iloc[-1]
            
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
            k_val = stoch.stoch().iloc[-1]
            
            # 你的原始邏輯條件
            if vol_ratio > 1.85 and (return3 > 0.20 or limit_up_sum >= 2) and k_val > 80:
                results.append({
                    "股票": s.replace(".TW", ""),
                    "價格": round(float(close_now), 2),
                    "量比": round(float(vol_ratio), 2),
                    "漲幅%": round(float(return3 * 100), 2),
                    "K值": round(float(k_val), 2)
                })
        except:
            continue
    progress_bar.empty()
    return pd.DataFrame(results)

st.title("🔥 台股噴發掃描器")
if st.button("開始掃描"):
    df = scan_all()
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("沒有股票同時滿足你的三個條件。")
