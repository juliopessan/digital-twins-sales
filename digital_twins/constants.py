"""Small shared constants with no other natural home.

Split out from digital_twins/office.py (now archived under legacy/) because
api/runner.py — part of the current Next.js/FastAPI stack — tags its event
log with these same two keys, and shouldn't have to import the legacy
Streamlit office-canvas module just to get two strings.
"""
from __future__ import annotations

FACILITATOR_KEY = "facilitator"
SYNTHESIZER_KEY = "synthesizer"
