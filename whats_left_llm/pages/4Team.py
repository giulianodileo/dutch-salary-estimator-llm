import streamlit as st
from pathlib import Path
import base64

# ------------------ Circule img ------------------------
def circular_image(path: str, size: int = 120, border_px: int = 4, border_color: str = "#023E8A"):
    """
    Muestra un avatar circular con una imagen local.
    - path: ruta local a la imagen (ej: "images/foto.png")
    - size: diámetro en px
    - border_px / border_color: grosor y color del borde
    """
    file_path = Path(path)
    if not file_path.exists():
        st.error(f"⚠️ Imagen no encontrada: {file_path.resolve()}")
        return

    with open(file_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    st.markdown(
        f"""
        <div style="
            width:{size}px;height:{size}px;
            border-radius:50%;
            overflow:hidden;
            margin: 20px auto;
            border:{border_px}px solid {border_color};
            margin:auto;
            box-shadow:0 4px 12px rgba(0,0,0,.15);
            background:#0b3a6f;
        ">
            <img src="data:image/png;base64,{img_b64}"
                 style="width:100%;height:100%;object-fit:cover;display:block;" />
        </div>
        """,
        unsafe_allow_html=True
    )

# ------------------ Square img ------------------------

def square_image(path: str, width: int = 100, height: int = 50, border_px: int = 4, border_color="#0077B6", radius=8):
    """
    Muestra una imagen dentro de un contenedor cuadrado.
    - path: ruta local a la imagen (ej: "images/foto.png")
    - size: tamaño del lado (px)
    - border_px / border_color: grosor y color del borde
    - radius: radio de las esquinas (0 = cuadrado perfecto, >0 = esquinas redondeadas)
    """
    file_path = Path(path)
    if not file_path.exists():
        st.error(f"⚠️ Imagen no encontrada: {file_path.resolve()}")
        return

    with open(file_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    st.markdown(
        f"""
        <div style="
            width:{width}px;height:{height}px;
            border-radius:{radius}px;
            overflow:hidden;
            border:{border_px}px solid {border_color};
            margin:10px auto 10px 0; /* 👈 alineado a la izquierda */
            float:right;
            box-shadow:0 0px 0px rgba(0,0,0, 0);
            background:#ffffff;
        ">
            <img src="data:image/png;base64,{img_b64}"
                 style="width:100%;height:100%;object-fit:cover;display:block;" />
        </div>
        """,
        unsafe_allow_html=True
    )


# ------------------ Structure ------------------------
with st.container():
    st.markdown(
        "<h3 style='text-align: center;'>Meet the team</h3>",
        unsafe_allow_html=True
    )
    st.markdown("<br>", unsafe_allow_html=True)

with st.container():
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        circular_image("whats_left_llm/giuliano.jpeg", size=140, border_px=0, border_color="#FFFFFF")
        st.markdown("<br>", unsafe_allow_html=True)
        st.write(
            "<p style='text-align: center;'>Giuliano Di Leo</p>",
            unsafe_allow_html=True
        )
    with col2:
        circular_image("whats_left_llm/thabiso.jpeg", size=140, border_px=0, border_color="#FFFFFF")
        st.markdown("<br>", unsafe_allow_html=True)
        st.write(
            "<p style='text-align: center;'>Thabiso Mokoena</p>",
            unsafe_allow_html=True
        )
    with col3:
        circular_image("whats_left_llm/alex.jpeg", size=140, border_px=0, border_color="#FFFFFF")
        st.markdown("<br>", unsafe_allow_html=True)
        st.write(
            "<p style='text-align: center;'>Alex Zeibel</p>",
            unsafe_allow_html=True
        )
    with col4:
        circular_image("whats_left_llm/andres.jpeg", size=140, border_px=0, border_color="#FFFFFF")
        st.markdown("<br>", unsafe_allow_html=True)
        st.write(
            "<p style='text-align: center;'>Andres Publio Gentile</p>",
            unsafe_allow_html=True
        )

with st.container():
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    square_image("whats_left_llm/lewagon.png", width=200, height= 62, border_px=0, border_color="#FFFFFF", radius=8)
