# 底层 API 与可调参数

脚本覆盖不到时，可直接驱动服务。服务启动：

```powershell
& "<工具目录>\.venv\Scripts\python.exe" -m stocking --isolated --no-window --stay --port 8766
```

工作目录（cwd）设为工具安装目录。所有接口在 `http://127.0.0.1:8766`。

---

## 1. 接口表

| 方法 路径 | 作用 |
|---|---|
| `GET /api/ping` | 探活 |
| `POST /api/open/path` `{path}` | 打开图片，返回 doc 状态 |
| `GET /api/doc` | 当前文档状态（区域 / 走向线 / 状态） |
| `GET /api/doc/{id}/art` | 原图 PNG |
| `GET /api/doc/{id}/regions/{rid}/mask` | 部位掩码 PNG（RGBA，A 通道为覆盖） |
| `POST /api/doc/{id}/regions` `{name}` | 新建部位 |
| `POST /api/doc/{id}/regions/{rid}/clear` | 清空该部位掩码 |
| `POST /api/doc/{id}/regions/{rid}/segment` `{x,y,subtract,seams}` | SAM 点选加入该部位（默认取最小候选） |
| `POST /api/doc/{id}/segment/select` `{k,seams}` | 切换 SAM 候选档位 k=0小/1中/2大 |
| `POST /api/doc/{id}/probe` `{points:[[x,y],...]}` | **只读 SAM 探针**（本 Skill 的补丁）：每点返回三档掩码的 area/bbox/centroid/lum，复用已加载模型、不改文档 |
| `GET /api/doc/{id}/segment/outlines` | 最近一次点选的候选轮廓（像素 ×10） |
| `POST /api/doc/{id}/regions/{rid}/paint` `{pts,radius,erase}` | 画笔 / 橡皮手动补画 |
| `POST /api/doc/{id}/strokes` `{pts,hint}` | 加走向线（pts 为扁平 `[x0,y0,x1,y1,...]`） |
| `DELETE /api/doc/{id}/strokes/{sid}` | 删走向线 |
| `POST /api/doc/{id}/dividers` `{pts,snap}` | 加隔开线 |
| `POST /api/doc/{id}/undo` `/redo` | 撤销 / 重做 |
| `PUT /api/doc/{id}/look` `{...}` | 设置样式参数并触发渲染 |
| `GET /api/doc/{id}/look` | 渲染状态（`solving` / `textured` / `check`） |
| `GET /api/doc/{id}/coverage/stats` | 各部位像素与覆盖数 |
| `GET /api/doc/{id}/render/fit?w=&h=` | 适配尺寸的渲染预览 PNG |
| `POST /api/doc/{id}/export` `{kind,path}` | 导出：`png` 成品 / `cutout` 仅丝袜 / `guides` 引导 PSD |

---

## 2. `PUT /api/doc/{id}/look` 可调参数

| 参数 | 默认 | 范围 | 说明 |
|---|---|---|---|
| `style` | `knit` | knit/loops/coil/lines/grain/oily | 样式 |
| `density` | 100 | 40–200 | 纹理密度 |
| `tilt` | 32 | 0–75 | 斜度，**仅 `lines` 用** |
| `strength` | 100 | 0–250 | 纹理强度 |
| `strength_auto` | true | bool | 自动强度：按丝袜明暗自动定强度（白丝自动调低） |
| `sparkle_depth` | 100 | 0–300 | 凸起处亮点 |
| `sparkle_bright` | 100 | 0–300 | 已画高光处亮点 |
| `sparkle_painted` | 0 | 0–300 | 亮点图层 |
| `sparkle_even` | 0 | 0–300 | 均匀亮点 |
| `sparkle_link` | true | bool | bright 跟随 depth（两者合一） |
| `moire_on` | false | bool | 摩尔纹开关 |
| `moire` | 100 | 0–100 | 摩尔纹强度（需 `moire_on=true`） |
| `moire_area` | 100 | 0–100 | 摩尔纹面积 |

另有**颜色排除**（默认开）：金边 / 手套 / 露肤处不加纹理。
若用户反馈透肉红润处没上纹理，除多补点外，可考虑关闭颜色排除（具体字段名以工具当前版本 UI 为准）。

---

## 3. `probe` 接口源码（手动打补丁用）

插入到 `stocking/server.py` 中 `@app.post('/api/doc/{doc_id}/segment/cycle')` **之前**：

```python
class ProbeIn(BaseModel):
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
```

依赖：文件里已有 `BaseModel`、`np`、`sam.service`、`doc_for`。

---

## 4. 自动检测打分逻辑（想改检测效果时看这里）

`auto_stocking.py` 里的 `_stocking_score(seg, W, H)`：

- 面积占比 `f = area / (W*H)`，要求 `0.004 ≤ f ≤ 0.20`，否则判 0。
- bbox 宽度 `bw > 0.80 * W` 判 0（横跨大半幅 = 合并背景 / 整条下身）。
- 长宽比 `ar < 1.4` 判 0。
- 打分 = `min(ar,5)^0.5 * f^0.35 * min(vert,3)^0.6 * (0.3+0.7*dark)^1.2`
  （`vert = bh/bw`，`dark = 1 - lum/255`）。

去重：`_pick_regions` 按 bbox IoU ≤ 0.35 抑制同区域与包含它的更大合并块，取最高分的 1–2 个。
落点网格：`_probe_grid` = 均匀网格（步长 `min(W,H)/18`）+ 深色连通块质心。
