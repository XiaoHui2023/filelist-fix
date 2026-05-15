# API

## events.filelist_build

### OnPreludeLoadedAPI

- **调用时机**：prelude 读入并入会话宏与 `+incdir+` 之后、闭包开始前
- **说明**：统计 prelude 路径数与宏行规模

### OnModuleResolveMissAPI

- **调用时机**：闭包循环内，某模块名首次经 fd→rg 仍未找到对应源文件时（**同一会话内每个名至多一次**）
- **说明**：该模块跳过；后续引用不再重复 fd/rg、不再入队

### OnModuleIndexInconsistentAPI

- **调用时机**：闭包循环内，模块已映射但该文件尚未进入已解析集合时
- **说明**：内部索引不一致，跳过该模块

### OnSourceParsedAPI

- **调用时机**：每文件完成解析或命中有效缓存并入图后
- **说明**：载荷含是否命中已保存结果

### OnClosureEmptyAPI

- **调用时机**：闭包结束且无任何文件级引用边时
- **说明**：仍写出仅含 prelude 等的 filelist

### OnBuildTopologyReadyAPI

- **调用时机**：拓扑排序得到有序路径列表之后、写 filelist 之前
- **说明**：载荷含排序后路径数等

### OnFilelistWriteAPI

- **调用时机**：filelist 正文拼好后
- **说明**：写出完整 filelist 到 `-o` 所指路径；正文里各源文件行的相对/绝对格式与 CLI `--path-style` 一致（prelude 头行不受此项影响）

### OnSessionEndAPI

- **调用时机**：一次构建收尾时
- **说明**：释放 `--save` 所用存储等资源

## events.progress

### OnProgressAPI

- **调用时机**：进入解析与闭包前；写 filelist 前一步；结束前
- **说明**：粗粒度阶段与可选调试日志

## resolve.verilog_text

### ScanVerilogForDependenciesAPI

- **调用时机**：与 `SqueezeForDependencyScanAPI` 同一步骤链上、紧接 squeeze 输出之后
- **说明**：从已压缩文本解析出定义模块、引用模块与 include 路径串

### JoinContinuedLinesAPI

- **调用时机**：单文件读入后、展开 include 与宏相关预处理之前
- **说明**：合并反斜杠续行

### SqueezeForDependencyScanAPI

- **调用时机**：文本按宏与 include 展平后、扫描模块名引用之前
- **说明**：按固定顺序整段压缩：去注释 → 去掉 **always**（含 **always_ff / always_comb / always_latch**）**initial**、**final**、**task**、**specify**、**generate…endgenerate** 等与例化无关的整块（**generate** 体内例化不计入依赖）→ 按行弱化声明与若干 `` ` `` 编译指令行 → 去掉各 **module** 端口头 → 例化端口骨架化，以缩短后续正则扫描文本

### StripVerilogCommentsAPI

- **说明**：与依赖扫描前的整段处理一并完成，本节不单列为一步

### DropAlwaysishBlocksAPI

- **说明**：去掉 **always** 全家、**initial**、**final**、**task…endtask**（含 **extern task** 原型）、**specify…endspecify** 等整块；输入一般为已去注释文本
