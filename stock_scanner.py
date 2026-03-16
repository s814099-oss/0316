import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import requests
from ta.momentum import StochasticOscillator

# 頁面設定
st.set_page_config(page_title="台股飆股進階掃描", layout="wide")

@st.cache_data(ttl=3600)
def get_all_tickers():
    urls = ["https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", 
            "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"]
    all_tickers = []
    for url in urls:
        try:
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            df = pd.read_html(resp.text)[0]
            # 篩選個股代號
            df = df[df.iloc[:, 0].str.match(r'^\d{4}\s', na=False)]
            tickers = [f"{str(x).split()[0]}.TW" for x in df.iloc[:, 0]]
            all_tickers.extend(tickers)
        except:
            continue
    return list(set(all_tickers))

def run_scanner(tickers):
    results_gain = []
    results_high = []
    
    batch_size = 10
    batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    
    progress_bar = st.progress(0)
    for i, batch in enumerate(batches):
        progress_bar.progress((i + 1) / len(batches))
        try:
            data = yf.download(batch, period="6mo", interval="1d", group_by='ticker', progress=False)
            
            for s in batch:
                df = data[s] if len(batch) > 1 else data
                if df.empty or len(df) < 125:
                    continue
                
                curr_close = float(df['Close'].iloc[-1])
                vol_ratio = (df['Volume'].rolling(5).mean().iloc[-1]) / (df['Volume'].rolling(20).mean().iloc[-1])
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
                k_val = float(stoch.stoch().iloc[-1])
                three_day_gain = (curr_close - df['Close'].iloc[-4]) / df['Close'].iloc[-4]
                six_mo_high = df['Close'].rolling(120).max().iloc[-1]

                if vol_ratio > 1.85 and k_val > 80:
                    if three_day_gain > 0.20:
                        results_gain.append({"代號": s.replace(".TW", ""), "現價": round(curr_close, 2), "漲幅": f"{round(three_day_gain*100, 2)}%", "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
                    if curr_close >= six_mo_high:
                        results_high.append({"代號": s.replace(".TW", ""), "現價": round(curr_close, 2), "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
            
            time.sleep(random.uniform(3, 5))
        except Exception:
            continue
            
    return pd.DataFrame(results_gain), pd.DataFrame(results_high)

# --- UI 渲染區塊 ---
st.title("📊 台股飆股進階掃描器")

if st.button("啟動全面掃描"):
    with st.spinner('正在計算資料，請稍候...'):
        all_tickers = get_all_tickers()
        df1, df2 = run_scanner(all_tickers)
    
    # 使用 Tabs 進行分頁，並確保所有 UI 元件掛載在明確的縮排區塊內
    tab1, tab2 = st.tabs(["🚀 短線強勢 (3天漲幅>20%)", "📈 中線突破 (半年新高)"])
    
    with tab1:
        # 使用明確的 if-else 語句塊，避免觸發語法解析錯誤
        if not df1.empty:
            st.dataframe(df1, use_container_width=True)
        else:
            st.info("目前無符合 3 天漲幅 > 20% 的標的")
            
    with tab2:
        # 使用明確的 if-else 語句塊
        if not df2.empty:
            st.dataframe(df2, use_container_width=True)
        else:
            st.info("目前無符合半年新高突破條件的標的")
