import streamlit as st
import pandas as pd
import yfinance as yf
from ta.momentum import StochasticOscillator
from streamlit_autorefresh import st_autorefresh
import datetime

# 設定手機適應介面
st.set_page_config(page_title="台股全市場飆股掃描", layout="wide")

# 每 30 秒自動刷新 (30000 毫秒)
st_autorefresh(interval=30000, key="data_refresh")

# 1. 取得全台股清單 (上市+上櫃)
@st.cache_data(ttl=86400)
def get_taiwan_stock_list():
    try:
        # 從證交所與櫃買中心抓取清單
        twse = pd.read_html("http://isin.twse.com.tw/isin/C_public.jsp?strMode=2")[0]
        otc = pd.read_html("http://isin.twse.com.tw/isin/C_public.jsp?strMode=4")[0]
        full = pd.concat([twse, otc])
        full.columns = full.iloc[0]
        full = full.iloc[1:]
        
        # 只抓代碼是 4 碼的普通股
        def is_stock(x):
            s = str(x).split('\u3000')
            return s[0] if len(s[1]) >= 2 and len(s[0]) == 4 else None
        
        codes = full['有價證券代號及名稱'].apply(is_stock).dropna().tolist()
        return [f"{c}.TW" for c in codes]
    except:
        return ["2330.TW", "2317.TW"] # 備援

# 2. 掃描引擎 (完全執行你的條件)
def run_scan(stock_list):
    results = []
    # 使用 threads=True 加速 1800 檔的下載速度
    data = yf.download(stock_list, period="1mo", interval="1d", group_by='ticker', threads=True)
    
    for s in stock_list:
        try:
            df = data[s].dropna()
            if len(df) < 20: continue

            # --- 你的原始條件 ---
            # 1. 量比 (5日均量 / 20日均量 > 1.85)
            vol5 = df['Volume'].rolling(5).mean().iloc[-1]
            vol20 = df['Volume'].rolling(20).mean().iloc[-1]
            vol_ratio = vol5 / vol20

            # 2. 三日漲幅 > 20% 或 三天內有兩根漲停
            close_now = df['Close'].iloc[-1]
            close_3 = df['Close'].iloc[-4]
            return3 = (close_now - close_3) / close_3
            
            df['ret'] = df['Close'].pct_change()
            # 台股漲停約 10%，設 9.8% 避免精確度落差
            limit_up_count = (df['ret'] >= 0.098).rolling(3).sum().iloc[-1]

            # 3. K 值 > 80 (KD 9,3,3)
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
            k_val = stoch.stoch().iloc[-1]

            # 最終判斷
            if (vol_ratio > 1.85) and (return3 > 0.20 or limit_up_count >= 2) and (k_val > 80):
                results.append({
                    "股票代碼": s.replace(".TW",""),
                    "價格": round(float(close_now), 2),
                    "量比": round(float(vol_ratio), 2),
                    "3日漲幅%": round(float(return3 * 100), 2),
                    "K值": round(float(k_val), 2)
                })
        except:
            continue
    return pd.DataFrame(results)

# --- 介面 ---
st.title("🔥 全台股噴發掃描器")
st.write(f"更新時間: {datetime.datetime.now().strftime('%H:%M:%S')} (每30秒自動掃描)")

codes = get_taiwan_stock_list()
st.caption(f"監控範圍：全市場 {len(codes)} 檔普通股")

# 執行並顯示表格
with st.spinner("正在掃描 1800+ 檔股票，請稍候..."):
    df_res = run_scan(codes)

if not df_res.empty:
    st.success(f"找到 {len(df_res)} 檔符合條件標的")
    st.dataframe(df_res.sort_values("量比", ascending=False), use_container_width=True)
else:
    st.info("目前全市場沒有標的符合所有條件。")