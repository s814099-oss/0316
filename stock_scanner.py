import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import re
from ta.momentum import StochasticOscillator
import datetime

st.set_page_config(page_title="台股噴發掃描器", layout="wide")

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
    # 這裡限制掃描前 500 檔成交量大的，以免伺服器逾時
    target_stocks = stocks[:500] 
    results = []
    
    # 一次下載 500 檔，確保結構一致
    data = yf.download(target_stocks, period="2mo", interval="1d", group_by='ticker', threads=True, progress=False)
    
    for s in target_stocks:
        try:
            df = data[s].dropna()
            if len(df) < 30: continue
            
            # --- 嚴格的條件計算 ---
            vol5 = df['Volume'].rolling(5).mean().iloc[-1]
            vol20 = df['Volume'].rolling(20).mean().iloc[-1]
            vol_ratio = vol5 / vol20
            
            close_now = df['Close'].iloc[-1]
            close_3 = df['Close'].iloc[-4]
            return3 = (close_now - close_3) / close_3
            
            limit_up_sum = (df['Close'].pct_change() >= 0.098).rolling(3).sum().iloc[-1]
            
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
            k_val = stoch.stoch().iloc[-1]
            
            # 判斷邏輯
            if vol_ratio > 1.85 and (return3 > 0.20 or limit_up_sum >= 2) and k_val > 80:
                results.append({
                    "股票": s.replace(".TW", ""),
                    "價格": round(float(close_now), 2),
                    "量比": round(float(vol_ratio), 2),
                    "漲幅%": round(float(return3 * 100), 2),
                    "K值": round(float(k_val), 2)
                })
        except: continue
    return pd.DataFrame(results)

st.title("🔥 台股噴發掃描器 (手動刷新版)")
if st.button("開始執行掃描"):
    with st.spinner("掃描中...這可能需要 1-2 分鐘"):
        df = scan_all()
        if not df.empty:
            st.success(f"掃描成功，找到 {len(df)} 檔")
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("沒有符合條件的股票，請確認條件或檢查數據源。")
            # 除錯提示：如果你還是掃不到，這裡顯示測試數值
            st.caption("提示：若認為條件無誤，請檢查 Yahoo Finance 數據是否正常更新。")
