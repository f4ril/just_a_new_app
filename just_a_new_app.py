import streamlit as st
import wntr
import plotly.graph_objects as go
import pandas as pd
from streamlit_autorefresh import st_autorefresh

st.set_page_config(layout="wide")
st.title("EPANET Animated Network Visualization – Nodes and Links")

uploaded = st.file_uploader("Upload EPANET INP file", type="inp")
if uploaded:
    path = "temp.inp"
    with open(path, "wb") as f:
        f.write(uploaded.read())
    wn = wntr.network.WaterNetworkModel(path)

    node_data = []
    for n in wn.node_name_list:
        x, y = wn.get_node(n).coordinates
        node_data.append(dict(name=n, x=x, y=y))
    node_df = pd.DataFrame(node_data)
    link_data = []
    for l in wn.link_name_list:
        start = wn.get_link(l).start_node_name
        end = wn.get_link(l).end_node_name
        link_data.append(dict(name=l, start=start, end=end))
    link_df = pd.DataFrame(link_data)

    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim()
    node_vars = list(results.node.keys())
    link_vars = list(results.link.keys())
    var_type = st.radio("Variable type", ["Node", "Link"], horizontal=True)
    if var_type == "Node":
        variable = st.selectbox("Node variable", node_vars, index=node_vars.index("pressure") if "pressure" in node_vars else 0)
        data = results.node[variable]
        items = node_df
    else:
        variable = st.selectbox("Link variable", link_vars, index=link_vars.index("flowrate") if "flowrate" in link_vars else 0)
        data = results.link[variable]
        items = link_df

    num_steps = data.shape[0]

    if "animate" not in st.session_state:
        st.session_state.animate = True
    if "frame" not in st.session_state:
        st.session_state.frame = 0
    if "playing" not in st.session_state:
        st.session_state.playing = True
    if "velocity" not in st.session_state:
        st.session_state.velocity = 0.2

    animate = st.checkbox("Enable animation", value=st.session_state.animate, key="animate")
    velocity = st.slider("Animation velocity (seconds per frame)", 0.05, 2.0, st.session_state.velocity, 0.05, key="velocity")
    col1, col2, col3 = st.columns([1,1,4])
    with col1:
        if st.button("Play"):
            st.session_state.playing = True
        if st.button("Pause"):
            st.session_state.playing = False
    with col3:
        frame = st.slider("Timestep", 0, num_steps - 1, st.session_state.frame, 1)
        st.session_state.frame = frame

    if animate and st.session_state.playing and num_steps > 1:
        st_autorefresh(interval=int(velocity*1000), key="anim_refresh")
        st.session_state.frame = (st.session_state.frame + 1) % num_steps

    timestep = st.session_state.frame

    fig = go.Figure()

    if var_type == "Node":
        vals = data.iloc[timestep]
        node_df["value"] = node_df["name"].map(vals)
        for _, row in link_df.iterrows():
            n1 = node_df[node_df["name"] == row["start"]].iloc[0]
            n2 = node_df[node_df["name"] == row["end"]].iloc[0]
            fig.add_trace(go.Scatter(
                x=[n1["x"], n2["x"]], y=[n1["y"], n2["y"]],
                mode="lines", line=dict(width=2, color="#bbbbbb"),
                hoverinfo="none", showlegend=False
            ))
        fig.add_trace(go.Scatter(
            x=node_df["x"], y=node_df["y"], mode="markers",
            marker=dict(
                size=15,
                color=node_df["value"],
                colorbar=dict(title=variable),
                colorscale="Viridis",
                line=dict(width=2, color="white"),
                showscale=True
            ),
            name=variable
        ))
    else:
        vals = data.iloc[timestep]
        link_df["value"] = link_df["name"].map(vals)
        for _, row in link_df.iterrows():
            n1 = node_df[node_df["name"] == row["start"]].iloc[0]
            n2 = node_df[node_df["name"] == row["end"]].iloc[0]
            fig.add_trace(go.Scatter(
                x=[n1["x"], n2["x"]], y=[n1["y"], n2["y"]],
                mode="lines",
                line=dict(
                    width=5,
                    color=row["value"],
                    colorscale="Viridis",
                    cmin=link_df["value"].min(),
                    cmax=link_df["value"].max(),
                    colorbar=dict(title=variable) if _ == 0 else None
                ),
                showlegend=False,
                hoverinfo="text",
                text=f"{row['name']}: {row['value']:.2f}"
            ))
        fig.add_trace(go.Scatter(
            x=node_df["x"], y=node_df["y"], mode="markers",
            marker=dict(size=10, color="#222", line=dict(width=1, color="white")),
            showlegend=False
        ))

    fig.update_layout(
        title=f"{variable.capitalize()} (Timestep {timestep+1}/{num_steps})",
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False, scaleanchor="x", scaleratio=1),
        width=900, height=700, margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(color='black')
    )
    st.plotly_chart(fig, use_container_width=True)

    if st.toggle("Show result table"):
        st.dataframe(vals)

    csv = vals.to_csv().encode()
    st.download_button("Download values as CSV", csv, f"{variable}_timestep_{timestep}.csv")
