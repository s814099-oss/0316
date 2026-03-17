import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
from ta.momentum import StochasticOscillator

st.set_page_config(layout="wide", page_title="📊 台股飆股掃描器")

# ===============================
# 1️⃣ 取得上市上櫃股票清單 (每天快取)
# ===============================
@st.cache_data(ttl=86400)
def get_all_tickers():
    urls = {
        "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2": "TW",   # 上市
        "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4": "TWO"  # 上櫃
    }
    all_tickers = []
    for url, suffix in urls.items():
        # 用 read_html 抓表格
        try:
            df = pd.read_html(url, header=0)[0]
            symbols = df[df.iloc[:,0].str.match(r"^\d{4}\s", na=False)].iloc[:,0]
            all_tickers.extend([f"{s.split()[0]}.{suffix}" for s in symbols])
        except Exception as e:
            st.warning(f"抓取股票清單失敗: {url}")
            continue
    return list(set(all_tickers))

# ===============================
# 2️⃣ 下載歷史股價 (快取 6 小時)
# ===============================
@st.cache_data(ttl=21600)
def download_stock_data(tickers):
    batch_size = 30
    batches = [tickers[i:i+batch_size] for i in range(0, len(tickers), batch_size)]
    all_data = {}
    for i, batch in enumerate(batches):
        try:
            data = yf.download(batch, period="6mo", interval="1d", group_by='ticker', threads=True, progress=False)
            for ticker in batch:
                df = data[ticker] if len(batch) > 1 else data
                all_data[ticker] = df
            time.sleep(random.uniform(1, 2))  # 避免被封鎖
        except Exception:
            continue
    return all_data

# ===============================
# 3️⃣ 扫描策略
# ===============================
def scan_strategies(all_data):
    results_3day = []
    results_6mo = []
    
    for ticker, df in all_data.items():
        if df.empty or len(df) < 30: 
            continue
        
        # 最近7天回溯
        for idx in range(-1, -8, -1):
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
                
                # 策略 A: 3天漲幅 > 20%
                if idx <= -4:
                    prev_close = float(df['Close'].iloc[idx-3])
                    three_day_gain = (float(df['Close'].iloc[idx]) - prev_close) / prev_close
                    if three_day_gain > 0.20:
                        results_3day.append({
                            "代號": ticker.split('.')[0],
                            "訊號日期": signal_date,
                            "最新現價": round(latest_close, 2),
                            "漲幅": f"{three_day_gain:.1%}",
                            "量比": round(vol_ratio,2),
                            "成交量(張)": int(vol_in_thousands)
                        })
                
                # 策略 B: 半年新高
                six_mo_high = df['Close'].rolling(120, min_periods=1).max().iloc[-1]
                if float(df['Close'].iloc[idx]) >= six_mo_high:
                    results_6mo.append({
                        "代號": ticker.split('.')[0],
                        "訊號日期": signal_date,
                        "最新現價": round(latest_close, 2),
                        "半年高點": round(six_mo_high,2),
                        "量比": round(vol_ratio,2),
                        "成交量(張)": int(vol_in_thousands)
                    })
                break
    return pd.DataFrame(results_3day), pd.DataFrame(results_6mo)

# ===============================
# 4️⃣ Streamlit UI
# ===============================
st.title("📈 台股飆股掃描器 (手機版友好)")

if st.button("啟動全市場掃描"):
    with st.spinner("掃描中，請稍候..."):
        all_tickers = get_all_tickers()
        all_data = download_stock_data(all_tickers)
        df_3day, df_6mo = scan_strategies(all_data)
    
    st.success(f"✅ 掃描完成！共處理 {len(all_tickers)} 檔股票。")
    
    # Tabs 手機友好
    tab1, tab2 = st.tabs(["短線噴出(3天>20%)", "半年新高"])
    
    with tab1:
        st.dataframe(df_3day, use_container_width=True)
        if not df_3day.empty:
            st.download_button("下載短線噴出 CSV", df_3day.to_csv(index=False), file_name="short_term.csv")
    with tab2:
        st.dataframe(df_6mo, use_container_width=True)
        if not df_6mo.empty:
            st.download_button("下載半年新高 CSV", df_6mo.to_csv(index=False), file_name="six_month_high.csv")
