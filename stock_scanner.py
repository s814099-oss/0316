import streamlit as st
import yfinance as yf

st.title("📊 飆股掃描器：強制診斷模式")

if st.button("執行強制診斷 (列印計算數據)"):
    # 我們隨機選一檔熱門股測試，或者你可以指定代號
    test_tickers = ["2330.TW", "2317.TW", "2454.TW"]
    
    for ticker in test_tickers:
        st.write(f"### 檢查標的: {ticker}")
        stock = yf.Ticker(ticker)
        df = stock.history(period="1mo")
        
        if df.empty:
            st.error("下載不到資料")
            continue
            
        # 計算診斷數據
        latest_vol = df['Volume'].iloc[-1] / 1000
        # 簡單計算量比：(今日成交量 / 20日均量)
        vol_ratio = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
        
        st.write(f"今日成交量(張): {latest_vol:,.0f}")
        st.write(f"今日量比值: {vol_ratio:.2f}")
        
        # 直接判斷
        if latest_vol >= 5000:
            st.write("✅ 成交量條件通過 (>= 5000 張)")
        else:
            st.write("❌ 成交量條件未通過")
            
        if vol_ratio > 1.85:
            st.write("✅ 量比條件通過 (> 1.85)")
        else:
            st.write("❌ 量比條件未通過")
