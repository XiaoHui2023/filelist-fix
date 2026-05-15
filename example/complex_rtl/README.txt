complex_rtl — 刻意复杂化的 Verilog/SystemVerilog 黄金样例
============================================================

目录结构（简要）：

  top_chip.v          顶层：串联多枚 `include，模块体由若干 .vh 拼接
  common/             嵌套 include、全局宏、带参 `define 试验
  pieces/             端口/连线 generate、celldefine 片段、多级 include 链 (chain_d→e→f)
  hier/               叶子与中层、generate-for、单文件双 module (dual_mods.sv)
  torture/            刁钻语法与注释牧场；torture/nested/ 下为四层 `include` 链 + 多层 ifdef/elsif/else + 嵌套 generate-for

用途：
- 示范「多文件通过 `include` 拼成逻辑整文件」；
- 覆盖 `ifdef/elsif/define/undef、celldefine、generate、层次实例化、单文件多 module（fd/rg 分工）`；**torture/torture_ifdef_zoo.v** 专门堆叠 **`ifndef` / `ifdef` / `elsif` / `else` 与嵌套 `ifndef`**（依赖 prelude 宏如 **WITH_DUAL**）；**torture/torture_primitives_gates.v** 堆叠 **IEEE 门级原语**（`not`/`buf`/`and`/…）与真实 **`torture_dep_a`** 例化，供依赖扫描排除原语；**torture/torture_udp_demo.v** 含 **用户定义 `primitive`（UDP）** 与同文件 **module 例化**，供闭包与 rg 按 `primitive` 声明定位；
- 作为 example 脚本与手工调试解析器的共同输入。
- 块注释内请勿写 `` `ifdef`` 等预处理行：当前管线在剥离块注释前逐行解释指令，会被误读。

运行：
  在仓库根执行 example.bat（Windows）或 ./example.sh（Linux/macOS）；静态前导文件为
  example/run_prelude.f（+define+ / +incdir+，路径相对该文件所在目录），输出写入
  example/generated/demo_filelist.f；generated/ 已加入 .gitignore。
