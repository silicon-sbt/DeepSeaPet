"""框架按 {model_path}/google/umt5-xxl 找 T5 tokenizer，但文件在 distill_fp8/ 下。
建目录 + 硬链接（零磁盘），并列出内容确认。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conn

c = conn.connect()
script = r'''
set -e
SRC=/root/autodl-tmp/ms_cache/distill_fp8/google/umt5-xxl
DST=/root/autodl-tmp/ms_cache/google/umt5-xxl
echo "== SRC 内容 =="
ls -la "$SRC"
mkdir -p "$DST"
for f in "$SRC"/*; do
  ln -f "$f" "$DST/$(basename "$f")"
done
echo "== DST 内容 =="
ls -la "$DST"
'''
_, out, err = c.exec_command(script, timeout=60)
print(out.read().decode(errors="replace"))
e = err.read().decode(errors="replace")
if e:
    print("STDERR:", e[-300:])
c.close()
