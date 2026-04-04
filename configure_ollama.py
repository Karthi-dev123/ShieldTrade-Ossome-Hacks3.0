import json
import os
import glob

models_config = {
  "providers": {
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
          "contextWindow": 16384,
          "maxTokens": 8192
        }
      ],
      "apiKey": "ollama-local"
    }
  }
}

# Write to global
os.makedirs(os.path.expanduser('~/.openclaw'), exist_ok=True)
with open(os.path.expanduser('~/.openclaw/models.json'), 'w') as f:
    json.dump(models_config, f, indent=2)

# Write to all agents
agent_dirs = glob.glob(os.path.expanduser('~/.openclaw/agents/*/agent'))
for adir in agent_dirs:
    with open(os.path.join(adir, 'models.json'), 'w') as f:
        json.dump(models_config, f, indent=2)

# Update openclaw.json
try:
    with open('config/openclaw.json', 'r') as f:
        config = json.load(f)
    
    if 'providers' in config:
        del config['providers']
        
    config['agents']['defaults']['model']['primary'] = "ollama/tinyllama:latest"
    config['agents']['defaults']['models'] = {"ollama/tinyllama:latest": {}}
    
    with open('config/openclaw.json', 'w') as f:
        json.dump(config, f, indent=2)
    print("Successfully patched OpenClaw configurations for tinyllama!")
except Exception as e:
    print("Error patching openclaw.json:", e)
