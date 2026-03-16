import streamlit as st
import pandas as pd
import yfinance as yf
import time
from ta.momentum import StochasticOscillator

st.set_page_config(layout="wide", page_title="飆股穩健掃描器")

# 建議：測試階段我們先縮小範圍，避免被 Yahoo 鎖 IP
@st.cache_data(ttl=3600)
def get_tickers():
    # 這裡放你要掃描的清單，全市場可改為從證交所下載
    return ["2330.TW", "2317.TW", "2454.TW", "2303.TW", "2412.TW", "2308.TW", "2881.TW", "2882.TW", "2002.TW", "1301.TW", "6669.TW", "3008.TW", "2357.TW"]

def scan_stocks(tickers):
    results = []
    progress_bar = st.progress(0)
    
    for i, ticker in enumerate(tickers):
        progress_bar.progress((i + 1) / len(tickers))
        try:
            # 加入 timeout 與更穩定的連線設定
            df = yf.download(ticker, period="6mo", interval="1d", threads=False, progress=False, timeout=10)
            if df.empty or len(df) < 20: continue
            
            # 成交量單位校正
            vol_raw = float(df['Volume'].iloc[-1])
            vol_in_zhang = vol_raw / 1000 if vol_raw > 100000 else vol_raw
            
            # 技術指標計算
            ma5 = df['Volume'].rolling(5, min_periods=1).mean().iloc[-1]
            ma20 = df['Volume'].rolling(20, min_periods=1).mean().iloc[-1]
            vol_ratio = (ma5 / ma20) if ma20 > 0 else 0
            
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, fillna=True)
            k = float(stoch.stoch().iloc[-1])
            
            # 放寬篩選條件：只要成交量大於 500 張、量比 > 1.0、K > 50 即納入
            if vol_in_zhang > 500 and vol_ratio > 1.0 and k > 50:
                results.append({"代號": ticker, "成交量(張)": int(vol_in_zhang), "量比": round(vol_ratio, 2), "K值": round(k, 2)})
            
            time.sleep(1.2) # 強制延遲，確保不會觸發伺服器防火牆
        except Exception as e:
            continue
    return pd.DataFrame(results)

st.title("📊 飆股策略穩健掃描器")
if st.button("啟動掃描"):
    df_res = scan_stocks(get_tickers())
    if not df_res.empty:
        st.dataframe(df_res, use_container_width=True)
    else:
        st.warning("本次掃描無符合條件股票，請調整篩選參數。")
