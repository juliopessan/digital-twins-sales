"""Simulação page — Office canvas and debate."""
import streamlit as st

def simulacao_page():
    """Simulation/Office canvas page."""
    st.markdown('<div class="ava-section-bar">Sala de reunião</div>', unsafe_allow_html=True)
    st.info("🎨 Página de simulação — agents em debate (em desenvolvimento)")
    
    st.markdown("**Status:** Aguardando simulação...")
    st.markdown("- Quando você clicar em 'Rodar simulação' no Setup, o debate aparecerá aqui")
    st.markdown("- Canvas mostrará agents caminhando, digitando e transitando de estados")
    st.markdown("- Transcrição completa aparecerá abaixo")
