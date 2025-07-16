import streamlit as st
import wntr
import matplotlib.pyplot as plt
import imageio
import numpy as np
import tempfile
import os

st.set_page_config(layout="wide")
st.title("EPANET Animated GIF Generator")

uploaded = st.file_uploader("Upload EPANET INP file", type="inp")
if uploaded:
    path = "uploaded.inp"
    with open(path, "wb") as f:
        f.write(uploaded.read())
    wn = wntr.network.WaterNetworkModel(path)
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim()
    node_vars = list(results.node.keys())
    link_vars = list(results.link.keys())
    node_names = wn.node_name_list
    link_names = wn.link_name_list

    node_coords = {n: wn.get_node(n).coordinates for n in node_names}
    link_pairs = [(wn.get_link(l).start_node_name, wn.get_link(l).end_node_name) for l in link_names]
    node_var = st.selectbox("Node variable", node_vars, index=node_vars.index("pressure") if "pressure" in node_vars else 0)
    link_var = st.selectbox("Link variable", link_vars, index=link_vars.index("flowrate") if "flowrate" in link_vars else 0)
    node_data = results.node[node_var]
    link_data = results.link[link_var]
    num_steps = node_data.shape[0]
    gif_duration = st.slider("GIF duration (seconds)", 2, 30, 8)
    make_gif = st.button("Generate GIF")

    if make_gif:
        with st.spinner("Generating GIF..."):
            images = []
            vmin_link, vmax_link = link_data.values.min(), link_data.values.max()
            vmin_node, vmax_node = node_data.values.min(), node_data.values.max()
            with tempfile.TemporaryDirectory() as tmpdir:
                for t in range(num_steps):
                    fig, ax = plt.subplots(figsize=(10,8))
                    # Draw links
                    for i, (start, end) in enumerate(link_pairs):
                        x0, y0 = node_coords[start]
                        x1, y1 = node_coords[end]
                        val = link_data.iloc[t][link_names[i]]
                        color = plt.cm.viridis((val-vmin_link)/(vmax_link-vmin_link) if vmax_link>vmin_link else 0.5)
                        ax.plot([x0, x1], [y0, y1], color=color, linewidth=4)
                    # Draw nodes
                    node_xs = [node_coords[n][0] for n in node_names]
                    node_ys = [node_coords[n][1] for n in node_names]
                    node_c = [node_data.iloc[t][n] for n in node_names]
                    sc = ax.scatter(node_xs, node_ys, c=node_c, cmap="viridis", vmin=vmin_node, vmax=vmax_node, s=90, edgecolors='k', zorder=10)
                    ax.set_aspect('equal')
                    ax.set_title(f"Timestep {t+1}/{num_steps}")
                    ax.axis('off')
                    # Add colorbars only on first frame
                    if t==0:
                        plt.colorbar(sc, ax=ax, fraction=0.035, pad=0.04, label=node_var)
                    # Save frame
                    fname = os.path.join(tmpdir, f"frame_{t:04d}.png")
                    plt.savefig(fname, bbox_inches='tight')
                    plt.close(fig)
                    images.append(imageio.imread(fname))
            gif_bytes = imageio.mimsave(os.path.join(tmpdir, "result.gif"), images, duration=gif_duration/num_steps)
            with open(os.path.join(tmpdir, "result.gif"), "rb") as f:
                gif_data = f.read()
        st.image(gif_data, caption="EPANET Animated Results", use_column_width=True)
        st.download_button("Download GIF", gif_data, "epanet_results.gif", "image/gif")
