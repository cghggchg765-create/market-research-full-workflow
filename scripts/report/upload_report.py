#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validated Feishu import with bounded retry, ticket polling and readback manifest."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from validate_report import validate as validate_final

URL_RE = re.compile(r"https?://[^\s\"']+")


def run(command: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def parse(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def deep_values(value):
    if isinstance(value, dict):
        yield from value.values()
        for child in value.values():
            yield from deep_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from deep_values(child)


def find_ticket(value) -> str:
    if isinstance(value, dict):
        for key in ("ticket", "import_ticket", "task_ticket"):
            if isinstance(value.get(key), str):
                return value[key]
    for child in deep_values(value):
        if isinstance(child, dict):
            found = find_ticket(child)
            if found:
                return found
    return ""


def find_url(text: str, value) -> str:
    for item in [value, text]:
        for candidate in deep_values(item) if value is item else [item]:
            if isinstance(candidate, str):
                match = URL_RE.search(candidate)
                if match and "feishu.cn" in match.group(0):
                    return match.group(0).rstrip(".,)")
    return ""


def import_once(file_path: Path, title: str, identity: str, folder_token: str) -> tuple[str, str]:
    command = ["lark-cli", "drive", "+import", "--as", identity, "--file", str(file_path), "--type", "docx", "--name", title, "--format", "json"]
    if folder_token:
        command.extend(["--folder-token", folder_token])
    code, stdout, stderr = run(command)
    if code != 0:
        raise RuntimeError(f"lark-cli 导入失败（exit={code}）：{stderr or stdout}")
    data = parse(stdout)
    ticket = find_ticket(data)
    url = find_url(stdout, data)
    return ticket, url


def wait_ticket(ticket: str, polls: int, interval: float) -> str:
    last = ""
    for index in range(polls):
        if index:
            time.sleep(interval * (2 ** min(index - 1, 3)))
        code, stdout, stderr = run(["lark-cli", "drive", "+task_result", "--scenario", "import", "--ticket", ticket, "--format", "json"])
        last = stderr or stdout
        if code != 0:
            continue
        data = parse(stdout)
        url = find_url(stdout, data)
        if url:
            return url
        text = json.dumps(data, ensure_ascii=False) if data is not None else stdout
        if any(word in text.lower() for word in ("failed", "error", "failure")):
            raise RuntimeError(f"飞书异步导入失败：{text[:500]}")
    raise TimeoutError(f"飞书异步导入轮询超时（ticket={ticket}，最后响应={last[:300]}）")


def main() -> int:
    p = argparse.ArgumentParser(description="校验并导入行业报告到飞书")
    p.add_argument("--file", type=Path, required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--identity", choices=("user", "bot"), default="user")
    p.add_argument("--folder-token", default="")
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--polls", type=int, default=8)
    p.add_argument("--poll-interval", type=float, default=2.0)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--run-dir", type=Path, required=True, help="交付目录；上传前强制校验（含图表产物）")
    p.add_argument("--target-words", type=int, default=32000)
    args = p.parse_args()
    if not args.file.is_file():
        raise SystemExit(f"[upload_report] 文件不存在: {args.file}")
    issues = validate_final(args.run_dir, args.target_words)
    if issues:
        print("[upload_report] 拒绝上传：交付门禁未通过：", file=sys.stderr)
        for it in issues:
            print("  ✗ " + it, file=sys.stderr)
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps({"status": "blocked", "issues": issues, "file": str(args.file.resolve())}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 1
    errors = []
    url = ""
    for attempt in range(args.retries + 1):
        try:
            ticket, url = import_once(args.file.resolve(), args.title, args.identity, args.folder_token)
            if not url and ticket:
                url = wait_ticket(ticket, args.polls, args.poll_interval)
            if not url:
                raise RuntimeError("导入成功但未解析到飞书 URL")
            break
        except (RuntimeError, TimeoutError, OSError) as exc:
            errors.append(f"attempt={attempt + 1}: {exc}")
            if attempt < args.retries:
                time.sleep(2 ** attempt)
    if not url:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps({"status": "failed", "errors": errors, "file": str(args.file.resolve())}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("[upload_report] 最终失败：" + " | ".join(errors))
        return 1
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps({"status": "uploaded", "url": url, "file": str(args.file.resolve()), "attempts": len(errors) + 1}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[upload_report] ✅ {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
