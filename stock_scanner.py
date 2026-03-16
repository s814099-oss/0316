import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import requests
from ta.momentum import StochasticOscillator

st.set_page_config(page_title="台股飆股進階掃描", layout="wide")

@st.cache_data(ttl=3600)
def get_all_tickers():
    # 改進：僅抓取 4 位數代號，初步過濾 ETF 或其他奇怪符號
    urls = ["https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", 
            "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"]
    all_tickers = []
    for url in urls:
        try:
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            df = pd.read_html(resp.text)[0]
            # 篩選：只留 4 位數代號
            df = df[df.iloc[:, 0].str.match(r'^\d{4}\s', na=False)]
            tickers = [f"{str(x).split()[0]}.TW" for x in df.iloc[:, 0]]
            all_tickers.extend(tickers)
        except: continue
    return list(set(all_tickers))

def run_scanner(tickers):
    results_gain, results_high = [], []
    batch_size = 10 # 縮小 batch 避免被鎖
    batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    
    progress_bar = st.progress(0)
    for i, batch in enumerate(batches):
        progress_bar.progress((i + 1) / len(batches))
        try:
            # 加入 group_by='ticker' 來確保結構穩定
            data = yf.download(batch, period="6mo", interval="1d", group_by='ticker', progress=False)
            
            for s in batch:
                if s not in data: continue
                df = data[s].dropna()
                if len(df) < 125: continue
                
                # 計算指標
                curr_close = float(df['Close'].iloc[-1])
                vol_ratio = (df['Volume'].rolling(5).mean().iloc[-1]) / (df['Volume'].rolling(20).mean().iloc[-1])
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
                k_val = float(stoch.stoch().iloc[-1])
                three_day_gain = (curr_close - df['Close'].iloc[-4]) / df['Close'].iloc[-4]
                six_mo_high = df['Close'].rolling(120).max().iloc[-1]

                # 篩選條件
                if vol_ratio > 1.85 and k_val > 80:
                    if three_day_gain > 0.20:
                        results_gain.append({"代號": s.replace(".TW", ""), "現價": round(curr_close, 2), "漲幅": f"{round(three_day_gain*100, 2)}%", "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
                    if curr_close >= six_mo_high:
                        results_high.append({"代號": s.replace(".TW", ""), "現價": round(curr_close, 2), "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
            
            time.sleep(random.uniform(3, 5)) # 增加休息時間，對抗 Rate Limit
        except Exception as e:
            if "Rate limited" in str(e): time.sleep(60) # 觸發限制則暫停 1 分鐘
            continue
            
    return pd.DataFrame(results_gain), pd.DataFrame(results_high)

st.title("📊 台股飆股掃描器")
if st.button("啟動掃描"):
    with st.spinner('正在掃描市場...'):
        all_tickers = get_all_tickers()
        df1, df2 = run_scanner(all_tickers)
        
        tab1, tab2 = st.tabs(["🚀 短線強勢", "📈 中線突破"])
        with tab1: st.dataframe(df1, use_container_width=True) if not df1.empty else st.info("無符合標的")
        with tab2: st.dataframe(df2, use_container_width=True) if not df2.empty else st.info("無符合標的")
