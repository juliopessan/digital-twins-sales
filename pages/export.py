"""Export page — Report generation."""
import streamlit as st

def export_page():
    """Export page."""
    st.markdown('<div class="ava-section-bar">Exportar relatório</div>', unsafe_allow_html=True)
    st.info("📤 Página de export — gerar e baixar relatórios (em desenvolvimento)")
    
    st.markdown("""
    **Formatos:**
    - Markdown (.md) — para compartilhamento rápido
    - HTML (.html) — para apresentações formais
    - JSON (.json) — para integração com sistemas
    """)
