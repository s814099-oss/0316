import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import requests
import urllib3
from ta.momentum import StochasticOscillator
import plotly.graph_objects as go
from datetime import datetime

# 1. 基礎設定與禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(layout="wide", page_title="台股飆股與突破掃描器")

# 自定義 CSS 讓表格更美觀
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stDataFrame { background-color: white; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# ====== 2. 取得上市櫃股票清單 (修復 No tables found) ======
@st.cache_data(ttl=86400)
def get_all_tickers():
    all_tickers_with_suffix = []
    ticker_to_suffix = {} 
    
    # A. 上市公司 (TWSE) - 使用 Open Data CSV 連結
    try:
        tw_url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_AVG_ALL?response=open_data"
        # 證交所 API 有時會擋無 Header 的請求
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(tw_url, headers=headers, verify=False, timeout=15)
        if r.status_code == 200:
            # 讀取 CSV，通常第一欄是代號，第二欄是名稱
            from io import StringIO
            df_tw = pd.read_csv(StringIO(r.text))
            for code in df_tw.iloc[:, 0].astype(str):
                code = code.strip()
                if len(code) == 4 and code.isdigit():
                    full_code = f"{code}.TW"
                    all_tickers_with_suffix.append(full_code)
                    ticker_to_suffix[code] = "TW"
    except Exception as e:
        st.error(f"上市清單讀取失敗 (TW): {e}")

    # B. 上櫃公司 (TPEx) - 使用 JSON API
    try:
        otc_url = "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/otc_quotes_no1430_result.php?l=zh-tw"
        resp = requests.get(otc_url, verify=False, timeout=15)
        if resp.status_code == 200:
            data = resp.json().get('aaData', [])
            for item in data:
                code = str(item[0]).strip()
                if len(code) == 4 and code.isdigit():
                    full_code = f"{code}.TWO"
                    all_tickers_with_suffix.append(full_code)
                    ticker_to_suffix[code] = "TWO"
    except Exception as e:
        st.error(f"上櫃清單讀取失敗 (TWO): {e}")
            
    # 保底機制
    if not all_tickers_with_suffix:
        st.warning("無法抓取線上清單，使用保底熱門股。")
        all_tickers_with_suffix = ["2330.TW", "2317.TW", "2454.TW", "2603.TW", "2609.TW", "2303.TW"]
        
    return list(set(all_tickers_with_suffix)), ticker_to_suffix

# ====== 3. 畫 K 線圖函數 ======
def plot_candlestick(full_ticker):
    try:
        df = yf.download(full_ticker, period="6mo", interval="1d", progress=False)
        if df.empty: return None
        
        # 計算均線
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()

        fig = go.Figure()
        # K 線
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            name="K線", increasing_line_color='#FF3333', decreasing_line_color='#00AA00'
        ))
        # 均線
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='orange', width=1.5), name="5MA"))
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='blue', width=1.5), name="20MA"))
        # 成交量
        fig.add_trace(go.Bar(
            x=df.index, y=df['Volume'], name="成交量",
            marker_color='gray', opacity=0.3, yaxis='y2'
        ))

        fig.update_layout(
            title=f"{full_ticker} 半年走勢圖",
            template="plotly_white",
            xaxis_rangeslider_visible=False,
            yaxis=dict(title="價格 (TWD)", side="left"),
            yaxis2=dict(title="成交量", overlaying="y", side="right", showgrid=False),
            height=500,
            margin=dict(t=50, b=10, l=10, r=10)
        )
        return fig
    except:
        return None

# ====== 4. 核心掃描邏輯 ======
def scan_full_market(all_tickers):
    results_3day = []
    results_6mo = []
    
    # 批次下載避免被封鎖 (25 檔一組)
    batch_size = 25
    batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, batch in enumerate(batches):
        progress_bar.progress((i + 1) / len(batches))
        status_text.text(f"🚀 掃描進度: {i*batch_size} / {len(all_tickers)} 檔...")
        
        try:
            # 抓取 7 個月資料確保 120MA 有效
            data = yf.download(batch, period="7mo", interval="1d", group_by='ticker', threads=True, progress=False, timeout=15)
            
            for ticker in batch:
                df = data[ticker] if len(batch) > 1 else data
                if df.empty or len(df) < 35: continue
                
                # 檢測最近 7 天內是否有符合條件的訊號
                for lookback in range(7):
                    idx = len(df) - 1 - lookback
                    if idx < 30: break
                    
                    df_sub = df.iloc[:idx+1]
                    
                    # 1. 門檻：成交量 > 5000 張 (台股張數 = volume / 1000)
                    vol_now = float(df_sub['Volume'].iloc[-1]) / 1000
                    if vol_now < 5000: continue
                    
                    # 2. 量比：MA5量 / MA20量 > 1.85
                    ma5_v = df_sub['Volume'].rolling(5).mean().iloc[-1]
                    ma20_v = df_sub['Volume'].rolling(20).mean().iloc[-1]
                    vol_ratio = ma5_v / ma20_v if ma20_v > 0 else 0
                    
                    # 3. K 值 > 80
                    stoch = StochasticOscillator(df_sub['High'], df_sub['Low'], df_sub['Close'], window=9)
                    k_val = stoch.stoch().iloc[-1]
                    
                    if vol_ratio > 1.85 and k_val > 80:
                        sig_date = df_sub.index[-1].strftime('%Y-%m-%d')
                        curr_price = round(float(df['Close'].iloc[-1]), 2)
                        
                        # A. 短線噴出：訊號日前 3 天漲幅 > 20%
                        if idx >= 3:
                            p_start = float(df_sub['Close'].iloc[-4])
                            p_end = float(df_sub['Close'].iloc[-1])
                            gain = (p_end - p_start) / p_start
                            if gain > 0.20:
                                results_3day.append({
                                    "代號": ticker, "日期": sig_date, "現價": curr_price,
                                    "3日漲幅": f"{gain:.1%}", "量比": round(vol_ratio, 2), "成交量": f"{int(vol_now)}張"
                                })
                        
                        # B. 中線突破：訊號日股價為 120 日新高
                        h_6m = df_sub['Close'].shift(1).rolling(120, min_periods=1).max().iloc[-1]
                        if float(df_sub['Close'].iloc[-1]) >= h_6m:
                            results_6mo.append({
                                "代號": ticker, "日期": sig_date, "現價": curr_price,
                                "前高點": round(h_6m, 2), "量比": round(vol_ratio, 2), "成交量": f"{int(vol_now)}張"
                            })
                        break # 一檔股票只要找到最近一次訊號就跳出
            # 隨機延遲保護 IP
            time.sleep(random.uniform(0.5, 1.2))
        except:
            continue
            
    status_text.empty()
    return pd.DataFrame(results_3day), pd.DataFrame(results_6mo)

# ====== 5. Streamlit UI ======
st.header("🔍 台股飆股量化掃描器")
st.info("篩選條件：1. 成交量 > 5,000張 | 2. 量比 (5V/20V) > 1.85 | 3. K 值 > 80")

# 初始化 Session State
if 'data_3d' not in st.session_state:
    st.session_state.data_3d = pd.DataFrame()
    st.session_state.data_6m = pd.DataFrame()

col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🚀 開始全市場掃描"):
        with st.spinner("掃描中...這大約需要 3 分鐘"):
            all_tickers, _ = get_all_tickers()
            st.session_state.data_3d, st.session_state.data_6m = scan_full_market(all_tickers)
            st.success(f"完成！找到 {len(st.session_state.data_3d)} 檔噴出股，{len(st.session_state.data_6m)} 檔突破股。")

# 顯示掃描結果
if not st.session_state.data_3d.empty or not st.session_state.data_6m.empty:
    tab1, tab2 = st.tabs(["🔥 短線強勢 (3天 > 20%)", "📈 中線突破 (半年新高)"])
    
    with tab1:
        st.dataframe(st.session_state.data_3d, use_container_width=True)
        if not st.session_state.data_3d.empty:
            sel = st.selectbox("選擇股票查看圖表", st.session_state.data_3d['代號'].tolist(), key="sb1")
            fig = plot_candlestick(sel)
            if fig: st.plotly_chart(fig, use_container_width=True)
            
    with tab2:
        st.dataframe(st.session_state.data_6m, use_container_width=True)
        if not st.session_state.data_6m.empty:
            sel = st.selectbox("選擇股票查看圖表", st.session_state.data_6m['代號'].tolist(), key="sb2")
            fig = plot_candlestick(sel)
            if fig: st.plotly_chart(fig, use_container_width=True)
else:
    st.write("---")
    st.write("🍵 點擊按鈕後請稍候，你可以先喝杯咖啡。")
