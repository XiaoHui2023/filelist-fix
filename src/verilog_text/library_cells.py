"""Broad model signals with a separate conservative directory-safety result."""
from __future__ import annotations

import re


def inspect_library_source(text: str) -> tuple[list[str], list[str], bool, str, bool, list[str]]:
    model_pragma = False
    def mask(match):
        nonlocal model_pragma
        if re.match(r'//\s*(?:synthesis|synopsys)\s+(?:syn_black_box|black_box)\b', match.group()):
            model_pragma = True
        return re.sub(r'[^\r\n]', ' ', match.group())
    text = re.sub(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*',
                  mask, text, flags=re.DOTALL)
    directives = re.findall(r'`([A-Za-z_]\w*)', text)
    permitted = {'celldefine', 'endcelldefine'}
    unsafe = sorted(set(directives) - permitted)
    local_preprocessor = {'define', 'undef', 'undefineall', 'ifdef', 'ifndef', 'elsif', 'else', 'endif'}
    compiler_context = bool(set(directives) - permitted - local_preprocessor)
    features = []
    if 'celldefine' in directives:
        features.append('celldefine')
    if re.search(r'\b(?:specify|specparam)\b', text):
        features.append('timing-model')
    if re.search(r'\bprimitive\b', text):
        features.append('udp')
    gates = ('and|nand|or|nor|xor|xnor|buf|not|bufif0|bufif1|notif0|notif1|'
             'nmos|pmos|cmos|rnmos|rpmos|rcmos|tran|rtran|tranif0|tranif1|'
             'rtranif0|rtranif1|pullup|pulldown')
    if re.search(r'(?:^|;)\s*(?:' + gates + r')\b\s*(?:[A-Za-z_]\w*\s*(?:\[[^\]\r\n]+\]\s*)*)?(?:\(|#)',
                 text, flags=re.MULTILINE):
        features.append('gate-primitive')
    if model_pragma or any(re.search(r'\b(?:blackbox|black_box|syn_black_box|whitebox|lib_whitebox|abc9_box)\b', attribute)
           for attribute in re.findall(r'\(\*.*?\*\)', text, flags=re.DOTALL)):
        features.append('model-attribute')
    if re.search(r'\b(?:supply0|supply1|trireg)\b', text):
        features.append('supply-or-charge-net')
    strengths = r'(?:supply[01]|strong[01]|pull[01]|weak[01]|highz[01]|large|medium|small)'
    if re.search(r'\(\s*' + strengths + r'\s*(?:,\s*' + strengths + r'\s*)?\)', text):
        features.append('drive-or-charge-strength')
    names, cells = [], []
    cell = False
    balanced = True
    pattern = (r'`(?P<directive>celldefine|endcelldefine|resetall)\b|'
               r'\b(?P<kind>module|macromodule|primitive|package|interface|program)\s+'
               r'(?:(?:automatic|static)\s+)?(?P<name>[A-Za-z_]\w*)\b')
    kinds = []
    for match in re.finditer(pattern, text):
        directive = match.group('directive')
        if directive == 'celldefine':
            balanced &= not cell
            cell = True
        elif directive in {'endcelldefine', 'resetall'}:
            if directive == 'endcelldefine':
                balanced &= cell
            cell = False
        else:
            names.append(match.group('name'))
            kinds.append(match.group('kind'))
            if cell:
                cells.append(match.group('name'))
    # Package/interface bodies have their own scope; declarations outside all
    # units can instead supply $unit types/functions to another source file.
    body = re.sub(r'\b(?:module|macromodule|primitive|package|interface|program)\b.*?'
                  r'\b(?:endmodule|endprimitive|endpackage|endinterface|endprogram)\b'
                  r'(?:\s*:\s*[A-Za-z_]\w*)?', '', text, flags=re.DOTALL)
    body = re.sub(r'^[ \t]*`[^\r\n]*|\(\*.*?\*\)', '', body, flags=re.MULTILINE | re.DOTALL)
    compiler_context |= bool(body.strip())
    if unsafe:
        return names, [], False, 'preprocessor context: ' + ', '.join(unsafe), compiler_context, features
    if not balanced or cell:
        return names, [], False, 'unbalanced celldefine', compiler_context, features
    if not names or any(kind not in {'module', 'macromodule', 'primitive'} for kind in kinds):
        return names, cells, False, 'non-cell compilation units', compiler_context, features
    if len(names) != 1:
        return names, cells, False, 'multiple compilation units', compiler_context, features
    # A module file may also export $unit declarations or perform global binds.
    # Those effects must remain eager even though its module name is addressable.
    if body.strip():
        return names, cells, False, 'compilation-unit declarations', compiler_context, features
    return names, cells, True, '', compiler_context, features
