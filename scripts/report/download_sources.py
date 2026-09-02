#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download only public source URLs listed in a knowledge-card manifest."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

MAX_BYTES = 50 * 1024 * 1024  # 单文件上限 50MB，防止大文件占满内存


def safe_name(value: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value, flags=re.UNICODE)
    return value.strip("._")[:100] or "source"


def download(item: dict, outdir: Path, timeout: int) -> dict:
    card_id = item.get("card_id", "K00")
    url = item.get("url", "")
    name = item.get("filename") or f"{card_id}_{safe_name(item.get('title', 'source'))}.bin"
    target = outdir / name
    result = {"card_id": card_id, "url": url, "filename": name, "status": "failed"}
    if not url.startswith(("https://", "http://")):
        result["reason"] = "URL 不是公开 HTTP(S) 地址"
        return result
    request = urllib.request.Request(url, headers={"User-Agent": "industry-research-source-archiver/1.0"})
    last_error = ""
    data = b""
    for attempt in range(2):  # 网络抖动重试一次
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status < 200 or response.status >= 300:
                    result["reason"] = f"HTTP {response.status}"
                    return result
                chunks = []
                total = 0
                while True:
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_BYTES:
                        result["reason"] = f"文件超过 {MAX_BYTES // 1048576}MB 上限"
                        return result
                    chunks.append(chunk)
                data = b"".join(chunks)
            break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)[:300]
            if attempt == 0:
                continue
    else:
        result["reason"] = last_error
        return result
    if len(data) < 1024:
        result["reason"] = "响应小于 1KB，疑似错误页或空文件"
        return result
    target.write_bytes(data)
    result.update(status="downloaded", bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="下载公开资料并生成下载结果清单")
    p.add_argument("--manifest", type=Path, required=True, help="JSON 下载清单")
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--result", type=Path, required=True)
    args = p.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    items = payload.get("items", payload) if isinstance(payload, dict) else payload
    args.outdir.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(items) or 1)) as pool:
        results = list(pool.map(lambda item: download(item, args.outdir, args.timeout), items))
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = sum(x["status"] == "downloaded" for x in results)
    print(f"[download_sources] 成功 {ok}/{len(results)}，结果：{args.result}")
    return 0 if all(x["status"] == "downloaded" for x in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
