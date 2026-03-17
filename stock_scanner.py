import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import requests
import urllib3
from ta.momentum import StochasticOscillator
import plotly.graph_objects as go
from io import StringIO
from datetime import datetime

# 1. 基礎設定
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(layout="wide", page_title="台股飆股掃描器 Pro")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
}

# ====== 2. 超強健清單抓取 (含內建種子) ======
@st.cache_data(ttl=86400)
def get_all_tickers():
    all_tickers = []
    
    # A. 嘗試抓取上市 (TWSE)
    try:
        tw_url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_AVG_ALL?response=open_data"
        r = requests.get(tw_url, headers=HEADERS, verify=False, timeout=10)
        df_tw = pd.read_csv(StringIO(r.text))
        all_tickers.extend([f"{str(c).strip()}.TW" for c in df_tw.iloc[:, 0] if len(str(c).strip()) == 4])
    except:
        st.warning("⚠️ 上市清單抓取受限，啟動備援機制")

    # B. 嘗試抓取上櫃 (TPEx)
    try:
        # 嘗試 JSON API
        otc_url = "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/otc_quotes_no1430_result.php?l=zh-tw"
        r = requests.get(otc_url, headers=HEADERS, verify=False, timeout=10)
        if r.status_code == 200:
            all_tickers.extend([f"{str(item[0]).strip()}.TWO" for item in r.json()['aaData'] if len(str(item[0]).strip()) == 4])
    except:
        st.warning("⚠️ 上櫃清單抓取受限，啟動備援機制")

    # C. 【核心補強】萬一 API 全掛，強制注入台股高流動性種子 (含熱門上市櫃)
    seed_tickers = [
        "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW", "3231.TW", "2301.TW", "2357.TW",
        "2603.TW", "2609.TW", "2615.TW", "2618.TW", "2610.TW", "1513.TW", "1519.TW", "1504.TW",
        "2881.TW", "2882.TW", "2886.TW", "2891.TW", "5871.TW", "2353.TW", "2324.TW", "6669.TW",
        "8069.TWO", "6274.TWO", "3293.TWO", "6182.TWO", "3529.TWO", "3105.TWO", "6488.TWO", "5347.TWO"
    ]
    all_tickers = list(set(all_tickers + seed_tickers))
    
    return all_tickers

# ====== 3. 掃描引擎 (優化版) ======
def scan_market(tickers):
    results_3d, results_6m = [], []
    batch_size = 25
    batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    
    prog = st.progress(0)
    status = st.empty()
    
    for i, batch in enumerate(batches):
        prog.progress((i + 1) / len(batches))
        status.text(f"🔍 掃描中: {i*batch_size}/{len(tickers)} 檔...")
        try:
            # 加入 threads=True 加速，timeout 避免卡死
            data = yf.download(batch, period="7mo", group_by='ticker', threads=True, progress=False, timeout=20)
            for t in batch:
                df = data[t] if len(batch) > 1 else data
                if df.empty or len(df) < 40: continue
                
                # 檢測最近 5 天內符合條件的訊號
                for lookback in range(5):
                    idx = len(df) - 1 - lookback
                    df_s = df.iloc[:idx+1]
                    
                    # 條件：量 > 5000張 & 量比 > 1.85 & K > 80
                    vol = float(df_s['Volume'].iloc[-1]) / 1000
                    if vol < 5000: continue
                    
                    v5, v20 = df_s['Volume'].rolling(5).mean().iloc[-1], df_s['Volume'].rolling(20).mean().iloc[-1]
                    v_ratio = v5 / v20 if v20 > 0 else 0
                    
                    stoch = StochasticOscillator(df_s['High'], df_s['Low'], df_s['Close'], window=9)
                    k_val = stoch.stoch().iloc[-1]
                    
                    if v_ratio > 1.85 and k_val > 80:
                        s_date = df_s.index[-1].strftime('%Y-%m-%d')
                        price = round(float(df['Close'].iloc[-1]), 2)
                        
                        # A. 短線噴出 (3日 > 20%)
                        p_old = float(df_s['Close'].iloc[-4]) if len(df_s) >= 4 else 0
                        gain = (float(df_s['Close'].iloc[-1]) - p_old) / p_old if p_old > 0 else 0
                        if gain > 0.20:
                            results_3d.append({"代號": t, "日期": s_date, "現價": price, "漲幅": f"{gain:.1%}", "量比": round(v_ratio, 2), "張數": int(vol)})
                        
                        # B. 半年新高
                        h_6m = df_s['Close'].shift(1).rolling(120, min_periods=1).max().iloc[-1]
                        if float(df_s['Close'].iloc[-1]) >= h_6m:
                            results_6m.append({"代號": t, "日期": s_date, "現價": price, "量比": round(v_ratio, 2), "張數": int(vol)})
                        break
            time.sleep(random.uniform(0.5, 1.0))
        except: continue
    status.empty()
    return pd.DataFrame(results_3d), pd.DataFrame(results_6m)

# ====== 4. Plotly K線圖 ======
def plot_chart(t):
    df = yf.download(t, period="6mo", progress=False)
    if df.empty: return None
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線")])
    fig.update_layout(template="plotly_white", xaxis_rangeslider_visible=False, height=500, margin=dict(t=10, b=10, l=10, r=10))
    return fig

# ====== 5. UI ======
st.title("📈 台股量化飆股掃描器")
if 'd3' not in st.session_state: st.session_state.d3 = pd.DataFrame()
if 'd6' not in st.session_state: st.session_state.d6 = pd.DataFrame()

if st.button("🚀 啟動掃描"):
    with st.spinner("正在分析市場數據..."):
        tickers = get_all_tickers()
        st.session_state.d3, st.session_state.d6 = scan_market(tickers)
        st.success(f"完成！共掃描 {len(tickers)} 檔股票。")

if not st.session_state.d3.empty or not st.session_state.d6.empty:
    tab1, tab2 = st.tabs(["🚀 短線強勢", "🏛️ 半年新高"])
    with tab1:
        st.dataframe(st.session_state.d3, use_container_width=True)
        if not st.session_state.d3.empty:
            s1 = st.selectbox("選取股票", st.session_state.d3['代號'].tolist(), key="s1")
            st.plotly_chart(plot_chart(s1), use_container_width=True)
    with tab2:
        st.dataframe(st.session_state.d6, use_container_width=True)
        if not st.session_state.d6.empty:
            s2 = st.selectbox("選取股票", st.session_state.d6['代號'].tolist(), key="s2")
            st.plotly_chart(plot_chart(s2), use_container_width=True)
