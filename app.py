from datetime import datetime, timezone
import math
import re
from html import escape
from urllib.parse import quote
import requests
import streamlit as st

st.set_page_config(page_title="BTC Up/Down | Signal Desk", page_icon="₿", layout="wide", initial_sidebar_state="expanded")

POLY = "https://gateway.polymarket.us"
COINBASE = "https://api.exchange.coinbase.com"
KRAKEN = "https://api.kraken.com/0/public"
DEFAULT_SLUG = "btc-updown-5m-2026-10-28-1355z"
DEFAULT_URL = f"https://polymarket.us/event/{DEFAULT_SLUG}"

st.markdown("""
<style>
:root { color-scheme: dark; }
.stApp { background: #0b1020; }
[data-testid="stHeader"] { background: rgba(11,16,32,.92); }
.block-container { max-width: 1320px; padding-top: 1.5rem; padding-bottom: 3rem; }
section[data-testid="stSidebar"] { background: #101729; border-right: 1px solid #26314a; }
.hero { padding: 1.25rem 1.4rem; border: 1px solid #293653; border-radius: 18px; background: linear-gradient(120deg,#17223b,#101729 65%,#152033); margin-bottom: 1.2rem; }
.eyebrow { color: #9aaccb; text-transform: uppercase; letter-spacing: .12em; font-size: .72rem; font-weight: 700; }
.hero h1 { margin: .35rem 0 .25rem 0; font-size: 2.1rem; letter-spacing: -.035em; }
.hero p { color: #aebbd2; margin: 0; }
.panel { background: #111a2c; border: 1px solid #293653; border-radius: 16px; padding: 1rem 1.1rem; min-height: 100%; }
.panel-label { color: #9aaccb; font-size: .78rem; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; }
.big-number { font-size: 1.65rem; font-weight: 750; letter-spacing: -.025em; margin-top: .25rem; }
.muted { color: #9eabc2; font-size: .86rem; }
.status-pill { display: inline-block; padding: .38rem .7rem; border-radius: 999px; background: #252f48; border: 1px solid #3a4969; color: #dce6fa; font-size: .8rem; font-weight: 700; }
hr { border-color: #27324a; }
div[data-testid="stMetric"] { background: #111a2c; border: 1px solid #293653; padding: 13px 15px; border-radius: 13px; }
div[data-testid="stMetricLabel"] { color: #9eabc2; }
div[data-testid="stAlert"] { border-radius: 12px; }
.stButton > button { border-radius: 10px; font-weight: 650; min-height: 2.65rem; }
[data-testid="stNumberInput"] input, [data-testid="stTextInput"] input { border-radius: 9px; }
.small-note { color: #8f9db6; font-size: .78rem; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

HEADERS = {"User-Agent": "BTC-UpDown-SignalDesk/2.0", "Accept": "application/json"}


def get_json(url, params=None, timeout=9):
    response = requests.get(url, params=params, timeout=timeout, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def pct_change(new, old):
    return ((new / old) - 1) * 100 if old else 0.0


def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    diffs = [closes[i] - closes[i - 1] for i in range(len(closes) - period, len(closes))]
    gains = sum(max(d, 0) for d in diffs) / period
    losses = sum(max(-d, 0) for d in diffs) / period
    if losses == 0:
        return 100.0 if gains else 50.0
    rs = gains / losses
    return 100 - (100 / (1 + rs))


def coinbase_btc():
    ticker = get_json(f"{COINBASE}/products/BTC-USD/ticker")
    candles = get_json(f"{COINBASE}/products/BTC-USD/candles", {"granularity": 60})
    candles = sorted(candles, key=lambda row: row[0])
    closes = [float(row[4]) for row in candles]
    if len(closes) < 16:
        raise ValueError("Not enough 1-minute candles from Coinbase")
    return {"price": float(ticker["price"]), "m1": pct_change(closes[-1], closes[-2]),
            "m5": pct_change(closes[-1], closes[-6]), "rsi": calc_rsi(closes), "source": "Coinbase"}


def kraken_btc():
    ticker_obj = get_json(f"{KRAKEN}/Ticker", {"pair": "XBTUSD"})
    ticker_row = next(iter(ticker_obj["result"].values()))
    ohlc_obj = get_json(f"{KRAKEN}/OHLC", {"pair": "XBTUSD", "interval": 1})
    rows = next((v for k, v in ohlc_obj["result"].items() if k != "last"), [])
    closes = [float(row[4]) for row in rows]
    if len(closes) < 16:
        raise ValueError("Not enough 1-minute candles from Kraken")
    return {"price": float(ticker_row["c"][0]), "m1": pct_change(closes[-1], closes[-2]),
            "m5": pct_change(closes[-1], closes[-6]), "rsi": calc_rsi(closes), "source": "Kraken"}


@st.cache_data(ttl=12, show_spinner=False)
def load_btc():
    errors = []
    for fn in (coinbase_btc, kraken_btc):
        try:
            return fn(), None
        except Exception as exc:
            errors.append(f"{fn.__name__.replace('_btc','').title()}: {exc}")
    return None, " · ".join(errors)


def slug_from_url(value):
    value = (value or "").strip()
    if not value:
        return ""
    if "polymarket.us" in value:
        return value.rstrip("/").split("/")[-1].split("?")[0]
    return value.split("?")[0].strip().strip("/")


def unwrap_dict(data):
    if isinstance(data, dict):
        for key in ("market", "data", "result", "marketData"):
            value = data.get(key)
            if isinstance(value, dict):
                return value
    return data if isinstance(data, dict) else {"response": data}


def request_first(urls):
    errors = []
    for url, params in urls:
        try:
            return get_json(url, params=params), None
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "HTTP"
            errors.append(f"{code} from {url}")
            if code not in (400, 404, 405):
                break
        except Exception as exc:
            errors.append(f"{type(exc).__name__} from {url}")
            break
    return None, "; ".join(errors)


@st.cache_data(ttl=8, show_spinner=False)
def load_market(slug):
    # The slug lookup is singular in the current public gateway; fallback to search/list patterns
    # to make errors more actionable if the gateway changes or a market is no longer listed.
    safe_slug = quote(slug, safe="-_.")
    detail, detail_err = request_first([
        (f"{POLY}/v1/market/slug/{safe_slug}", None),
        (f"{POLY}/v1/markets", {"slug": slug}),
        (f"{POLY}/v1/search", {"query": slug}),
    ])
    bbo, bbo_err = request_first([
        (f"{POLY}/v1/markets/{safe_slug}/bbo", None),
        (f"{POLY}/v1/orderbook/{safe_slug}/bbo", None),
    ])
    history, _ = request_first([(f"{POLY}/v1/price-history", {"symbol": slug, "fidelity": 1, "fixedInterval": "1m"})])
    if detail is None and bbo is None:
        return None, None, history, f"Market details: {detail_err or 'unavailable'}. Quotes: {bbo_err or 'unavailable'}"
    return detail, bbo, history, None


def find_first(obj, keys):
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and obj[key] is not None:
                return obj[key]
        for val in obj.values():
            found = find_first(val, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for val in obj:
            found = find_first(val, keys)
            if found is not None:
                return found
    return None


def to_float(value):
    try:
        if isinstance(value, dict):
            value = value.get("value", value.get("price", value.get("amount")))
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def cents(value):
    val = to_float(value)
    if val is None:
        return None
    # Most APIs return decimal dollar probabilities (0-1); some return cents (0-100).
    if 0 <= val <= 1:
        return val * 100
    if 0 <= val <= 100:
        return val
    return None


def money(value):
    return f"${value:,.2f}" if value is not None else "—"


def probability_label(price_cents):
    return f"{price_cents:.1f}¢  ·  {price_cents:.1f}%" if price_cents is not None else "Not available"


st.markdown("""
<div class="hero">
  <div class="eyebrow">Prediction market toolkit · read-only</div>
  <h1>₿ BTC Up/Down <span style="color:#8da9ff">Signal Desk</span></h1>
  <p>Fast market context, contract odds, and a simple stake planner — no automatic trading.</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Market setup")
    market_url = st.text_input("Polymarket US market URL or slug", value=DEFAULT_URL, help="Paste the full Polymarket US event link or just its market slug.")
    slug = slug_from_url(market_url)
    refresh = st.button("↻  Refresh live data", use_container_width=True, type="primary")
    if refresh:
        st.cache_data.clear()
        st.rerun()
    st.caption("Public market data only. The app never connects to your account or places orders.")
    st.divider()
    st.markdown("### Contract stake planner")
    stake = st.number_input("Stake amount ($)", min_value=1.0, max_value=10000.0, value=10.0, step=1.0, help="How much money you would put into the contract.")
    entry_odds = st.slider("Entry odds (¢ per contract)", min_value=1, max_value=99, value=50, help="A binary contract typically costs 1¢–99¢ and pays $1 if it resolves in your favor.")
    exit_odds = st.slider("Target sell odds (¢)", min_value=1, max_value=99, value=60)
    st.caption("Odds are contract prices, not sportsbook odds. A 50¢ contract costs $0.50 and pays $1 if it wins.")

btc, btc_error = load_btc()

# Topline metrics
st.markdown("#### Market pulse")
if btc:
    m1, m5, rsi = btc["m1"], btc["m5"], btc["rsi"]
    metric_cols = st.columns(4)
    metric_cols[0].metric("Bitcoin spot", money(btc["price"]))
    metric_cols[1].metric("1-minute move", f"{m1:+.3f}%")
    metric_cols[2].metric("5-minute move", f"{m5:+.3f}%")
    metric_cols[3].metric("RSI · 14", f"{rsi:.1f}" if rsi is not None else "—")
    st.caption(f"Spot reference: {btc['source']} · updated {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')} · BTC spot is context only, not the contract's settlement source.")
else:
    st.warning("Bitcoin spot feed is temporarily unavailable. The app will not create a directional signal without fresh data.")
    with st.expander("Feed diagnostics"):
        st.code(btc_error or "No details returned")

sig_col, market_col = st.columns([0.8, 1.2], gap="large")
with sig_col:
    st.markdown("#### Momentum read")
    if not btc:
        st.markdown('<div class="panel"><div class="status-pill">WAIT · NO LIVE DATA</div><p class="muted" style="margin-top:.8rem">No directional read until fresh BTC data is available.</p></div>', unsafe_allow_html=True)
    else:
        m1, m5, rsi = btc["m1"], btc["m5"], btc["rsi"]
        if m1 > 0 and m5 > 0 and rsi is not None and 50 <= rsi <= 70:
            label, detail = "WATCH · UP BIAS", "Both short windows are positive and RSI is not in the extreme zone. This is only a momentum filter, not proof of an edge."
        elif m1 < 0 and m5 < 0 and rsi is not None and 30 <= rsi <= 50:
            label, detail = "WATCH · DOWN BIAS", "Both short windows are negative and RSI is not in the extreme zone. This is only a momentum filter, not proof of an edge."
        elif rsi is not None and (rsi >= 75 or rsi <= 25):
            label, detail = "WAIT · EXTREME RSI", "Momentum may be stretched. Avoid treating a sharp move as a guaranteed continuation."
        else:
            label, detail = "WAIT · NO CLEAR EDGE", "The short-term filters are mixed. Skipping a trade is a valid decision."
        st.markdown(f'<div class="panel"><div class="status-pill">{label}</div><p style="margin-top:.85rem;margin-bottom:.4rem">{detail}</p><div class="muted">This does not estimate the chance that the contract settles Up or Down.</div></div>', unsafe_allow_html=True)

with market_col:
    st.markdown("#### Your Polymarket US contract")
    if not slug:
        st.info("Paste a market URL or slug in the sidebar to load a contract.")
        market_data = bbo_data = history = None
    else:
        with st.spinner("Checking the public market gateway…"):
            market_raw, bbo_raw, history, market_error = load_market(slug)
        market_data = unwrap_dict(market_raw) if market_raw is not None else {}
        bbo_data = unwrap_dict(bbo_raw) if bbo_raw is not None else {}
        title = str(find_first(market_data, ["title", "question", "name", "marketTitle"]) or slug)
        status = str(find_first(market_data, ["status", "state", "marketStatus"]) or ("Closed" if find_first(market_data, ["closed"]) is True else "Status unavailable"))
        st.markdown(f'<div class="panel"><div class="panel-label">Selected market</div><div style="font-size:1.12rem;font-weight:700;margin:.3rem 0 .45rem">{escape(title)}</div><span class="status-pill">{escape(status)}</span><p class="muted" style="margin-top:.7rem;margin-bottom:0">Slug: <code>{escape(slug)}</code></p></div>', unsafe_allow_html=True)
        bid_raw = find_first(bbo_data, ["bestBid", "best_bid", "bidPrice", "bid", "longBid", "yesBid"])
        ask_raw = find_first(bbo_data, ["bestAsk", "best_ask", "askPrice", "ask", "longAsk", "yesAsk"])
        bid_c, ask_c = cents(bid_raw), cents(ask_raw)
        quote_cols = st.columns(3)
        quote_cols[0].metric("Best bid · Yes/Up", probability_label(bid_c) if bid_c is not None else "—")
        quote_cols[1].metric("Best ask · Yes/Up", probability_label(ask_c) if ask_c is not None else "—")
        spread = (ask_c - bid_c) if bid_c is not None and ask_c is not None else None
        quote_cols[2].metric("Bid–ask spread", f"{spread:.1f}¢" if spread is not None else "—")
        if market_error:
            st.warning("Market details or live quotes could not be fully loaded. The market may have expired, the slug may be wrong, or the public gateway may be unavailable.")
            with st.expander("Market connection details"):
                st.code(market_error)
        if market_raw is None and bbo_raw is None:
            st.markdown(f"[Open this market on Polymarket US](https://polymarket.us/event/{slug})")
        if bbo_raw is not None and bid_c is None and ask_c is None:
            st.info("The quote connection responded, but its price fields did not match the formats this dashboard recognizes. Open the quote details below to inspect the response.")
        with st.expander("Technical market response (optional)"):
            if market_raw is not None:
                st.markdown("**Market details**")
                st.json(market_raw)
            if bbo_raw is not None:
                st.markdown("**Best bid / offer response**")
                st.json(bbo_raw)
            if history is not None:
                st.markdown("**Recent price history**")
                st.json(history)

st.divider()
st.markdown("#### Contract payoff planner")
st.caption("This calculates a simple binary contract purchase and resale. It does not send orders, and estimates exclude fees and spread.")
entry = entry_odds / 100
exit = exit_odds / 100
contracts = stake / entry if entry > 0 else 0
sale_value = contracts * exit
pnl = sale_value - stake
max_loss = stake
payout_if_win = contracts * 1.0
profit_if_held_to_win = payout_if_win - stake
breakeven_pct = entry_odds
risk_cols = st.columns(4)
risk_cols[0].metric("Estimated contracts", f"{contracts:.2f}")
risk_cols[1].metric("Target resale value", money(sale_value))
risk_cols[2].metric("Gross P/L at target", f"{'+' if pnl >= 0 else '−'}${abs(pnl):.2f}")
risk_cols[3].metric("Stake at risk", money(max_loss))
more_cols = st.columns(3)
more_cols[0].metric("Payout if correct at settlement", money(payout_if_win))
more_cols[1].metric("Profit if held and correct", f"+${profit_if_held_to_win:.2f}")
more_cols[2].metric("Break-even win rate before fees", f"{breakeven_pct:.1f}%")
if exit_odds < entry_odds:
    st.warning(f"Your target sell odds ({exit_odds}¢) are below your entry odds ({entry_odds}¢), so selling at that target would create an estimated gross loss of ${abs(pnl):.2f}.")
else:
    st.info(f"At {entry_odds}¢ entry and {exit_odds}¢ target, a ${stake:.2f} stake represents about {contracts:.2f} contracts and an estimated gross P/L of ${pnl:.2f} if sold at the target. Fees, spread, slippage, and partial fills can change the result.")

with st.expander("How to use this dashboard"):
    st.markdown("""
    - **Contract price / odds:** A binary contract often costs between 1¢ and 99¢ and pays $1 per contract if its outcome is correct. A 50¢ price is roughly a 50% market-implied probability before fees, not a guarantee.
    - **Best bid:** Approximate price buyers currently offer. **Best ask:** Approximate price sellers currently request. A trade may fill at a worse price or not fill at all.
    - **Momentum read:** Uses BTC spot momentum and RSI as context only. It does not calculate a reliable win probability or know the exact contract settlement calculation.
    - **Risk:** If a contract settles against you, you can lose the full amount paid. This planner is gross-only and does not include fees.
    - **Read-only:** No login, API keys, account access, or order placement is used.
    """)
st.markdown('<p class="small-note">Data connections: Coinbase BTC/USD with Kraken fallback; Polymarket US public gateway. Prices can be delayed, unavailable, or different from executable quotes. Always verify the contract, expiration, rules, and live bid/ask on Polymarket US before acting.</p>', unsafe_allow_html=True)
