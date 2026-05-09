// Gate-level built-ins (IEEE 1364 primitives) mixed with a real module instance.
// Scanner must not treat not/buf/and/... as user-defined modules to resolve.
module torture_primitives_gates ();
  wire a, b, c, y, z;

  not   g_not   (y, a);
  buf   g_buf   (y, a);
  bufif0 g_bf0  (y, a, b);
  bufif1 g_bf1  (y, a, b);
  notif0 g_nf0  (y, a, b);
  notif1 g_nf1  (y, a, b);
  and   g_and   (y, a, b);
  nand  g_nand  (y, a, b);
  or    g_or    (y, a, b);
  nor   g_nor   (y, a, b);
  xor   g_xor   (y, a, b);
  xnor  g_xnor  (y, a, b);
  tran  g_tran  (a, b);
  tranif0 g_t0 (a, b, c);
  tranif1 g_t1 (a, b, c);
  pullup   (a);
  pulldown (b);
  nmos  g_nm (y, a, b);
  pmos  g_pm (y, a, b);
  rnmos g_rnm (y, a, b);
  rpmos g_rpm (y, a, b);
  cmos  g_cm (y, a, b, c, z);
  rcmos g_rcm (y, a, b, c, z);
  tri   g_tri (y, a);
  tri0  g_t0n (y);
  tri1  g_t1n (y);
  triand g_ta (y, a, b);
  trior  g_to (y, a, b);
  trireg g_tr (y);
  wand  g_wand (y, a, b);
  wor   g_wor  (y, a, b);

  torture_dep_a u_real_module ();
endmodule
