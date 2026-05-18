# AI Router Token 配额系统 — 2026-05-17

## 目标
为 AI Router 添加月 token 配额系统，客户订阅后获分配额，后台自动追踪用量。超额时管理员手动通知客户升级。

## 套餐配额

| 档位 | 月费 | Token 配额 | 你的成本上限 | 利润下限 | 利润率 |
|------|------|-----------|------------|--------|--------|
| Starter | $9.9 | 15M | $1.10 | $8.80 | 89% |
| Pro | $29.9 | 40M | $6.50 | $23.40 | 78% |
| Team | $49.9 | 80M | $13.50 | $36.40 | 73% |
| Business | $99.9 | 150M | $28.50 | $71.40 | 71% |

## 后端改动 (app.py)

### 新增功能
- `PLAN_QUOTAS` 字典：定义每个套餐的月 token 上限
- `check_and_log_quota()`：请求前预检，打印 80%+ 告警
- `add_usage()`：请求后在 quotas.json 累计实际用量
- `GET /admin/quotas`：查看所有客户用量和超标比例
- `GET /admin/plans`：查看套餐配置
- `POST /admin/set-plan`：为客户分配套餐（key_short + plan）
- 聊天接口两条路径（流式/非流式）均已插入 `add_usage()` 调用

### 管理命令
```bash
# 查看所有客户用量
curl -H "Authorization: Bearer admin123" http://localhost:9876/admin/quotas

# 为客户分配套餐
curl -X POST http://localhost:9876/admin/set-plan \
  -H "Authorization: Bearer admin123" \
  -H "Content-Type: application/json" \
  -d '{"key_short":"sk-xxxx","plan":"team"}'
```

## 前端改动 (static/index.html)

- 四张价格卡的第3行 `price-per` 从"$XX monthly credit"改为"XXM tokens / month"
- 下拉选项显示 token 配额：`Starter — $9.9/mo (15M tokens)`
- 功能列第二条从"$1 / $2 per 1M tokens"改为"Smart auto-routing"（不暴露内部定价）

## 不需要做的事
- 暂不自动阻断超额请求（前期客户少，手动通知）
- 暂不自动化邮件提醒
- 暂不暴露 token 实时余额给客户（只给管理员看 /admin/quotas）