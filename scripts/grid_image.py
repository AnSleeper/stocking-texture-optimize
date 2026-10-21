#!/usr/bin/env python3
"""在原图上画坐标网格，供用户报点（看图被内容过滤挡住时的兜底）。

用法:
  python grid_image.py <图片路径> [输出路径]
默认输出: <工具目录>\\工作目录\\产物\\<输入文件名>\\temp\\<原名>_网格.png
          （如 青崽123.png -> ...\\产物\\青崽123\\temp\\青崽123_网格.png）
每 100px 一条黄线，每 200px 标一个 "x,y" 坐标。

工具目录定位同 auto_stocking.py：STOCKING_TOOL_DIR 环境变量 / --tool-dir / 脚本旁 tool_dir.txt / 向上找 stocking 包 / 常见安装位置。
"""
import os
import sys

import cv2
import numpy as np

COMMON_TOOL_DIRS = (
    os.path.expanduser('~/stocking-texture-tool'),
    r'C:\stocking-texture-tool',
    r'D:\stocking-texture-tool',
)


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


def out_root():
    tool = find_tool_dir()
    return os.environ.get('STOCKING_OUT_ROOT') or os.path.join(tool, '工作目录', '产物')


def main():
    argv = sys.argv[1:]
    if argv and argv[0] == '--tool-dir' and len(argv) >= 3:
        os.environ['STOCKING_TOOL_DIR'] = argv[1]
        argv = argv[2:]
    if not argv:
        print('用法: python grid_image.py <图片路径> [输出路径]')
        return 1
    src = argv[0]
    stem = os.path.splitext(os.path.basename(src))[0]
    out = argv[1] if len(argv) > 1 else os.path.join(out_root(), stem, 'temp', stem + '_网格.png')
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    img = cv2.imdecode(np.fromfile(src, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        print(f'读不到图片: {src}')
        return 1
    H, W = img.shape[:2]
    for x in range(0, W, 100):
        cv2.line(img, (x, 0), (x, H), (0, 220, 255), 1)
    for y in range(0, H, 100):
        cv2.line(img, (0, y), (W, y), (0, 220, 255), 1)
    for x in range(0, W, 200):
        for y in range(0, H, 200):
            cv2.putText(img, f'{x},{y}', (x + 3, y + 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
    cv2.imencode('.png', img)[1].tofile(out)
    print(out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
