# BTC Up/Down Signal Desk

A read-only Streamlit dashboard for short-term BTC prediction markets on Polymarket US. It shows BTC spot context, a cautious momentum filter, market quote information where available, and a binary-contract stake/payoff planner.

## Deploy on Streamlit Community Cloud

1. Upload `app.py` and `requirements.txt` to the root of your GitHub repository (the top-level page, not inside a folder).
2. In Streamlit Community Cloud, choose that repository and the `main` branch.
3. Set **Main file path** to `app.py` and deploy.

## Notes

- The app is read-only. It does not log in, access accounts, or place orders.
- Public data endpoints can be unavailable or change. If a market quote cannot be parsed, open **Technical market response** to inspect the response.
- The risk planner uses contract price in cents, stake in dollars, estimated contract count, target resale value, gross profit/loss, and break-even probability before fees.
- No directional signal is shown when fresh BTC price data is unavailable.
