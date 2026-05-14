`include "common/param_macro.vh"

// #() 位置/命名参数、宏、`define 展开后嵌套括号、续行折行、匿名例化、默认 #()
module torture_hash_params ();
  torture_param_leaf #(`TORTURE_P_W, `TORTURE_P_D) u_pos_macros ();
  torture_param_leaf #(16, 8) u_pos_numeric ();
  torture_param_leaf #(`TORTURE_P_W, 2) u_pos_mixed ();
  torture_param_leaf #(.W(`TORTURE_P_W), .D(`TORTURE_P_D)) u_named_macros ();
  torture_param_leaf #(.W(4), .D(2)) u_named_plain ();
  torture_param_leaf #( \
    `TORTURE_P_W, `TORTURE_P_D \
  ) ();
  torture_param_leaf #() u_default ();
  torture_param_leaf #(.W(5'ha), .D(1'd1)) u_sized_dec_hex ();
  torture_param_leaf #(.W({4'd1, 4'd0}), .D(2)) u_param_concat ();
  torture_param_leaf #(.W({4{1'b1}}), .D(1)) u_repl_concat ();
  torture_dep_a u_keep ();
endmodule
