import streamlit as st
import wntr
import matplotlib.pyplot as plt

st.title("EPANET Network Viewer")

uploaded = st.file_uploader("Upload INP file", type="inp")
if uploaded:
    path = "temp.inp"
    with open(path, "wb") as f:
        f.write(uploaded.read())
    wn = wntr.network.WaterNetworkModel(path)

    st.header("Network Summary")
    st.write({
        "junctions": len(wn.junction_name_list),
        "tanks": len(wn.tank_name_list),
        "reservoirs": len(wn.reservoir_name_list),
        "pipes": len(wn.pipe_name_list),
        "pumps": len(wn.pump_name_list),
        "valves": len(wn.valve_name_list),
    })

    st.header("Visualization")
    fig, ax = plt.subplots(figsize=(8, 6))
    wntr.graphics.plot_network(wn, ax=ax, node_size=10, node_labels=False, link_labels=False)
    st.pyplot(fig)

    if st.toggle("Show node coordinates"):
        nodes = wn.node_name_list
        coords = [wn.get_node(n).coordinates for n in nodes]
        st.dataframe({"node": nodes, "x": [c[0] for c in coords], "y": [c[1] for c in coords]})
