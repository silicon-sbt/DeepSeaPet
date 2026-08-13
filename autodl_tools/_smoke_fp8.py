"""远端 RTX 5090 冒烟测试：torch._scaled_mm (fp8) 是否可用"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conn

TEST = r'''
import torch
torch.manual_seed(0)
dev = "cuda"
cap = torch.cuda.get_device_capability(0)
print("GPU:", torch.cuda.get_device_name(0), "cap", cap)
# fp8 e4m3 scaled matmul (Blackwell sm_120)
a = torch.randn(4, 16, dtype=torch.float16, device=dev).contiguous()
b = torch.randn(16, 16, dtype=torch.float16, device=dev).contiguous().t().contiguous()
sa = torch.randn(4, 1, device=dev).contiguous() * 448
sb = torch.randn(1, 16, device=dev).contiguous() * 448
aq = (a / sa).to(torch.float8_e4m3fn).contiguous()
bq = (b / sb).to(torch.float8_e4m3fn).contiguous()
o = torch._scaled_mm(aq, bq, scale_a=sa, scale_b=sb, out_dtype=torch.bfloat16)
print("scaled_mm OK shape", tuple(o.shape))
# torch SDPA
import torch.nn.functional as F
q = torch.randn(2, 8, 16, 32, device=dev)
o2 = F.scaled_dot_product_attention(q, q, q)
print("SDPA OK shape", tuple(o2.shape))
'''

c = conn.connect()
# 写入远端脚本后执行，避免引号地狱
sftp = c.open_sftp()
with sftp.open("/tmp/_smoke.py", "w") as f:
    f.write(TEST)
sftp.close()
_, out, err = c.exec_command("/root/miniconda3/bin/python /tmp/_smoke.py", timeout=120)
print(out.read().decode(errors="replace"))
e = err.read().decode(errors="replace")
if e:
    print("STDERR:", e[-800:])
c.close()
