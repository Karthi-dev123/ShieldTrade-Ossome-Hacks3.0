import json
with open('config/openclaw.json', 'r') as f:
    data = json.load(f)

data['providers'] = {
    "ollama": {
      "baseUrl": "http://127.0.0.1:11434",
      "api": "ollama",
      "models": [
        {
          "id": "tinyllama:latest",
          "name": "tinyllama:latest",
          "reasoning": False,
          "input": ["text"],
          "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
          "contextWindow": 2048,
          "maxTokens": 8192
        }
      ],
      "apiKey": "ollama-local"
    }
}
data['agents']['defaults']['model']['primary'] = 'ollama/tinyllama:latest'
data['agents']['defaults']['models'] = {'ollama/tinyllama:latest': {}}

with open('config/openclaw.json', 'w') as f:
    json.dump(data, f, indent=2)
