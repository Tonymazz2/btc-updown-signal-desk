# BTC Up/Down Signal Desk — website app

This is a Streamlit web application, not a local HTML file. It performs data requests server-side, which avoids the browser `file://` CORS problem.

## Run on your Windows PC
1. Install Python 3 from https://www.python.org/downloads/ (enable “Add Python to PATH”).
2. Extract this ZIP to a folder.
3. Open Command Prompt in that folder.
4. Run:
   ```
   py -m pip install -r requirements.txt
   py -m streamlit run app.py
   ```
5. Your browser should open a local website, usually `http://localhost:8501`.

## Publish it as a website
You can upload these files to a GitHub repository and deploy them using Streamlit Community Cloud. The app runs on the hosted server, not directly in your browser. You will need to sign in and complete the hosting setup yourself; this ZIP does not automatically publish a public website.

## Notes
- Read-only market analysis only. It does not place trades or ask for account credentials.
- It uses Binance public BTC/USDT price/candle data and Polymarket US public market-data endpoints.
- Public endpoints may change or be unavailable. Verify live quotes directly on Polymarket US.
- Signal rules are simple momentum filters, not a validated profitable strategy.
