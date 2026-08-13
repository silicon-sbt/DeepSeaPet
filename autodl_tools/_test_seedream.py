"""测试火山引擎即梦 Seedream 4.0 img2img：参考图 base64 data URI 传法。
零依赖（urllib），key 从环境变量 VOLCENGINE_API_KEY 读。
"""
import base64, json, os, sys, urllib.request, urllib.error

key = os.environ.get("VOLCENGINE_API_KEY", "").strip()
REF = r"E:\code\deepseek的桌宠\module_5_assets\base_idle.png"
URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

with open(REF, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

body = {
    "model": "doubao-seedream-4-0-250828",
    "prompt": "保持参考图中角色的外貌完全不变（蓝发、头顶双触角、女仆装、鲸鱼尾巴），"
              "生成该角色开心微笑的全身立绘，纯白色背景，单角色，正面朝前",
    "image": f"data:image/png;base64,{b64}",
    "size": "1k",
}

req = urllib.request.Request(URL, json.dumps(body).encode(), {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {key}",
})
try:
    with urllib.request.urlopen(req, timeout=180) as r:
        print("HTTP", r.status)
        print(r.read().decode()[:3000])
except urllib.error.HTTPError as e:
    print("HTTP", e.code)
    print(e.read().decode()[:3000])
