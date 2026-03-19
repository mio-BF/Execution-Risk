

import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")

st.title("Execution Risk Governance Dashboard")

tab1, tab2, tab3, tab4 = st.tabs([
    "Instrument Risk",
    "Execution Group Risk",
    "Monthly Passing Rates by Country",
    "Weekly Passing Rates by Account Size"
])

# -------------------------
# LOAD DATA
# -------------------------

 #Option 1: load from CSV
df = pd.read_csv("weekly_risk_output.csv")

group_df = pd.read_csv("weekly_risk_execution.csv")

group_df.columns = group_df.columns.str.strip()

group_df["week_end"] = pd.to_datetime(group_df["week_end"], errors="coerce")

group_df = group_df.sort_values(["Execution Group", "week_end"])

country_df = pd.read_csv("passing_rates_monthly_Country.csv")
country_df["Date"] = pd.to_datetime(country_df["Date"])

account_w_df = pd.read_csv("passing_rates_weekly_Account.csv")
account_w_df['Week'] = pd.to_datetime(account_w_df['Week'])


# Get previous week risk
df_sorted = df.sort_values(["Instrument", "week"])

df_sorted["prev_risk"] = (
    df_sorted.groupby("Instrument")["execution_risk_8w"].shift(1)
)


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

df = df.sort_values(["Instrument", "week"])

df["prev_risk"] = (
    df.groupby("Instrument")["execution_risk_8w"].shift(1)
)

df = df.sort_values(["week", "execution_risk_8w"], ascending=[True, False])

df["rank"] = df.groupby("week")["execution_risk_8w"] \
               .rank(method="min", ascending=False)
df["prev_rank"] = df.groupby("Instrument")["rank"].shift(1)



# Latest week per instrument
latest = (
    df.sort_values("week")
      .groupby("Instrument")
      .tail(1)
      .reset_index(drop=True)
)

latest["rank_change"] = latest["prev_rank"] - latest["rank"]


# Compute percentiles on CURRENT distribution
p75 = df["execution_risk_8w"].quantile(0.75)
p95 = df["execution_risk_8w"].quantile(0.95)

def assign_band(score):
    if score >= p95:
        return "Hard Review"
    elif score >= p75:
        return "Monitor"
    else:
        return "Normal"

latest["band"] = latest["band"]

latest["prev_band"] = latest.groupby("Instrument")["band"].shift(1)
latest["strong_recovery"] = latest["PnL ($/M)"] > 0

def apply_recovery_override(row):
    if row["prev_band"] == "Hard Review" and row["strong_recovery"]:
        return "Monitor"
    return row["band"]

latest["band"] = latest.apply(apply_recovery_override, axis=1)


# Calculate change
latest["risk_change"] = latest["execution_risk_8w"] - latest["prev_risk"]

def format_rank_change(x):
    if pd.isna(x):
        return ""
    elif x > 0:
        return f"+{int(x)} 🔴"
    elif x < 0:
        return f"{int(x)} 🟢"
    else:
        return "0 🟰"

latest["Trend"] = latest["rank_change"].apply(format_rank_change)



with tab1:

# -------------------------
# KPI SUMMARY
# -------------------------

    hard = (latest["band"] == "Hard Review").sum()
    monitor = (latest["band"] == "Monitor").sum()
    normal = (latest["band"] == "Normal").sum()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Hard Review", hard)
    col2.metric("Monitor", monitor)
    col3.metric("Normal", normal)

    st.divider()

# -------------------------
# RISK RANKING TABLE
# -------------------------

    st.subheader("Instrument Risk Ranking")

    ranking = latest.sort_values("execution_risk_8w", ascending=False)

    display_df = ranking[
    [
        "Instrument",
        "execution_risk_8w",
        "weekly_risk_score",
        "pct_system",
        "band",
        "Trend"
    ]
    ].copy()


# Round values
    display_df["execution_risk_8w"] = display_df["execution_risk_8w"].round(2)
    display_df["weekly_risk_score"] = display_df["weekly_risk_score"].round(2)
    display_df["pct_system"] = display_df["pct_system"].round(1)

# Rename columns
    display_df = display_df.rename(columns={
    "execution_risk_8w": "Rolling 8 Week Execution Risk",
    "weekly_risk_score": "Weekly Risk Score",
    "pct_system": "System Percentage",
    "band": "Band"
     })

    display_df["System Percentage"] = display_df["System Percentage"].astype(str) + "%"

    def band_color(val):
        if val == "Hard Review":
            return "background-color: #ff4d4d; color: white;"
        elif val == "Monitor":
            return "background-color: #ffd966;"
        else:
            return "background-color: #c6efce;"



    styled_df = display_df.style \
    .format({
        "Rolling 8 Week Execution Risk": "{:.2f}",
        "Weekly Risk Score": "{:.2f}",
        "System Percentage": "{}"   # already formatted as string with %
    }) \
    .applymap(band_color, subset=["Band"]) \
    .set_properties(subset=[
        "Rolling 8 Week Execution Risk",
        "Weekly Risk Score",
        "System Percentage"
    ], **{"text-align": "right"}) \
    .set_properties(subset=["Instrument"], **{"text-align": "left"}) \
    .set_properties(subset=["Trend"], **{"text-align": "center"})


# Display
    st.dataframe(styled_df, use_container_width=True)

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
        y=df["execution_risk_8w"].quantile(0.75),
        line_dash="dash",
        line_color="orange",
        annotation_text="Monitor Threshold"
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

    fig_weekly_volume = px.line(
        inst_recent,
        x="week",
        y="Volume",
        markers=True,
        title="Weekly Volume m$ (Last 2 Months)"
    )

    fig_weekly_LR.update_layout(
        xaxis_title="Week",
        yaxis_title="m$ ",
        template="plotly_white"
    )

    st.plotly_chart(fig_weekly_volume, use_container_width=True)

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


    latest_inst_row = inst_df.iloc[-1]
    contributions = {
    "Bad Week": 1.0 * latest_inst_row["bad_week"],
    "System Hurt": 1.5 * latest_inst_row["material_system_hurt"],
    "Consecutive Losses": 2.0 * latest_inst_row["consecutive_bad"],
    "Excess Severity": 0.5 * latest_inst_row["excess_severity"],
    "Trend Penalty": 0.5 * latest_inst_row["trend_penalty"]
    }

    contrib_df = pd.DataFrame({
    "Component": list(contributions.keys()),
    "Contribution": list(contributions.values())
    })

    total_risk = latest_inst_row["weekly_risk_score"]

    if total_risk == 0:
        contrib_df["Percentage"] = 0
    else:
        contrib_df["Percentage"] = (
        contrib_df["Contribution"] / total_risk * 100
    )

    contrib_df = contrib_df.sort_values("Percentage", ascending=True)

    st.subheader("Risk Decomposition (Latest Week)")

    import plotly.express as px

    fig_decomp = px.bar(
    contrib_df,
    x="Percentage",
    y="Component",
    orientation="h",
    title="Weekly Risk Contribution (%)",
    text="Percentage"
    )

    fig_decomp.update_traces(
    texttemplate="%{text:.1f}%",
    textposition="outside"
    )

    fig_decomp.update_layout(
    template="plotly_white",
    xaxis_title="Contribution (%)",
    yaxis_title="",
    height=350,
    xaxis=dict(range=[0, 100])
    )

    st.plotly_chart(fig_decomp, use_container_width=True)

with tab2:
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

    groups = sorted(
        group_df["Execution Group"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

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
    fig_risk.add_hline(y=30, line_dash="dash", line_color="gray", annotation_text="Monitor     Threshold")
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
    st.subheader("Risk Score Decomposition (Latest Week)")

    latest_row = group_filtered.iloc[-1]

    total_risk = latest_row["risk_score"]

    contributions = {
        "Negative Weeks": 0.15 * latest_row["score_neg_week"],
        "Streak": 0.25 * latest_row["score_streak"],
        "Drawdown": 0.25 * latest_row["score_drawdown"],
        "Regime": 0.20 * latest_row["regime_penalty"],
        "Large Drop": 0.15 * latest_row["score_large_drop"]
    }

    contrib_df = pd.DataFrame({
    "Component": list(contributions.keys()),
    "Contribution": list(contributions.values())
    })

    contrib_df["Percentage"] = (
    contrib_df["Contribution"] / total_risk * 100
    )

    if total_risk == 0:
        contrib_df["Percentage"] = 0
    else:
        contrib_df["Percentage"] = (
        contrib_df["Contribution"] / total_risk * 100
    )

    contrib_df = contrib_df.sort_values("Percentage", ascending=True)

    import plotly.express as px

    fig_decomp = px.bar(
        contrib_df,
        x="Percentage",
        y="Component",
        orientation="h",
        title="Risk Score Contribution (%)",
        text="Percentage"
    )

    fig_decomp.update_traces(
    texttemplate="%{text:.1f}%",
    textposition="outside"
    )

    fig_decomp.update_layout(
    template="plotly_white",
    xaxis_title="Contribution (%)",
    yaxis_title="",
    height=400,
    xaxis=dict(range=[0, 100])  # ensures consistent scale
    )

    

    st.plotly_chart(fig_decomp, use_container_width=True)


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

with tab3:

    st.header("Prop Firm Passing Rates")

    import plotly.graph_objects as go

    # Ensure date column is datetime
    country_df["Date"] = pd.to_datetime(country_df["Date"])

    # ---- Phase selector ----
    phase = st.selectbox(
        "Select Phase",
        sorted(country_df["Phase"].unique())
    )
    

    phase_df = country_df[country_df["Phase"] == phase]

    regions = phase_df["region"].dropna().unique()

    for region in regions:

        region_df = phase_df[phase_df["region"] == region]

        if region_df.empty:
            continue

        fig = go.Figure()

        # ---- Country lines ----
        for country, g in region_df.groupby("Country"):

            if country == "All":
                continue

            fig.add_trace(
                go.Scatter(
                    x=g["Date"],
                    y=g["Passing Rate"],
                    mode="lines+markers+text",
                    name=country,
                    opacity=0.5,
                    text=[f"{v:.1%}" for v in g["Passing Rate"]],
                    textposition="top center"
                )
            )

        # ---- Aggregate benchmark ----
        agg = (
        phase_df[["Date", "all_passing_rate"]]
        .drop_duplicates()
        .sort_values("Date")
    )

        fig.add_trace(
            go.Scatter(
            x=agg["Date"],
            y=agg["all_passing_rate"],
            mode="lines+markers+text",
            name="All (Benchmark)",
            line=dict(width=4, dash="dash"),
            text=[f"{v:.1%}" for v in agg["all_passing_rate"]],
            textposition="top center"
        )
    )
        fig.update_layout(
            title=f"Passing Rate – Phase {phase} | Region: {region}",
            xaxis_title="Month",
            yaxis_title="Passing Rate",
            yaxis=dict(range=[0, 1], tickformat=".0%"),
            hovermode="x unified",
            template="plotly_white",
            height=600
        )

        st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    st.subheader("Country Passing Rate Heatmap")

    import plotly.graph_objects as go

    # Filter for selected phase
    heat_df = country_df[country_df["Phase"] == phase].copy()

    # Remove benchmark rows if present
    heat_df = heat_df[heat_df["Country"] != "All"]

    # Create pivot table
    heat_pivot = heat_df.pivot_table(
    index="Country",
    columns="Date",
    values="Passing Rate"
    )

    # Sort countries by average pass rate (optional but helpful)
    heat_pivot = heat_pivot.loc[
        heat_pivot.mean(axis=1).sort_values(ascending=False).index
     ]

    fig_heat = go.Figure(
    data=go.Heatmap(
        z=heat_pivot.values,
        x=heat_pivot.columns,
        y=heat_pivot.index,
        colorscale="RdYlGn_r",
        zmin=0,
        zmax=1,
        colorbar=dict(title="Passing Rate")
    )
    )

    fig_heat.update_layout(
        title=f"Country Passing Rate Heatmap – Phase {phase}",
        xaxis_title="Month",
        yaxis_title="Country",
        height=600,
        template="plotly_white"
    )
  
    st.plotly_chart(fig_heat, use_container_width=True)

    st.divider()
    st.subheader("Country vs Benchmark Passing Rate Spread")

    spread_df = country_df[country_df["Phase"] == phase].copy()

    spread_df = spread_df[spread_df["Country"] != "All"]

    spread_df["spread"] = (
        spread_df["Passing Rate"] - spread_df["all_passing_rate"]
    )

    spread_pivot = spread_df.pivot_table(
    index="Country",
    columns="Date",
    values="spread"
    )

    spread_pivot = spread_pivot.loc[
        spread_pivot.mean(axis=1).sort_values(ascending=False).index
    ]

    import plotly.graph_objects as go

    fig_spread = go.Figure(
            data=go.Heatmap(
            z=spread_pivot.values,
            x=spread_pivot.columns,
            y=spread_pivot.index,
            colorscale="RdBu_r",
            zmid=0,
            colorbar=dict(title="Rate vs Benchmark")
        )
    )

    fig_spread.update_layout(
        title=f"Country Passing Rate vs Global – Phase {phase}",
        xaxis_title="Month",
        yaxis_title="Country",
        height=600,
        template="plotly_white"
    )

    st.plotly_chart(fig_spread, use_container_width=True)

with tab4: 

    st.header("Prop Firm Passing Rates")

    import plotly.graph_objects as go

    # ---- Phase selector ----
    phase = st.selectbox(
    "Select Phase",
    sorted(account_w_df["Phase"].unique()),
    key="phase_selector_tab4"
    )

    phase_df = account_w_df[account_w_df["Phase"] == phase]

    fig = go.Figure()

        # ---- Account lines ----
    for account, g in phase_df[phase_df['Account size'] != 'All'].groupby('Account size'):

        fig.add_trace(
           go.Scatter(
                x=g["Week"],
                y=g["Passing Rate"],
                mode="lines+markers+text",
                name=account,
                opacity=0.5,
                text=[f"{v:.1%}" for v in g["Passing Rate"]],
                textposition="top center"
            )
        )

        # ---- Aggregate benchmark ----
    agg = phase_df[phase_df['Account size'] == 'All']
        
    fig.add_trace(
        go.Scatter(
        x=agg["Week"],
        y=agg["Passing Rate"],
        mode="lines+markers+text",
        name="All (Benchmark)",
        line=dict(width=4, dash="dash"),
        text=[f"{v:.1%}" for v in agg["Passing Rate"]],
        textposition="top center"
    )
)
    fig.update_layout(
        title=f"Passing Rate Over Time – {phase}",
        xaxis_title="Week",
        yaxis_title="Passing Rate",
        yaxis=dict(range=[0, 1], tickformat=".0%"),
        hovermode="x unified",
        template="plotly_white",
        height=600
    )

    st.plotly_chart(fig, use_container_width=True)
    