#!/usr/bin/env python3
"""一键丝袜质感优化流水线（黑丝/白丝通用，默认黑丝细线）。

用法：
  python auto_stocking.py 图片路径 [更多图片...] [选项]

路径（装在别处时，任选一种方式指定工具目录）：
  1) 环境变量 STOCKING_TOOL_DIR=<工具安装目录>
  2) 命令行 --tool-dir <工具安装目录>
  3) 在本文件旁建 tool_dir.txt，第一行写工具目录

选项：
  --out DIR        产物根目录（默认 <工具目录>\\工作目录\\产物）。
                   每张图会在其下按输入文件名建同名子目录（如 青崽123.png -> 产物\\青崽123\\），
                   该子目录放 原图.png + 各样式成品；掩码图/预览图等中间件放其下的 temp\\。
  --name NAME      输出文件名（不含扩展名；默认 丝袜质感优化_<样式>）
  --style S        只出指定样式：knit|loops|coil|lines|grain|oily。
                   不填则**默认出全部 6 种样式各一版**（每版文件名带样式后缀）。
  --density N      密度（默认 100）
  --strength N     强度（默认 100，配合 --no-auto-strength 才生效）
  --points "x,y[,k][+x,y[,k]]*[;...]"
                   直接指定丝袜位置的点（最可靠）。用 ';' 分隔部位；同一部位可用 '+' 连接多个点
                   （同部位多点会合并，用于"补全/合并"某条腿）；每个点可带第 3 段档位 k（0小/1中/2大），
                   省略则用 --grow。--preview 打印的就是这个格式，原样复制即可复现。
  --grow k         未在 --points 里指定档位时的默认档：k0 小 / k1 中 / k2 大（默认 k0，最小档最贴合腿部、不易带进背景）
  --auto           不用 --points，自动检测丝袜部位（OpenCV 出候选 + 服务内 GPU SAM 探针精修）
  --port N         服务端口（默认 8766）
  --preview        只做检测+分区，输出 _掩码.png（带部位编号 + 落点十字）供人工检查，不导出成品。**出图前必跑这一步**。

流程：确保服务在跑 -> 打开图 -> 定部位（--points 或 --auto 的 SAM 探针）-> 输出 _掩码.png（编号+十字）给用户确认
      -> （确认后复用同一坐标）自动铺走向线 -> 渲染 -> 导出到 <--out>\\<输入文件名>\\。

产物目录规则：所有产物统一放在 <--out> 根目录下、以输入文件名命名的子目录里。例如输入 青崽123.png，
      任务目录 ...\\产物\\青崽123\\ 下放：原图.png（原图副本）+ 各样式成品；中间件（_掩码.png / _预览.png）
      放在该任务目录下的 temp\\ 子文件夹里。一轮任务一个目录，互不混淆。

默认出图规则：不带 --style 时，默认把全部 6 种样式各出一版（细线/针织/线圈/斜单线/加濑风/油光），
      文件名形如 丝袜质感优化_细线.png、丝袜质感优化_针织.png……都落在同一个任务子目录里。

档位经验：别盲目拉满——相邻部位用大档(k2)会大范围重叠，工具把重叠只判给其中一块，另一块会被裁掉
      （实测曾出现某部位只剩 4422px）。部位不够全时，优先"降档 + 在同部位用 '+' 补点合并"，而不是升档。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

import cv2
import numpy as np

# 工具安装位置。装在别处时，任选一种方式指定（不要把个人路径写进代码）：
#   1) 环境变量 STOCKING_TOOL_DIR
#   2) 命令行 --tool-dir
#   3) 在本文件旁建 tool_dir.txt，第一行写工具目录
COMMON_TOOL_DIRS = (
    os.path.expanduser('~/stocking-texture-tool'),
    r'C:\stocking-texture-tool',
    r'D:\stocking-texture-tool',
)


def _find_tool_dir():
    """按优先级定位工具安装目录：环境变量 -> 脚本旁 tool_dir.txt -> 向上找 stocking 包 -> 常见安装位置。"""
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


TOOL_DIR = ''
VENV_PY = ''
STAGE = ''
WORK_DIR = ''
OUT_ROOT = ''
STYLE_CN = {'knit': '细线', 'loops': '针织', 'coil': '线圈',
            'lines': '斜单线', 'grain': '加濑风', 'oily': '油光'}


def _init_paths(tool_dir):
    global TOOL_DIR, VENV_PY, STAGE, WORK_DIR, OUT_ROOT
    TOOL_DIR = os.path.abspath(tool_dir)
    win = os.name == 'nt'
    VENV_PY = os.path.join(TOOL_DIR, '.venv', 'Scripts' if win else 'bin',
                           'python.exe' if win else 'python')
    STAGE = os.path.join(TOOL_DIR, '.tmp_run')
    WORK_DIR = os.environ.get('STOCKING_WORK_DIR') or os.path.join(TOOL_DIR, '工作目录')
    OUT_ROOT = os.environ.get('STOCKING_OUT_ROOT') or os.path.join(WORK_DIR, '产物')


_init_paths(_find_tool_dir())


def http(base, path, body=None, method=None, raw=False, timeout=600):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(base + path, data=data,
                               headers={'Content-Type': 'application/json'}, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            b = resp.read()
            return resp.status, (b if raw else json.loads(b))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')


def ping(base):
    try:
        s, _ = http(base, '/api/ping', timeout=3)
        return s == 200
    except Exception:
        return False


def ensure_server(base, port):
    if ping(base):
        return
    os.makedirs(STAGE, exist_ok=True)
    env = dict(os.environ)
    env['TEMP'] = env['TMP'] = STAGE
    log = open(os.path.join(STAGE, 'server.log'), 'ab')
    flags = 0x08000000 | 0x00000200 if os.name == 'nt' else 0   # CREATE_NO_WINDOW | NEW_PROCESS_GROUP
    subprocess.Popen([VENV_PY, '-m', 'stocking', '--isolated', '--no-window', '--stay',
                      '--port', str(port)], cwd=TOOL_DIR, env=env,
                     stdout=log, stderr=log, creationflags=flags)
    for _ in range(90):
        if ping(base):
            return
        time.sleep(1)
    raise RuntimeError('丝袜纹理工具服务启动失败')


def mask_of(base, did, rid):
    _, b = http(base, f'/api/doc/{did}/regions/{rid}/mask', raw=True)
    m = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_UNCHANGED)
    return m[..., 3] > 0


def guide_lines(mask):
    """每个连通块按主轴垂直方向铺 1-3 条走向线。"""
    n, lab = cv2.connectedComponents(mask.astype(np.uint8))
    out = []
    for i in range(1, n):
        ys, xs = np.nonzero(lab == i)
        if len(xs) < 800:
            continue
        P = np.stack([xs, ys], 1).astype(np.float64)
        mean = P.mean(0)
        Q = P - mean
        _, V = np.linalg.eigh(Q.T @ Q / len(Q))
        v1, v2 = V[:, -1], V[:, 0]
        t, s = Q @ v1, Q @ v2
        t0, t1 = t.min(), t.max()
        fr = (0.35, 0.5, 0.65) if len(xs) > 6000 else (0.5,)
        for frac in fr:
            tc = t0 + frac * (t1 - t0)
            sel = np.abs(t - tc) < 3.0
            if sel.sum() < 4:
                continue
            p0 = mean + tc * v1 + s[sel].min() * v2
            p1 = mean + tc * v1 + s[sel].max() * v2
            out.append([float(p0[0]), float(p0[1]), float(p1[0]), float(p1[1])])
    return out


def _save_mask_overlay(base, did, rids, out_path, points=None):
    """把各部位掩码半透明叠在原图上，在质心标 1/2/3 编号，并把落点画成红色十字，
    供人工核对"点落在哪、区域圈到哪"（出图前必看）。"""
    art = np.frombuffer(http(base, f'/api/doc/{did}/art', raw=True)[1], np.uint8)
    vis = cv2.imdecode(art, cv2.IMREAD_COLOR)
    colors = [(250, 167, 101), (59, 130, 242), (140, 230, 140), (80, 80, 240), (240, 200, 60)]
    for i, rid in enumerate(rids):
        m = mask_of(base, did, rid)
        color = colors[i % len(colors)]
        vis[m] = (vis[m] * 0.5 + np.array(color) * 0.5).astype(np.uint8)
    for i, rid in enumerate(rids):
        ys, xs = np.nonzero(mask_of(base, did, rid))
        if not len(xs):
            continue
        cx, cy = int(xs.mean()), int(ys.mean())
        txt = str(i + 1)
        cv2.putText(vis, txt, (cx - 14, cy + 16), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (255, 255, 255), 9, cv2.LINE_AA)
        cv2.putText(vis, txt, (cx - 14, cy + 16), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (0, 0, 0), 3, cv2.LINE_AA)
    for x, y, _k in (points or []):
        x, y = int(x), int(y)
        cv2.drawMarker(vis, (x, y), (255, 255, 255), cv2.MARKER_CROSS, 46, 9, cv2.LINE_AA)
        cv2.drawMarker(vis, (x, y), (0, 0, 255), cv2.MARKER_CROSS, 46, 4, cv2.LINE_AA)
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    cv2.imencode('.png', vis)[1].tofile(out_path)
    return out_path


def _dark_blobs(img_bgr):
    """纯 OpenCV 启发式：找"深色细长"块，返回 (score, cx, cy) 降序。用作 SAM 探针的落点，也作兜底。"""
    H, W = img_bgr.shape[:2]
    L = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)[:, :, 0]
    thr = max(40, int(np.percentile(L, 35)))
    m = (L < thr).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, cc, stats, cent = cv2.connectedComponentsWithStats(m)
    cands = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < 0.004 * W * H or area > 0.35 * W * H:
            continue
        ar = max(w, h) / max(1, min(w, h))
        if ar < 1.5 or y + h / 2 < 0.15 * H:
            continue
        lum = float(L[cc == i].mean())
        cands.append((ar * (area / (W * H)) * (1.0 - lum / 255.0),
                      int(cent[i][0]), int(cent[i][1])))
    cands.sort(reverse=True)
    return cands


def _probe_grid(img_bgr):
    """SAM 探针落点：均匀网格 + 深色块质心，去重。"""
    H, W = img_bgr.shape[:2]
    step = max(40, int(min(W, H) / 18))
    pts = [(x, y) for y in range(step // 2, H, step) for x in range(step // 2, W, step)]
    pts += [(cx, cy) for _, cx, cy in _dark_blobs(img_bgr)]
    seen, out = set(), []
    for x, y in pts:
        k = (x // 12, y // 12)
        if k in seen:
            continue
        seen.add(k)
        out.append((float(x), float(y)))
    return out


def _stocking_score(seg, W, H):
    """给 SAM 的一个掩码打分：越像丝袜（纵向细长、面积适中、偏暗）分越高。0 = 不像。
    关键是把 SAM 常犯的"大合并块"（横跨大半幅宽度、或面积过大）直接判 0，否则会选中整块背景/下身。"""
    a = seg.get('area') or 0
    if not a:
        return 0.0
    f = a / float(W * H)
    if f < 0.004 or f > 0.20:
        return 0.0
    _, _, bw, bh = seg['bbox']
    if bw > 0.80 * W:               # 横跨大半幅宽度 = 合并背景/整条下身，不是一条腿
        return 0.0
    ar = max(bw, bh) / max(1, min(bw, bh))
    if ar < 1.4:
        return 0.0
    vert = bh / max(1, bw)          # 腿是"高比宽长"
    lum = min(max(seg.get('lum') or 0.0, 0.0), 255.0)
    dark = 1.0 - lum / 255.0
    return (min(ar, 5.0) ** 0.5) * (f ** 0.35) * (min(vert, 3.0) ** 0.6) * ((0.3 + 0.7 * dark) ** 1.2)


def _bbox_iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    if inter <= 0:
        return 0.0
    return inter / float(aw * ah + bw * bh - inter)


def _pick_regions(scored, max_pts, iou_max=0.35):
    """scored: (score, x, y, k, bbox)。按分取 max_pts 个彼此重叠很少的区域：
    用 bbox 的 IoU 抑制"同一块"以及"包含它的更大合并块"，避免把一条腿选成两个部位。
    返回 [(x, y, k)]：x,y 是探针的原始落点，k 是当时命中的 SAM 档位（0小/1中/2大）——
    复现同一掩码靠"同一落点 + 同一档位"。"""
    keep = []
    for sc, x, y, k, bbox in sorted(scored, key=lambda t: -t[0]):
        if all(_bbox_iou(bbox, it[4]) <= iou_max for it in keep):
            keep.append((sc, x, y, k, bbox))
        if len(keep) >= max_pts:
            break
    return [(int(x), int(y), int(k)) for _, x, y, k, _ in keep]


def _pick_far(scored, W, H, max_pts):
    """兜底：拿不到 bbox 时按质心距离取点。档位取最小(0)，避免把背景框进来。"""
    keep, rad = [], (0.08 * max(W, H)) ** 2
    for sc, cx, cy in sorted(scored, key=lambda t: -t[0]):
        if all((cx - k[0]) ** 2 + (cy - k[1]) ** 2 > rad for k in keep):
            keep.append((cx, cy))
        if len(keep) >= max_pts:
            break
    return [(int(x), int(y), 0) for x, y in keep]


def detect_points(base, did, img_bgr, max_pts=2):
    """效果优先：用服务里已加载的 GPU SAM 做点探针（点提示只跑轻量 mask decoder，不额外占显存），
    选最像丝袜的掩码、按区域重叠去重。返回 [(x, y, k)]：落点 + 该掩码命中的 SAM 档位；
    复现时"同落点 + 同档位"即得同一掩码。探针接口不可用时退回纯 OpenCV 启发式。"""
    H, W = img_bgr.shape[:2]
    pts = _probe_grid(img_bgr)
    s, r = http(base, f'/api/doc/{did}/probe', {'points': pts}, method='POST')
    if s != 200:
        print(f'[检测] SAM 探针不可用（{r}），退回启发式')
        return _pick_far(_dark_blobs(img_bgr), W, H, max_pts)
    scored = []
    for res in r['results']:
        px, py = res['x'], res['y']
        for si, seg in enumerate(res['segments']):
            sc = _stocking_score(seg, W, H)
            if sc > 0:
                scored.append((sc, px, py, si, seg['bbox']))
    return _pick_regions(scored, max_pts)


def _parse_points(s, default_k):
    """解析 --points：组间用 ';' 分隔，每组 = 一个部位；组内用 '+' 连接该部位的多个点
    （同部位多点会合并，用于补全/合并同一部位）。单点写法 'x,y[,k]'，k 省略时用 default_k。
    返回 [[(x,y,k), ...], ...]（外层 = 部位，内层 = 该部位的点）。"""
    groups = []
    for grp in s.split(';'):
        grp = grp.strip()
        if not grp:
            continue
        pts = []
        for p in grp.split('+'):
            p = p.strip()
            if not p:
                continue
            v = [float(t) for t in p.split(',')]
            pts.append((v[0], v[1], int(v[2]) if len(v) > 2 else default_k))
        if pts:
            groups.append(pts)
    return groups


def _warn_clipped(base, did, groups, rids):
    """预警"被相邻部位裁切"：部位间大范围重叠时，工具会把重叠只判给其中一块，另一块被裁掉。
    只对单点部位做（拿首点所选档位的候选面积 vs 最终覆盖像素），明显偏小就提示降档或改用 '+' 补点。"""
    pts = [[g[0][0], g[0][1]] for g in groups if len(g) == 1]
    if not pts:
        return
    s, r = http(base, f'/api/doc/{did}/probe', {'points': pts}, method='POST')
    if s != 200:
        return
    _, st = http(base, f'/api/doc/{did}/coverage/stats')
    cov = {row['id']: row['pixels'] for row in st['regions']}
    for i, grp in enumerate(groups):
        if len(grp) != 1:
            continue
        res = next((rr for rr in r['results']
                    if abs(rr['x'] - grp[0][0]) < 1 and abs(rr['y'] - grp[0][1]) < 1), None)
        if not res:
            continue
        segs = res.get('segments') or []
        k = grp[0][2]
        if k >= len(segs) or not segs[k].get('area'):
            continue
        final, cand = cov.get(rids[i], 0), segs[k]['area']
        if final < 0.5 * cand:
            print(f'  ⚠ 部位{i + 1} 疑似被相邻部位裁切：最终 {final}px 不足候选 {cand}px 的一半。'
                  f'建议降档，或在同一部位用 "+" 补点合并。')


def region_ids(base, did):
    _, st = http(base, '/api/doc')
    return [r['id'] for r in st['regions']]


def run_one(base, img_path, args, style, multi=False):
    stem = os.path.splitext(os.path.basename(img_path))[0]
    if args.name:
        name = args.name + (f'_{STYLE_CN[style]}' if multi else '')
    else:
        name = f'丝袜质感优化_{STYLE_CN[style]}'
    out_dir = os.path.join(args.out, stem)      # 每轮任务：产物根目录下按输入文件名建子目录
    tmp_dir = os.path.join(out_dir, 'temp')     # 中间件（掩码/预览）都放这个 temp 里，成品留在任务目录根
    os.makedirs(out_dir, exist_ok=True)
    try:                                        # 原图也存一份到任务目录，方便对照
        shutil.copy2(img_path, os.path.join(out_dir, '原图.png'))
    except Exception as e:
        print(f'[{stem}] 保存原图失败: {e}')
    s, st = http(base, '/api/open/path', {'path': img_path}, method='POST')
    if s != 200:
        raise RuntimeError(f'打开图片失败: {st}')
    did = st['id']
    print(f'[{stem}] 打开 {st["width"]}x{st["height"]} doc={did}')

    if args.points:
        groups = _parse_points(args.points, args.grow)
        print(f'[{stem}] 使用指定点（{len(groups)} 个部位）: '
              f'{[[(int(x), int(y), k) for x, y, k in g] for g in groups]}')
    else:
        art = np.frombuffer(http(base, f'/api/doc/{did}/art', raw=True)[1], np.uint8)
        bgr = cv2.imdecode(art, cv2.IMREAD_COLOR)
        groups = [[p] for p in detect_points(base, did, bgr)]
        print(f'[{stem}] SAM 自动检测到 {len(groups)} 个候选部位: '
              f'{[(int(g[0][0]), int(g[0][1]), g[0][2]) for g in groups]}')

    if not groups:
        print(f'[{stem}] 未能定位丝袜，请用 --points 指定坐标')
        return None

    rids = region_ids(base, did)
    while len(rids) < len(groups):
        s, r = http(base, f'/api/doc/{did}/regions', {'name': f'部位{len(rids)+1}'}, method='POST')
        rids = [x['id'] for x in r['regions']]
    for i, grp in enumerate(groups):
        rid = rids[i]
        http(base, f'/api/doc/{did}/regions/{rid}/clear', {}, method='POST')
        for x, y, k in grp:                 # 同组多点：依次点选+选档，累加进同一部位（合并）
            http(base, f'/api/doc/{did}/regions/{rid}/segment', {'x': x, 'y': y}, method='POST')
            http(base, f'/api/doc/{did}/segment/select', {'k': k}, method='POST')
    for i in range(len(groups), len(rids)):
        http(base, f'/api/doc/{did}/regions/{rids[i]}/clear', {}, method='POST')

    os.makedirs(tmp_dir, exist_ok=True)
    mask_path = os.path.join(tmp_dir, f'{name}_掩码.png')
    _save_mask_overlay(base, did, rids[:len(groups)], mask_path,
                       [p for g in groups for p in g])
    _warn_clipped(base, did, groups, rids[:len(groups)])

    if args.preview:
        pts_arg = ';'.join('+'.join(f'{int(x)},{int(y)},{k}' for x, y, k in g) for g in groups)
        print(f'[{stem}] 部位已就绪，请检查掩码图确认范围: {mask_path}')
        print(f'[{stem}] 确认无误后导出（原样复用 坐标+档位）: --points "{pts_arg}"')
        return mask_path

    _, st = http(base, '/api/doc')
    for s_ in st['strokes']:
        http(base, f'/api/doc/{did}/strokes/{s_["id"]}', method='DELETE')
    for rid in rids[:len(groups)]:
        for ln in guide_lines(mask_of(base, did, rid)):
            http(base, f'/api/doc/{did}/strokes', {'pts': ln, 'hint': rid}, method='POST')

    look = {'style': style, 'density': args.density, 'tilt': 32.0,
            'strength': args.strength, 'strength_auto': not args.no_auto_strength}
    http(base, f'/api/doc/{did}/look', look, method='PUT')
    for _ in range(240):
        _, info = http(base, f'/api/doc/{did}/look')
        if not info.get('solving') and info.get('textured'):
            break
        time.sleep(1)
    cov = http(base, f'/api/doc/{did}/coverage/stats')[1]['regions']
    print(f'[{stem}] 覆盖: ' + ', '.join(f'部位{r["id"]}={r["pixels"]}px' for r in cov[:len(groups)]))

    os.makedirs(STAGE, exist_ok=True)
    stage_png = os.path.join(STAGE, f'{name}.png')
    s, res = http(base, f'/api/doc/{did}/export', {'kind': 'png', 'path': stage_png}, method='POST')
    if s != 200:
        raise RuntimeError(f'导出失败: {res}')

    final = os.path.join(out_dir, f'{name}.png')
    try:
        shutil.copy2(res['file'], final)
    except Exception as e:
        print(f'[{stem}] 复制到 {out_dir} 被拦截（{e}）；成品在 {res["file"]}')
        final = res['file']

    png = http(base, f'/api/doc/{did}/render/fit?w=896&h=576', raw=True)[1]
    with open(os.path.join(tmp_dir, f'{name}_预览.png'), 'wb') as f:
        f.write(png)
    print(f'[{stem}] 产物目录: {out_dir}')
    print(f'[{stem}] 成品: {final}（掩码图: {mask_path}）')
    return final


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('images', nargs='+')
    ap.add_argument('--tool-dir', default=None,
                    help="工具安装目录（含 stocking 包与 .venv）；默认自动探测")
    ap.add_argument('--out', default=None,
                    help="产物根目录；每张图会在其下按输入文件名建同名子目录（默认 <工具目录>\\工作目录\\产物）")
    ap.add_argument('--name', default=None)
    ap.add_argument('--style', default=None, choices=list(STYLE_CN),
                    help="只出指定样式；不填则默认出全部 6 种各一版")
    ap.add_argument('--density', type=float, default=100.0)
    ap.add_argument('--strength', type=float, default=100.0)
    ap.add_argument('--no-auto-strength', action='store_true')
    ap.add_argument('--points', default=None,
                    help="x,y[,k][+x,y[,k]]*[;...]：';' 分部位，'+' 同部位合并多点，k=0小/1中/2大")
    ap.add_argument('--grow', type=int, default=0)
    ap.add_argument('--auto', action='store_true')
    ap.add_argument('--port', type=int, default=8766)
    ap.add_argument('--preview', action='store_true')
    args = ap.parse_args()

    if args.tool_dir:
        _init_paths(args.tool_dir)
    if not args.out:
        args.out = OUT_ROOT
    if not os.path.isdir(os.path.join(TOOL_DIR, 'stocking')):
        print(f'找不到工具目录（{TOOL_DIR} 下没有 stocking 包）。请用 --tool-dir 或设置 STOCKING_TOOL_DIR。')
        return 2

    styles = [args.style] if args.style else list(STYLE_CN)   # 不指定样式 = 默认全出 6 种
    if args.preview and not args.style:
        styles = styles[:1]                                   # 预览只需一张掩码，避免重复分割 6 次
    multi = len(styles) > 1
    base = f'http://127.0.0.1:{args.port}'
    ensure_server(base, args.port)
    for img in args.images:
        if not os.path.isfile(img):
            print(f'跳过（不存在）: {img}')
            continue
        for style in styles:
            run_one(base, img, args, style, multi)


if __name__ == '__main__':
    main()
