# ===== REUSABLE STYLING CODE FOR ALL PAGES =====
# Copy this entire section to each page of your Streamlit app

import streamlit as st

# ----- Page Config (Optional - customize per page) -----
st.set_page_config(page_title="Your Page Title", layout="wide")

# ----- MAIN STYLING SECTION (Copy this to all pages) -----
st.markdown("""
<style>
/* Remove the white bar / header background */
header[data-testid="stHeader"] {
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%);
    border-bottom: none;
}

/* Also color the toolbar (Deploy / menu) area */
header[data-testid="stHeader"] .st-emotion-cache-1dp5vir {
    background: transparent;
}

/* Main app background with enhanced gradient */
.stApp {
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%);
    min-height: 100vh;
}

/* All text colors */
h1, h2, h3, h4, h5, h6, p, span, div, .stMarkdown {
    color: white !important;
}

/* Title styling */
h1 {
    font-size: 2.5rem !important;
    font-weight: 600 !important;
    text-align: center;
    margin-bottom: 2rem !important;
    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
}

/* Section headers */
h3 {
    font-size: 1.5rem !important;
    font-weight: 500 !important;
    margin-bottom: 1.5rem !important;
    text-align: center;
    text-shadow: 0 1px 2px rgba(0,0,0,0.2);
}

/* Hide Streamlit elements */
.stDeployButton {
    display: none;
}

footer {
    display: none;
}

#MainMenu {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)

# ===== OPTIONAL ADDITIONAL COMPONENTS =====
# Include these only on pages where you need them

# ----- Glassmorphism Container Styling (for cards/containers) -----
glassmorphism_css = """
<style>
/* Column containers */
.column-container {
    padding: 1rem;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 15px;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
}

/* Item styling for lists/rows */
.item-row {
    display: flex;
    align-items: center;
    padding: 0.8rem 1rem;
    margin-bottom: 1rem;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    backdrop-filter: blur(5px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    transition: all 0.3s ease;
}

.item-row:hover {
    background: rgba(255, 255, 255, 0.15);
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

/* Image container */
.item-image {
    margin-right: 1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 50px;
    height: 50px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 50%;
    padding: 8px;
}

/* Item text */
.item-text {
    font-weight: 500 !important;
    font-size: 1.1rem !important;
    color: white !important;
}
</style>
"""

# ----- Divider Styling (for column separators) -----
divider_css = """
<style>
/* Enhanced divider styling */
.divider {
    border-left: 2px solid rgba(255, 255, 255, 0.3);
    min-height: 400px;
    margin: auto;
    box-shadow: 0 0 10px rgba(255, 255, 255, 0.1);
}
</style>
"""

# ===== USAGE EXAMPLES =====

# To use glassmorphism containers:
# st.markdown(glassmorphism_css, unsafe_allow_html=True)
# st.markdown("<div class='column-container'>Your content here</div>", unsafe_allow_html=True)

# To use dividers:
# st.markdown(divider_css, unsafe_allow_html=True)
# st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# ===== SIMPLIFIED VERSION FOR BASIC PAGES =====
# If you just need the background and text colors, use only this:

# ---------- BASIC PAGE STYLING ---------- #

def apply_full_styling():
    """Apply complete blue theme styling including sidebar"""
    st.markdown("""
    <style>
    /* Remove the white bar / header background */
    header[data-testid="stHeader"] {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%);
        border-bottom: none;
    }

    /* Also color the toolbar (Deploy / menu) area */
    header[data-testid="stHeader"] .st-emotion-cache-1dp5vir {
        background: transparent;
    }

    /* Main app background with enhanced gradient */
    .stApp {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%);
        min-height: 100vh;
    }

    /* All text colors */
    h1, h2, h3, h4, h5, h6, p, span, div, .stMarkdown {
        color: white !important;
    }

    /* Title styling */
    h1 {
        font-size: 2.5rem !important;
        font-weight: 600 !important;
        text-align: center;
        margin-bottom: 2rem !important;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }

    /* Section headers */
    h3 {
        font-size: 1.5rem !important;
        font-weight: 500 !important;
        margin-bottom: 1.5rem !important;
        text-align: center;
        text-shadow: 0 1px 2px rgba(0,0,0,0.2);
    }

    /* SIDEBAR STYLING */
    /* Sidebar background */
    .css-1d391kg {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%);
    }

    /* Sidebar content area */
    .stSidebar > div:first-child {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%);
    }

    /* Fix for newer Streamlit versions */
    section[data-testid="stSidebar"] {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%) !important;
    }

    section[data-testid="stSidebar"] > div {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%) !important;
    }

    /* Sidebar text colors */
    .stSidebar .stMarkdown,
    .stSidebar .stSelectbox label,
    .stSidebar .stTextInput label,
    .stSidebar .stNumberInput label,
    .stSidebar .stTextArea label,
    .stSidebar .stDateInput label,
    .stSidebar .stTimeInput label,
    .stSidebar .stFileUploader label,
    .stSidebar .stColorPicker label,
    .stSidebar .stSlider label,
    .stSidebar .stRadio label,
    .stSidebar .stCheckbox label,
    .stSidebar .stMultiSelect label,
    .stSidebar h1, .stSidebar h2, .stSidebar h3,
    .stSidebar h4, .stSidebar h5, .stSidebar h6,
    .stSidebar p, .stSidebar span, .stSidebar div {
        color: white !important;
    }

    /* Sidebar input fields */
    .stSidebar .stSelectbox select,
    .stSidebar .stTextInput input,
    .stSidebar .stNumberInput input,
    .stSidebar .stTextArea textarea {
        background: rgba(255, 255, 255, 0.1) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 5px;
    }

    /* Sidebar buttons */
    .stSidebar .stButton button {
        background: rgba(255, 255, 255, 0.1) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 8px;
        backdrop-filter: blur(5px);
        transition: all 0.3s ease;
    }

    .stSidebar .stButton button:hover {
        background: rgba(255, 255, 255, 0.2) !important;
        border-color: rgba(255, 255, 255, 0.5) !important;
        transform: translateY(-1px);
    }

    /* Hide Streamlit elements */
    .stDeployButton {
        display: none;
    }

    footer {
        display: none;
    }

    #MainMenu {
        visibility: hidden;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------- LLM CHAT STYLING ---------- #

def apply_chat_styling():
    """Apply blue theme styling for Salary Chat page (with left-aligned big title)"""
    st.markdown("""
    <style>
    /* Background + header */
    header[data-testid="stHeader"] {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%) !important;
        border-bottom: none !important;
    }
    header[data-testid="stHeader"] .st-emotion-cache-1dp5vir {
        background: transparent !important;
    }
    .stApp {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%) !important;
        min-height: 100vh !important;
    }

    /* Text */
    h1, h2, h3, h4, h5, h6, p, span, div, .stMarkdown {
        color: white !important;
    }

    /* Title */
    h1 {
        font-size: 3rem !important;     /* bigger than default */
        font-weight: 700 !important;    /* bolder */
        text-align: left !important;    /* lock to left */
        margin-bottom: 2rem !important;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3) !important;
    }

    /* Info boxes */
    .stAlert {
        background: rgba(255, 255, 255, 0.15) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 8px !important;
    }

    /* Buttons (Ask + Suggested Questions unified style) */
    .stButton button {
        background: rgba(255, 255, 255, 0.25) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 500 !important;
        backdrop-filter: blur(8px) !important;
        transition: all 0.3s ease !important;
        font-size: 1rem !important;
    }
    .stButton button:hover {
        background: rgba(255, 255, 255, 0.35) !important;
        border-color: rgba(255, 255, 255, 0.6) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3) !important;
    }

    /* Typing bar (textarea) */
    div[data-testid="stTextArea"] textarea {
        background-color: rgba(255, 255, 255, 0.25) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
        border-radius: 8px !important;
        padding: 0.6rem !important;
        backdrop-filter: blur(8px) !important;
        font-size: 1rem !important;
    }
    div[data-testid="stTextArea"] textarea::placeholder {
        color: rgba(255, 255, 255, 0.8) !important;
    }

    /* Text input (if used) */
    div[data-testid="stTextInput"] input {
        background-color: rgba(255, 255, 255, 0.25) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
        border-radius: 8px !important;
        padding: 0.5rem !important;
        backdrop-filter: blur(8px) !important;
        font-size: 1rem !important;
    }
    div[data-testid="stTextInput"] input::placeholder {
        color: rgba(255, 255, 255, 0.8) !important;
    }

    /* Hide Streamlit branding */
    .stDeployButton { display: none !important; }
    footer { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    </style>
    """, unsafe_allow_html=True)

# ---------- CALCULATOR STYLING --------- #

def apply_calculator_styling():
    """Apply blue theme styling for Salary Calculator page (with transparent charts)"""
    st.markdown("""
    <style>
    /* Background + header */
    header[data-testid="stHeader"] {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%) !important;
        border-bottom: none !important;
    }
    header[data-testid="stHeader"] .st-emotion-cache-1dp5vir {
        background: transparent !important;
    }
    .stApp {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%) !important;
        min-height: 100vh !important;
    }

    /* Text */
    h1, h2, h3, h4, h5, h6, p, span, div, .stMarkdown {
        color: white !important;
    }

    /* Title */
    h1 {
        font-size: 3rem !important;
        font-weight: 700 !important;
        text-align: left !important;
        margin-bottom: 2rem !important;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3) !important;
    }

    /* Info boxes */
    .stAlert {
        background: rgba(255, 255, 255, 0.15) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 8px !important;
    }

    /* Buttons */
    .stButton button {
        background: rgba(255, 255, 255, 0.25) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 500 !important;
        backdrop-filter: blur(8px) !important;
        transition: all 0.3s ease !important;
        font-size: 1rem !important;
    }
    .stButton button:hover {
        background: rgba(255, 255, 255, 0.35) !important;
        border-color: rgba(255, 255, 255, 0.6) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3) !important;
    }

    /* Plotly chart containers (force transparent) */
    div[data-testid="stPlotlyChart"] {
        background: rgba(0,0,0,0) !important;
    }
    div[data-testid="stPlotlyChart"] iframe {
        background: rgba(0,0,0,0) !important;
    }

    /* Hide Streamlit branding */
    .stDeployButton { display: none !important; }
    footer { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    </style>
    """, unsafe_allow_html=True)
