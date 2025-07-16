import streamlit as st
import wntr
import plotly.graph_objects as go
import pandas as pd
from streamlit_autorefresh import st_autorefresh

st.set_page_config(layout="wide")
st.title("EPANET Animated Network Visualization (Nodes and Links Together)")

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

    cvars1, cvars2 = st.columns(2)
    with cvars1:
        node_var = st.selectbox("Node variable", node_vars, index=node_vars.index("pressure") if "pressure" in node_vars else 0)
    with cvars2:
        link_var = st.selectbox("Link variable", link_vars, index=link_vars.index("flowrate") if "flowrate" in link_vars else 0)

    node_data_all = results.node[node_var]
    link_data_all = results.link[link_var]
    num_steps = node_data_all.shape[0]

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
    c1, c2, c3 = st.columns([1,1,4])
    with c1:
        if st.button("Play"):
            st.session_state.playing = True
        if st.button("Pause"):
            st.session_state.playing = False
    with c3:
        frame = st.slider("Timestep", 0, num_steps - 1, st.session_state.frame, 1)
        st.session_state.frame = frame

    # Animation: only advance if playing, animation enabled, and NOT slider-dragging
    if animate and st.session_state.playing and num_steps > 1 and not st.session_state._shown_slider_changed:
        st_autorefresh(interval=int(velocity*1000), key="anim_refresh")
        st.session_state.frame = (st.session_state.frame + 1) % num_steps

    timestep = st.session_state.frame
    node_vals = node_data_all.iloc[timestep]
    link_vals = link_data_all.iloc[timestep]
    node_df["value"] = node_df["name"].map(node_vals)
    link_df["value"] = link_df["name"].map(link_vals)

    fig = go.Figure()
    link_colors = link_df["value"]
    link_color_min = link_colors.min()
    link_color_max = link_colors.max()
    for i, row in link_df.iterrows():
        n1 = node_df[node_df["name"] == row["start"]].iloc[0]
        n2 = node_df[node_df["name"] == row["end"]].iloc[0]
        fig.add_trace(go.Scatter(
            x=[n1["x"], n2["x"]], y=[n1["y"], n2["y"]],
            mode="lines",
            line=dict(
                width=5,
                color=row["value"],
                colorscale="Viridis",
                cmin=link_color_min,
                cmax=link_color_max
            ),
            hoverinfo="text",
            text=f"{row['name']}: {row['value']:.2f}",
            showlegend=False
        ))
    fig.add_trace(go.Scatter(
        x=node_df["x"], y=node_df["y"], mode="markers",
        marker=dict(
            size=15,
            color=node_df["value"],
            colorbar=dict(title=node_var),
            colorscale="Viridis",
            line=dict(width=2, color="white"),
            showscale=True
        ),
        name=node_var
    ))

    # Add hidden scatter for link colorbar (hack: Plotly limitation in Streamlit)
    fig.add_trace(go.Scatter(
        x=[None], y=[None],
        mode="markers",
        marker=dict(
            size=0.1,
            color=[link_color_min, link_color_max],
            colorbar=dict(title=link_var, len=0.7, y=0.5),
            colorscale="Viridis",
            showscale=True
        ),
        showlegend=False,
        hoverinfo='none'
    ))

    fig.update_layout(
        title=f"Node: {node_var} | Link: {link_var} (Timestep {timestep+1}/{num_steps})",
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False, scaleanchor="x", scaleratio=1),
        width=1000, height=700, margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(color='black')
    )
    st.plotly_chart(fig, use_container_width=True)

    st.write(f"Nodes: {node_var} | Links: {link_var} | Timestep: {timestep+1}/{num_steps}")

    if st.toggle("Show node table"):
        st.dataframe(node_vals)
    if st.toggle("Show link table"):
        st.dataframe(link_vals)

    st.download_button("Download node values as CSV", node_vals.to_csv().encode(), f"{node_var}_timestep_{timestep}.csv")
    st.download_button("Download link values as CSV", link_vals.to_csv().encode(), f"{link_var}_timestep_{timestep}.csv")
