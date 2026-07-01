"""
Digital Twins Sales Simulator — Refactored UI v2 with Navigation Bar.
Applies Microsoft Streamlit_UI_Template App 2 patterns with Avanade theme.
"""
from __future__ import annotations

import streamlit as st
from streamlit_navigation_bar import st_navbar

# ─────────────────────────────────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sales Digital Twins — Board Simulator",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────
# Custom CSS & Theme
# ─────────────────────────────────────────────────────────────────────────

def _inject_custom_css() -> None:
    """Inject custom CSS with Avanade theme + navigation styling."""
    st.markdown(
        """
        <style>
        /* ─── Root Variables ─── */
        :root {
            --ava-orange: #FF5800;
            --ava-dark-orange: #DC4600;
            --ava-grey-80: #333333;
            --ava-grey-60: #666666;
            --ava-grey-40: #999999;
            --ava-grey-20: #cccccc;
            --ava-grey-10: #e5e5e5;
            --ava-solar: #FFD700;
            --ava-aurora: #890078;
        }

        /* ─── Global Typography ─── */
        html, body, [class*="css"] {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            color: var(--ava-grey-80);
        }

        /* ─── Navigation Bar Container ─── */
        nav {
            background: linear-gradient(90deg, var(--ava-orange) 0%, var(--ava-aurora) 100%) !important;
            box-shadow: 0 2px 8px rgba(255, 88, 0, 0.15) !important;
            padding: 0 !important;
        }

        /* ─── Nav Links ─── */
        nav a, nav span {
            color: #ffffff !important;
            font-weight: 500 !important;
            padding: 12px 18px !important;
            font-size: 14px !important;
        }

        nav a:hover {
            background-color: rgba(255, 255, 255, 0.1) !important;
        }

        /* ─── Active Nav Item ─── */
        nav [class*="active"] {
            background-color: rgba(255, 255, 255, 0.25) !important;
            border-bottom: 3px solid #ffffff !important;
        }

        /* ─── Hero Section ─── */
        .ava-hero {
            background: linear-gradient(135deg, #FF5800 0%, #890078 100%);
            color: #fff;
            padding: 40px 36px;
            border-radius: 8px;
            position: relative;
            overflow: hidden;
            margin-bottom: 24px;
        }
        .ava-hero::after {
            content: "";
            position: absolute;
            right: -100px; top: -100px;
            width: 360px; height: 360px;
            background: radial-gradient(circle, rgba(255,215,0,.45) 0%, rgba(255,215,0,0) 70%);
        }
        .ava-hero h1 { font-weight: 300; font-size: 34px; margin: 0 0 6px 0; position: relative; z-index: 2; }
        .ava-hero h1 b { font-weight: 700; }
        .ava-hero .kicker {
            font-size: 12px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase;
            opacity: .9; margin-bottom: 10px; position: relative; z-index: 2;
        }
        .ava-hero .lede { font-weight: 300; opacity: .95; max-width: 70ch; position: relative; z-index: 2; }

        /* ─── Section Bar ─── */
        .ava-section-bar {
            border-left: 4px solid var(--ava-orange);
            padding-left: 12px; margin: 28px 0 12px 0;
            font-weight: 600; font-size: 19px; color: var(--ava-grey-80);
        }

        /* ─── Cards ─── */
        .ava-card {
            background: #fff;
            border: 1px solid var(--ava-grey-10);
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            margin-bottom: 16px;
        }

        /* ─── Buttons ─── */
        .stButton > button {
            background: linear-gradient(135deg, #FF5800 0%, #DC4600 100%) !important;
            color: white !important;
            border: none !important;
            font-weight: 600 !important;
        }
        .stButton > button:hover {
            background: linear-gradient(135deg, #DC4600 0%, #B43C14 100%) !important;
        }

        /* ─── Tabs ─── */
        [role="tablist"] button {
            font-weight: 600 !important;
        }
        [role="tablist"] button[aria-selected="true"] {
            border-bottom: 3px solid var(--ava-orange) !important;
            color: var(--ava-orange) !important;
        }

        /* ─── Main Content ─── */
        .main {
            max-width: 100%;
        }

        /* ─── Theme Toggle ─── */
        .theme-toggle {
            position: absolute;
            top: 10px;
            right: 20px;
            font-size: 18px;
            cursor: pointer;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────────────────────────────────
# Navigation Bar Setup
# ─────────────────────────────────────────────────────────────────────────

def _get_navbar() -> str:
    """Create and display navigation bar, return selected page."""
    
    # Pages list
    pages = [
        "🎯 Setup",
        "🎨 Simulação",
        "📋 Veredito",
        "👔 Coach",
        "📤 Export",
    ]
    
    # Navigation styles (Avanade theme)
    # Note: logo_path expects SVG; we skip it since favicon.ico is binary
    styles = {
        "nav": {
            "background-color": "linear-gradient(90deg, #FF5800 0%, #890078 100%)",
            "justify-content": "left",
            "padding": "0",
        },
        "span": {
            "color": "#FFFFFF",
            "padding": "0 14px",
            "font-weight": "500",
            "font-size": "14px",
        },
        "active": {
            "background-color": "rgba(255, 255, 255, 0.25)",
            "color": "#FFFFFF",
            "font-weight": "600",
            "border-bottom": "3px solid #FFFFFF",
            "padding": "0 14px",
        },
    }
    
    # Options
    options = {
        "show_menu": False,
        "show_sidebar": True,
    }
    
    # Create navbar (no logo_path to avoid encoding issues with .ico)
    selected_page = st_navbar(
        pages=pages,
        styles=styles,
        options=options,
    )
    
    return selected_page

# ─────────────────────────────────────────────────────────────────────────
# Placeholder Page Functions (will be populated from pages/)
# ─────────────────────────────────────────────────────────────────────────

def setup_page():
    """Setup/Configuration page."""
    st.markdown('<h1 class="title">🎯 Configuração</h1>', unsafe_allow_html=True)
    st.info("Página de configuração — em desenvolvimento")

def simulacao_page():
    """Simulation/Office canvas page."""
    st.markdown('<h1 class="title">🎨 Simulação</h1>', unsafe_allow_html=True)
    st.info("Página de simulação — em desenvolvimento")

def veredito_page():
    """Verdict/Objections page."""
    st.markdown('<h1 class="title">📋 Veredito</h1>', unsafe_allow_html=True)
    st.info("Página de veredito — em desenvolvimento")

def coach_page():
    """Coach/Feedback page."""
    st.markdown('<h1 class="title">👔 Coach</h1>', unsafe_allow_html=True)
    st.info("Página de coach — em desenvolvimento")

def export_page():
    """Export page."""
    st.markdown('<h1 class="title">📤 Exportar</h1>', unsafe_allow_html=True)
    st.info("Página de export — em desenvolvimento")

# ─────────────────────────────────────────────────────────────────────────
# Main App
# ─────────────────────────────────────────────────────────────────────────

def main():
    """Main app entry point with navigation."""
    
    # Inject theme
    _inject_custom_css()
    
    # Display navigation bar
    selected_page = _get_navbar()
    
    # Route to selected page
    page_functions = {
        "🎯 Setup": setup_page,
        "🎨 Simulação": simulacao_page,
        "📋 Veredito": veredito_page,
        "👔 Coach": coach_page,
        "📤 Export": export_page,
    }
    
    # Get and call the appropriate page function
    page_func = page_functions.get(selected_page)
    if page_func:
        page_func()
    else:
        st.markdown('<h1 class="title">Sales Digital Twins — Board Simulator</h1>', unsafe_allow_html=True)
        st.markdown("""
        Bem-vindo ao **Board Simulator** v2 com navegação renovada.
        
        Use a barra de navegação acima para:
        - **🎯 Setup** — Configurar conta, pitch e comitê
        - **🎨 Simulação** — Rodar debate e ver agents em ação na sala de reunião
        - **📋 Veredito** — Analisar objeções, bloqueadores e estratégias de contorno
        - **👔 Coach** — Receber feedback sobre seu pitch
        - **📤 Export** — Exportar relatório em Markdown ou HTML
        """)

if __name__ == "__main__":
    main()
