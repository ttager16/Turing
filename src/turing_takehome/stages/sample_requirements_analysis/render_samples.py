from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[3]
JSONL_PATH = PROJECT_ROOT / "artifacts" / "provided" / "Samples.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "sample_requirements_analysis" / "rendered_samples"
EDGE_PATH = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def normalize_text(text: str) -> str:
    if not text:
        return ""
    suspicious = ("â", "Ã", "Â", "ð", "�")
    if any(ch in text for ch in suspicious):
        try:
            repaired = text.encode("latin-1").decode("utf-8")
            if repaired.count("�") <= text.count("�"):
                text = repaired
        except Exception:
            pass
    return text.replace("\r\n", "\n").replace("\r", "\n")


def slug_to_title(key: str) -> str:
    parts = re.split(r"[_\-\s]+", key.strip())
    return " ".join(part.capitalize() if part else "" for part in parts)


def escape(value: Any) -> str:
    return html.escape(str(value), quote=False)


def format_inline(text: str) -> str:
    text = escape(normalize_text(text))
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^\*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^\*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"\\\((.+?)\\\)", r'<span class="math inline">\1</span>', text)
    text = re.sub(r"\$(.+?)\$", r'<span class="math inline">\1</span>', text)
    return text


def paragraphize(text: str) -> str:
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "".join(f"<p>{format_inline(part).replace(chr(10), '<br>')}</p>" for part in parts)


def fenced_code_to_html(language: str, code: str) -> str:
    label = f'<div class="code-label">{escape(language)}</div>' if language else ""
    return f'<div class="code-block">{label}<pre><code>{escape(normalize_text(code))}</code></pre></div>'


def markdownish_to_html(text: str) -> str:
    text = normalize_text(text).strip()
    if not text:
        return '<p class="muted">Empty</p>'

    chunks: list[str] = []
    lines = text.split("\n")
    i = 0
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            chunks.append("</ol>")
            in_list = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            close_list()
            language = stripped[3:].strip()
            i += 1
            code_lines: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            chunks.append(fenced_code_to_html(language, "\n".join(code_lines)))
        elif re.fullmatch(r"-{3,}", stripped):
            close_list()
            chunks.append("<hr>")
        elif match := re.match(r"^(#{1,6})\s+(.*)$", stripped):
            close_list()
            level = min(len(match.group(1)) + 1, 6)
            chunks.append(f"<h{level}>{format_inline(match.group(2))}</h{level}>")
        elif match := re.match(r"^\d+\.\s+(.*)$", stripped):
            if not in_list:
                chunks.append("<ol>")
                in_list = True
            chunks.append(f"<li>{format_inline(match.group(1))}</li>")
        elif stripped:
            close_list()
            paragraph_lines = [stripped]
            i += 1
            while i < len(lines) and lines[i].strip():
                paragraph_lines.append(lines[i].strip())
                i += 1
            chunks.append(f"<p>{format_inline(' '.join(paragraph_lines))}</p>")
            continue
        else:
            close_list()
        i += 1

    close_list()
    return "".join(chunks)


def looks_like_json(text: str) -> bool:
    text = text.strip()
    return (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]"))


def render_json_value(value: Any, depth: int = 0) -> str:
    if isinstance(value, dict):
        cards = []
        heading_tag = "h3" if depth == 0 else "h4" if depth == 1 else "h5"
        for key, item in value.items():
            cards.append(
                f'<section class="kv-card depth-{depth}">'
                f"<{heading_tag}>{escape(slug_to_title(str(key)))}</{heading_tag}>"
                f"{render_json_value(item, depth + 1)}"
                f"</section>"
            )
        return "".join(cards) or '<p class="muted">Empty object</p>'
    if isinstance(value, list):
        if not value:
            return '<p class="muted">Empty list</p>'
        items = []
        for index, item in enumerate(value):
            items.append(
                f'<section class="list-item depth-{depth}">'
                f'<div class="list-index">Item {index}</div>{render_json_value(item, depth + 1)}</section>'
            )
        return f'<div class="list-wrap">{"".join(items)}</div>'
    if isinstance(value, str):
        return render_string(value)
    if isinstance(value, bool):
        return f'<p><span class="pill {"true" if value else "false"}">{str(value).lower()}</span></p>'
    if value is None:
        return '<p class="muted">null</p>'
    return f"<p>{escape(value)}</p>"


def render_string(value: str) -> str:
    value = normalize_text(value).strip()
    if not value:
        return '<p class="muted">Empty</p>'
    if looks_like_json(value):
        try:
            parsed = json.loads(value)
        except Exception:
            parsed = None
        if parsed is not None:
            return render_json_value(parsed, depth=1)
    if value.startswith("```") or "\n### " in value or value.startswith("#"):
        return markdownish_to_html(value)
    if "\n" in value:
        if len(value) > 400 or value.count("\n") > 5:
            return fenced_code_to_html("", value)
        return paragraphize(value)
    return f"<p>{format_inline(value)}</p>"


def render_test_cases(raw: str, title: str) -> str:
    try:
        cases = json.loads(normalize_text(raw))
    except Exception:
        return section_html(title, render_string(raw))

    body = [f'<div class="section-intro">Count: {len(cases)}</div>']
    for idx, case in enumerate(cases):
        body.append(
            "<article class=\"test-card\">"
            f"<h3>{escape(title[:-1] if title.endswith('s') else title)} {idx + 1}</h3>"
            f"<div class=\"meta-grid\">"
            f"<div><span class=\"meta-label\">Type</span><span>{escape(case.get('testtype', ''))}</span></div>"
            f"</div>"
            f"<div class=\"io-grid\">"
            f"<section><h4>Input</h4>{fenced_code_to_html('json-ish', case.get('input', ''))}</section>"
            f"<section><h4>Output</h4>{fenced_code_to_html('json', case.get('output', ''))}</section>"
            f"</div>"
            "</article>"
        )
    return section_html(title, "".join(body))


def section_html(title: str, content: str) -> str:
    return f'<section class="main-section"><h2>{escape(title)}</h2>{content}</section>'


def render_sample(index: int, sample: dict[str, Any]) -> str:
    hero_bits = [
        ("Platform", sample.get("platform", "")),
        ("Difficulty", sample.get("difficulty", "")),
        ("Question ID", sample.get("question_id", "")),
        ("Contest ID", sample.get("contest_id", "")),
        ("Contest Date", sample.get("contest_date", "")),
    ]
    hero = "".join(
        f'<div class="hero-chip"><span class="meta-label">{escape(label)}</span><span>{escape(normalize_text(value))}</span></div>'
        for label, value in hero_bits
        if value
    )

    sections = [
        section_html("Question Content", render_string(sample.get("question_content", ""))),
        section_html("Starter Code", render_string(sample.get("starter_code", ""))),
        render_test_cases(sample.get("public_test_cases", "[]"), "Public Test Cases"),
        render_test_cases(sample.get("private_test_cases", "[]"), "Private Test Cases"),
        section_html("Ideal Response", render_string(sample.get("ideal_response", ""))),
        section_html("Metadata", render_string(sample.get("metadata", "{}"))),
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sample {index}: {escape(normalize_text(sample.get("question_title", "Untitled")))}</title>
  <style>
    :root {{
      --bg: #f4efe7;
      --paper: #fffdfa;
      --ink: #18212c;
      --muted: #556070;
      --line: #ddd2c2;
      --accent: #ad5a2d;
      --accent-soft: #f6e2d5;
      --accent-2: #234f63;
      --section: #f8f3ec;
      --code-bg: #1f2430;
      --code-ink: #eff3f8;
      --shadow: 0 18px 40px rgba(53, 39, 25, 0.12);
    }}
    @page {{
      size: Letter;
      margin: 0.6in;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(173, 90, 45, 0.16), transparent 30%),
        linear-gradient(180deg, #f6f0e6 0%, #f2ece4 100%);
      font-family: "Georgia", "Times New Roman", serif;
      line-height: 1.55;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}
    .page {{
      max-width: 8.1in;
      margin: 0 auto;
      padding: 0.18in;
    }}
    .hero {{
      background:
        linear-gradient(135deg, rgba(255,255,255,0.96), rgba(247, 239, 228, 0.92)),
        linear-gradient(135deg, rgba(173, 90, 45, 0.15), rgba(35, 79, 99, 0.08));
      border: 1px solid rgba(173, 90, 45, 0.18);
      border-radius: 22px;
      padding: 28px 30px 24px;
      box-shadow: var(--shadow);
      margin-bottom: 24px;
    }}
    .eyebrow {{
      font-family: "Segoe UI", Arial, sans-serif;
      font-size: 11px;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 8px;
      font-weight: 700;
    }}
    h1 {{
      font-size: 28px;
      line-height: 1.15;
      margin: 0 0 16px;
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }}
    .hero-chip, .meta-grid > div {{
      background: rgba(255,255,255,0.68);
      border: 1px solid rgba(35, 79, 99, 0.12);
      border-radius: 14px;
      padding: 10px 12px;
      display: flex;
      flex-direction: column;
      gap: 4px;
      min-height: 54px;
    }}
    .meta-label {{
      font-family: "Segoe UI", Arial, sans-serif;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .main-section {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 22px;
      box-shadow: 0 10px 24px rgba(24, 33, 44, 0.06);
      margin-bottom: 18px;
      page-break-inside: avoid;
    }}
    h2 {{
      font-family: "Segoe UI", Arial, sans-serif;
      color: var(--accent-2);
      font-size: 17px;
      margin: 0 0 14px;
      padding-bottom: 8px;
      border-bottom: 2px solid rgba(35, 79, 99, 0.12);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    h3, h4, h5 {{
      font-family: "Segoe UI", Arial, sans-serif;
      margin: 16px 0 10px;
      color: #283d4d;
    }}
    p {{
      margin: 0 0 12px;
    }}
    ol {{
      margin: 0 0 12px 22px;
    }}
    li {{
      margin-bottom: 6px;
    }}
    hr {{
      border: none;
      border-top: 1px solid var(--line);
      margin: 16px 0;
    }}
    code {{
      font-family: "Cascadia Code", "Consolas", monospace;
      background: rgba(35, 79, 99, 0.08);
      border-radius: 6px;
      padding: 1px 5px;
      font-size: 0.94em;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: "Cascadia Code", "Consolas", monospace;
      font-size: 11px;
      line-height: 1.45;
    }}
    .code-block {{
      background: var(--code-bg);
      color: var(--code-ink);
      border-radius: 16px;
      padding: 14px 16px;
      margin: 10px 0 14px;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.06);
      page-break-inside: avoid;
    }}
    .code-label {{
      font-family: "Segoe UI", Arial, sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 10px;
      color: #a9c0d4;
      margin-bottom: 8px;
    }}
    .kv-card, .list-item, .test-card {{
      background: var(--section);
      border: 1px solid rgba(173, 90, 45, 0.15);
      border-radius: 16px;
      padding: 16px;
      margin: 10px 0;
      page-break-inside: avoid;
    }}
    .list-index, .section-intro {{
      font-family: "Segoe UI", Arial, sans-serif;
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
      font-weight: 700;
    }}
    .list-wrap {{
      display: block;
    }}
    .io-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      align-items: start;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }}
    .pill {{
      display: inline-block;
      font-family: "Segoe UI", Arial, sans-serif;
      font-size: 12px;
      padding: 4px 10px;
      border-radius: 999px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .pill.true {{
      color: #165c37;
      background: #dff3e5;
    }}
    .pill.false {{
      color: #7b1d1d;
      background: #f7dede;
    }}
    .muted {{
      color: var(--muted);
      font-style: italic;
    }}
    .math {{
      font-family: "Cambria Math", "STIX Two Math", "Times New Roman", serif;
      font-style: italic;
      background: rgba(173, 90, 45, 0.08);
      padding: 1px 6px;
      border-radius: 6px;
      white-space: nowrap;
    }}
    @media print {{
      .main-section, .hero, .test-card, .kv-card, .list-item {{
        break-inside: avoid;
      }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="eyebrow">Turing Take-Home Sample {index}</div>
      <h1>{escape(normalize_text(sample.get("question_title", "Untitled Sample")))}</h1>
      <div class="hero-grid">{hero}</div>
    </section>
    {''.join(sections)}
  </main>
</body>
</html>"""


def locate_browser() -> Path:
    for path in (EDGE_PATH, CHROME_PATH):
        if path.exists():
            return path
    raise FileNotFoundError("Neither Microsoft Edge nor Google Chrome was found.")


def print_html_to_pdf(browser_path: Path, html_path: Path, pdf_path: Path) -> None:
    command = [
        str(browser_path),
        "--headless=new",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={pdf_path}",
        str(html_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Browser failed for {html_path.name} with code {result.returncode}: "
            f"{result.stderr or result.stdout}"
        )

    for _ in range(60):
        if pdf_path.exists() and pdf_path.stat().st_size > 0:
            return
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for {pdf_path.name} to be created.")


def iterate_samples() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with JSONL_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render Samples.jsonl into polished PDFs.")
    parser.add_argument("--start", type=int, default=0, help="Start index, inclusive.")
    parser.add_argument("--end", type=int, default=None, help="End index, exclusive.")
    args = parser.parse_args(argv)

    samples = iterate_samples()
    start = max(args.start, 0)
    end = len(samples) if args.end is None else min(args.end, len(samples))
    browser = locate_browser()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="sample_html_", dir=str(OUTPUT_DIR)) as temp_dir:
        temp_root = Path(temp_dir)
        for index in range(start, end):
            sample = samples[index]
            html_path = temp_root / f"{index}.html"
            pdf_path = OUTPUT_DIR / f"{index}.pdf"
            html_path.write_text(render_sample(index, sample), encoding="utf-8")
            print_html_to_pdf(browser, html_path, pdf_path)
            print(f"Rendered sample {index} -> {pdf_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
