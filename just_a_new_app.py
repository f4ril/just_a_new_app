import streamlit as st
import wntr
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

st.set_page_config(layout="wide")
st.title("EPANET Node & Link Animation — Failsafe Version")

uploaded = st.file_uploader("Upload EPANET INP file", type="inp")
if uploaded:
    path = "uploaded.inp"
    with open(path, "wb") as f:
        f.write(uploaded.read())
    try:
        wn = wntr.network.WaterNetworkModel(path)
        sim = wntr.sim.EpanetSimulator(wn)
        results = sim.run_sim()
        node_vars = list(results.node.keys())
        link_vars = list(results.link.keys())
        node_names = wn.node_name_list
        link_names = wn.link_name_list

        # Coordinates: fail if any missing
        node_coords = {}
        for n in node_names:
            try:
                node_coords[n] = wn.get_node(n).coordinates
            except Exception:
                st.error(f"Node '{n}' is missing coordinates. Please check your INP file.")
                st.stop()

        link_coords = []
        for l in link_names:
            try:
                start = wn.get_link(l).start_node_name
                end = wn.get_link(l).end_node_name
                link_coords.append((start, end))
            except Exception:
                st.error(f"Link '{l}' is missing start/end nodes. Please check your INP file.")
                st.stop()

        node_df = [{"name": n, "x": node_coords[n][0], "y": node_coords[n][1]} for n in node_names]
        link_df = [{"name": l, "start": s, "end": e} for l, (s, e) in zip(link_names, link_coords)]

        node_var = st.selectbox("Node variable", node_vars, index=node_vars.index("pressure") if "pressure" in node_vars else 0)
        link_var = st.selectbox("Link variable", link_vars, index=link_vars.index("flowrate") if "flowrate" in link_vars else 0)

        node_data = results.node[node_var]
        link_data = results.link[link_var]
        num_steps = node_data.shape[0]

        # Animation controls
        if "frame" not in st.session_state:
            st.session_state.frame = 0
        if "playing" not in st.session_state:
            st.session_state.playing = True
        if "velocity" not in st.session_state:
            st.session_state.velocity = 0.2
        velocity = st.slider("Animation velocity (seconds per frame)", 0.05, 2.0, st.session_state.velocity, 0.05)
        play, pause, slider = st.columns([1,1,4])
        with play:
            if st.button("Play"):
                st.session_state.playing = True
        with pause:
            if st.button("Pause"):
                st.session_state.playing = False
        with slider:
            frame = st.slider("Timestep", 0, num_steps - 1, st.session_state.frame, 1)
            st.session_state.frame = frame

        # Only autorefresh if data is ready and plot is possible
        if st.session_state.playing and num_steps > 1:
            st_autorefresh(interval=int(velocity*1000), key="anim_refresh")
            st.session_state.frame = (st.session_state.frame + 1) % num_steps

        t = st.session_state.frame
        node_vals = node_data.iloc[t]
        link_vals = link_data.iloc[t]
        node_val_map = {n: node_vals[n] for n in node_names}
        link_val_map = {l: link_vals[l] for l in link_names}

        # Plot
        fig = go.Figure()

        link_cmin = min(link_vals)
        link_cmax = max(link_vals)
        for row in link_df:
            xs = [node_coords[row["start"]][0], node_coords[row["end"]][0]]
            ys = [node_coords[row["start"]][1], node_coords[row["end"]][1]]
            color = link_val_map[row["name"]]
            fig.add_trace(go.Scatter(
                x=xs, y=ys,
                mode="lines",
                line=dict(width=5, color=color, colorscale="Viridis", cmin=link_cmin, cmax=link_cmax),
                showlegend=False,
                hoverinfo="text",
                text=f"{row['name']}: {color:.2f}"
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
        # Link colorbar
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(size=0.1, color=[link_cmin, link_cmax], colorscale="Viridis", colorbar=dict(title=link_var, len=0.3, y=0.2)),
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

        if st.toggle("Show node table"):
            st.dataframe(node_vals)
        if st.toggle("Show link table"):
            st.dataframe(link_vals)

        st.download_button("Download node values as CSV", node_vals.to_csv().encode(), f"{node_var}_timestep_{t}.csv")
        st.download_button("Download link values as CSV", link_vals.to_csv().encode(), f"{link_var}_timestep_{t}.csv")

    except Exception as e:
        st.error(f"Error: {e}")
