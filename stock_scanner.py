def scan_full_market(all_tickers):
    # 只取前 5 檔進行測試
    test_tickers = all_tickers[:5] 
    st.write(f"正在測試診斷前 5 檔: {test_tickers}")
    
    try:
        data = yf.download(test_tickers, period="1mo", interval="1d", group_by='ticker', threads=True, progress=False)
        
        for ticker in test_tickers:
            df = data[ticker] if len(test_tickers) > 1 else data
            if df.empty:
                st.error(f"❌ {ticker} 下載到的資料是空的！")
                continue
            
            # 顯示這檔股票的數據摘要
            st.write(f"--- {ticker} 資料摘要 ---")
            st.write(df.tail(3)) # 顯示最後 3 天的資料
            
            # 檢查成交量格式
            vol = float(df['Volume'].iloc[-1])
            st.write(f"今日成交量 (股數): {vol:,}")
            
    except Exception as e:
        st.error(f"下載失敗: {e}")
        
    return pd.DataFrame(), pd.DataFrame()
