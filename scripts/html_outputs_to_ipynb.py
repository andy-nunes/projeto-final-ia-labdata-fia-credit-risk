"""Injeta outputs de export HTML JupyterLab em um notebook .ipynb."""

from __future__ import annotations

import json
import re
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


class NotebookHTMLParser(HTMLParser):
    """Parser mínimo para células JupyterLab HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.cells: list[dict[str, Any]] = []
        self._cell_stack: list[str] = []
        self._in_main = False
        self._in_code_pre = False
        self._in_output_area = False
        self._in_output_block = False
        self._output_mime: str | None = None
        self._output_class: str = ''
        self._capture_tag: str | None = None
        self._capture_parts: list[str] = []
        self._current_code: list[str] = []
        self._current_outputs: list[dict[str, Any]] = []
        self._current_output_children: list[dict[str, Any]] = []
        self._execution_count: int | None = None
        self._pending_prompt_text: list[str] = []
        self._in_input_prompt = False
        self._img_src: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        classes = attrs_dict.get('class', '') or ''

        if tag == 'main':
            self._in_main = True
            return
        if not self._in_main:
            return

        if tag == 'div' and 'jp-Cell jp-CodeCell' in classes:
            self._cell_stack.append('code')
            self._current_code = []
            self._current_outputs = []
            self._execution_count = None
            return

        if tag == 'div' and 'jp-Cell jp-MarkdownCell' in classes:
            self._cell_stack.append('markdown')
            return

        if not self._cell_stack:
            return

        if self._cell_stack[-1] == 'code':
            if tag == 'div' and 'jp-InputPrompt' in classes:
                self._in_input_prompt = True
                self._pending_prompt_text = []
            elif tag == 'pre' and self._in_code_context(classes):
                self._in_code_pre = True
                self._current_code = []
            elif tag == 'div' and 'jp-OutputArea jp-Cell-outputArea' in classes:
                self._in_output_area = True
            elif self._in_output_area and tag == 'div' and 'jp-OutputArea-output' in classes:
                self._in_output_block = True
                self._output_mime = attrs_dict.get('data-mime-type')
                self._output_class = classes
                self._capture_parts = []
            elif self._in_output_block and tag in {'pre', 'div', 'table', 'img'}:
                if tag == 'img' and 'src' in attrs_dict:
                    self._img_src = attrs_dict['src']
                self._capture_tag = tag
                self._capture_parts = []

    def _in_code_context(self, classes: str) -> bool:
        return 'highlight' in classes or 'hl-python' in classes

    def handle_endtag(self, tag: str) -> None:
        if tag == 'main':
            self._in_main = False
            return
        if not self._in_main:
            return

        if tag == 'div' and self._cell_stack and self._cell_stack[-1] == 'code':
            if self._in_output_block and tag == 'div':
                output = self._build_output()
                if output:
                    self._current_output_children.append(output)
                self._in_output_block = False
                self._output_mime = None
                self._output_class = ''
                self._img_src = None
            elif self._in_output_area and tag == 'div' and self._current_output_children:
                # end of one output child handled above
                pass
            elif self._in_output_area and tag == 'div':
                # closing output area wrapper at cell level - attach children
                if self._current_output_children:
                    self._current_outputs.extend(self._current_output_children)
                    self._current_output_children = []
                self._in_output_area = False

        if tag == 'div' and self._cell_stack:
            if self._cell_stack[-1] == 'code' and 'jp-Cell jp-CodeCell' in self._closing_cell_marker():
                pass

        if tag == 'pre' and self._in_code_pre:
            self._in_code_pre = False

        if tag == 'div' and self._in_input_prompt:
            self._in_input_prompt = False
            prompt = unescape(''.join(self._pending_prompt_text)).strip()
            match = re.search(r'In\s*\[(\d+)\]', prompt)
            if match:
                self._execution_count = int(match.group(1))

        if self._in_output_block and tag == self._capture_tag:
            self._capture_tag = None

        if tag == 'div':
            # close code/markdown cell when output wrapper ends and next cell begins
            if (
                self._cell_stack
                and self._cell_stack[-1] == 'code'
                and not self._in_output_area
                and self._current_code
                and self._current_outputs is not None
                and classes_end_code_cell(self)
            ):
                pass

        if tag == 'div' and self._cell_stack and self._cell_stack[-1] == 'code':
            # Heuristic: when we see jp-Cell-outputWrapper closed, keep outputs
            pass

        if tag == 'div' and len(self._cell_stack) == 1 and self._cell_stack[0] == 'code':
            # Detect end of code cell by output wrapper closure
            pass

        if tag == 'div' and self._cell_stack:
            classes = getattr(self, '_last_div_classes', '')
            if 'jp-Cell jp-CodeCell' in classes or 'jp-Cell jp-MarkdownCell' in classes:
                pass

    def handle_data(self, data: str) -> None:
        if not self._in_main:
            return
        if self._in_input_prompt:
            self._pending_prompt_text.append(data)
        if self._in_code_pre:
            self._current_code.append(data)
        if self._in_output_block and self._capture_tag:
            self._capture_parts.append(data)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def _build_output(self) -> dict[str, Any] | None:
        if self._img_src and self._img_src.startswith('data:image/png;base64,'):
            b64 = self._img_src.split(',', 1)[1]
            return {
                'output_type': 'display_data',
                'data': {'image/png': b64},
                'metadata': {},
            }

        content = unescape(''.join(self._capture_parts))
        mime = self._output_mime or ''

        if mime == 'text/plain':
            text = content.strip('\n')
            if 'jp-OutputArea-executeResult' in self._output_class:
                return {
                    'output_type': 'execute_result',
                    'data': {'text/plain': text},
                    'metadata': {},
                    'execution_count': self._execution_count,
                }
            return {
                'output_type': 'stream',
                'name': 'stdout',
                'text': text.splitlines(keepends=True) if text else [],
            }

        if mime == 'text/html':
            return {
                'output_type': 'display_data',
                'data': {'text/html': content},
                'metadata': {},
            }

        if content.strip():
            return {
                'output_type': 'display_data',
                'data': {'text/plain': content.strip('\n')},
                'metadata': {},
            }
        return None


def classes_end_code_cell(_parser: NotebookHTMLParser) -> bool:
    return False


def parse_html_with_regex(html: str) -> list[dict[str, Any]]:
    """Extrai células e outputs via regex (robusto ao HTML grande)."""
    main_match = re.search(r'<main[^>]*>(.*)</main>', html, re.DOTALL)
    if not main_match:
        raise ValueError('Tag <main> não encontrada no HTML')
    body = main_match.group(1)

    cell_pattern = re.compile(
        r'<div class="jp-Cell jp-(CodeCell|MarkdownCell) jp-Notebook-cell[^"]*"[^>]*>(.*?)(?=<div class="jp-Cell jp-(?:CodeCell|MarkdownCell)|\Z)',
        re.DOTALL,
    )

    cells: list[dict[str, Any]] = []
    for match in cell_pattern.finditer(body):
        cell_type = 'code' if match.group(1) == 'CodeCell' else 'markdown'
        chunk = match.group(2)
        cell: dict[str, Any] = {'cell_type': cell_type}

        if cell_type == 'code':
            prompt_match = re.search(r'<div class="jp-InputPrompt[^"]*">\s*In\s*\[(\d+)\]:', chunk)
            execution_count = None
            if prompt_match:
                execution_count = int(prompt_match.group(1))
            cell['execution_count'] = execution_count

            pre_match = re.search(r'<div class="highlight hl-python"><pre[^>]*>(.*?)</pre>', chunk, re.DOTALL)
            if pre_match:
                source = strip_html_to_text(pre_match.group(1))
                cell['source'] = source
            else:
                cell['source'] = ''

            outputs: list[dict[str, Any]] = []
            output_area_match = re.search(r'<div class="jp-OutputArea jp-Cell-outputArea">(.*?)</div>\s*</div>\s*</div>\s*$', chunk, re.DOTALL)
            if output_area_match:
                area = output_area_match.group(1)
                child_pattern = re.compile(
                    r'<div class="jp-OutputArea-child">(.*?)</div>\s*(?=<div class="jp-OutputArea-child"|</div>)',
                    re.DOTALL,
                )
                for child in child_pattern.finditer(area):
                    child_html = child.group(1)
                    outputs.extend(parse_output_child(child_html, execution_count))
            cell['outputs'] = outputs
        cells.append(cell)
    return cells


def strip_html_to_text(html_fragment: str) -> str:
    text = re.sub(r'<span[^>]*>', '', html_fragment)
    text = re.sub(r'</span>', '', text)
    text = re.sub(r'<pre[^>]*>', '', text)
    text = re.sub(r'</pre>', '', text)
    text = unescape(text)
    # Normaliza NBSP
    text = text.replace('\xa0', ' ')
    return text


def parse_output_child(child_html: str, execution_count: int | None) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []

    for img_match in re.finditer(r'<img[^>]+src="(data:image/png;base64,[^"]+)"', child_html):
        b64 = img_match.group(1).split(',', 1)[1]
        outputs.append({
            'output_type': 'display_data',
            'data': {'image/png': b64},
            'metadata': {},
        })

    for html_match in re.finditer(
        r'<div class="jp-RenderedHTMLCommon[^"]*jp-OutputArea-output"[^>]*data-mime-type="text/html"[^>]*>(.*?)</div>\s*(?=<div class="jp-OutputPrompt|<div class="jp-OutputArea-child|$)',
        child_html,
        re.DOTALL,
    ):
        html_content = html_match.group(1).strip()
        outputs.append({
            'output_type': 'display_data',
            'data': {'text/html': html_content},
            'metadata': {},
        })

    for text_match in re.finditer(
        r'<div class="jp-RenderedText jp-OutputArea-output"[^>]*data-mime-type="text/plain"[^>]*>\s*<pre[^>]*>(.*?)</pre>',
        child_html,
        re.DOTALL,
    ):
        text = unescape(strip_html_to_text(text_match.group(1)))
        if not text.endswith('\n') and text:
            text += '\n'
        outputs.append({
            'output_type': 'stream',
            'name': 'stdout',
            'text': text.splitlines(keepends=True),
        })

    return outputs


def normalize_source(source: str | list[str]) -> str:
    if isinstance(source, list):
        source = ''.join(source)
    source = source.replace('\r\n', '\n')
    lines = [line.rstrip() for line in source.split('\n')]
    return '\n'.join(lines).strip()


def sources_compatible(a: str, b: str) -> bool:
    if a == b:
        return True
    # tolera diferença pequena (ex.: resolução de ABT_PATH)
    a_lines = a.splitlines()
    b_lines = b.splitlines()
    if abs(len(a_lines) - len(b_lines)) > 8:
        return False
    shared = min(len(a_lines), len(b_lines))
    if shared == 0:
        return True
    matches = sum(1 for i in range(shared) if a_lines[i] == b_lines[i])
    return matches / shared >= 0.85


def merge_outputs(html_path: Path, ipynb_path: Path) -> None:
    html = html_path.read_text(encoding='utf-8')
    html_cells = parse_html_with_regex(html)

    nb = json.loads(ipynb_path.read_text(encoding='utf-8'))
    nb_cells = nb['cells']

    html_code = [c for c in html_cells if c['cell_type'] == 'code']
    ipynb_code = [c for c in nb_cells if c['cell_type'] == 'code']

    if len(html_code) != len(ipynb_code):
        raise ValueError(
            f'Contagem de células de código difere: HTML={len(html_code)} ipynb={len(ipynb_code)}'
        )

    merged = 0
    html_idx = 0
    for cell in nb_cells:
        if cell['cell_type'] != 'code':
            continue
        html_cell = html_code[html_idx]
        html_idx += 1
        ipynb_src = normalize_source(cell.get('source', ''))
        html_src = normalize_source(html_cell.get('source', ''))
        if not sources_compatible(ipynb_src, html_src):
            print(
                f'Aviso: célula de código #{html_idx} difere levemente entre HTML e ipynb; '
                'aplicando outputs mesmo assim.'
            )
        if html_cell.get('outputs'):
            cell['outputs'] = html_cell['outputs']
            cell['execution_count'] = html_cell.get('execution_count')
            merged += 1

    ipynb_path.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'Outputs aplicados em {merged}/{len(ipynb_code)} células de código -> {ipynb_path}')


def main() -> None:
    html_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/mnt/c/Users/Anderson/Downloads/HMDR_Modelagem_HomeCredit.html')
    ipynb_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('scripts/abt_to_model_home_credit_test.ipynb')
    merge_outputs(html_path, ipynb_path)


if __name__ == '__main__':
    main()
