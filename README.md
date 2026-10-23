# stocking-texture-optimize

> 给 AI 用的「丝袜质感优化」Skill：把插画图发给 AI，它会自动圈出丝袜部位、先出掩码图给你确认，确认后一次性输出 6 种织物纹理成品。

这是一个 **AI Skill**（`SKILL.md` + 自动化脚本），适用于 Trae、Claude Code 等支持 `SKILL.md` 的 AI 工具。
真正的渲染引擎是开源软件 **[丝袜纹理工具（stocking-texture-tool）](https://github.com/silvermoong/stocking-texture-tool)**（见下方重点介绍），
本仓库只负责把「分割部位 → 人工确认 → 铺走向线 → 渲染 → 导出」这套流程自动化。
全程本地运行，不联网、不上传图片。

---

## ⭐ 先认识渲染引擎：丝袜纹理工具

**本 Skill 只是「自动驾驶」，真正干活的是开源软件《丝袜纹理工具》**，所有渲染能力都来自它：

- **软件原作者：B 站 UP 主 纯银碎月**（GitHub：[@silvermoong](https://github.com/silvermoong)）
- 项目主页：**https://github.com/silvermoong/stocking-texture-tool** （MIT 开源、免费）
- 作者介绍视频：**[《轻松提升丝袜的绘画质感：丝袜纹理工具（开源免费）》](https://www.bilibili.com/video/BV1tkpW63EC6)**

它给插画里的丝袜加上**算出来的**真实织物纹理——纹理是几何计算的结果，不是生成式 AI 画的。粗选出丝袜所在部位，沿横纹画几条走向线，工具就算出纹理怎样绕着腿和身体走，再按选定的样式渲染。

主要功能（摘自作者介绍）：

- **点选**：点一下选出一条腿，小 / 中 / 大三档范围，画笔和橡皮修边
- **走向线**：沿横纹画 1–3 条线，一两秒横纹就铺满；另一侧点「镜像」直接翻过去
- **复杂场景**：腿弯折时画一条隔开线，膝盖补一条弧线平顺过渡；上衣可以切开、自动分割左右
- **织物样式**：细线、针织、线圈、斜单线、加濑风、油光（试验）
- **参数**：密度、强度、斜度、亮点；黑丝白丝按深浅自动设强度；细节预览随滑杆实时变化
- **没有摩尔纹**：横纹太密时自动减弱，导出的像素里没有摩尔纹
- **导出**：成品图、可叠回原图的透明丝袜层 PNG、可再打开接着改的引导 PSD；原文件不会被改写
- **全程本机运行**：安装后无须联网，什么都不上传

安装（Windows 10 / 11，有 NVIDIA 显卡更快，没有也能用）：下载仓库后双击 `install.bat` 一键安装，桌面会出现快捷方式；再双击一次 `install.bat` 就是更新。离线安装文件包：[releases/deps-1](https://github.com/silvermoong/stocking-texture-tool/releases/tag/deps-1)。

> **没有它，本 Skill 什么都做不了。请先安装它，也欢迎去原作者的项目点个 star、看他的介绍视频。**

---

## 能做什么

- **自动圈丝袜**：复用工具内已加载的 Segment Anything，按「纵向细长 + 面积适中 + 偏暗」挑出最像丝袜的区域
- **先确认再出图**：只出掩码图（部位编号 + 落点十字），你点头后才渲染，避免白跑
- **一次出 6 种样式**：细线、针织、线圈、斜单线、加濑风、油光
- **黑丝 / 白丝都行**：强度默认按丝袜深浅自动设定
- **按任务归档**：每张输入图一个目录，原图、成品、中间件分开放
- **手动兜底**：看图被内容过滤挡住时，可生成坐标网格图，让用户按坐标报点

## 工作流

```
发图 → 自动检测 / 报坐标 → 出掩码图确认 → 确认后渲染 6 种 → 导出到 产物/<文件名>/
                                      ↑
                              不满意就补点/降档，循环确认
```

---

## 依赖

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows 10 / 11（上游工具支持范围） |
| 渲染引擎 | [stocking-texture-tool](https://github.com/silvermoong/stocking-texture-tool) 已安装 |
| Python | 使用工具自带的 `.venv`，无需另装 |
| 显卡 | 有 NVIDIA 显卡更快，没有也能用 CPU |

---

## 安装

### 1. 安装渲染引擎

按上游 README 操作：下载仓库 → 双击 `install.bat` → 等待依赖和模型装完。
装好后目录里应有 `stocking/`、`.venv/`、`models/`。

### 2. 放入 Skill 目录

把本仓库放进你所用 AI 的 skills 目录：

> 不想手动挑文件的话，直接从 [Releases](https://github.com/AnSleeper/stocking-texture-optimize/releases) 下载打包好的 Skill zip（内含接收方使用说明），解压放入即可。

```
<Trae 项目或用户目录>/.trae/skills/stocking-texture-optimize/
```

其他支持 `SKILL.md` 的工具，放进对应 skills 目录即可。重启 AI 会话让它识别。

### 3. 打探针补丁（只需一次）

自动检测需要一个**只读** SAM 探针接口 `POST /api/doc/{doc_id}/probe`。运行：

```powershell
& "<工具目录>\.venv\Scripts\python.exe" "<skills目录>\stocking-texture-optimize\scripts\patch_probe.py" "<工具目录>"
```

- 幂等，重复运行无副作用
- 自动备份原 `server.py`
- 复用已加载的 SAM，只跑轻量 mask decoder，**不额外占显存**
- 打完重启工具服务生效

### 4. 指定工具目录

脚本按以下优先级自动定位（含 `stocking/` 包的目录）：

1. 环境变量 `STOCKING_TOOL_DIR`
2. `scripts/tool_dir.txt` 第一行
3. 从脚本位置向上逐级查找 `stocking/`
4. 常见安装位置（`~/stocking-texture-tool`、`C:\stocking-texture-tool`、`D:\stocking-texture-tool`）

任选一种配置方式：

```powershell
# A. 环境变量
$env:STOCKING_TOOL_DIR = "D:\stocking-texture-tool"

# B. 每次命令传参
& $py $s "图片.png" --tool-dir "D:\stocking-texture-tool" --preview

# C. 在 scripts/ 下建 tool_dir.txt，第一行写：
# D:\stocking-texture-tool
```

---

## 使用

### 交给 AI

直接把图发给 AI，说：

> 这张图帮我处理丝袜质感，是白丝

AI 会先出掩码图让你确认，确认后输出全部 6 种样式。

### 命令行

```powershell
$py = "<工具目录>\.venv\Scripts\python.exe"
$s  = "<skills目录>\stocking-texture-optimize\scripts\auto_stocking.py"

# 第 1 步：出掩码图确认（只分割，不渲染）
& $py $s "D:\图\青崽123.png" --points "400,800,0;1200,600,0" --preview

# 第 2 步：确认后原样复用坐标，出全部 6 种
& $py $s "D:\图\青崽123.png" --points "400,800,0;1200,600,0"
```

坐标语法：

```
--points "x,y[,k][+x,y[,k]]*[;...]"
```

- `;` 分隔**部位**，`+` 连接**同一部位的多个点**（会合并）
- `k` = SAM 档位：`0` 小 / `1` 中 / `2` 大，省略用 `--grow`
- 例：`400,800,0+800,1000,0;1312,672,0` = 部位①由两点合并；部位②单点

### 产物结构

```
<工具目录>/工作目录/产物/<输入文件名>/
├── 原图.png
├── 丝袜质感优化_细线.png
├── 丝袜质感优化_针织.png
├── 丝袜质感优化_线圈.png
├── 丝袜质感优化_斜单线.png
├── 丝袜质感优化_加濑风.png
├── 丝袜质感优化_油光.png
└── temp/
    ├── <输入文件名>_网格.png
    ├── 丝袜质感优化_<样式>_掩码.png
    └── 丝袜质感优化_<样式>_预览.png
```

---

## 目录结构

```
stocking-texture-optimize/
├── SKILL.md                      # AI 读取的主流程
├── scripts/
│   ├── auto_stocking.py          # 一键流水线
│   ├── grid_image.py             # 坐标网格图
│   ├── patch_probe.py            # 探针补丁（幂等）
│   └── tool_dir.txt.example      # 工具目录配置示例
└── references/
    ├── setup.md                  # 安装与配置
    └── api-and-params.md         # REST 接口、可调参数、探针源码
```

---

## 常用参数

| 参数 | 说明 |
|---|---|
| `--style S` | 只出指定样式；**不填 = 全部 6 种** |
| `--density N` | 密度，默认 100 |
| `--strength N` | 强度，默认 100（需配 `--no-auto-strength`） |
| `--no-auto-strength` | 关闭自动强度 |
| `--grow k` | points 未写档位时的默认档，默认 0 |
| `--out DIR` | 产物根目录，默认 `<工具目录>/工作目录/产物` |
| `--name NAME` | 输出文件名 |
| `--preview` | 只出掩码图，不导出成品 |
| `--port N` | 服务端口，默认 8766 |

完整参数与底层 API 见 [references/api-and-params.md](references/api-and-params.md)。

---

## 常见问题

**Q：自动圈得不准怎么办？**
以掩码图为准，手动报坐标；或运行 `grid_image.py` 生成带坐标的网格图，让用户按网格报点。

**Q：某条腿没圈全？**
优先「降档 + 同一部位用 `+` 补点合并」，不要盲目升到最大档——相邻部位用大档会大范围重叠、互相裁切。

**Q：提示「SAM 探针不可用」？**
补丁没生效，或服务还是旧进程。重新运行 `patch_probe.py` 并重启工具服务。

**Q：显存不够？**
不要为自动检测再加载第二个 SAM 实例。本 Skill 的探针复用服务内已加载的模型，不会额外占显存。

**Q：透肉/红润处没上纹理？**
该区域容易被当成皮肤，也可能被工具默认的「颜色排除」跳过。先多补几个点圈进掩码；仍不行再考虑关闭颜色排除。

---

## 与上游的关系

- **渲染引擎（软件本体）**：[silvermoong/stocking-texture-tool](https://github.com/silvermoong/stocking-texture-tool)，**原作者为 B 站 UP 主 纯银碎月（GitHub：[@silvermoong](https://github.com/silvermoong)）**，MIT 开源。[介绍视频：《轻松提升丝袜的绘画质感：丝袜纹理工具（开源免费）》](https://www.bilibili.com/video/BV1tkpW63EC6)
- 分割模型：Segment Anything（Meta，Apache-2.0）
- 深度模型：Depth Anything V2 Small（Apache-2.0）

本仓库只包含流程脚本与说明，不包含上游代码和模型文件。**全部渲染能力归功于原作者 [@silvermoong](https://github.com/silvermoong)，本 Skill 只是在其之上做流程自动化。**

## License

[MIT](LICENSE)
