import requests
import time

BASE_URL = "http://localhost:8000/api"

def get_assistants():
    """Fetches all assistants."""
    try:
        response = requests.get(f"{BASE_URL}/assistants")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def create_chat(graph_id, assistant_id):
    """Creates a new chat thread."""
    try:
        payload = {"graph_id": graph_id, "assistant_id": assistant_id}
        response = requests.post(f"{BASE_URL}/chat/new", json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def create_run(thread_id, assistant_id, message):
    """Creates a new run in a chat thread."""
    try:
        payload = {
            "assistant_id": assistant_id,
            "input": {"messages": [{"type": "human", "content": [{"type": "text", "text": message}]}]}
        }
        response = requests.post(f"{BASE_URL}/chat/{thread_id}/runs", json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def get_run_status(thread_id, run_id):
    """Gets the status of a specific run."""
    try:
        response = requests.get(f"{BASE_URL}/chat/{thread_id}/runs/{run_id}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def get_chat_history(thread_id, limit=1):
    """Fetches the history of a chat thread."""
    try:
        payload = {"limit": limit}
        response = requests.post(f"{BASE_URL}/chat/{thread_id}/history", json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def create_assistant(graph_id, name, description, system_prompt):
    """Creates a new assistant."""
    try:
        payload = {
            "graph_id": graph_id,
            "name": name,
            "description": description,
            "context": {"system_prompt": system_prompt}
        }
        response = requests.post(f"{BASE_URL}/assistants", json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def search_chats(metadata):
    """Searches for chats with specific metadata."""
    try:
        payload = {"metadata": metadata}
        response = requests.post(f"{BASE_URL}/chat/search", json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def stream_chat(thread_id, assistant_id, message):
    """Streams a chat response."""
    try:
        payload = {
            "assistant_id": assistant_id,
            "input": {"messages": [{"type": "human", "content": [{"type": "text", "text": message}]}]}
        }
        with requests.post(f"{BASE_URL}/threads/{thread_id}/runs/stream", json=payload, stream=True) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=8192):
                yield chunk
    except requests.exceptions.RequestException as e:
        yield f"Error: {str(e)}".encode('utf-8')