# ---------- LIBRARIES ----------

import streamlit as st

st.set_page_config(page_title="Next Steps", layout="wide")

# ----- White Bar Remover -----
st.markdown("""
<style>
/* Remove the white bar / header background */
header[data-testid="stHeader"] {
    background: linear-gradient(180deg, #004e92, #000428);
}

/* Also color the toolbar (Deploy / menu) area */
header[data-testid="stHeader"] .st-emotion-cache-1dp5vir {
    background: transparent;
}
</style>
""", unsafe_allow_html=True)

# ----- Page Style -----
st.markdown("""
<style>
.stApp {
    background: linear-gradient(180deg, #004e92, #000428);
}
h1, h2, h3, p {
    color: white !important;
}
.divider {
    border-left: 2px solid #ddd;
    min-height: 400px;
    margin: auto;
}
</style>
""", unsafe_allow_html=True)

st.title("Next Steps")

# ----- Columns -----
col1, divider1, col2, divider2, col3 = st.columns([3,0.2,3,0.2,3])

with divider1:
    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
with divider2:
    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# Column 1 - Countries
with col1:
    st.markdown("### More Countries")
    st.markdown("<br>", unsafe_allow_html=True)

    for img, label in [
        ("france.png", "France"),
        ("italy.png", "Italy"),
        ("germany.png", "Germany"),
        ("spain.png", "Spain"),
    ]:
        c1, c2 = st.columns([1,3])
        with c1:
            st.image(f"whats_left_llm/images/{img}", width=40)
        with c2:
            st.markdown(f"**{label}**")
        st.markdown("<br>", unsafe_allow_html=True)

# Column 2 - Jobs
with col2:
    st.markdown("### More Jobs")
    st.markdown("<br>", unsafe_allow_html=True)
    for img, label in [
        ("construction.png", "Blue-Collar Jobs"),
        ("teacher.png", "Educators"),
        ("police.png", "Public Servants"),
        ("scientist.png", "Scientists"),
    ]:
        c1, c2 = st.columns([1,3])
        with c1:
            st.image(f"whats_left_llm/images/{img}", width=40)
        with c2:
            st.markdown(f"**{label}**")
        st.markdown("<br>", unsafe_allow_html=True)

# Column 3 - Expenses
with col3:
    st.markdown("### Personalized Expenses")
    st.markdown("<br>", unsafe_allow_html=True)

    for img, label in [
        ("weightlifting.png", "Gym Membership"),
        ("grocery.png", "Groceries"),
        ("public-transport.png", "Public Transport"),
        ("wi-fi.png", "Internet"),
    ]:
        c1, c2 = st.columns([1,3])
        with c1:
            st.image(f"whats_left_llm/images/{img}", width=40)
        with c2:
            st.markdown(f"**{label}**")
        st.markdown("<br>", unsafe_allow_html=True)
