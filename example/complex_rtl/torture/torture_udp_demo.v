// 用户定义 primitive（UDP）：例化语法与 module 相同；依赖闭包须识别 primitive 定义。
primitive torture_udp_inv (q, a);
  output q;
  input a;

  table
 // a : q
    0 : 1;
    1 : 0;
  endtable
endprimitive

module torture_udp_demo ();
  wire q, a;
  torture_udp_inv u_inv (q, a);
endmodule
