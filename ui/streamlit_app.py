"""Streamlit chat UI — a thin wrapper over the oracle library.

All AI logic lives in oracle.agent; this file only handles UI state.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from oracle.runtime import build_agent

load_dotenv()

st.set_page_config(page_title="Lineage Oracle", page_icon="🔮", layout="wide")
st.title("🔮 Lineage Oracle")
st.caption("Ask questions about your data warehouse, with grounded citations.")

INDEX_DIR = Path(".oracle")
WAREHOUSE = Path("data/jaffle_shop/dbt_project/jaffle_shop.duckdb")
SEARCH_DIR = Path("data/jaffle_shop")


@st.cache_resource
def load_agent():
    agent, _vstore = build_agent(
        index_dir=INDEX_DIR,
        warehouse_path=WAREHOUSE,
        search_dir=SEARCH_DIR,
    )
    return agent


agent = load_agent()

if "history" not in st.session_state:
    st.session_state.history = []

for role, text in st.session_state.history:
    with st.chat_message(role):
        st.markdown(text)

prompt = st.chat_input("Ask Oracle a question...")
if prompt:
    st.session_state.history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer = agent.ask(prompt)
        st.markdown(answer)
    st.session_state.history.append(("assistant", answer))
