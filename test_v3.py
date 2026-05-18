import requests, json

key = 'sk-klawlexvccoeyepgylpwtaldcvculyxkksnirugitmstlmxe'
base = 'http://localhost:9876'

# Test 1: models
print('=== Models ===')
r = requests.get(f'{base}/v1/models', timeout=5)
print(json.dumps(r.json(), indent=2))

# Test 2: chat - easy task
print('\n=== Chat (easy) ===')
r = requests.post(f'{base}/v1/chat/completions',
    headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
    json={'model': 'ai-router', 'messages': [{'role': 'user', 'content': 'Say hi in Chinese'}]},
    timeout=30)
data = r.json()
print(f'Model returned: {data["model"]}')
print(f'Content: {data["choices"][0]["message"]["content"]}')
print(f'Usage: prompt={data["usage"]["prompt_tokens"]} completion={data["usage"]["completion_tokens"]}')

# Test 3: chat - hard task (code)
print('\n=== Chat (hard - code) ===')
r = requests.post(f'{base}/v1/chat/completions',
    headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
    json={'model': 'ai-router', 'messages': [{'role': 'user', 'content': 'Write a quicksort in Python'}]},
    timeout=60)
data = r.json()
print(f'Model returned: {data["model"]}')
content = data['choices'][0]['message']['content']
print(f'Content preview: {content[:150]}...')

# Test 4: profit dashboard
print('\n=== Profit Dashboard ===')
r = requests.get(f'{base}/admin/profit', headers={'Authorization': 'Bearer admin123'}, timeout=5)
print(json.dumps(r.json(), indent=2))
