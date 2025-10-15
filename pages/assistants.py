import streamlit as st
import api_client
import json

st.set_page_config(page_title="Assistants", page_icon="🤖")

def load_css():
    with open("styles.css") as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css()

st.title("🤖 Assistants")

# Fetch all assistants
assistants = api_client.get_assistants()
if "error" in assistants:
    st.error(f"Failed to load assistants: {assistants['error']}")
    st.stop()

# Sidebar for assistant selection
assistant_names = [a["name"] for a in assistants]
selected_assistant_name = st.sidebar.selectbox("Select an Assistant", assistant_names)

if selected_assistant_name:
    selected_assistant = next((a for a in assistants if a["name"] == selected_assistant_name), None)

    if selected_assistant:
        st.header(f"Chat with {selected_assistant['name']}")

        # Chat history and creation in sidebar
        st.sidebar.subheader("Chats")
        chats = api_client.search_chats(metadata={"graph_id": selected_assistant["graph_id"]})

        if "error" in chats:
            st.sidebar.error("Could not load chats.")
        else:
            chat_ids = [c["thread_id"] for c in chats["threads"]]
            if st.sidebar.button("New Chat"):
                new_chat = api_client.create_chat(selected_assistant["graph_id"], selected_assistant["assistant_id"])
                if "error" in new_chat:
                    st.sidebar.error("Failed to create new chat.")
                else:
                    st.session_state.selected_chat = new_chat["thread_id"]
                    st.experimental_rerun()

            # Display existing chats
            for chat_id in chat_ids:
                if st.sidebar.button(f"Chat {chat_id[:8]}"):
                    st.session_state.selected_chat = chat_id

        # Main chat interface
        if 'selected_chat' in st.session_state:
            thread_id = st.session_state.selected_chat

            # Display chat messages
            history = api_client.get_chat_history(thread_id, limit=100) # Fetch more history for display
            if "error" not in history and history:
                messages = history[0]['values']['messages']
                for msg in messages:
                    with st.chat_message(msg["type"]):
                        st.markdown(msg["content"])

            # User input
            prompt = st.chat_input("What would you like to ask?")
            if prompt:
                with st.chat_message("human"):
                    st.markdown(prompt)

                with st.chat_message("ai"):
                    message_placeholder = st.empty()
                    full_response = ""

                    for chunk in api_client.stream_chat(thread_id, selected_assistant["assistant_id"], prompt):
                        try:
                            # Process streaming data
                            data_str = chunk.decode('utf-8').strip()
                            if data_str.startswith("data:"):
                                json_str = data_str[len("data:"):].strip()
                                data = json.loads(json_str)

                                if "messages" in data:
                                    for message in data["messages"]:
                                        if message.get("type") == "AIMessageChunk":
                                            full_response += message.get("content", "")
                                            message_placeholder.markdown(full_response + "▌")
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            # Handle non-JSON chunks or decoding errors if any
                            pass

                    message_placeholder.markdown(full_response)