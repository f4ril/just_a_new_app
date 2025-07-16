import streamlit as st
import wntr
import plotly.graph_objects as go
import plotly.colors as pc
from streamlit_autorefresh import st_autorefresh

st.set_page_config(layout="wide")
st.title("EPANET Node & Link Animation — Bulletproof")

@st.cache_data(show_spinner=True)
def run_epanet(inp_bytes):
    with open("uploaded.inp", "wb") as f:
        f.write(inp_bytes)
    wn = wntr.network.WaterNetworkModel("uploaded.inp")
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim()
    return wn, results

uploaded = st.file_uploader("Upload EPANET INP file", type="inp")
if uploaded:
    wn, results = run_epanet(uploaded.read())
    node_vars = list(results.node.keys())
    link_vars = list(results.link.keys())
    node_names = wn.node_name_list
    link_names = wn.link_name_list

    node_coords = {n: wn.get_node(n).coordinates for n in node_names}
    link_df = [{"name": l,
                "start": wn.get_link(l).start_node_name,
                "end": wn.get_link(l).end_node_name}
                for l in link_names]

    node_var = st.selectbox("Node variable", node_vars, index=node_vars.index("pressure") if "pressure" in node_vars else 0)
    link_var = st.selectbox("Link variable", link_vars, index=link_vars.index("flowrate") if "flowrate" in link_vars else 0)

    node_data = results.node[node_var]
    link_data = results.link[link_var]
    num_steps = node_data.shape[0]

    # Only reset session state on new file!
    if "last_file" not in st.session_state or st.session_state.last_file != uploaded.name:
        st.session_state.frame = 0
        st.session_state.playing = True
        st.session_state.velocity = 0.2
        st.session_state.last_file = uploaded.name

    velocity = st.slider("Animation velocity (seconds per frame)", 0.05, 2.0, st.session_state.velocity, 0.05)
    c1, c2, c3 = st.columns([1,1,4])
    with c1:
        if st.button("Play"):
            st.session_state.playing = True
    with c2:
        if st.button("Pause"):
            st.session_state.playing = False
    with c3:
        frame = st.slider("Timestep", 0, num_steps - 1, st.session_state.frame, 1)
        st.session_state.frame = frame

    # Animate: only advance the frame if playing, never reset!
    if st.session_state.playing and num_steps > 1:
        st_autorefresh(interval=int(velocity * 1000), key="anim_refresh")
        st.session_state.frame = (st.session_state.frame + 1) % num_steps

    t = st.session_state.frame
    node_vals = node_data.iloc[t]
    link_vals = link_data.iloc[t]
    node_val_map = {n: node_vals[n] for n in node_names}
    link_val_map = {l: link_vals[l] for l in link_names}

    fig = go.Figure()
    vmin = min(link_vals)
    vmax = max(link_vals)
    cscale = pc.get_colorscale("Viridis")
    def val_to_color(val):
        norm = (val - vmin) / (vmax - vmin) if vmax > vmin else 0.5
        return pc.sample_colorscale(cscale, [norm])[0]
    for row in link_df:
        xs = [node_coords[row["start"]][0], node_coords[row["end"]][0]]
        ys = [node_coords[row["start"]][1], node_coords[row["end"]][1]]
        color = val_to_color(link_val_map[row["name"]])
        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="lines",
            line=dict(width=5, color=color),
            showlegend=False,
            hoverinfo="text",
            text=f"{row['name']}: {link_val_map[row['name']]:.2f}"
        ))
    node_xs = [node_coords[n][0] for n in node_names]
    node_ys = [node_coords[n][1] for n in node_names]
    node_colors = [node_val_map[n] for n in node_names]
    fig.add_trace(go.Scatter(
        x=node_xs, y=node_ys,
        mode="markers",
        marker=dict(size=15, color=node_colors, colorscale="Viridis", colorbar=dict(title=node_var), line=dict(width=2, color="white")),
        name=node_var,
        showlegend=False
    ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None],
        mode="markers",
        marker=dict(size=0.1, color=[vmin, vmax], colorscale="Viridis", colorbar=dict(title=link_var, len=0.3, y=0.2)),
        showlegend=False, hoverinfo='none'
    ))

    fig.update_layout(
        title=f"Node: {node_var} | Link: {link_var} (Timestep {t+1}/{num_steps})",
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False, scaleanchor="x", scaleratio=1),
        width=1000, height=700, margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor='white', paper_bgcolor='white', font=dict(color='black')
    )
    st.plotly_chart(fig, use_container_width=True)

    st.write(f"Nodes: {node_var} | Links: {link_var} | Timestep: {t+1}/{num_steps}")

    if st.toggle("Show node table"):
        st.dataframe(node_vals)
    if st.toggle("Show link table"):
        st.dataframe(link_vals)

    st.download_button("Download node values as CSV", node_vals.to_csv().encode(), f"{node_var}_timestep_{t}.csv")
    st.download_button("Download link values as CSV", link_vals.to_csv().encode(), f"{link_var}_timestep_{t}.csv")
