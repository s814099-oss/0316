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

# 1. 初始化環境設定
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(layout="wide", page_title="台股量化篩選器 Pro")

# 模擬真實瀏覽器 Header
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
}

# ====== 2. 高穩定度清單抓取 (CSV Stream 版) ======
@st.cache_data(ttl=86400)
def get_all_tickers():
    all_tickers = []
    ticker_to_suffix = {} 
    
    # A. 上市公司 (TWSE)
    try:
        tw_url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_AVG_ALL?response=open_data"
        r = requests.get(tw_url, headers=HEADERS, verify=False, timeout=15)
        if r.status_code == 200:
            df_tw = pd.read_csv(StringIO(r.text))
            for code in df_tw.iloc[:, 0].astype(str):
                code = code.strip()
                if len(code) == 4 and code.isdigit():
                    all_tickers.append(f"{code}.TW")
                    ticker_to_suffix[code] = "TW"
    except Exception as e:
        st.error(f"上市清單讀取失敗: {e}")

    # B. 上櫃公司 (TPEx) - 解決 JSON 解析錯誤，改用下載流
    try:
        otc_url = "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/otc_quotes_no1430_download.php?l=zh-tw"
        r = requests.get(otc_url, headers=HEADERS, verify=False, timeout=15)
        if r.status_code == 200:
            # 櫃買 CSV 通常前三行為標題，使用 skiprows 跳過
            df_otc = pd.read_csv(StringIO(r.text), skiprows=3)
            for code in df_otc.iloc[:, 0].astype(str):
                # 清理代號中的引號或等於符號 (例如 ="2330")
                code = code.replace('"', '').replace('=', '').strip()
                if len(code) == 4 and code.isdigit():
                    all_tickers.append(f"{code}.TWO")
                    ticker_to_suffix[code] = "TWO"
    except Exception as e:
        st.error(f"上櫃清單讀取失敗: {e}")
            
    # 如果線上抓取失敗的保底
    if not all_tickers:
        all_tickers = ["2330.TW", "2317.TW", "2454.TW", "2603.TW", "6278.TWO", "8069.TWO"]
        
    return list(set(all_tickers)), ticker_to_suffix

# ====== 3. 視覺化 K 線圖 ======
def plot_candlestick(full_ticker):
    try:
        df = yf.download(full_ticker, period="6mo", interval="1d", progress=False, timeout=15)
        if df.empty: return None
        
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            name="K線", increasing_line_color='#FF3333', decreasing_line_color='#00AA00'
        ))
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='orange', width=1), name="5MA"))
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='blue', width=1), name="20MA"))
        fig.add_trace(go.Bar(
            x=df.index, y=df['Volume'], name="成交量", marker_color='gray', opacity=0.2, yaxis='y2'
        ))

        fig.update_layout(
            template="plotly_white", xaxis_rangeslider_visible=False,
            yaxis=dict(title="價格", side="left"),
            yaxis2=dict(title="成交量", overlaying="y", side="right", showgrid=False),
            height=500, margin=dict(t=30, b=10, l=10, r=10)
        )
        return fig
    except:
        return None

# ====== 4. 掃描引擎 ======
def scan_market(all_tickers):
    results_3d = []
    results_6m = []
    
    batch_size = 25
    batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
    
    prog = st.progress(0)
    status = st.empty()
    
    for i, batch in enumerate(batches):
        prog.progress((i + 1) / len(batches))
        status.text(f"🔍 掃描中: {i*batch_size}/{len(all_tickers)} 檔股票...")
        
        try:
            # 同步下載一整組數據
            data = yf.download(batch, period="7mo", group_by='ticker', threads=True, progress=False, timeout=20)
            
            for ticker in batch:
                df = data[ticker] if len(batch) > 1 else data
                if df.empty or len(df) < 40: continue
                
                # 檢測最近 5 天的訊號
                for lookback in range(5):
                    idx = len(df) - 1 - lookback
                    df_s = df.iloc[:idx+1]
                    
                    # 條件 1: 成交量 > 5,000 張
                    vol_val = float(df_s['Volume'].iloc[-1]) / 1000
                    if vol_val < 5000: continue
                    
                    # 條件 2: 量比 > 1.85 (5V/20V)
                    v5 = df_s['Volume'].rolling(5).mean().iloc[-1]
                    v20 = df_s['Volume'].rolling(20).mean().iloc[-1]
                    v_ratio = v5 / v20 if v20 > 0 else 0
                    if v_ratio <= 1.85: continue
                    
                    # 條件 3: K值 > 80 (Stochastic Oscillator)
                    stoch = StochasticOscillator(df_s['High'], df_s['Low'], df_s['Close'], window=9)
                    k_val = stoch.stoch().iloc[-1]
                    
                    if k_val > 80:
                        s_date = df_s.index[-1].strftime('%Y-%m-%d')
                        price = round(float(df['Close'].iloc[-1]), 2)
                        
                        # 分類 A: 短線強勢 (3日漲幅 > 20%)
                        p_old = float(df_s['Close'].iloc[-4]) if len(df_s) >= 4 else 0
                        gain = (float(df_s['Close'].iloc[-1]) - p_old) / p_old if p_old > 0 else 0
                        if gain > 0.20:
                            results_3d.append({
                                "代號": ticker, "日期": s_date, "現價": price, 
                                "漲幅": f"{gain:.1%}", "量比": round(v_ratio, 2), "張數": int(vol_val)
                            })
                        
                        # 分類 B: 半年新高
                        h_prev = df_s['Close'].shift(1).rolling(120, min_periods=1).max().iloc[-1]
                        if float(df_s['Close'].iloc[-1]) >= h_prev:
                            results_6m.append({
                                "代號": ticker, "日期": s_date, "現價": price, 
                                "量比": round(v_ratio, 2), "張數": int(vol_val)
                            })
                        break
            time.sleep(random.uniform(0.5, 1.0))
        except:
            continue
            
    status.empty()
    return pd.DataFrame(results_3d), pd.DataFrame(results_6m)

# ====== 5. 網頁 UI ======
st.title("📈 台股精準量化掃描器")

# 使用 session_state 保持掃描結果
if 'df3' not in st.session_state:
    st.session_state.df3 = pd.DataFrame()
    st.session_state.df6 = pd.DataFrame()

if st.button("🚀 啟動全市場深度掃描"):
    with st.spinner("正在抓取最新資料並執行策略分析..."):
        all_list, _ = get_all_tickers()
        st.session_state.df3, st.session_state.df6 = scan_market(all_list)
        st.success(f"掃描完畢！共處理 {len(all_list)} 檔標的。")

# 顯示分頁結果
if not st.session_state.df3.empty or not st.session_state.df6.empty:
    t1, t2 = st.tabs(["🚀 短線飆股", "🏛️ 半年新高突破"])
    
    with t1:
        st.dataframe(st.session_state.df3, use_container_width=True)
        if not st.session_state.df3.empty:
            pick1 = st.selectbox("選取股票查看 K 線", st.session_state.df3['代號'].tolist(), key="k1")
            fig1 = plot_candlestick(pick1)
            if fig1: st.plotly_chart(fig1, use_container_width=True)
            
    with t2:
        st.dataframe(st.session_state.df6, use_container_width=True)
        if not st.session_state.df6.empty:
            pick2 = st.selectbox("選取股票查看 K 線", st.session_state.df6['代號'].tolist(), key="k2")
            fig2 = plot_candlestick(pick2)
            if fig2: st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("目前尚無掃描資料，請點擊上方按鈕開始。")
