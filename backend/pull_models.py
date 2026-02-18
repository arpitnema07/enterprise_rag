import requests
import json

OLLAMA_BASE_URL = "http://SRPTH1IDMQFS02.vecvnet.com:11434"
MODELS = ["nomic-embed-text", "gemma3:4b"]


def pull_model(model_name):
    url = f"{OLLAMA_BASE_URL}/api/pull"
    payload = {"name": model_name}

    print(f"Pulling model: {model_name}...")
    try:
        # Stream the response to show progress
        with requests.post(url, json=payload, stream=True) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    status = data.get("status")
                    if status:
                        print(f"Status: {status}", end="\r")
        print(f"\nSuccessfully pulled {model_name}\n")
    except requests.exceptions.RequestException as e:
        print(f"\nError pulling {model_name}: {e}")


if __name__ == "__main__":
    print(f"Connecting to Ollama at {OLLAMA_BASE_URL}")
    for model in MODELS:
        pull_model(model)
    print("All models processed.")
