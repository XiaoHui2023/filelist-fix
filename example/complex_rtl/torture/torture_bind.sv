`include "common/param_macro.vh"

// bind：目标层次后的模块类型与实例名；第二条带 #(宏参数)
module torture_bind_mon ();
endmodule

bind top_chip torture_bind_mon torture_bind_mon_inst ();

bind top_chip torture_param_leaf #(`TORTURE_P_W, `TORTURE_P_D) torture_bind_param_inst ();
