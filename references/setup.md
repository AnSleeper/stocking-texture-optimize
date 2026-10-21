# 安装与配置

## 1. 安装工具本体

上游项目：`https://github.com/silvermoong/stocking-texture-tool`

1. 下载仓库（Code → Download ZIP 解压，或 `git clone`）。
2. 双击文件夹里的 `install.bat`。安装程序会：
   - 检测显卡（NVIDIA RTX 20 系或更新、驱动 570+ 走 GPU 版；否则 CPU 版）
   - 下载独立 Python 3.12、依赖、对应 PyTorch 和两个模型（SAM ViT-B、Depth Anything V2 Small）
   - 在桌面建「丝袜纹理工具」快捷方式
3. 装好后目录里会有：
   - `stocking/` 包
   - `.venv/Scripts/python.exe`（Windows）
   - `models/`（含 `sam_vit_b_01ec64.pth` 等）
   - `start.bat`

> 路径不要太长（100 字符以内）。显卡版下载约 3.3 GB，装完约占 5 GB。
> 断网可重新运行 `install.bat`，已下载部分不会重复下载。

**离线安装**：从 releases 的 `deps-1` 下载 `stt-deps-1-base.zip` + 对应 torch 包，
放进 `install.bat` 旁的 `deps/` 文件夹（不解压、不改名），再运行 `install.bat`。

---

## 2. 打探针补丁（自动检测必需）

自动检测依赖一个**只读** SAM 探针接口 `POST /api/doc/{doc_id}/probe`。
它复用服务里已加载的 SAM，只跑轻量 mask decoder，**不额外占显存**、不改文档。

```powershell
& "<工具目录>\.venv\Scripts\python.exe" "<SKILL_DIR>\scripts\patch_probe.py" "<工具目录>"
```

- 脚本幂等：已存在该接口时直接跳过。
- 打补丁前会自动备份 `server.py`（`.bak-时间戳`）。
- 打完重启工具服务生效。
- 若提示找不到锚点（工具版本不同），参考 `api-and-params.md` 里的源码手动插入。

---

## 3. 指定工具目录

脚本按以下优先级定位工具目录（含 `stocking/` 包）：

1. 环境变量 `STOCKING_TOOL_DIR`
2. `scripts/tool_dir.txt` 第一行
3. 从脚本位置向上逐级查找 `stocking/`
4. 常见安装位置（`~/stocking-texture-tool`、`C:\stocking-texture-tool`、`D:\stocking-texture-tool`）
5. 脚本所在目录（兜底）

推荐做法（任选一种）：

```powershell
# A. 环境变量（当前会话）
$env:STOCKING_TOOL_DIR = "D:\stocking-texture-tool"

# B. 每次命令传参
& $py $s "<图>" --tool-dir "D:\stocking-texture-tool" --preview

# C. 在 scripts/ 下建 tool_dir.txt，第一行写：
# D:\stocking-texture-tool
```

---

## 4. 验证

```powershell
# 服务能起来、探针可用
& $py $s "<任意图片>" --preview
```

正常输出应包含：
- `打开 <宽>x<高> doc=...`
- `SAM 自动检测到 N 个候选部位`（或 `使用指定点...`）
- `部位已就绪，请检查掩码图确认范围: ...temp\..._掩码.png`

若看到 `SAM 探针不可用` 并退回启发式，说明补丁没生效或服务是旧进程——重启服务再试。

---

## 5. 产物目录

默认 `<工具目录>/工作目录/产物`。想换位置：

```powershell
$env:STOCKING_OUT_ROOT = "D:\我的产物"
# 或
& $py $s "<图>" --out "D:\我的产物"
```

每张图仍会在该根目录下按输入文件名建子目录，规则不变。
