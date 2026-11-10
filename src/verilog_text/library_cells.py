"""Conservative, source-local evidence for cell models and lazy directory lookup."""
from __future__ import annotations

import re


def inspect_library_source(text: str) -> tuple[list[str], list[str], bool, str]:
    text = re.sub(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*',
                  lambda m: re.sub(r'[^\r\n]', ' ', m.group()), text, flags=re.DOTALL)
    directives = re.findall(r'`([A-Za-z_]\w*)', text)
    permitted = {'celldefine', 'endcelldefine'}
    unsafe = sorted(set(directives) - permitted)
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
    if unsafe:
        return names, [], False, 'preprocessor context: ' + ', '.join(unsafe)
    if not balanced or cell:
        return names, [], False, 'unbalanced celldefine'
    if not names or any(kind not in {'module', 'macromodule', 'primitive'} for kind in kinds):
        return names, cells, False, 'non-cell compilation units'
    if len(names) != 1:
        return names, cells, False, 'multiple compilation units'
    return names, cells, True, ''
