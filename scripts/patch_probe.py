#!/usr/bin/env python3
"""给 stocking-texture-tool 补一个只读 SAM 探针接口（幂等，可重复运行）。

作用：在 stocking/server.py 里插入 POST /api/doc/{doc_id}/probe。
它复用服务里已加载的 SAM，只跑轻量 mask decoder，不额外占显存、不改文档，
供 auto_stocking.py 的自动检测使用。

用法:
  python patch_probe.py [工具安装目录]
  不给目录时按 auto_stocking.py 的规则自动探测。
"""
import os
import shutil
import sys
import time

COMMON_TOOL_DIRS = (
    os.path.expanduser('~/stocking-texture-tool'),
    r'C:\stocking-texture-tool',
    r'D:\stocking-texture-tool',
)

PROBE_BLOCK = '''class ProbeIn(BaseModel):
    points: list[list[float]]          # [[x, y], ...] in image px


@app.post('/api/doc/{doc_id}/probe')
def probe(doc_id: str, body: ProbeIn):
    """Read-only SAM point probe, for external automation: for each point, SAM's three nested segments (smallest
    first) with area, bbox, centroid and mean luminance. Reuses the already loaded model and image embedding, so it
    costs no extra VRAM; it never edits the document (unlike /segment, which commits a click)."""
    d = doc_for(doc_id)
    art = d.art
    results = []
    for pt in body.points:
        x = float(np.clip(pt[0], 0, d.w - 1))
        y = float(np.clip(pt[1], 0, d.h - 1))
        try:
            masks, best, scores = sam.service.candidates(d, x, y)
        except RuntimeError as e:
            raise ValueError(str(e)) from e
        segs = []
        for m in masks:
            n = int(m.sum())
            if n == 0:
                segs.append({'area': 0, 'bbox': None, 'centroid': None, 'lum': None})
                continue
            ys, xs = np.nonzero(m)
            x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
            segs.append({'area': n, 'bbox': [x0, y0, x1 - x0 + 1, y1 - y0 + 1],
                         'centroid': [float(xs.mean()), float(ys.mean())],
                         'lum': float(art[m].mean())})
        results.append({'x': x, 'y': y, 'best': best, 'scores': scores, 'segments': segs})
    return {'results': results}
'''

ANCHOR = "@app.post('/api/doc/{doc_id}/segment/cycle')"


def find_tool_dir():
    env = os.environ.get('STOCKING_TOOL_DIR')
    if env and os.path.isdir(os.path.join(env, 'stocking')):
        return os.path.abspath(env)
    here = os.path.dirname(os.path.abspath(__file__))
    cfg = os.path.join(here, 'tool_dir.txt')
    if os.path.isfile(cfg):
        with open(cfg, encoding='utf-8-sig') as f:
            line = f.readline().strip()
        if line and os.path.isdir(os.path.join(line, 'stocking')):
            return os.path.abspath(line)
    d = here
    for _ in range(5):
        if os.path.isdir(os.path.join(d, 'stocking')):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    for cand in COMMON_TOOL_DIRS:
        if os.path.isdir(os.path.join(cand, 'stocking')):
            return os.path.abspath(cand)
    return here


def main():
    tool = sys.argv[1] if len(sys.argv) > 1 else find_tool_dir()
    path = os.path.join(tool, 'stocking', 'server.py')
    if not os.path.isfile(path):
        print(f'找不到 {path}')
        print('请先安装 stocking-texture-tool，或把工具安装目录作为参数传入。')
        return 1

    with open(path, encoding='utf-8') as f:
        src = f.read()

    if "/api/doc/{doc_id}/probe" in src:
        print('probe 接口已存在，无需重复打补丁。')
        return 0

    if ANCHOR not in src:
        print('找不到插入锚点 segment/cycle，工具版本可能不同。')
        print('请参考 references/api-and-params.md 手动添加 probe 接口。')
        return 1

    bak = path + time.strftime('.bak-%Y%m%d-%H%M%S')
    shutil.copy2(path, bak)
    src = src.replace(ANCHOR, PROBE_BLOCK + '\n\n' + ANCHOR, 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(src)
    print(f'补丁已写入 {path}')
    print(f'原文件备份: {bak}')
    print('重启工具服务后生效。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
