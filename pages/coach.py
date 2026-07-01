"""Coach page — Pitch feedback."""
import streamlit as st

def coach_page():
    """Coach/Feedback page."""
    st.markdown('<div class="ava-section-bar">Coach — Feedback do pitch</div>', unsafe_allow_html=True)
    st.info("👔 Página de coach — avaliação de sua fala de abertura (em desenvolvimento)")
    
    st.markdown("""
    **Análise:**
    - Nota geral do pitch (A–F)
    - O que funcionou (pontos de aterramento)
    - O que saiu pela culatra (armadilhas)
    - Sugestões de reescrita (antes/depois)
    """)
