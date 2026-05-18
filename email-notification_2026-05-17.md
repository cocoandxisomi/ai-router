# AI Router QQ 邮箱通知系统完成

**时间**: 2026-05-17 19:27 ~ 19:30

## 背景
用户要求将 3050781742@qq.com 绑定到 AI Router，用于：
- 客户订阅通知（生成 key 时发邮件）
- Token 用量 80% 告警（发邮件提醒升级）
- 未来与客户的邮件沟通

## SMTP 配置
- 服务器: smtp.qq.com:465 (SSL)
- 用户名: 3050781742@qq.com
- 授权码已写入 .env (SMTP_PASS)
- 测试邮件发送成功

## 代码改动 (app.py v3.1)
1. 新增 `send_notification(subject, body)` — QQ SMTP 发送邮件
2. 新增 `alert_sent()` / `mark_alert_sent()` — 防止 80% 告警重复发送
3. `POST /admin/generate-key` — 成功后自动邮件通知管理员
4. `POST /v1/chat/completions` — 用量 ≥80% 时发邮件（同月同 key 只发一次）

## 测试结果
- 生成 key: status=200 ✅
- 邮件已弹出（+ 确认 SMTP 直连成功）
- 用量告警防重复机制就绪

## 待完成
- Render 免费部署（拿永久链接）
- Reddit 发帖推广