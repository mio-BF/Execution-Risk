
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")

st.title("Execution Risk Governance Dashboard")

# -------------------------
# LOAD DATA
# -------------------------

 #Option 1: load from CSV
df = pd.read_csv("weekly_risk_output.csv")

# Force clean schema
df.columns = df.columns.str.strip()

if "week" not in df.columns:
    df = df.reset_index()

df["week"] = pd.to_datetime(df["week"], errors="coerce")

if df["week"].isna().all():
    st.error("Week column failed to parse.")
    st.stop()

df = df.sort_values(["Instrument", "week"])

# -------------------------
# BAND ASSIGNMENT
# -------------------------

# Latest week per instrument
latest = (
    df.sort_values("week")
      .groupby("Instrument")
      .tail(1)
      .reset_index(drop=True)
)

# Compute percentiles on CURRENT distribution
p75 = latest["execution_risk_8w"].quantile(0.75)
p90 = latest["execution_risk_8w"].quantile(0.90)
p95 = latest["execution_risk_8w"].quantile(0.95)

def assign_band(score):
    if score >= p95:
        return "Hard Review"
    elif score >= p90:
        return "Soft Escalation"
    elif score >= p75:
        return "Monitor"
    else:
        return "Normal"

latest["band"] = latest["execution_risk_8w"].apply(assign_band)



# -------------------------
# KPI SUMMARY
# -------------------------

hard = (latest["band"] == "Hard Review").sum()
soft = (latest["band"] == "Soft Escalation").sum()
monitor = (latest["band"] == "Monitor").sum()
normal = (latest["band"] == "Normal").sum()

col1, col2, col3, col4 = st.columns(4)

col1.metric("Hard Review", hard)
col2.metric("Soft Escalation", soft)
col3.metric("Monitor", monitor)
col4.metric("Normal", normal)

st.divider()

# -------------------------
# RISK RANKING TABLE
# -------------------------

st.subheader("Instrument Risk Ranking")

ranking = latest.sort_values("execution_risk_8w", ascending=False)

st.dataframe(
    ranking[
        [
            "Instrument",
            "execution_risk_8w",
            "weekly_risk_score",
            "pct_system",
            "band",
        ]
    ],
    use_container_width=True
)

st.divider()

# -------------------------
# INSTRUMENT DRILLDOWN
# -------------------------

st.subheader("Instrument Drilldown")

instrument = st.selectbox(
    "Select Instrument",
    ranking["Instrument"].unique()
)

import plotly.express as px
import pandas as pd

inst_df = (
    df[df["Instrument"] == instrument]
      .sort_values("week")
)

# Ensure datetime
inst_df["week"] = pd.to_datetime(inst_df["week"])

# Get last 8 weeks
max_date = inst_df["week"].max()
cutoff_date = max_date - pd.Timedelta(weeks=8)

inst_recent = inst_df[inst_df["week"] >= cutoff_date]


fig_roll = px.line(
    inst_recent,
    x="week",
    y="execution_risk_8w",
    markers=True,
    title="8-Week Rolling Risk (Last 2 Months)"
)

fig_roll.update_layout(
    xaxis_title="Week",
    yaxis_title="Rolling Risk Score",
    template="plotly_white"
)

fig_roll.add_hline(
    y=latest["execution_risk_8w"].quantile(0.90),
    line_dash="dash",
    line_color="orange",
    annotation_text="Soft Escalation Threshold"
)

fig_roll.add_hline(
    y=latest["execution_risk_8w"].quantile(0.95),
    line_dash="dash",
    line_color="red",
    annotation_text="Hard Review Threshold"
)

st.plotly_chart(fig_roll, use_container_width=True)


import plotly.express as px

fig_weekly = px.line(
    inst_recent,
    x="week",
    y="weekly_risk_score",
    markers=True,
    title="Weekly Risk Score (Last 2 Months)"
)

fig_weekly.update_layout(
    xaxis_title="Week",
    yaxis_title="Weekly Risk",
    template="plotly_white"
)

st.plotly_chart(fig_weekly, use_container_width=True)



# -------------------------
# ATTRIBUTION VIEW
# -------------------------

st.write("### System vs Market Attribution (Latest Week)")

latest_inst = latest[latest["Instrument"] == instrument]

pct_system = latest_inst["pct_system"].values[0]
pct_market = 100 - pct_system

attrib_df = pd.DataFrame(
    {
        "Attribution": ["System", "Market"],
        "Percentage": [pct_system, pct_market]
    }
)

st.bar_chart(attrib_df.set_index("Attribution"))

