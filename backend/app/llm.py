"""
llm.py

Step 11: the LLM. We talk to a local Ollama server over its HTTP API using only
the standard library - no data leaves your machine, which suits a privacy project.
Make sure Ollama is running and the model is pulled:  ollama pull llama3.2:3b
"""

import json
import os
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")


class LLMUnavailable(Exception):
    pass


def ask_llm(system: str, user: str, timeout: int = 180) -> str:
    payload = {
        "model": MODEL,
        "stream": False,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "options": {"temperature": 0.2},
    }
    request = urllib.request.Request(
        OLLAMA_URL, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        raise LLMUnavailable(f"Ollama returned an error ({e.code}). Is '{MODEL}' pulled? Try: ollama pull {MODEL}")
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        raise LLMUnavailable("Could not reach Ollama at localhost:11434. Start Ollama and try again.")
