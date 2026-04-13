import os
import requests

api_key = os.environ.get("GEMINI_API_KEY")

def test_models():
    if not api_key:
        print("NO API KEY")
        return
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        models = data.get("models", [])
        for m in models:
            if "embedContent" in m.get("supportedGenerationMethods", []):
                print(f"Supported embedding model: {m['name']}")
    else:
        print("ERROR:", r.text)

if __name__ == "__main__":
    test_models()
