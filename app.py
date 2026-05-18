"""
AI Router v3.1 — 极简智能路由网关（带 Key 管理）
====================================================
核心：一个接口 /v1/chat/completions
客户用你生成的 key，后台自动分流到最优模型。

新增 v3.1：
  - 自己生成 API Key（sk-ar-xxx），跟硅基无关
  - 按 Key 分配套餐 + Token 配额
  - 超额提醒

Usage:
  1. Edit .env with your SF_API_KEY
  2. pip install -r requirements.txt
  3. python app.py
"""

import os, sys, json, time, secrets, smtplib, ssl
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import httpx
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIG
# ============================================================

SF_API_KEY = os.getenv("SF_API_KEY", "")
SF_BASE_URL = "https://api.siliconflow.cn/v1"
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin123")

UNIFIED_MODEL = "ai-router"
KEY_PREFIX = "sk-ar-"  # ar = AI Router，客户看到的 key 前缀

# 邮件通知（QQ 邮箱 SMTP）
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "3050781742@qq.com")
SMTP_PASS = os.getenv("SMTP_PASS", "")
ADMIN_EMAIL = SMTP_USER  # 所有通知发到这个邮箱
ALERT_FILE = "logs/alerts.json"  # 防止 80% 通知重复发送

# ============================================================
# 模型分级 — 商业机密，客户永远看不到
# ============================================================

TIERS = {
    "easy": {
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "cost_in": 0.07,
        "cost_out": 0.07,
        "keywords": [
            "翻译", "translate", "总结", "summarize", "摘要", "概括",
            "你好", "hello", "hi", "hey", "thanks", "再见", "bye",
            "什么是", "what is", "who is", "定义", "define",
            "列出", "list", "情感", "sentiment", "提取", "extract",
            "改写", "rewrite", "润色", "polish", "解释", "explain",
            "意见", "opinion", "对比", "比较", "compare", "greeting",
        ],
    },
    "normal": {
        "model": "deepseek-ai/DeepSeek-V3",
        "cost_in": 0.29,
        "cost_out": 1.14,
        "keywords": [],
    },
    "hard": {
        "model": "deepseek-ai/DeepSeek-R1",
        "cost_in": 0.57,
        "cost_out": 2.29,
        "keywords": [
            "写代码", "生成代码", "write code", "code this", "implement",
            "debug", "调试", "fix this", "修复", "架构", "architecture",
            "system design", "数学", "math", "证明", "prove", "推导",
            "算法", "algorithm", "机器学习", "machine learning",
            "sql", "数据库设计", "database schema", "正则表达式", "regex",
            "docker", "部署", "deploy", "安全", "security", "加密",
            "encrypt", "optimize", "performance", "benchmark",
            "api", "endpoint", "integration", "compiler", "parser",
        ],
    },
    "pro": {
        "model": "deepseek-ai/DeepSeek-V4-Flash",
        "cost_in": 0.86,
        "cost_out": 3.43,
        "keywords": [
            "学术论文", "research paper", "thesis", "dissertation",
            "深度分析", "deep analysis", "deep dive", "战略", "strategy",
            "strategic", "复杂推理", "complex reasoning", "博士", "phd",
            "research proposal", "文献综述", "literature review",
            "脑暴", "brainstorm", "创意", "creative writing",
            "长篇", "long-form", "comprehensive", "投资分析",
            "investment analysis", "医学", "medical", "diagnosis",
            "法律", "legal", "law", "合同", "contract",
        ],
    },
}

PRICE_IN = 1.00
PRICE_OUT = 2.00

# ============================================================
# 套餐 & 配额
# ============================================================

PLAN_QUOTAS = {
    "starter":  15_000_000,
    "pro":      40_000_000,
    "team":     80_000_000,
    "business": 150_000_000,
}

# ============================================================
# KEY 管理 — 核心：你的 key 跟硅基无关
# ============================================================

KEYS_FILE = "logs/keys.json"
LOG_FILE = "logs/costs.jsonl"
QUOTA_FILE = "logs/quotas.json"

def ensure_log_dir():
    os.makedirs("logs", exist_ok=True)

def send_notification(subject: str, body: str):
    """发送通知邮件到管理员 QQ 邮箱。"""
    if not SMTP_PASS or SMTP_PASS == "你的QQ邮箱授权码填这里":
        print(f"  [EMAIL SKIP] SMTP not configured: {subject}")
        return
    msg = f"From: AI Router <{SMTP_USER}>\nTo: {ADMIN_EMAIL}\nSubject: {subject}\nContent-Type: text/plain; charset=utf-8\n\n{body}"
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=10) as s:
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, [ADMIN_EMAIL], msg.encode("utf-8"))
        print(f"  [EMAIL SENT] {subject}")
    except Exception as e:
        print(f"  [EMAIL FAIL] {subject}: {e}")

def alert_sent(alert_key: str) -> bool:
    """检查这个警告是否已经发过，防止重复发送。"""
    ensure_log_dir()
    alerts = _load_json(ALERT_FILE, {})
    return alerts.get(alert_key, False)

def mark_alert_sent(alert_key: str):
    """标记警告已发送。"""
    ensure_log_dir()
    alerts = _load_json(ALERT_FILE, {})
    alerts[alert_key] = True
    _save_json(ALERT_FILE, alerts)

def _load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_keys() -> dict:
    """加载所有客户 key。格式: {"sk-ar-xxx": {"name": "张三", "plan": "pro", "email": "...", "created": "...", "enabled": true}}"""
    return _load_json(KEYS_FILE, {})

def save_keys(data: dict):
    _save_json(KEYS_FILE, data)

def generate_key() -> str:
    """生成一个 AI Router 专属 key，格式: sk-ar-xxxxxxxxxxxxxxxx"""
    rand = secrets.token_hex(16)  # 32 字符
    return f"{KEY_PREFIX}{rand}"

def validate_key(api_key: str) -> dict:
    """
    校验客户 key，返回 key 信息。
    如果 key 无效或被禁用，返回 None。
    """
    keys = load_keys()
    info = keys.get(api_key)
    if not info:
        return None
    if not info.get("enabled", True):
        return None
    return info

# ============================================================
# 配额追踪
# ============================================================

def load_quotas() -> dict:
    return _load_json(QUOTA_FILE, {})

def save_quotas(data: dict):
    _save_json(QUOTA_FILE, data)

def get_month_key() -> str:
    return datetime.now().strftime("%Y-%m")

def check_quota(api_key: str, plan: str) -> tuple:
    """检查配额，返回 (used, limit, pct)"""
    month = get_month_key()
    quotas = load_quotas()
    used = quotas.get(f"{api_key}:{month}", 0)
    limit = PLAN_QUOTAS.get(plan, 15_000_000)
    pct = used / limit * 100 if limit > 0 else 0
    return used, limit, pct

def add_usage(api_key: str, tokens_in: int, tokens_out: int):
    """累计 token 用量"""
    month = get_month_key()
    quotas = load_quotas()
    key = f"{api_key}:{month}"
    quotas[key] = quotas.get(key, 0) + tokens_in + tokens_out
    save_quotas(quotas)


# ============================================================
# 任务分类器 — 核心商业逻辑
# ============================================================

def classify(messages: list) -> str:
    text = " ".join(
        m.get("content", "") if isinstance(m.get("content"), str) else ""
        for m in messages
    ).lower()
    msg_len = len(text)

    for kw in TIERS["pro"]["keywords"]:
        if kw.lower() in text:
            return "pro"

    hard_hits = sum(1 for kw in TIERS["hard"]["keywords"] if kw.lower() in text)
    if hard_hits >= 2 or (hard_hits >= 1 and msg_len > 300):
        return "hard"

    easy_hits = sum(1 for kw in TIERS["easy"]["keywords"] if kw.lower() in text)
    if (msg_len < 80 and hard_hits == 0) or (easy_hits >= 2 and hard_hits == 0):
        return "easy"

    return "normal"


# ============================================================
# 成本 & 利润
# ============================================================

def calc_profit(tier: str, prompt_tokens: int, completion_tokens: int) -> dict:
    t = TIERS[tier]
    cost = prompt_tokens / 1e6 * t["cost_in"] + completion_tokens / 1e6 * t["cost_out"]
    charge = prompt_tokens / 1e6 * PRICE_IN + completion_tokens / 1e6 * PRICE_OUT
    profit = charge - cost
    return {
        "tier": tier,
        "real_model": t["model"],
        "cost_usd": round(cost, 6),
        "charge_usd": round(charge, 6),
        "profit_usd": round(profit, 6),
        "margin_pct": round(profit / charge * 100, 1) if charge > 0 else 0,
    }

def log_record(api_key: str, info: dict):
    ensure_log_dir()
    rec = {
        "time": datetime.now().isoformat(),
        "key": api_key,
        **info,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  [ROUTE] {info['tier']:6s} | cost=${info['cost_usd']:.4f} "
          f"charge=${info['charge_usd']:.4f} | profit=${info['profit_usd']:.4f} "
          f"({info['margin_pct']}%)")


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="AI Router",
    description="Smart model routing — one API, best price.",
    version="3.1",
)
client = httpx.AsyncClient(timeout=180.0)


@app.get("/")
def root():
    return {"service": "AI Router", "status": "ok", "version": "3.1"}


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [{
            "id": UNIFIED_MODEL,
            "object": "model",
            "owned_by": "ai-router",
            "created": int(datetime.now().timestamp()),
        }]
    }


# ============================================================
# 核心接口 — 客户调用的唯一接口
# ============================================================

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    客户调用这个接口。
    1. 校验客户 key（你生成的 sk-ar-xxx）
    2. 分类任务
    3. 用你的硅基 key 转发到对应模型
    4. 返回结果（model 改成 ai-router）
    """
    # 1) 鉴权 — 必须是你生成的 key
    auth = request.headers.get("Authorization", "")
    api_key = auth.replace("Bearer ", "").strip()
    if not api_key:
        raise HTTPException(status_code=401, detail="API Key required")

    key_info = validate_key(api_key)
    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid or disabled API Key")

    plan = key_info.get("plan", "starter")
    customer_name = key_info.get("name", "unknown")

    # 2) 解析请求
    body = await request.json()
    messages = body.get("messages", [])
    stream = body.get("stream", False)

    # 3) 分类 → 选模型
    tier = classify(messages)
    real_model = TIERS[tier]["model"]

    print(f"\n[REQUEST] {datetime.now().strftime('%H:%M:%S')} | customer={customer_name} "
          f"plan={plan} | route={tier} -> {real_model}")

    # 4) 配额预检
    used, limit, pct = check_quota(api_key, plan)
    if pct >= 80:
        alert_key = f"{api_key}:80pct"
        if not alert_sent(alert_key):
            send_notification(
                f"[AI Router] 客户用量告警 — {customer_name}",
                f"{customer_name} 的 Token 用量已达 {pct:.0f}%！\n"
                f"已用: {used:,} / {limit:,} tokens\n"
                f"套餐: {plan} ({limit//1_000_000}M/月)\n"
                f"Key: {api_key[:10]}...{api_key[-4:]}\n"
                f"\n请主动联系客户升级套餐。"
            )
            mark_alert_sent(alert_key)
        print(f"  [QUOTA WARN] {pct:.0f}% used ({used:,}/{limit:,}) - tell customer to upgrade!")

    # 5) 转发到硅基流动 — ⚠️ 用的是你自己的 SF_API_KEY
    proxy_body = {**body, "model": real_model}
    headers = {
        "Authorization": f"Bearer {SF_API_KEY}",   # 你的硅基 key，不是客户的
        "Content-Type": "application/json",
    }

    # ── 非流式 ──
    if not stream:
        resp = await client.post(
            f"{SF_BASE_URL}/chat/completions",
            json=proxy_body, headers=headers,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Upstream error: {resp.status_code}")

        data = resp.json()
        usage = data.get("usage", {})
        p_tokens = usage.get("prompt_tokens", 0)
        c_tokens = usage.get("completion_tokens", 0)

        info = calc_profit(tier, p_tokens, c_tokens)
        log_record(api_key, info)
        add_usage(api_key, p_tokens, c_tokens)

        # 隐藏真实模型
        data["model"] = UNIFIED_MODEL
        return JSONResponse(content=data)

    # ── 流式 ──
    async def stream_gen():
        p_tokens, c_tokens = 0, 0
        try:
            async with client.stream(
                "POST", f"{SF_BASE_URL}/chat/completions",
                json=proxy_body, headers=headers,
            ) as resp:
                if resp.status_code != 200:
                    err = await resp.aread()
                    yield f"data: {json.dumps({'error':{'message':f'Error {resp.status_code}','type':'upstream'}})}\n\n"
                    return
                async for line in resp.aiter_lines():
                    if not line or line == "data: [DONE]":
                        if line:
                            yield line + "\n\n"
                        continue
                    if not line.startswith("data: "):
                        continue
                    try:
                        chunk = json.loads(line[6:])
                        chunk["model"] = UNIFIED_MODEL
                        u = chunk.get("usage")
                        if u:
                            p_tokens = u.get("prompt_tokens", 0)
                            c_tokens = u.get("completion_tokens", 0)
                        yield f"data: {json.dumps(chunk)}\n\n"
                    except json.JSONDecodeError:
                        yield line + "\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error':{'message':str(e)[:200],'type':'stream_err'}})}\n\n"
        finally:
            if c_tokens > 0:
                info = calc_profit(tier, p_tokens, c_tokens)
                log_record(api_key, info)
                add_usage(api_key, p_tokens, c_tokens)

    return StreamingResponse(stream_gen(), media_type="text/event-stream")


# ============================================================
# ADMIN — Key 管理
# ============================================================

@app.get("/admin/keys")
async def list_keys(request: Request):
    """查看所有客户 key"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin token required")

    keys = load_keys()
    result = []
    for k, v in keys.items():
        # 隐藏完整 key，只显示前 10 位 + 后 4 位
        masked = k[:10] + "..." + k[-4:] if len(k) > 14 else k
        result.append({
            "key_masked": masked,
            "name": v.get("name", ""),
            "email": v.get("email", ""),
            "plan": v.get("plan", "starter"),
            "enabled": v.get("enabled", True),
            "created": v.get("created", ""),
            "limit": f"{PLAN_QUOTAS.get(v.get('plan','starter'),0)//1_000_000}M tokens/mo",
        })
    return {"total": len(result), "keys": result}


@app.post("/admin/generate-key")
async def gen_key(request: Request):
    """
    生成一个新的客户 API Key。
    body: {"name": "客户名", "email": "xxx@xx.com", "plan": "pro"}
    返回完整 key（只显示一次，记住它！）
    """
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin token required")

    body = await request.json()
    name = body.get("name", "unnamed")
    email = body.get("email", "")
    plan = body.get("plan", "starter")

    if plan not in PLAN_QUOTAS:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {plan}. Valid: {list(PLAN_QUOTAS.keys())}")

    new_key = generate_key()
    keys = load_keys()
    keys[new_key] = {
        "name": name,
        "email": email,
        "plan": plan,
        "enabled": True,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    save_keys(keys)
    ensure_log_dir()

    # ── 发邮件通知管理员：有人订阅了
    send_notification(
        f"[AI Router] 新客户订阅 — {name}",
        f"新客户已生成 API Key\n"
        f"姓名: {name}\n"
        f"邮箱: {email}\n"
        f"套餐: {plan} ({PLAN_QUOTAS[plan]//1_000_000}M tokens/月)\n"
        f"Key: {new_key[:10]}...{new_key[-4:]}\n"
        f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"\n记住把 Key 发给客户。"
    )

    return {
        "ok": True,
        "key": new_key,
        "key_masked": new_key[:10] + "..." + new_key[-4:],
        "name": name,
        "email": email,
        "plan": plan,
        "limit": f"{PLAN_QUOTAS[plan]//1_000_000}M tokens/month",
        "note": "Send this key to customer. You won't see it again from /admin/keys!",
    }


@app.post("/admin/disable-key")
async def disable_key(request: Request):
    """禁用一个客户 key（不删除，可重新启用）"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin token required")

    body = await request.json()
    key_mask = body.get("key", "")  # 完整 key 或部分 key
    keys = load_keys()

    found = None
    for k in keys:
        if k == key_mask or key_mask in k:
            found = k
            break

    if not found:
        raise HTTPException(status_code=404, detail="Key not found")

    keys[found]["enabled"] = False
    save_keys(keys)
    return {"ok": True, "key": found[:10] + "..." + found[-4:], "action": "disabled"}


@app.post("/admin/enable-key")
async def enable_key(request: Request):
    """重新启用一个 key"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin token required")

    body = await request.json()
    key_mask = body.get("key", "")
    keys = load_keys()

    found = None
    for k in keys:
        if k == key_mask or key_mask in k:
            found = k
            break

    if not found:
        raise HTTPException(status_code=404, detail="Key not found")

    keys[found]["enabled"] = True
    save_keys(keys)
    return {"ok": True, "key": found[:10] + "..." + found[-4:], "action": "enabled"}


@app.post("/admin/change-plan")
async def change_plan(request: Request):
    """修改客户套餐。body: {"key": "完整key", "plan": "team"}"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin token required")

    body = await request.json()
    key_search = body.get("key", "")
    new_plan = body.get("plan", "")

    if new_plan not in PLAN_QUOTAS:
        raise HTTPException(status_code=400, detail=f"Unknown plan. Valid: {list(PLAN_QUOTAS.keys())}")

    keys = load_keys()
    found = None
    for k in keys:
        if k == key_search or key_search in k:
            found = k
            break

    if not found:
        raise HTTPException(status_code=404, detail="Key not found")

    old_plan = keys[found]["plan"]
    keys[found]["plan"] = new_plan
    save_keys(keys)

    return {
        "ok": True,
        "key": found[:10] + "..." + found[-4:],
        "old_plan": old_plan,
        "new_plan": new_plan,
        "new_limit": f"{PLAN_QUOTAS[new_plan]//1_000_000}M tokens/month",
    }


# ============================================================
# ADMIN — 查看
# ============================================================

@app.get("/admin/profit")
async def profit_dashboard(request: Request):
    """查看利润概览"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin token required")

    if not os.path.exists(LOG_FILE):
        return {"message": "No requests yet"}

    records = [json.loads(l) for l in open(LOG_FILE, encoding="utf-8").read().strip().split("\n") if l]
    if not records:
        return {"message": "No data yet"}

    total_cost = sum(r["cost_usd"] for r in records)
    total_charge = sum(r["charge_usd"] for r in records)
    total_profit = sum(r["profit_usd"] for r in records)

    dist = {}
    for r in records:
        t = r.get("tier", "unknown")
        if t not in dist:
            dist[t] = {"calls": 0, "profit": 0.0}
        dist[t]["calls"] += 1
        dist[t]["profit"] += r.get("profit_usd", 0)

    return {
        "total_calls": len(records),
        "total_cost": f"${total_cost:.4f}",
        "total_revenue": f"${total_charge:.4f}",
        "total_profit": f"${total_profit:.4f}",
        "margin": f"{total_profit/total_charge*100:.1f}%" if total_charge > 0 else "N/A",
        "by_tier": {t: {"calls": v["calls"], "profit": f"${v['profit']:.4f}"} for t, v in sorted(dist.items())},
        "recent": records[-5:] if len(records) > 5 else records,
    }


@app.get("/admin/quotas")
async def quota_dashboard(request: Request):
    """查看所有客户用量"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin token required")

    month = get_month_key()
    keys = load_keys()
    quotas = load_quotas()
    result = []

    for full_key, key_info in keys.items():
        plan = key_info.get("plan", "starter")
        limit = PLAN_QUOTAS.get(plan, 0)
        used = quotas.get(f"{full_key}:{month}", 0)
        pct = used / limit * 100 if limit > 0 else 0

        result.append({
            "key": full_key[:10] + "..." + full_key[-4:],
            "name": key_info.get("name", ""),
            "plan": plan,
            "used": f"{used:,}",
            "limit": f"{limit:,}",
            "pct": round(pct, 1),
            "alert": "UPGRADE" if pct >= 80 else "OK",
        })

    return {"month": month, "clients": sorted(result, key=lambda x: x["pct"], reverse=True)}


# ============================================================
# 前端页面 — 落地页
# ============================================================

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/home")
@app.get("/landing")
@app.get("/buy")
def landing_page():
    index = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index, media_type="text/html")
    return {"msg": "Landing page not found"}


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    import uvicorn
    ensure_log_dir()
    print("=" * 56)
    print("  AI Router v3.1 — Smart Model Routing Gateway")
    print("=" * 56)
    print(f"  Endpoint:   POST /v1/chat/completions")
    print(f"  Model:      \"{UNIFIED_MODEL}\" (auto-routed)")
    print(f"  Key prefix: {KEY_PREFIX}***")
    print(f"  Profit:     GET /admin/profit")
    print(f"  Keys:       POST /admin/generate-key")
    print(f"  Quotas:     GET /admin/quotas")
    print("=" * 56)
    uvicorn.run(app, host="0.0.0.0", port=9876, log_level="warning")
