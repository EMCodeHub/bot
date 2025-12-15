import argparse
import pathlib
import textwrap
import re
from typing import List


FRONTMATTER_TEMPLATE = """---
title: "{title}"
tags: [{tags}]
locale: es-ES
source: knowledge_base
---

"""


def _detect_title(content: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line.lstrip("# ").strip()
        if line:
            return line[:120]
    return "Documento conocimiento"


def _normalize_heading(line: str, default: str) -> str:
    line = line.strip()
    if not line:
        return default
    if re.match(r"^#{1,3}\s+", line):
        if line.startswith("###"):
            return line
        level = "###"
        text = line.lstrip("#").strip()
        return f"{level} {text}"
    return f"### {line}"


def _process_blocks(body: str) -> List[str]:
    parts = [part.strip() for part in re.split(r"\n-{3,}\n", body)]
    output = []
    section_index = 1
    for part in parts:
        if not part:
            continue
        lines = [line.rstrip() for line in part.splitlines() if line.strip()]
        if not lines:
            continue
        heading_line = None
        remaining = []
        for line in lines:
            if not heading_line and re.match(r"^#{1,6}\s+", line):
                heading_line = line
            else:
                remaining.append(line)
        heading_line = _normalize_heading(heading_line or lines[0], f"### Sección {section_index}")
        section_index += 1
        block = "\n".join(
            [heading_line, ""]
            + remaining
            + ["", "----", ""]
        )
        output.append(block.strip())
    return output


def restructure_file(path: pathlib.Path) -> None:
    raw = path.read_text(encoding="utf-8")
    front_matter = ""
    body = raw
    if raw.startswith("---"):
        match = re.match(r"^(-{3}\n.*?\n-{3}\n)(.*)$", raw, flags=re.S)
        if match:
            front_matter = match.group(1)
            body = match.group(2)
    title = _detect_title(body)
    tags = ', '.join(f"\"{part}\"" for part in path.parts[-2:])
    new_front = FRONTMATTER_TEMPLATE.format(title=title, tags=tags)
    processed = "\n\n".join(_process_blocks(body))
    if processed.endswith("----"):
        processed = processed[: processed.rfind("----")].strip()
    summary_block = "\n\n### Resumen rápido\n- Contenido validado para preguntas frecuentes\n- Etiquetas: " + tags.replace('"', "")
    output = new_front + processed + "\n\n" + summary_block + "\n"
    path.write_text(output.strip() + "\n", encoding="utf-8")


def restructure_all(root: pathlib.Path) -> None:
    for md in root.rglob("*.md"):
        restructure_file(md)
        print(f"Reformateado: {md.relative_to(root.parent)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reestructura knowledge_base para embeddings")
    parser.add_argument(
        "--base",
        type=pathlib.Path,
        default=pathlib.Path("src/knowledge_base"),
        help="Directorio base con archivos Markdown",
    )
    args = parser.parse_args()
    restructure_all(args.base)


if __name__ == "__main__":
    main()
