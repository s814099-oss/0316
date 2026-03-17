import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import requests
import urllib3
from ta.momentum import StochasticOscillator
import plotly.graph_objects as go

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(layout="wide", page_title="台股飆股與突破掃描器")

# ====== 1. 取得上市櫃股票清單 ======
@st.cache_data(ttl=86400)
def get_all_tickers():
    urls = {
        "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2": "TW",  # 上市
        "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4": "TWO"  # 上櫃
    }
    all_tickers_with_suffix = []
    ticker_to_suffix = {} 
    
    for url, suffix in urls.items():
        try:
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=15)
            # 使用 pd.read_html 解析表格
            dfs = pd.read_html(resp.text)
            df = dfs[0]
            # 篩選出純股票（代號 4 碼且開頭符合格式）
            symbols = df[df.iloc[:, 0].str.match(r'^\d{4}\s', na=False)].iloc[:, 0]
            for s in symbols:
                code = s.split()[0]
                full_code = f"{code}.{suffix}"
                all_tickers_with_suffix.append(full_code)
                ticker_to_suffix[code] = suffix
        except Exception as e:
            st.error(f"讀取清單失敗 ({suffix}): {e}")
            
    return all_tickers_with_suffix, ticker_to_suffix

# ====== 2. 畫 K 線圖函數 ======
def plot_candlestick(full_ticker):
    # 抓取半年資料
    df = yf.download(full_ticker, period="6mo", interval="1d", progress=False)
    if df.empty:
        st.warning(f"無法取得 {full_ticker} 的圖表數據")
        return None
    
    # 計算簡單均線
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()

    fig = go.Figure()

    # K 線圖
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name="K線", increasing_line_color='#FF3333', decreasing_line_color='#00AA00'
    ))

    # 均線
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='orange', width=1), name="5MA"))
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='blue', width=1), name="20MA"))

    # 成交量 (量能圖)
    fig.add_trace(go.Bar(
        x=df.index, y=df['Volume'], name="成交量",
        marker_color='gray', opacity=0.3, yaxis='y2'
    ))

    fig.update_layout(
        title=f"{full_ticker} 歷史走勢",
        template="plotly_white",
        xaxis_rangeslider_visible=False,
        yaxis=dict(title="價格", side="left"),
        yaxis2=dict(title="成交量", overlaying="y", side="right", showgrid=False),
        height=600
    )
    return fig

# ====== 3. 掃描邏輯 ======
def scan_full_market(all_tickers):
    results_3day = []
    results_6mo = []
    
    batch_size = 25
    batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, batch in enumerate(batches):
        progress_bar.progress((i + 1) / len(batches))
        status_text.text(f"正在掃描: {i*batch_size} / {len(all_tickers)} 檔股票...")
        
        try:
            data = yf.download(batch, period="7mo", interval="1d", group_by='ticker', threads=True, progress=False)
            
            for ticker in batch:
                df = data[ticker] if len(batch) > 1 else data
                if df.empty or len(df) < 35: continue
                
                # 遍歷最近 7 天找訊號
                for lookback in range(7):
                    idx = -(lookback + 1)
                    df_sub = df.iloc[:len(df)+idx+1] # 修正切片邏輯
                    
                    if len(df_sub) < 30: continue
                    
                    # 1. 量能篩選
                    vol_now = float(df_sub['Volume'].iloc[-1]) / 1000
                    if vol_now < 5000: continue
                    
                    ma5_v = df_sub['Volume'].rolling(5).mean().iloc[-1]
                    ma20_v = df_sub['Volume'].rolling(20).mean().iloc[-1]
                    vol_ratio = ma5_v / ma20_v if ma20_v > 0 else 0
                    
                    # 2. KD 篩選
                    stoch = StochasticOscillator(df_sub['High'], df_sub['Low'], df_sub['Close'], window=9)
                    k_val = stoch.stoch().iloc[-1]
                    
                    if vol_ratio > 1.85 and k_val > 80:
                        sig_date = df_sub.index[-1].strftime('%Y-%m-%d')
                        curr_price = round(float(df['Close'].iloc[-1]), 2)
                        
                        # 策略 A: 短線噴出
                        # 檢查訊號日當天往前 3 天的漲幅
                        if len(df_sub) >= 4:
                            p_old = float(df_sub['Close'].iloc[-4])
                            p_new = float(df_sub['Close'].iloc[-1])
                            gain = (p_new - p_old) / p_old
                            if gain > 0.20:
                                results_3day.append({
                                    "代號": ticker, "訊號日期": sig_date, "現價": curr_price,
                                    "3日漲幅": f"{gain:.1%}", "量比": round(vol_ratio, 2), "張數": int(vol_now)
                                })
                        
                        # 策略 B: 半年新高
                        h_6m = df_sub['Close'].shift(1).rolling(120, min_periods=1).max().iloc[-1]
                        if float(df_sub['Close'].iloc[-1]) >= h_6m:
                            results_6mo.append({
                                "代號": ticker, "訊號日期": sig_date, "現價": curr_price,
                                "量比": round(vol_ratio, 2), "張數": int(vol_now)
                            })
                        break
            time.sleep(random.uniform(0.5, 1.0))
        except:
            continue
            
    status_text.empty()
    return pd.DataFrame(results_3day), pd.DataFrame(results_6mo)

# ====== 4. Streamlit UI ======
st.title("📊 台股飆股策略精準掃描器")

# 初始化 session_state
if 'df_3d' not in st.session_state:
    st.session_state.df_3d = pd.DataFrame()
    st.session_state.df_6m = pd.DataFrame()

if st.button("🚀 啟動全市場掃描"):
    with st.spinner("掃描中，請稍候（約需 3-5 分鐘）..."):
        all_tickers, _ = get_all_tickers()
        st.session_state.df_3d, st.session_state.df_6m = scan_full_market(all_tickers)
        st.success(f"掃描完成！共分析 {len(all_tickers)} 檔股票。")

# 顯示結果
if not st.session_state.df_3d.empty or not st.session_state.df_6m.empty:
    tab1, tab2 = st.tabs(["🔥 短線噴出強勢股", "📈 半年新高突破股"])

    with tab1:
        st.subheader("策略：3日漲幅 > 20% + 量比爆發 + K > 80")
        st.dataframe(st.session_state.df_3d, use_container_width=True)
        if not st.session_state.df_3d.empty:
            sel_1 = st.selectbox("查看股票 K 線圖 (短線)", st.session_state.df_3d['代號'].unique())
            fig1 = plot_candlestick(sel_1)
            if fig1: st.plotly_chart(fig1, use_container_width=True)

    with tab2:
        st.subheader("策略：創半年新高 + 量比爆發 + K > 80")
        st.dataframe(st.session_state.df_6m, use_container_width=True)
        if not st.session_state.df_6m.empty:
            sel_2 = st.selectbox("查看股票 K 線圖 (半年新高)", st.session_state.df_6m['代號'].unique())
            fig2 = plot_candlestick(sel_2)
            if fig2: st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("請點擊上方按鈕開始掃描。")
