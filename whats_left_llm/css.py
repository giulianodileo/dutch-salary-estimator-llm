import streamlit as st

def apply_custom_css():
    st.markdown(
        """
        <style>
        /* Asegura que el contenedor del botón no limite el ancho */
        div.stButton {
            display: flex;
            flex-direction: column;
            align-items: stretch;
        }

        /* Botón personalizado */
        div.stButton > button {
            all: unset;  /* Resetea todo el estilo original del botón */
            background-color: #374151;
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            font-weight: bold;
            text-align: left;
            margin-bottom: 0.5rem;
            width: 100%;
            box-sizing: border-box;
            cursor: pointer;
        }

        div.stButton > button:hover {
            background-color: #374151;
        }

        section[data-testid="stSidebar"] {
            background-color: #1f2937;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

def input_details():
    st.markdown(
        """
        <style>
        /* Aumentar tamaño de letra de labels en inputs */
        label {
            font-size: 50px !important;
            color: red;
            font-weight: 600 !important; /* opcional: poner en negrita */
        }
        </style>
        """,
        unsafe_allow_html=True
    )
