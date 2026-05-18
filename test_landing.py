import requests
base = 'http://localhost:9876'

# 1. Landing page
r = requests.get(f'{base}/buy', timeout=5)
print(f'Landing /buy: {r.status_code} | {len(r.text)} chars')
print(f'  Has pricing cards: {"$5" in r.text and "$20" in r.text}')
print(f'  Has email field: {"email" in r.text.lower()}')

# 2. API root
r = requests.get(f'{base}/', timeout=5)
print(f'\nRoot /: {r.json()}')

# 3. Models
r = requests.get(f'{base}/v1/models', timeout=5)
data = r.json()
print(f'\n/v1/models: {len(data["data"])} model(s)')
for m in data['data']:
    print(f'  - {m["id"]}')

# 4. Chat
key = 'sk-klawlexvccoeyepgylpwtaldcvculyxkksnirugitmstlmxe'
r = requests.post(f'{base}/v1/chat/completions',
    headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
    json={'model': 'ai-router', 'messages': [{'role': 'user', 'content': 'Say hi'}]},
    timeout=30)
d = r.json()
print(f'\nChat: model={d["model"]}')
print(f'Content: {d["choices"][0]["message"]["content"]}')

# 5. Profit dashboard
r = requests.get(f'{base}/admin/profit', headers={'Authorization': 'Bearer admin123'}, timeout=5)
p = r.json()
print(f'\nProfit: {p.get("total_calls",0)} calls | margin {p.get("margin","?")}')
print('\nALL PASSED!')
