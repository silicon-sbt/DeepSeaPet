"""准备 Wan I2V 基准图：rembg 抠图后的豆包 f0 → 白底 RGB 720x720"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image

src = 'module_5_assets/sprites/idle_00.png'
dst = 'module_5_assets/base_idle.png'

img = Image.open(src).convert('RGBA')
bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
bg.alpha_composite(img)
rgb = bg.convert('RGB')
rgb.save(dst)
print(f'{dst} 保存完成 {rgb.size}')
