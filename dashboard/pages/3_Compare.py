"""Compare two parameter entries side-by-side."""
import pandas as pd
import streamlit as st

from utils.data import list_parameter_entries, load_bundle_tables

st.title("Compare Bundles")

bundles = list_parameter_entries()
if not bundles:
    st.info("No parameter entries. Run the seed script.")
    st.stop()

names = [f"{e['name']}@{e['version']}" for e in bundles]
name_to_entry = dict(zip(names, bundles))

col1, col2 = st.columns(2)
with col1:
    name_a = st.selectbox("Bundle A:", names, key="cmp_a")
with col2:
    # default the second selector to a different bundle when possible
    default_b_idx = 1 if len(names) > 1 else 0
    name_b = st.selectbox("Bundle B:", names, index=default_b_idx, key="cmp_b")

if name_a == name_b:
    st.info("Select two different bundles to compare.")
    st.stop()

tables_a = load_bundle_tables(name_to_entry[name_a]["path"])
tables_b = load_bundle_tables(name_to_entry[name_b]["path"])

from upm.registry.diff import diff_tables
diff = diff_tables(tables_a, tables_b)

c1, c2, c3 = st.columns(3)
c1.metric("Added Types", f"+{len(diff.added_types)}")
c2.metric("Removed Types", f"-{len(diff.removed_types)}")
c3.metric("Changed Params", f"~{len(diff.changed_params)}")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["Added Types", "Removed Types", "Changed Parameters"])

with tab1:
    if diff.added_types:
        st.write(f"Types in **{name_b}** but not in **{name_a}**:")
        for chunk in [diff.added_types[i:i + 8] for i in range(0, len(diff.added_types), 8)]:
            st.write(", ".join(f"`{t}`" for t in chunk))
    else:
        st.info("No added types.")

with tab2:
    if diff.removed_types:
        st.write(f"Types in **{name_a}** but not in **{name_b}**:")
        for chunk in [diff.removed_types[i:i + 8] for i in range(0, len(diff.removed_types), 8)]:
            st.write(", ".join(f"`{t}`" for t in chunk))
    else:
        st.info("No removed types.")

with tab3:
    if diff.changed_params:
        rows = [{"atom_type": c.key, "field": c.field,
                 f"{name_a}": c.old_value, f"{name_b}": c.new_value}
                for c in diff.changed_params]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=400)
    else:
        st.info("No changed parameters.")

st.markdown("---")
st.text(diff.summary())
