---
name: python-project-design-notes
description: >-
  本仓库：给 AI Agent 的指令、验收与设计备忘（单一真源）；不替代代码与对外 README。
---

# 本仓库 · Agent 设计笔记与要求

## 设计意图（像设计图）

本工具从用户给出的 **HDL 检索根目录 / 文件** 与 **一个或多个顶层模块名** 出发，用 **fd（同名速查）→ rg（按 module 声明补漏）** 定位定义文件，再对 SystemVerilog / Verilog 做 **条件编译 + include 展开 + 去噪声压缩** 后抽取模块依赖，按 **依赖在前** 排序输出 **filelist**；可选 **SQLite** 按 mtime/size 缓存单文件解析结果以加速重复运行。控制面使用 **python-library-callback** 的 **`api` / `impl`**，进度通过 **`OnProgressAPI`** 在 **`impl/sink`** 联动 **rich** 与 **alive-progress**；**`AppContext`** 给主流程与事件载荷共用。

## 来自用户/团队的设计与验收要求（原始条目）

以下为当期需求口径，实现以代码为准；此处只保存「要做什么」，不写具体符号实现。

1. **CLI**：`argparse`；**多个**源目录或文件；**多个**顶层模块名。
2. **结构**：目录按功能聚合、分散多文件；职责相近的函数收到**工具类**里，主流程**实例化**该类再调方法，便于传参与共享状态、入口清晰。
3. **tools/**：提供 **Linux shell** 与 **Windows bat**，从官方静态发行页下载 **rg**、**fd**，解压后放入 **`tools/bin`**并统一命名；README 写链接、步骤与约定。
4. **搜索双路径（core）**：**fd** 快速路径，适用「模块名 = 文件名」；**rg** 精读路径。二者共用 **`core/hdl_extensions.py`** 中的后缀表，覆盖 **`.v` / `.sv` / `.vh` / `.svh`、VHDL（`.vhd` / `.vhdl`）及常见扩展（如 `.vp` / `.sva` / `.vams` / `.vl` / `.verilog` 等）**；**不**刻意扫隐藏路径以提速。
5. **框架**：依赖 **python-library-callback**，采用 **`api` + `impl`** 分层（事件类型与 sink 注册分离）。
6. **可观测性**：**rich** + **logging**；日志路径由参数指定，**默认不写文件**；终端用**动态进度条**类库；进度通过 **api 事件 + impl** 驱动（非裸写进度逻辑）。
7. **上下文**：提供 **context**，主流程与 impl-api 共用（控制台、日志、进度句柄、`emit`/`fire` 环境等）。
8. **filelist 前导**：参数可指定含 **`+define+` / `+incdir+`** 或普通 filelist 片段的文件；这些内容**原样置于**最终 filelist **开头**，并参与解析侧宏/路径语义。
9. **解析**：独立能力解析 **filelist 指令** 与 **Verilog 相关语法**；按**加载顺序**推算条件编译，判断哪些源码在宏开启/关闭下参与依赖。
10. **性能**：依赖分析不必解析 **always** 等大段行为块；宜先做**删减/压缩**再跑正则，降低扫描成本。
11. **运行态组件**：有对象**跟踪当前 filelist 构建进度**、**宏定义的增减**（解析过程中演化），**每次解析**后更新一致状态（与实现中 `FilelistSessionState` 等对应；若代码演进，本节描述的是意图）。
12. **存档**：可选 **数据库文件**；未指定则不用存档。指定时用于**恢复**：按存档记录的顺序检查 **filelist 项及对应文件**是否变更（如 mtime），**恢复到未变路径的最大前缀**，从**首次变更处**重算，避免重复劳动又避免遗漏。

## 与当前实现的对齐与折中（硬性记录）

- CLI：`--prelude` / `--output` / `--archive` / `--log-file` / `--rg` / `--fd` 等已对齐意图；多 **SOURCE**、多 **`--top`**。
- **存档**：现为 **按单文件** SQLite 缓存解析结果 + **mtime/size** 失效；效果上接近「未改文件不重解析」。**未单独实现**「整条 filelist 全局状态机按序逐格回放」的独立模块；若需与第 12 条字面完全一致，需后续迭代。
- **宏**：**prelude** 与**单文件内** `ifdef` / `define` / `include` 展开已覆盖；**跨文件、严格按最终 filelist 顺序累积的全局 `` `define``** 未完整仿真（见下备忘）。
- **HDL 后缀**：**fd** 与 **rg** 的候选文件后缀由 **`core/hdl_extensions.HD_SOURCE_EXTENSIONS`** 单一维护（必含 **sv**），新增后缀只改此处。
- **example**：`demo.py` 在生成 `example/generated/run_prelude.f` 与 **`demo_filelist.f`** 后，用断言校验 prelude 行与 **filelist 拓扑序** 与黄金样例 `complex_rtl` 一致（若解析/排序逻辑变更需同步更新 `EXPECTED_TOPO_ORDER`）。

## 备忘与待定

- 可补充 **api/resolve** 清单 + **impl/resolve**，将测试桩 **`find_file`** 提升为正式依赖注入。
- 评估是否实现：**全工程宏序** + **按存档 filelist 顺序**做过期检测与断点续跑（相对当前按文件缓存更进一步）。
