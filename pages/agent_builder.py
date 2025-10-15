import streamlit as st
import api_client
import time

st.set_page_config(page_title="Agent Builder", page_icon="🛠️")

def load_css():
    with open("styles.css") as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css()

st.title("🛠️ Agent Builder")
st.markdown("Create a new AI agent by providing a task name and description.")

task_name = st.text_input("Task Name", placeholder="e.g., Release Note Generator")
task_description = st.text_area("Task Description", placeholder="e.g., An agent that compiles release notes from GitHub PRs, drafts them in Google Docs, and posts to Discord.")

if st.button("Create Agent"):
    if not task_name or not task_description:
        st.error("Please provide both a task name and description.")
    else:
        with st.spinner("Building your agent... This may take a moment."):
            try:
                # 1. Get agent_builder assistant
                assistants = api_client.get_assistants()
                if "error" in assistants:
                    st.error(f"Failed to get assistants: {assistants['error']}")
                    st.stop()

                agent_builder = next((a for a in assistants if a.get("graph_id") == "agent_builder"), None)
                if not agent_builder:
                    st.error("Could not find the 'agent_builder' assistant.")
                    st.stop()

                # 2. Create a chat for the agent_builder
                chat = api_client.create_chat("agent_builder", agent_builder["assistant_id"])
                if "error" in chat:
                    st.error(f"Failed to create chat: {chat['error']}")
                    st.stop()

                # 3. Create a run to generate the system prompt
                run = api_client.create_run(chat["thread_id"], agent_builder["assistant_id"], f"{task_name} - {task_description}")
                if "error" in run:
                    st.error(f"Failed to create run: {run['error']}")
                    st.stop()

                # 4. Poll for run completion
                while True:
                    run_status = api_client.get_run_status(chat["thread_id"], run["run_id"])
                    if "error" in run_status:
                        st.error(f"Failed to get run status: {run_status['error']}")
                        st.stop()
                    if run_status["status"] == "completed":
                        break
                    time.sleep(2)

                # 5. Get the generated system prompt
                history = api_client.get_chat_history(chat["thread_id"])
                if "error" in history:
                    st.error(f"Failed to get chat history: {history['error']}")
                    st.stop()

                ai_messages = [msg for msg in history[0]['values']['messages'] if msg['type'] == 'ai']
                if not ai_messages:
                    st.error("No AI message found in the chat history.")
                    st.stop()

                system_prompt = ai_messages[-1]['content']

                # 6. Create the new agent
                new_assistant = api_client.create_assistant("agent_template", task_name, task_description, system_prompt)
                if "error" in new_assistant:
                    st.error(f"Failed to create new assistant: {new_assistant['error']}")
                    st.stop()

                st.success(f"Agent '{task_name}' created successfully!")
                st.balloons()

                # Optional: Display the generated prompt
                with st.expander("View Generated System Prompt"):
                    st.text_area("", system_prompt, height=300)

            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")