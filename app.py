import time
from datetime import datetime
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="BTC Up/Down Signal Desk", page_icon="₿", layout="wide")

POLY = "https://gateway.polymarket.us"
BINANCE = "https://api.binance.com/api/v3"
DEFAULT_SLUG = "btc-updown-5m-2026-10-28-1355z"
DEFAULT_URL = f"https://polymarket.us/event/{DEFAULT_SLUG}"

st.markdown("""
<style>
.block-container{padding-top:1.6rem;max-width:1250px}
div[data-testid="stMetric"]{background:#111a2b;border:1px solid #263653;padding:14px;border-radius:12px}
</style>
""", unsafe_allow_html=True)

def get_json(url, params=None, timeout=10):
    r = requests.get(url, params=params, timeout=timeout, headers={"User-Agent":"BTC-UpDown-SignalDesk/1.0","Accept":"application/json"})
    r.raise_for_status()
    return r.json()

def unwrap(obj):
    if isinstance(obj, dict):
        for key in ("market", "data", "result"):
            val = obj.get(key)
            if isinstance(val, dict):
                return val
    return obj

def as_float(x):
    try:
        if isinstance(x, dict):
            x = x.get("value", x.get("price", x.get("amount")))
        return float(x)
    except (TypeError, ValueError):
        return None

def fmt_money(x):
    return "Unavailable" if x is None else f"${x:,.2f}"

def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    changes = [closes[i] - closes[i-1] for i in range(len(closes)-period, len(closes))]
    gains = sum(x for x in changes if x > 0) / period
    losses = -sum(x for x in changes if x < 0) / period
    if losses == 0:
        return 100.0
    return 100 - 100 / (1 + gains / losses)

@st.cache_data(ttl=10, show_spinner=False)
def get_btc():
    ticker = get_json(f"{BINANCE}/ticker/price", {"symbol":"BTCUSDT"})
    klines = get_json(f"{BINANCE}/klines", {"symbol":"BTCUSDT", "interval":"1m", "limit":30})
    closes = [float(k[4]) for k in klines]
    m1 = (closes[-1] / closes[-2] - 1) * 100
    m5 = (closes[-1] / closes[-6] - 1) * 100
    rsi = calculate_rsi(closes)
    return float(ticker["price"]), m1, m5, rsi

@st.cache_data(ttl=5, show_spinner=False)
def get_market(slug):
    details = get_json(f"{POLY}/v1/markets/{slug}")
    bbo = get_json(f"{POLY}/v1/markets/{slug}/bbo")
    history = None
    try:
        history = get_json(f"{POLY}/v1/price-history", {"symbol":slug, "fidelity":1, "fixedInterval":"1m"})
    except Exception:
        pass
    return details, bbo, history

st.title("₿ BTC Up/Down Signal Desk")
st.caption("Polymarket US · short-term BTC markets · read-only analysis, no automatic trading")

with st.sidebar:
    st.header("Market")
    market_url = st.text_input("Polymarket US event URL", value=DEFAULT_URL)
    slug = market_url.rstrip("/").split("/")[-1].split("?")[0].strip()
    refresh = st.button("Refresh live data", use_container_width=True)
    if refresh:
        st.cache_data.clear()
    st.divider()
    st.header("Risk planner")
    budget = st.number_input("Trade budget ($)", min_value=1.0, max_value=10000.0, value=10.0, step=1.0)
    buy_cents = st.number_input("Buy price (¢)", min_value=1, max_value=99, value=50, step=1)
    exit_cents = st.number_input("Planned exit price (¢)", min_value=1, max_value=99, value=60, step=1)
    st.caption("Estimates exclude fees, spread, slippage, and execution uncertainty.")

left, right = st.columns([1, 1], gap="large")
btc_data = None
with left:
    st.subheader("Bitcoin live context")
    try:
        btc_data = get_btc()
        price, m1, m5, rsi = btc_data
        c1,c2 = st.columns(2)
        c1.metric("BTC / USDT", fmt_money(price))
        c2.metric("Updated", datetime.now().strftime("%H:%M:%S"))
        c3,c4,c5 = st.columns(3)
        c3.metric("1-minute momentum", f"{m1:+.3f}%")
        c4.metric("5-minute momentum", f"{m5:+.3f}%")
        c5.metric("RSI (14)", "—" if rsi is None else f"{rsi:.1f}")
    except Exception as e:
        st.error(f"Bitcoin feed unavailable: {e}")
        st.info("The app runs server-side requests, avoiding browser file:// CORS issues. If this error persists, the provider or network may be unreachable.")
with right:
    st.subheader("Signal (not a prediction)")
    if btc_data:
        _, m1, m5, rsi = btc_data
        if m1 > 0 and m5 > 0 and rsi is not None and 50 <= rsi <= 70:
            st.success("WATCH · UP BIAS")
            st.write("Short-term momentum aligns upward. Check actual market price, spread, time remaining and fees before considering any trade.")
        elif m1 < 0 and m5 < 0 and rsi is not None and 30 <= rsi <= 50:
            st.error("WATCH · DOWN BIAS")
            st.write("Short-term momentum aligns downward. Check actual market price, spread, time remaining and fees before considering any trade.")
        elif rsi is not None and (rsi > 75 or rsi < 25):
            st.warning("WAIT · EXTREME RSI")
            st.write("Momentum may be stretched; avoid chasing a sharp move.")
        else:
            st.warning("WAIT · NO CLEAR EDGE")
            st.write("Momentum is mixed or not confirmed. Skipping a trade is a valid decision.")
    else:
        st.warning("WAIT · NO LIVE DATA")
        st.write("No signal is generated until fresh Bitcoin data loads.")

st.divider()
st.subheader("Your Polymarket US market")
st.caption("Market API endpoints are queried by the app server, not by the browser.")
market = bbo = history = None
if not slug:
    st.warning("Enter a valid Polymarket US event URL.")
else:
    try:
        with st.spinner("Loading market details and best bid/offer…"):
            market, bbo, history = get_market(slug)
        market = unwrap(market)
        bbo = unwrap(bbo)
        title = market.get("title") or market.get("question") or market.get("name") or slug
        st.markdown(f"**{title}**")
        status = market.get("status") or market.get("state") or ("Closed" if market.get("closed") else "Status not provided")
        st.caption(f"Market status: {status} · Slug: `{slug}`")
        sides = market.get("marketSides") or market.get("sides") or []
        if isinstance(sides, list) and sides:
            with st.expander("Market outcome details"):
                st.json(sides)
        st.write("Best bid/offer response")
        st.json(bbo)
        st.write("Market metadata")
        st.json(market)
        if history:
            st.write("Recent price history response")
            st.json(history)
    except Exception as e:
        st.error(f"Could not load this market: {e}")
        st.markdown(f"[Open your market directly]({market_url})")
        st.info("This website app makes server-side requests, so it avoids local HTML browser CORS restrictions. If the API returns 404, the endpoint or market slug may differ; if it times out, the provider/network may be unavailable.")

st.divider()
st.subheader("Risk calculator")
buy = buy_cents / 100
exit_price = exit_cents / 100
shares = budget / buy
gross = shares * (exit_price - buy)
r1,r2,r3 = st.columns(3)
r1.metric("Approx. shares before fees", f"{shares:.2f}")
r2.metric("Gross profit at planned exit", f"${gross:+.2f}")
r3.metric("Full stake at risk if shares go to $0", f"${budget:.2f}")
st.warning("A momentum signal is not a validated edge. Short-term contracts can move abruptly, and the entire stake can be lost. Start with paper trading, set a strict loss limit, and check the market's actual fee schedule and resolution terms.")

with st.expander("How to interpret this tool"):
    st.markdown("""
    - **WATCH** means the BTC momentum filters align; it is not an automatic buy instruction.
    - **WAIT** means no clear setup is present or data is missing.
    - Compare the estimated direction with the contract's executable bid/ask and remaining time.
    - The calculator is gross-only and does not account for fees, spread, slippage, or partial fills.
    - This app is read-only and never connects to your account or places orders.
    """)
st.caption("Public data: Binance BTC/USDT candles and Polymarket US public market-data gateway. Refresh manually if values appear stale.")
