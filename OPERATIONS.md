# AI Router 运营指南

## 启动服务

```bat
双击 start.bat 即可启动完整服务
```

启动后会显示：
- AI Router 本地地址：`http://localhost:9876`
- 公网隧道地址：`https://xxxx.loca.lt`（每次重启会变）

## 客户接入

客户只需要两样东西：

### 1. 给他们 API Key
```bash
curl -X POST http://localhost:9876/admin/keys \
  -H "Authorization: Bearer admin123" \
  -H "Content-Type: application/json" \
  -d '{"name":"客户名称","email":"client@example.com","limit_monthly_usd":100}'
```

### 2. 给他们连接方式
```python
# Python (OpenAI SDK)
from openai import OpenAI
client = OpenAI(
    base_url="https://odd-forks-travel.loca.lt/v1",
    api_key="sk-518ff97ff1ef"   # 你发给客户的那个
)
response = client.chat.completions.create(
    model="ai-router",
    messages=[{"role":"user","content":"你的问题"}]
)
print(response.choices[0].message.content)
```

```javascript
// Node.js
const res = await fetch("https://odd-forks-travel.loca.lt/v1/chat/completions", {
  method: "POST",
  headers: {
    "Authorization": "Bearer sk-518ff97ff1ef",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    model: "ai-router",
    messages: [{role:"user", content:"Translate: Hello world"}]
  })
})
```

## 管理操作

### 创建新客户 Key
```
POST /admin/keys  (Authorization: Bearer admin123)
{
  "name": "Acme Corp",
  "email": "billing@acme.com",
  "limit_monthly_usd": 200
}
```

### 查看所有客户用量
```
GET /admin/usage  (Authorization: Bearer admin123)
```
返回每个客户本月调用次数、费用、限额使用率

### 导出账单 CSV
```
GET /admin/export?month=2026-05  (Authorization: Bearer admin123)
```
直接下载 CSV，含客户名/Key/用量/费用/利润，自动附合计行

### 启停客户 Key
```
PATCH /admin/keys/sk-xxx  (Authorization: Bearer admin123)
{"enabled": false}   // 停用
{"enabled": true}    // 启用
{"limit_monthly_usd": 500}  // 调限额
```

### 查看运营面板
```
GET /admin/dashboard  (Authorization: Bearer admin123)
```
总调用数/利润/路由分布/客户明细

## 定价模型

| 级别 | 自动触发条件 | 使用模型 | 成本($/M tokens) | 收费($/M tokens) |
|------|-------------|----------|-----------------|-----------------|
| intern | 翻译/总结/打招呼等 | Qwen2.5-7B | $0.07 | $2 |
| mid | 中等任务 | DeepSeek-V3 | $0.29~$1.14 | $2~$4 |
| expert | 代码/算法/数学 | DeepSeek-R1 | $0.57~$2.29 | $2~$4 |

客户看到的是 OpenAI 兼容接口，不知道背后用了哪个模型。

## 安全提示

- **Admin Key**：存在 `.env` 的 `ADMIN_KEY`，默认 `admin123`，建议修改
- **硅基流动 Key**：存在 `.env` 的 `SF_API_KEY`
- **客户 Key**：存储在 `data/api_keys.json`
- **用量数据**：存储在 `data/usage.json`
- **详细日志**：存储在 `data/costs.jsonl`

## 进阶：固定域名

目前 localtunnel 每次重启 URL 会变。如需固定域名：
1. 买一个域名（GoDaddy/Namecheap $10/年）
2. 用 Cloudflare 解析
3. 安装 Cloudflare Tunnel 绑定固定域名
4. 或部署到 VPS（如 RackNerd $11/年）