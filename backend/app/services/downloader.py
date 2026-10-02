from __future__ import annotations

from pathlib import Path

import httpx


async def download_file(url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".part")

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        async with client.stream("GET", url, headers={"User-Agent": "SurveyGen/0.1"}) as r:
            r.raise_for_status()
            with tmp.open("wb") as f:
                async for chunk in r.aiter_bytes():
                    if chunk:
                        f.write(chunk)

    tmp.replace(out_path)

