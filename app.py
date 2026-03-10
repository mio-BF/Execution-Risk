

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

group_df = pd.read_csv("weekly_risk_execution.csv")

group_df.columns = group_df.columns.str.strip()

group_df["week_end"] = pd.to_datetime(group_df["week_end"], errors="coerce")

group_df = group_df.sort_values(["Execution Group", "week_end"])

# -------------------------
# LATEST WEEK SNAPSHOT (EXECUTION GROUPS)
# -------------------------

latest_week = group_df["week_end"].max()

latest_groups = (
    group_df[group_df["week_end"] == latest_week]
    .copy()
)

red_groups = latest_groups[
    latest_groups["risk_flag"] == "Implement Changes"
]["Execution Group"].tolist()

monitor_groups = latest_groups[
    latest_groups["risk_flag"] == "Monitor"
]["Execution Group"].tolist()


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
p75 = df["execution_risk_8w"].quantile(0.75)
p90 = df["execution_risk_8w"].quantile(0.90)
p95 = df["execution_risk_8w"].quantile(0.95)

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
    y=df["execution_risk_8w"].quantile(0.90),
    line_dash="dash",
    line_color="orange",
    annotation_text="Soft Escalation Threshold"
)

fig_roll.add_hline(
    y=df["execution_risk_8w"].quantile(0.95),
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

fig_weekly_PnL = px.line(
    inst_recent,
    x="week",
    y="PnL",
    markers=True,
    title="Weekly PnL (Last 2 Months)"
)

fig_weekly_PnL.update_layout(
    xaxis_title="Week",
    yaxis_title="Weekly PnL",
    template="plotly_white"
)

fig_weekly_PnL.add_hline(
    y=0,
    line_dash="dash",
    line_color="red",
)

st.plotly_chart(fig_weekly_PnL, use_container_width=True)

fig_weekly_LR = px.line(
    inst_recent,
    x="week",
    y="LR PnL",
    markers=True,
    title="Weekly LR PnL (Last 2 Months)"
)

fig_weekly_LR.update_layout(
    xaxis_title="Week",
    yaxis_title="Weekly LR",
    template="plotly_white"
)

st.plotly_chart(fig_weekly_LR, use_container_width=True)

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

st.divider()
st.title("Execution Group Risk Monitoring")

st.subheader(f"Weekly Flag Summary ({latest_week.date()})")

if len(red_groups) > 0:
    st.error(
        f"🔴 Implement Changes Required: {', '.join(red_groups)}"
    )

if len(monitor_groups) > 0:
    st.warning(
        f"🟡 Monitor: {', '.join(monitor_groups)}"
    )

if len(red_groups) == 0 and len(monitor_groups) == 0:
    st.success("✅ No Groups Were Flagged This Week")

flag_changes = (
    group_df.sort_values("week_end")
    .groupby("Execution Group")["risk_flag"]
    .apply(lambda x: x.iloc[-1] != x.iloc[-2] if len(x) > 1 else False)
)

changed_groups = flag_changes[flag_changes].index.tolist()

if changed_groups:
    st.info(f"🔄 Flag Changed This Week: {', '.join(changed_groups)}")

groups = sorted(group_df["Execution Group"].unique())

selected_group = st.selectbox(
    "Select Execution Group",
    groups,
    key="exec_group"
)

group_filtered = (
    group_df[group_df["Execution Group"] == selected_group]
    .sort_values("week_end")
)

max_date = group_filtered["week_end"].max()
cutoff_date = max_date - pd.Timedelta(weeks=8)

group_recent = group_filtered[group_filtered["week_end"] >= cutoff_date]

latest_group = group_filtered.iloc[-1]

col1, col2, col3, col4 = st.columns(4)

col1.metric("Risk Score", round(latest_group["risk_score"], 2))
col2.metric("Risk Flag", latest_group["risk_flag"])
col3.metric("4W Rolling PnL", round(latest_group["rolling_4w_pnl"], 2))
col4.metric("Realized Vol", round(latest_group["realized_vol"], 2))


import plotly.express as px

fig_risk = px.line(
    group_recent,
    x="week_end",
    y="risk_score",
    markers=True,
    title="Risk Score Over Time"
)

fig_risk.update_layout(
    xaxis_title="Week",
    yaxis_title="Risk Score",
    template="plotly_white"
)

# Add thresholds
fig_risk.add_hline(y=30, line_dash="dash", line_color="gray", annotation_text="Monitor Threshold")
fig_risk.add_hline(y=65, line_dash="dash", line_color="red",  annotation_text="Implement Changes Threshold")

st.plotly_chart(fig_risk, use_container_width=True)


fig_pnl = px.line(
    group_recent,
    x="week_end",
    y="rolling_4w_pnl",
    markers=True,
    title="Rolling 4-Week PnL"
)

fig_pnl.update_layout(
    xaxis_title="Week",
    yaxis_title="PnL ($/M)",
    template="plotly_white"
)

st.plotly_chart(fig_pnl, use_container_width=True)


fig_vol = px.line(
    group_recent,
    x="week_end",
    y="realized_vol",
    markers=True,
    title="Realized Volatility"
)

fig_vol.update_layout(
    xaxis_title="Week",
    yaxis_title="Realized Vol",
    template="plotly_white"
)

st.plotly_chart(fig_vol, use_container_width=True)

st.divider()
st.subheader("Execution Group Risk Heatmap (Last 8 Weeks)")

# Get global last 8 weeks cutoff
global_max = group_df["week_end"].max()
global_cutoff = global_max - pd.Timedelta(weeks=8)

heatmap_df = group_df[group_df["week_end"] >= global_cutoff]

# Pivot table
heatmap_pivot = heatmap_df.pivot_table(
    index="Execution Group",
    columns="week_end",
    values="risk_score"
)

import plotly.graph_objects as go

fig_heatmap = go.Figure(
    data=go.Heatmap(
        z=heatmap_pivot.values,
        x=heatmap_pivot.columns,
        y=heatmap_pivot.index,
        colorscale="RdYlGn_r",
        zmin=0,
        zmax=100,
        colorbar=dict(title="Risk Score")
    )
)

fig_heatmap.update_layout(
    title="Risk Score Heatmap (Last 8 Weeks)",
    xaxis_title="Week",
    yaxis_title="Execution Group",
    height=500
)

st.plotly_chart(fig_heatmap, use_container_width=True)


