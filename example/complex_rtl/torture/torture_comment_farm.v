// 整行 // 注释（ASCII）
/* 单行块注释：含 // 与关键字 module endmodule 仅作噪声，不应截断结构 */
module torture_comment_farm (  // 行尾 //
  /* 端口列表里的块注释 */
  // 端口之间
);
  /*
   多行块注释：
   // 伪行注释
   module fake_inner (); endmodule
   不在此写反引号指令，以免未去注释前的预处理误读
  */
  /*** 类 JavaDoc 风格块头，仅装饰 ***/
  //	tab 缩进行注释（制表符后接 //）
  wire x;  // endmodule 若被当源码会坏事——应在行注释中去掉

  /* 块包实例 */ torture_dep_a /* 名与括号间 */ u_a /* ( */ ( /* ) */ );  // 尾注释

  torture_dep_b u_b ( /* 端口侧块注释 */ );  // 与续行不同：避免单独一行「实例名 ();」被误扫为匿名例化

  localparam string HINT = "string://not-a-comment/*nor*/";
  /* 另一实例：与上行同型，单行书写以免「仅空白括号」被误扫为匿名例化 */
  torture_dep_a u_a2 ();  // 与 u_a 同型重复例化，依赖仍为 torture_dep_a

endmodule
// 文件末尾行注释（其后仍有换行，便于工具链）
