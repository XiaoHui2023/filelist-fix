`define WORD_SEL(bus, idx) (((bus) >> ((idx) * 8)) & 8'hFF)

// torture_hash_params / bind：例化 #() 里用的宽度类宏（避免与 WORD_SEL 混在同一行）
`define TORTURE_P_W 8
`define TORTURE_P_D 4
