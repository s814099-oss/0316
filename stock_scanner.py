import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import requests
import urllib3
from ta.momentum import StochasticOscillator
import plotly.graph_objects as go

# 禁用警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(layout="wide", page_title="台股飆股與突破掃描器")

# ====== 取得上市櫃股票清單 ======
@st.cache_data(ttl=86400)
def get_all_tickers():
    urls = {
        "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2": "TW",  # 上市
        "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4": "TWO"  # 上櫃
    }
    all_tickers = []
    ticker_suffix = {}  # 存股票代號對應後綴
    for url, suffix in urls.items():
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=15)
        df = pd.read_html(resp.text)[0]
        symbols = df[df.iloc[:, 0].str.match(r'^\d{4}\s', na=False)].iloc[:, 0]
        for s in symbols:
            code = s.split()[0]
            all_tickers.append(code)
            ticker_suffix[code] = suffix
    return list(set(all_tickers)), ticker_suffix

# ====== 掃描全市場策略 ======
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
                if df.empty or len(df) < 30: continue
                for lookback in range(7):
                    idx = -(lookback + 1)
                    df_sub = df.iloc[:idx+1]
                    if len(df_sub) < 20: continue
                    vol_in_thousands = float(df_sub['Volume'].iloc[-1]) / 1000
                    if vol_in_thousands < 5000: continue
                    ma5 = df_sub['Volume'].rolling(5, min_periods=1).mean().iloc[-1]
                    ma20 = df_sub['Volume'].rolling(20, min_periods=1).mean().iloc[-1]
                    vol_ratio = (ma5 / ma20) if ma20 > 0 else 0
                    stoch = StochasticOscillator(df_sub['High'], df_sub['Low'], df_sub['Close'], window=9, fillna=True)
                    k = float(stoch.stoch().iloc[-1])
                    if vol_ratio > 1.85 and k > 80:
                        signal_date = df.index[idx].strftime('%Y-%m-%d')
                        latest_close = float(df['Close'].iloc[-1])
                        if idx <= -4:
                            prev_close = float(df['Close'].iloc[idx-3])
                            three_day_gain = (float(df['Close'].iloc[idx]) - prev_close) / prev_close
                            if three_day_gain > 0.20:
                                results_3day.append({
                                    "代號": ticker,
                                    "訊號日期": signal_date,
                                    "最新現價": round(latest_close, 2),
                                    "漲幅": f"{three_day_gain:.1%}",
                                    "量比": round(vol_ratio, 2),
                                    "成交量(張)": int(vol_in_thousands)
                                })
                        six_mo_high = df['Close'].rolling(120, min_periods=1).max().iloc[-1]
                        if float(df['Close'].iloc[idx]) >= six_mo_high:
                            results_6mo.append({
                                "代號": ticker,
                                "訊號日期": signal_date,
                                "最新現價": round(latest_close, 2),
                                "半年高點": round(six_mo_high, 2),
                                "量比": round(vol_ratio, 2),
                                "成交量(張)": int(vol_in_thousands)
                            })
                        break
            time.sleep(random.uniform(1, 2))
        except Exception:
            continue
    return pd.DataFrame(results_3day), pd.DataFrame(results_6mo)

# ====== 畫 K 線圖 ======
def plot_candlestick(ticker, suffix):
    df = yf.download(f"{ticker}.{suffix}", period="6mo", interval="1d")
    if df.empty:
        return None
    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        increasing_line_color='green',
        decreasing_line_color='red',
        name=ticker
    )])
    fig.add_trace(go.Bar(
        x=df.index,
        y=df['Volume']/1000,
        marker_color='blue',
        name='Volume',
        yaxis='y2',
        opacity=0.3
    ))
    fig.update_layout(
        yaxis=dict(title='Price'),
        yaxis2=dict(title='Volume (千張)', overlaying='y', side='right', showgrid=False),
        xaxis=dict(title='Date'),
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(orientation='h', y=-0.2)
    )
    return fig

# ====== Streamlit UI ======
st.title("📊 飆股策略精準掃描器")

if st.button("啟動全市場掃描"):
    with st.spinner("掃描中，請稍候..."):
        all_tickers, ticker_suffix = get_all_tickers()
        df_3day, df_6mo = scan_full_market(all_tickers)
        st.success(f"✅ 掃描完成！總共處理 {len(all_tickers)} 檔股票。")

        tab1, tab2 = st.tabs(["短線噴出", "半年新高"])

        with tab1:
            st.subheader("🚀 短線噴出 (3天漲幅 > 20%)")
            st.dataframe(df_3day, use_container_width=True)
            if not df_3day.empty:
                selected_stock = st.selectbox("選擇股票查看K線", df_3day['代號'].tolist())
                if selected_stock:
                    suffix = ticker_suffix.get(selected_stock, "TW")
                    fig = plot_candlestick(selected_stock, suffix)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.subheader("📈 中線突破 (半年新高)")
            st.dataframe(df_6mo, use_container_width=True)
            if not df_6mo.empty:
                selected_stock = st.selectbox("選擇股票查看K線 (半年新高)", df_6mo['代號'].tolist())
                if selected_stock:
                    suffix = ticker_suffix.get(selected_stock, "TW")
                    fig = plot_candlestick(selected_stock, suffix)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
