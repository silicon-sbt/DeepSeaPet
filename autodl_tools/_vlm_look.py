"""用 Ollama 本地视觉模型描述图片，弥补无视觉输入缺陷。
用法: python _vlm_look.py <图片路径> [提示词] [模型名]
默认模型 llava:7b，零依赖（仅标准库 urllib）。
"""
import base64, json, sys, urllib.request

def look(path: str, prompt: str, model: str = "llava:7b") -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    body = json.dumps(
        {"model": model, "prompt": prompt, "images": [b64], "stream": False}
    ).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate", body, {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read())["response"]

if __name__ == "__main__":
    path = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else (
        "请详细描述这张图片：画面里是什么角色？外观、颜色、姿态如何？"
        "背景是什么颜色？整体画质正常吗，有没有变形、畸变、奇怪的地方？"
    )
    model = sys.argv[3] if len(sys.argv) > 3 else "llava:7b"
    print(look(path, prompt))
