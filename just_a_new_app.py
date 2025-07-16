import streamlit as st
import wntr
import plotly.graph_objects as go
import pandas as pd
import time

st.title("EPANET Interactive Viewer & Dynamic Results")

uploaded = st.file_uploader("Upload INP file", type="inp")
if uploaded:
    path = "temp.inp"
    with open(path, "wb") as f:
        f.write(uploaded.read())
    wn = wntr.network.WaterNetworkModel(path)

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

    link_data = []
    for l in wn.link_name_list:
        start = wn.get_link(l).start_node_name
        end = wn.get_link(l).end_node_name
        link_data.append(dict(name=l, start=start, end=end))
    link_df = pd.DataFrame(link_data)

    colors = dict(junction="blue", tank="red", reservoir="green", other="gray")

    # --- Simulation ---
    st.header("Hydraulic Simulation Results")
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim()

    variable = st.selectbox("Result variable", ["pressure", "demand", "head", "leak_demand"])
    nodes = results.node[variable]
    num_steps = nodes.shape[0]

    # Animation controls
    st.subheader("Dynamic Results Animation")
    animate = st.checkbox("Enable animation")
    velocity = st.slider("Animation velocity (seconds per frame)", 0.1, 2.0, 0.5, 0.1)

    # Session state for animation
    if "frame" not in st.session_state:
        st.session_state.frame = 0
    if "playing" not in st.session_state:
        st.session_state.playing = False

    # Buttons and slider
    col1, col2, col3 = st.columns([1,1,4])
    with col1:
        if st.button("Play"):
            st.session_state.playing = True
        if st.button("Pause"):
            st.session_state.playing = False
    with col3:
        frame = st.slider("Timestep", 0, num_steps - 1, st.session_state.frame, 1)
        st.session_state.frame = frame

    # Animation logic: Only move frame if animate is enabled and playing
    if animate and st.session_state.playing:
        # Don't use st.experimental_rerun(), instead rely on autorefresh
        time.sleep(velocity)
        st.session_state.frame = (st.session_state.frame + 1) % num_steps
        st.write(f"Animating... frame: {st.session_state.frame}")
        st.experimental_rerun()  # This is the safest place for rerun (end of script)
    else:
        st.write(f"Static... frame: {st.session_state.frame}")

    timestep = st.session_state.frame
    vals = nodes.iloc[timestep]
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
        title=f"Node {variable.capitalize()} (Timestep {timestep})",
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False, scaleanchor="x", scaleratio=1),
        width=850, height=600, margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor='white'
    )
    st.plotly_chart(fig2, use_container_width=True)

    if st.toggle("Show result table"):
        st.dataframe(vals)

    csv = vals.to_csv().encode()
    st.download_button("Download values as CSV", csv, f"{variable}_timestep_{timestep}.csv")
