from __future__ import annotations

from verilog_text.scan import (
    _ENDMODULE,
    _MODULE_HEAD,
    parse_instance_line_analysis,
    _parse_bind_line,
)


def build_instance_scan_trace(text: str) -> str:
    """生成与 ``scan_verilog_body`` 对齐的例化/bind 逐行判定说明，供 --debug-dump 写入。

    多行例化的中间行仍可能为 SKIP（本函数按行调用 ``parse_instance_line_analysis``），
    与 ``scan_verilog_body`` 的整段锚点扫描结论不必逐行一致。
    """

    parts: list[str] = []
    pos = 0
    found_module = False
    while True:
        mh = _MODULE_HEAD.search(text, pos)
        if not mh:
            break
        found_module = True
        em = _ENDMODULE.search(text, mh.end())
        if not em:
            parts.append(f"=== module {mh.group(1)}（未找到 endmodule，停止体追踪）===\n")
            break
        name = mh.group(1)
        body = text[mh.end() : em.start()]
        parts.append(f"=== module {name}（self_mod={name!r}）===\n")
        for bi, line in enumerate(body.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                parts.append(f"b{bi:04d} |\n     | SKIP | 空行\n")
                continue
            bh = _parse_bind_line(line)
            if bh:
                parts.append(f"b{bi:04d} | {line}\n     | BIND | 绑定模块类型={bh!r}\n")
                continue
            inst, why = parse_instance_line_analysis(line, name)
            if inst:
                parts.append(f"b{bi:04d} | {line}\n     | MATCH | 模块类型={inst!r} | {why}\n")
            else:
                parts.append(f"b{bi:04d} | {line}\n     | SKIP | {why}\n")
        pos = em.end()

    if not found_module:
        parts.append("=== 无 module…endmodule 对（整文件按 scan 退化路径扫例化）===\n")
        for fi, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                parts.append(f"f{fi:04d} |\n     | SKIP | 空行\n")
                continue
            bh = _parse_bind_line(line)
            if bh:
                parts.append(f"f{fi:04d} | {line}\n     | BIND | 绑定模块类型={bh!r}\n")
                continue
            inst, why = parse_instance_line_analysis(line, "")
            if inst:
                parts.append(f"f{fi:04d} | {line}\n     | MATCH | 模块类型={inst!r} | {why}\n")
            else:
                parts.append(f"f{fi:04d} | {line}\n     | SKIP | {why}\n")
        return "".join(parts)

    parts.append("\n=== bind 行（全文件第二遍，与 scan 一致）===\n")
    for fi, line in enumerate(text.splitlines(), start=1):
        bh = _parse_bind_line(line)
        if bh:
            parts.append(f"f{fi:04d} | {line}\n     | BIND | 绑定模块类型={bh!r}\n")

    return "".join(parts)
