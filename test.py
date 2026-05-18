"""
🔧 AI Router 测试脚本
用法: python test.py
"""

import requests

# 服务地址
BASE_URL = "http://localhost:8000"

# 测试用的 API Key
API_KEY = "sk-test"

# ============================================================
# 测试 1：简单任务（应该路由到实习生模型）
# ============================================================
print("=" * 50)
print("🧪 测试1：简单任务 — "你好，请翻译这句话：今天的天气真好"")
print("   预期：路由到 intern（最便宜模型）")
print("=" * 50)

resp = requests.post(
    f"{BASE_URL}/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    },
    json={
        "model": "ai-router",
        "messages": [
            {"role": "user", "content": "你好，请把这句话翻译成英文：今天的天气真好"}
        ],
    },
)

print(f"状态码: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"回复: {data['choices'][0]['message']['content'][:200]}")
    print(f"Token: prompt={data['usage']['prompt_tokens']}, "
          f"completion={data['usage']['completion_tokens']}")
else:
    print(f"错误: {resp.text}")

# ============================================================
# 测试 2：复杂任务（应该路由到专家模型）
# ============================================================
print()
print("=" * 50)
print("🧪 测试2：复杂任务 — "帮我写一段Python代码实现快速排序"")
print("   预期：路由到 expert（推理模型）")
print("=" * 50)

resp = requests.post(
    f"{BASE_URL}/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    },
    json={
        "model": "ai-router",
        "messages": [
            {"role": "user", "content": "帮我写一段 Python 代码实现快速排序"}
        ],
    },
)

print(f"状态码: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"回复: {data['choices'][0]['message']['content'][:200]}...")
    print(f"Token: prompt={data['usage']['prompt_tokens']}, "
          f"completion={data['usage']['completion_tokens']}")
else:
    print(f"错误: {resp.text}")

# ============================================================
# 测试 3：中等任务（应该路由到中级模型）
# ============================================================
print()
print("=" * 50)
print("🧪 测试3：中等任务 — "分析一下AI行业发展趋势"")
print("   预期：路由到 mid（DeepSeek-V3）")
print("=" * 50)

resp = requests.post(
    f"{BASE_URL}/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    },
    json={
        "model": "ai-router",
        "messages": [
            {"role": "user", "content": "分析一下2025年AI行业的发展趋势，重点说说大模型方向"}
        ],
    },
)

print(f"状态码: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"回复: {data['choices'][0]['message']['content'][:200]}...")
    print(f"Token: prompt={data['usage']['prompt_tokens']}, "
          f"completion={data['usage']['completion_tokens']}")
else:
    print(f"错误: {resp.text}")

# ============================================================
# 查看仪表盘
# ============================================================
print()
print("=" * 50)
print("📊 查看仪表盘")
print("=" * 50)

resp = requests.get(
    f"{BASE_URL}/dashboard",
    headers={"Authorization": "Bearer admin123"},
)
if resp.status_code == 200:
    import json
    print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
else:
    print(f"错误: {resp.status_code} - {resp.text}")

print()
print("✅ 测试完成！去 http://localhost:8000/dashboard 看面板")