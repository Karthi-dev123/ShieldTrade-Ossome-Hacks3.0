import json
with open('config/openclaw.json', 'r') as f:
    data = json.load(f)

if 'providers' in data:
    del data['providers']
data['agents']['defaults']['model']['primary'] = 'ollama/tinyllama:latest'
data['agents']['defaults']['models'] = {'ollama/tinyllama:latest': {}}

with open('config/openclaw.json', 'w') as f:
    json.dump(data, f, indent=2)
