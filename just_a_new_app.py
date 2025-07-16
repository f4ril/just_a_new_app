import streamlit as st
import wntr
import plotly.graph_objects as go
import pandas as pd

st.title("EPANET Interactive Viewer & Results")

uploaded = st.file_uploader("Upload INP file", type="inp")
if uploaded:
    path = "temp.inp"
    with open(path, "wb") as f:
        f.write(uploaded.read())
    wn = wntr.network.WaterNetworkModel(path)

    # Build dataframe of node positions and types
    node_data = []
    for n in wn.node_name_list:
        x, y = wn.get_node(n).coordinates
        if n in wn.junction_name_list:
            t = "junction"
        elif n in wn.tank_name_list:
            t = "tank"
        elif n in wn.reservoir_name_list:
            t = "reservoir"
        else:
            t = "other"
        node_data.append(dict(name=n, x=x, y=y, type=t))
    node_df = pd.DataFrame(node_data)

    # Build dataframe for links (pipes, pumps, valves)
    link_data = []
    for l in wn.link_name_list:
        start = wn.get_link(l).start_node_name
        end = wn.get_link(l).end_node_name
        link_data.append(dict(name=l, start=start, end=end))
    link_df = pd.DataFrame(link_data)

    # Interactive plot
    fig = go.Figure()
    colors = dict(junction="blue", tank="red", reservoir="green", other="gray")
    for t in node_df["type"].unique():
        df = node_df[node_df["type"] == t]
        fig.add_trace(go.Scatter(
            x=df["x"], y=df["y"], mode="markers+text",
            marker=dict(size=10, color=colors.get(t, "gray")),
            text=df["name"], textposition="top center",
            name=t.capitalize()
        ))
    for _, row in link_df.iterrows():
        n1 = node_df[node_df["name"] == row["start"]].iloc[0]
        n2 = node_df[node_df["name"] == row["end"]].iloc[0]
        fig.add_trace(go.Scatter(
            x=[n1["x"], n2["x"]], y=[n1["y"], n2["y"]],
            mode="lines", line=dict(width=2, color="gray"),
            showlegend=False
        ))
    fig.update_layout(
        title="Network (interactive)", xaxis_title="X", yaxis_title="Y",
        width=900, height=600, margin=dict(l=10, r=10, t=30, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- Run Simulation and Display Results ---
    st.header("Hydraulic Simulation Results")
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim()

    variable = st.selectbox("Result variable", ["pressure", "demand", "head", "leak_demand"])
    nodes = results.node[variable]
    timestep = st.slider("Timestep", 0, nodes.shape[0] - 1, 0)
    vals = nodes.iloc[timestep]

    # Map result values to color
    node_df["value"] = node_df["name"].map(vals)
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=node_df["x"], y=node_df["y"], mode="markers+text",
        marker=dict(size=13, color=node_df["value"], colorbar=dict(title=variable), colorscale="Viridis"),
        text=node_df["name"], textposition="top center",
        name=variable
    ))
    for _, row in link_df.iterrows():
        n1 = node_df[node_df["name"] == row["start"]].iloc[0]
        n2 = node_df[node_df["name"] == row["end"]].iloc[0]
        fig2.add_trace(go.Scatter(
            x=[n1["x"], n2["x"]], y=[n1["y"], n2["y"]],
            mode="lines", line=dict(width=2, color="gray"),
            showlegend=False
        ))
    fig2.update_layout(
        title=f"Node {variable.capitalize()} (Timestep {timestep})", xaxis_title="X", yaxis_title="Y",
        width=900, height=600, margin=dict(l=10, r=10, t=30, b=10)
    )
    st.plotly_chart(fig2, use_container_width=True)

    if st.toggle("Show result table"):
        st.dataframe(vals)

    csv = vals.to_csv().encode()
    st.download_button("Download values as CSV", csv, f"{variable}_timestep_{timestep}.csv")
