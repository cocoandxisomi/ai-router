import requests, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

r = requests.get('http://localhost:9876/buy', timeout=5)
t = r.text
print(f'Status: {r.status_code}')
checks = [
    ('GLM', 'GLM (Zhipu)'),
    ('Kimi', 'Kimi (Moonshot)'),
    ('GLM coding card', 'The Coding Powerhouse'),
    ('GLM code FAQ', 'Is GLM really that good for coding'),
    ('Kimi long-context', 'long-context'),
    ('CODE tag', 'CODE'),
    ('Western developers', 'Western developers'),
]
for label, keyword in checks:
    ok = 'OK' if keyword in t else 'MISS'
    print(f'  [{ok}] {label} : {keyword}')
print(f'Total size: {len(t)} bytes')