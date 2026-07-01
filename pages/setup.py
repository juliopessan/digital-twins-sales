"""Setup page — Account and configuration."""
import streamlit as st

def setup_page():
    """Setup/Configuration page."""
    st.markdown('<div class="ava-section-bar">Configuração da rodada</div>', unsafe_allow_html=True)
    st.info("🔧 Página de setup — selecione conta, API key e parâmetros da simulação")
    
    with st.form("setup_form"):
        account = st.selectbox("Selecione uma conta", ["iFood", "Nubank", "Vale"])
        api_key = st.text_input("Anthropic API Key", type="password")
        max_rounds = st.slider("Máximo de rounds", 1, 5, 3)
        seller_opening = st.text_area("Sua fala de abertura (opcional)")
        submitted = st.form_submit_button("▶️ Rodar simulação", use_container_width=True)
        
        if submitted:
            st.success(f"Pronto para rodar com {account}!")
