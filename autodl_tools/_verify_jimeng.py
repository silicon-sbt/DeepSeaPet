"""验证火山引擎即梦(Seedream) API key 是否有效 + 列出可用模型。
零依赖（仅标准库 urllib），key 从环境变量 VOLCENGINE_API_KEY 读取。
"""
import os, json, sys, urllib.request, urllib.error

key = os.environ.get("VOLCENGINE_API_KEY", "").strip()
if not key:
    print("未设置 VOLCENGINE_API_KEY")
    sys.exit(1)

BASE = "https://ark.cn-beijing.volces.com/api/v3"

def call(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(BASE + path, data, {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

print(f"key 前缀: {key[:12]}... 长度 {len(key)}")
code, body = call("GET", "/models")
print(f"=== GET /models -> HTTP {code} ===")
print(body[:3000])
