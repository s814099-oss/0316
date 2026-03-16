import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import requests
import urllib3
from ta.momentum import StochasticOscillator

# 設定環境
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(layout="wide", page_title="台股飆股與突破掃描")

@st.cache_data(ttl=86400)
def get_all_tickers():
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=15)
    df = pd.read_html(resp.text)[0]
    df = df[df.iloc[:, 0].str.match(r'^\d{4}\s', na=False)]
    return [f"{t.split()[0]}.TW" for t in df.iloc[:, 0]]

def scan_full_market(all_tickers):
    results_3day = []
    results_6mo = []
    
    batch_size = 30
    batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
    
    progress = st.progress(0)
    for i, batch in enumerate(batches):
        progress.progress((i + 1) / len(batches))
        try:
            data = yf.download(batch, period="6mo", interval="1d", group_by='ticker', threads=True, progress=False)
            
            for ticker in batch:
                df = data[ticker] if len(batch) > 1 else data
                if df.empty or len(df) < 125: continue
                
                # --- 計算共同技術指標 ---
                vol_ratio = (df['Volume'].rolling(5).mean().iloc[-1]) / (df['Volume'].rolling(20).mean().iloc[-1])
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9)
                k = float(stoch.stoch().iloc[-1])
                
                # 共同篩選門檻
                if vol_ratio > 1.85 and k > 80:
                    curr_close = float(df['Close'].iloc[-1])
                    
                    # 條件 A: 3天漲幅 > 20%
                    three_day_gain = (curr_close - float(df['Close'].iloc[-4])) / float(df['Close'].iloc[-4])
                    if three_day_gain > 0.20:
                        results_3day.append({"代號": ticker.replace(".TW", ""), "漲幅": f"{three_day_gain:.1%}", "量比": round(vol_ratio, 2), "K值": round(k, 2)})
                    
                    # 條件 B: 半年新高
                    six_mo_high = df['Close'].rolling(120).max().iloc[-1]
                    if curr_close >= six_mo_high:
                        results_6mo.append({"代號": ticker.replace(".TW", ""), "現價": round(curr_close, 2), "半年高點": round(six_mo_high, 2), "量比": round(vol_ratio, 2), "K值": round(k, 2)})
            
            time.sleep(random.uniform(2, 4))
        except Exception:
            continue
            
    return pd.DataFrame(results_3day), pd.DataFrame(results_6mo)

# --- UI 渲染 ---
st.title("📊 飆股與突破分開掃描器")
if st.button("開始掃描"):
    with st.spinner("掃描中..."):
        tickers = get_all_tickers()
        # 這裡明確接收兩個回傳值
        df_3day, df_6mo = scan_full_market(tickers)
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🚀 短線噴出 (3天漲幅>20%)")
            st.dataframe(df_3day, use_container_width=True)
        with col2:
            st.subheader("📈 中線突破 (半年新高)")
            st.dataframe(df_6mo, use_container_width=True)
