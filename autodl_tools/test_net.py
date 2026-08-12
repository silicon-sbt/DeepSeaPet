"""测试 AutoDL 网络"""
import urllib.request, socket

# 测试 DNS
print("DNS huggingface.co:", socket.getaddrinfo("huggingface.co", 443)[0][4])

# 测试镜像
for url in [
    "https://hf-mirror.com",
    "https://hf-mirror.com/Linaqruf/animagine-xl-3.1/resolve/main/animagine-xl-3.1.safetensors",
]:
    try:
        req = urllib.request.Request(url, method="HEAD")
        r = urllib.request.urlopen(req, timeout=15)
        size = r.headers.get("Content-Length", "?")
        print(f"OK {r.getcode()} size={size} -> {url}")
    except Exception as e:
        print(f"FAIL {e} -> {url}")
