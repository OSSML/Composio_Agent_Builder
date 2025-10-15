import streamlit as st

st.set_page_config(
    page_title="Composio Agent Builder",
    page_icon="🤖",
    layout="wide"
)

st.title("Welcome to the Composio Agent Builder! 👋")

st.markdown("""
This application allows you to create and interact with custom AI agents.

**👈 Select a page from the sidebar to get started!**

### Pages:
- **Agent Builder:** Create a new AI agent by providing a task name and description.
- **Assistants:** Chat with your created agents.
""")