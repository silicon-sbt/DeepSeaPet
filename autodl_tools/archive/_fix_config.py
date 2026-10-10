"""给 wan_pipeline/transformer/config.json 补 in_channels=36（diffusers 0.39 读 in_channels 不读 in_dim）"""
import json

p = '/root/autodl-tmp/wan_pipeline/transformer/config.json'
d = json.load(open(p))
d['in_channels'] = 36
json.dump(d, open(p, 'w'), indent=2)
print('config 已补 in_channels=36', flush=True)
