"""Streamlit dashboard: 6 panel theo contract config/dashboard.yaml, nguồn data/logs.jsonl."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"]


def load_logs() -> pd.DataFrame:
    rows = []
    if LOG_PATH.exists():
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    df = pd.DataFrame(rows)
    if not df.empty and "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    return df


def threshold_status(value: float, threshold: dict) -> tuple[str, bool]:
    op = threshold["operator"]
    limit = threshold["value"]
    ok = value <= limit if op == "lte" else value >= limit
    return ("🟢 OK" if ok else "🔴 VI PHẠM SLO"), ok


def panel_latency(df: pd.DataFrame, cfg: dict, window_start: pd.Timestamp) -> None:
    sent = df[(df.get("event") == "response_sent") & (df["ts"] >= window_start)]
    st.subheader(f"1. {cfg['title']}  (unit: {cfg['unit']})")
    if sent.empty:
        st.info("Chưa có dữ liệu response_sent trong cửa sổ thời gian.")
        return
    p50, p95, p99 = sent["latency_ms"].quantile([0.5, 0.95, 0.99])
    status, _ = threshold_status(p95, cfg["threshold"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("P50 (ms)", f"{p50:.0f}")
    c2.metric("P95 (ms)", f"{p95:.0f}")
    c3.metric("P99 (ms)", f"{p99:.0f}")
    c4.metric("SLO (P95 <= 3000ms)", status)
    fig = go.Figure(go.Scatter(x=sent["ts"], y=sent["latency_ms"], mode="markers+lines", name="latency_ms"))
    fig.add_hline(y=cfg["threshold"]["value"], line_dash="dash", line_color="red",
                  annotation_text=f"threshold p95={cfg['threshold']['value']}ms")
    st.plotly_chart(fig, use_container_width=True)


def panel_traffic(df: pd.DataFrame, cfg: dict, window_start: pd.Timestamp) -> None:
    recv = df[(df.get("event") == "request_received") & (df["ts"] >= window_start)]
    st.subheader(f"2. {cfg['title']}  (unit: {cfg['unit']})")
    if recv.empty:
        st.info("Chưa có request_received trong cửa sổ thời gian.")
        return
    per_min = recv.set_index("ts").resample("1min").size().rename("requests_per_minute")
    rate = per_min.mean()
    status, _ = threshold_status(rate, cfg["threshold"])
    c1, c2 = st.columns(2)
    c1.metric("Tổng requests", len(recv))
    c2.metric("Avg req/phút (SLO >= 1)", f"{rate:.2f}  {status}")
    st.bar_chart(per_min)


def panel_errors(df: pd.DataFrame, cfg: dict, window_start: pd.Timestamp) -> None:
    recv = df[(df.get("event") == "request_received") & (df["ts"] >= window_start)]
    failed = df[(df.get("event") == "request_failed") & (df["ts"] >= window_start)]
    st.subheader(f"3. {cfg['title']}  (unit: {cfg['unit']})")
    total = len(recv)
    error_rate = (len(failed) / total * 100) if total else 0.0
    status, _ = threshold_status(error_rate, cfg["threshold"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Requests", total)
    c2.metric("Failed", len(failed))
    c3.metric("Error rate % (SLO <= 2%)", f"{error_rate:.2f}  {status}")
    if not failed.empty and "error_type" in failed.columns:
        st.bar_chart(failed["error_type"].value_counts())
    else:
        st.caption("Không có lỗi nào trong cửa sổ thời gian.")


def panel_cost(df: pd.DataFrame, cfg: dict, window_start: pd.Timestamp) -> None:
    sent = df[(df.get("event") == "response_sent") & (df["ts"] >= window_start)]
    st.subheader(f"4. {cfg['title']}  (unit: {cfg['unit']})")
    if sent.empty:
        st.info("Chưa có dữ liệu cost trong cửa sổ thời gian.")
        return
    total_cost = sent["cost_usd"].sum()
    status, _ = threshold_status(total_cost, cfg["threshold"])
    c1, c2 = st.columns(2)
    c1.metric("Tổng cost (USD)", f"{total_cost:.4f}")
    c2.metric("SLO (<= $2.5 / 60 phút)", status)
    per_min = sent.set_index("ts").resample("1min")["cost_usd"].sum()
    st.bar_chart(per_min)


def panel_tokens(df: pd.DataFrame, cfg: dict, window_start: pd.Timestamp) -> None:
    sent = df[(df.get("event") == "response_sent") & (df["ts"] >= window_start)]
    st.subheader(f"5. {cfg['title']}  (unit: {cfg['unit']})")
    if sent.empty:
        st.info("Chưa có dữ liệu token trong cửa sổ thời gian.")
        return
    tokens_in = sent["tokens_in"].sum()
    tokens_out = sent["tokens_out"].sum()
    status, _ = threshold_status(tokens_in + tokens_out, cfg["threshold"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Tokens in", int(tokens_in))
    c2.metric("Tokens out", int(tokens_out))
    c3.metric("SLO (tong <= 50000)", status)
    st.bar_chart(pd.DataFrame({"tokens_in": [tokens_in], "tokens_out": [tokens_out]}).T.rename(columns={0: "count"}))


def panel_quality(df: pd.DataFrame, cfg: dict, window_start: pd.Timestamp) -> None:
    sent = df[(df.get("event") == "response_sent") & (df["ts"] >= window_start)]
    st.subheader(f"6. {cfg['title']}  (unit: {cfg['unit']})")
    if sent.empty:
        st.info("Chưa có dữ liệu quality_score trong cửa sổ thời gian.")
        return
    mean_q = sent["quality_score"].mean()
    status, _ = threshold_status(mean_q, cfg["threshold"])
    c1, c2 = st.columns(2)
    c1.metric("Mean quality_score", f"{mean_q:.2f}")
    c2.metric("SLO (>= 0.75)", status)
    fig = go.Figure(go.Scatter(x=sent["ts"], y=sent["quality_score"], mode="markers+lines"))
    fig.add_hline(y=cfg["threshold"]["value"], line_dash="dash", line_color="red",
                  annotation_text=f"threshold={cfg['threshold']['value']}")
    st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="Day 13 AI Observability", layout="wide")
    cfg = load_config()
    st.title(cfg["title"])

    now = datetime.now(timezone.utc)
    window_minutes = cfg["time_range_minutes"]
    window_start = pd.Timestamp(now - timedelta(minutes=window_minutes))

    st.caption(
        f"Time range: last {window_minutes} minutes (now = {now.strftime('%Y-%m-%d %H:%M:%S UTC')}) "
        f"| Refresh: every {cfg['refresh_seconds']}s (bấm 'R' hoặc nút Rerun để làm mới) "
        f"| Source: data/logs.jsonl"
    )

    df = load_logs()
    if df.empty:
        st.warning("data/logs.jsonl trống. Chạy API + load_test.py trước.")
        return

    panels = {p["id"]: p for p in cfg["panels"]}
    panel_latency(df, panels["latency"], window_start)
    panel_traffic(df, panels["traffic"], window_start)
    panel_errors(df, panels["errors"], window_start)
    panel_cost(df, panels["cost"], window_start)
    panel_tokens(df, panels["tokens"], window_start)
    panel_quality(df, panels["quality"], window_start)


if __name__ == "__main__":
    main()
