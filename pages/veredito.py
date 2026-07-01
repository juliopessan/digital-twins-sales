"""Veredito page — Objections and analysis."""
import streamlit as st

def veredito_page():
    """Verdict/Objections page."""
    st.markdown('<div class="ava-section-bar">Análise do veredito</div>', unsafe_allow_html=True)
    st.info("📋 Página de veredito — objeções, bloqueadores e estratégias (em desenvolvimento)")
    
    st.markdown("""
    **Seções:**
    - Principais objeções dos stakeholders
    - Bloqueadores & Estratégias de contorno
    - Busca de consenso
    - Scorecard MEDDPICC (com explicação interativa)
    - Plano de ação recomendado
    - Avaliação de risco
    """)
