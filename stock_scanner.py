import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import ssl
import requests
from ta.momentum import StochasticOscillator

# 強制繞過 SSL 憑證檢查 (解決 CERTIFICATE_VERIFY_FAILED)
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

st.set_page_config(page_title="台股全市場飆股掃描器", layout="wide")

# 1. 抓取證交所所有上市股票代碼
@st.cache_data(ttl=86400)
def get_all_tickers():
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        df = pd.read_html(response.text)[0]
        df = df.iloc[1:, [0, 1]]
        df.columns = ['代號名稱', 'ISIN']
        # 提取前 4 碼數字
        df['代號'] = df['代號名稱'].str.extract(r'^(\d{4})\s')
        tickers = df['代號'].dropna().unique().tolist()
        return [f"{t}.TW" for t in tickers]
    except Exception as e:
        st.error(f"清單獲取失敗: {e}")
        return []

# 2. 核心掃描運算
def run_scanner(tickers):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 為測試穩定性，此處示範掃描前 200 檔，若要掃全市場可改為 tickers
    scan_list = tickers[:200] 
    total = len(scan_list)
    
    for i, s in enumerate(scan_list):
        progress_bar.progress((i + 1) / total)
        status_text.text(f"正在掃描 ({i+1}/{total}): {s}")
        
        try:
            # 隨機延遲避開 Yahoo 封鎖
            time.sleep(random.uniform(0.1, 0.3))
            df = yf.download(s, period="2mo", interval="1d", progress=False)
            
            if df.empty or len(df) < 20:
                continue
            
            # 處理 MultiIndex 欄位
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # 指標計算
            price = float(df['Close'].iloc[-1])
            volume = float(df['Volume'].iloc[-1])
            vol5 = df['Volume'].rolling(5).mean().iloc[-1]
            vol20 = df['Volume'].rolling(20).mean().iloc[-1]
            
            if vol20 == 0: continue
            vol_ratio = vol5 / vol20
            
            # KD 指標
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'])
            k_val = float(stoch.stoch().iloc[-1])
            
            # 你的核心條件：量比與 K 值
            if vol_ratio > 1.2 and k_val > 60:
                results.append({
                    "股票": s.replace(".TW", ""),
                    "現價": round(price, 2),
                    "成交量": int(volume),
                    "量比": round(vol_ratio, 2),
                    "K值": round(k_val, 2)
                })
        except:
            continue
            
    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(results)

# 3. 網頁介面
st.title("🚀 台股全市場飆股自動掃描")
st.markdown("---")

if st.button("開始掃描全市場"):
    tickers = get_all_tickers()
    if tickers:
        df_res = run_scanner(tickers)
        if not df_res.empty:
            st.success(f"掃描完成！符合條件標的如下：")
            # 修正後的 2026 版寬度語法
            st.dataframe(
                df_res.sort_values(by="量比", ascending=False), 
                use_container_width=True
            )
        else:
            st.warning("掃描完成，目前市場沒有符合條件的標的。")
    else:
        st.error("無法載入股票清單，請檢查連線。")
