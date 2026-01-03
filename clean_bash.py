# -*- coding: utf-8 -*-
"""
WeChat HTML Cleaner (Fully Offline) - Batch Version
- INPUT_PATH points to a FOLDER now
- Traverse all .html/.htm files, clean each into:
  <OUTPUT_ROOT_DIR>/<html_stem>/index.html + image/img001.xxx...
- Random sleep 10-20s BETWEEN every 2 files (to reduce risk)
Core sanitization functions are kept the same.
"""

from __future__ import annotations

import re
import base64
import shutil
import random
import time
from pathlib import Path
from typing import Dict, Tuple, Optional
from urllib.parse import urlparse, unquote

import requests
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag


# =========================
# ONLY EDIT THESE 2 LINES
# =========================
INPUT_PATH = r"INPUT-PATH"      # now a FOLDER
OUTPUT_ROOT_DIR = r"OUTPUT-PATH"


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
TIMEOUT = 30

# 1x1 transparent PNG (base64)
TRANSPARENT_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMA"
    "ASsJTYQAAAAASUVORK5CYII="
)


def is_remote_url(u: str) -> bool:
    if not u:
        return False
    u = u.strip()
    return u.startswith("http://") or u.startswith("https://") or u.startswith("//")


def normalize_url(u: str) -> str:
    u = (u or "").strip()
    if u.startswith("//"):
        return "https:" + u
    return u


def guess_ext(url: str, content_type: Optional[str]) -> str:
    ct = (content_type or "").lower().split(";")[0].strip()
    if ct == "image/jpeg":
        return ".jpg"
    if ct == "image/png":
        return ".png"
    if ct == "image/gif":
        return ".gif"
    if ct == "image/webp":
        return ".webp"
    if ct == "image/svg+xml":
        return ".svg"

    try:
        path = urlparse(url).path
        path = unquote(path)
        ext = Path(path).suffix.lower()
        if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico"]:
            return ".jpg" if ext == ".jpeg" else ext
    except Exception:
        pass
    return ".jpg"


def looks_like_image_url(url: str) -> bool:
    url = url.lower()
    if any(s in url for s in ["wx_fmt=", "mmbiz_", "qpic.cn"]):
        return True
    return bool(re.search(r"\.(jpg|jpeg|png|gif|webp|svg|bmp|ico)(\?|$)", url))


def safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    data = path.read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="ignore")


def extract_doctype(html: str) -> str:
    m = re.match(r"\s*(<!doctype[^>]*>\s*)", html, flags=re.I)
    if m:
        return m.group(1).strip()
    return "<!DOCTYPE html>"


def make_session(referer: str) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": referer or "https://mp.weixin.qq.com/",
        }
    )
    return s


def download_binary(session: requests.Session, url: str) -> Tuple[Optional[bytes], Optional[str]]:
    try:
        r = session.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        return r.content, r.headers.get("Content-Type")
    except Exception:
        return None, None


def write_placeholder_png(dst: Path) -> None:
    dst.write_bytes(base64.b64decode(TRANSPARENT_PNG_B64))


def css_rewrite_urls(
    css_text: str,
    session: requests.Session,
    image_dir: Path,
    url_to_local: Dict[str, str],
    counter: Dict[str, int],
) -> str:
    """
    Rewrite url(...) in CSS to local.
    If remote url is not image-like, remove it (empty).
    """

    def repl(m: re.Match) -> str:
        raw = m.group(1).strip().strip("'\"")
        if not raw or raw.startswith("data:"):
            return f"url({m.group(1)})"
        if not is_remote_url(raw):
            return f"url({m.group(1)})"

        u = normalize_url(raw)
        if not looks_like_image_url(u):
            return "url()"

        local = get_local_path_for_url(session, u, image_dir, url_to_local, counter)
        return f"url('{local}')"

    return re.sub(r"url\(\s*([^)]+?)\s*\)", repl, css_text, flags=re.I)


def get_local_path_for_url(
    session: requests.Session,
    url: str,
    image_dir: Path,
    url_to_local: Dict[str, str],
    counter: Dict[str, int],
) -> str:
    url = normalize_url(url)

    if url in url_to_local:
        return url_to_local[url]

    idx = counter["n"]
    counter["n"] += 1

    content, ctype = download_binary(session, url)
    ext = guess_ext(url, ctype)
    fname = f"img{idx:03d}{ext}"
    dst = image_dir / fname

    if content is None:
        if ext != ".png":
            dst = image_dir / f"img{idx:03d}.png"
            fname = dst.name
        write_placeholder_png(dst)
    else:
        dst.write_bytes(content)

    local = f"image/{fname}"
    url_to_local[url] = local
    return local


def rewrite_srcset(
    srcset: str,
    session: requests.Session,
    image_dir: Path,
    url_to_local: Dict[str, str],
    counter: Dict[str, int],
) -> str:
    parts = [p.strip() for p in srcset.split(",") if p.strip()]
    new_parts = []
    for p in parts:
        tokens = p.split()
        if not tokens:
            continue
        u = tokens[0].strip().strip("'\"")
        desc = " ".join(tokens[1:]) if len(tokens) > 1 else ""
        if is_remote_url(u):
            u2 = normalize_url(u)
            if looks_like_image_url(u2):
                local = get_local_path_for_url(session, u2, image_dir, url_to_local, counter)
                new_parts.append((local + (" " + desc if desc else "")).strip())
            else:
                continue
        else:
            new_parts.append(p)
    return ", ".join(new_parts)


def remove_trailing_image_wall(soup: BeautifulSoup) -> None:
    body = soup.body
    if not body:
        return

    last_tag = None
    for x in reversed(list(body.contents)):
        if isinstance(x, NavigableString) and not x.strip():
            continue
        if isinstance(x, Tag):
            last_tag = x
        break

    if isinstance(last_tag, Tag) and last_tag.name in ("div", "section", "p"):
        imgs = last_tag.find_all("img", recursive=True)
        if len(imgs) >= 3:
            ok = True
            for im in imgs:
                src = (im.get("src") or "").strip()
                if not src.startswith("image/"):
                    ok = False
                    break
            text = last_tag.get_text(strip=True)
            if ok and (text == ""):
                last_tag.decompose()
                return

    tail_imgs = []
    for x in reversed(list(body.contents)):
        if isinstance(x, NavigableString) and not x.strip():
            continue
        if isinstance(x, Tag) and x.name == "img":
            src = (x.get("src") or "").strip()
            if src.startswith("image/"):
                tail_imgs.append(x)
                continue
        break

    if len(tail_imgs) >= 3:
        for im in tail_imgs:
            im.decompose()


def drop_or_sanitize_external_attrs(soup: BeautifulSoup) -> None:
    for sc in soup.find_all("script"):
        sc.decompose()

    for tag in soup.find_all(True):
        for k in list(tag.attrs.keys()):
            if k == "xmlns" or k.startswith("xmlns:"):
                del tag.attrs[k]

    for link in soup.find_all("link"):
        href = (link.get("href") or "").strip()
        if is_remote_url(href):
            link.decompose()

    for tname in ("iframe", "embed", "object"):
        for t in soup.find_all(tname):
            src = (t.get("src") or "").strip()
            data = (t.get("data") or "").strip()
            if is_remote_url(src) or is_remote_url(data):
                t.decompose()

    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        if is_remote_url(href):
            a["href"] = "#"
        for attr, val in list(a.attrs.items()):
            if isinstance(val, str) and ("http://" in val or "https://" in val or val.strip().startswith("//")):
                if attr != "href":
                    del a.attrs[attr]

    for tag in soup.find_all(True):
        for attr, val in list(tag.attrs.items()):
            if isinstance(val, list):
                continue
            if not isinstance(val, str):
                continue
            v = val.strip()
            if "http://" in v or "https://" in v or v.startswith("//"):
                del tag.attrs[attr]


def finalize_hard_no_external(html_out: str) -> str:
    html_out = re.sub(r'(?i)(["\'(])\s*//[^\s"\'<>)]*', r"\1", html_out)
    html_out = re.sub(r"(?i)https?://[^\s\"'<>)]*", "", html_out)
    return html_out


# -----------------------
# Per-file processing wrapper (core logic unchanged, just parameterized)
# -----------------------
def process_one_file(in_path: Path, out_root: Path) -> None:
    stem = in_path.stem
    out_dir = out_root / stem
    image_dir = out_dir / "image"

    # recreate
    if out_dir.exists():
        shutil.rmtree(out_dir)
    safe_mkdir(image_dir)

    html_text = read_text(in_path)
    doctype = extract_doctype(html_text)

    soup = BeautifulSoup(html_text, "html.parser")

    # referer for downloading
    referer = "https://mp.weixin.qq.com/"
    ogurl = soup.find("meta", attrs={"property": "og:url"})
    if ogurl and isinstance(ogurl, Tag):
        c = (ogurl.get("content") or "").strip()
        if c.startswith("http"):
            referer = c

    session = make_session(referer)

    url_to_local: Dict[str, str] = {}
    counter = {"n": 1}

    # ---- 1) Localize images in <img> ----
    for img in soup.find_all("img"):
        cand_attrs = ["data-src", "data-original", "data-actualsrc", "data-backup-src", "src"]
        src_url = ""
        for a in cand_attrs:
            v = (img.get(a) or "").strip()
            if v and (v.startswith("data:") or is_remote_url(v)):
                src_url = v
                break
            if v and a == "src":
                src_url = v

        if src_url and is_remote_url(src_url):
            u = normalize_url(src_url)
            local = get_local_path_for_url(session, u, image_dir, url_to_local, counter)
            img["src"] = local

        for a in list(img.attrs.keys()):
            v = img.get(a)
            if isinstance(v, str) and is_remote_url(v):
                if a != "src":
                    del img.attrs[a]

    # ---- 2) Localize srcset in <source>/<img> if any ----
    for tag in soup.find_all(["img", "source"]):
        ss = (tag.get("srcset") or "").strip()
        if ss:
            tag["srcset"] = rewrite_srcset(ss, session, image_dir, url_to_local, counter)

    # ---- 3) Localize meta images, drop meta urls ----
    for meta in soup.find_all("meta"):
        prop = (meta.get("property") or meta.get("name") or "").strip().lower()
        content = (meta.get("content") or "").strip()
        if not content:
            continue

        if prop in ("og:image", "twitter:image") and is_remote_url(content):
            u = normalize_url(content)
            local = get_local_path_for_url(session, u, image_dir, url_to_local, counter)
            meta["content"] = local
            continue

        if prop in ("og:url", "twitter:url") and (content.startswith("http") or content.startswith("//")):
            meta.decompose()
            continue

        if ("http://" in content) or ("https://" in content) or content.startswith("//"):
            meta.decompose()

    # ---- 4) Rewrite CSS url(...) in <style> and style="" ----
    for st in soup.find_all("style"):
        if st.string:
            new_css = css_rewrite_urls(st.string, session, image_dir, url_to_local, counter)
            st.string.replace_with(new_css)

    for tag in soup.find_all(True):
        style = (tag.get("style") or "").strip()
        if style and ("url(" in style.lower()):
            tag["style"] = css_rewrite_urls(style, session, image_dir, url_to_local, counter)

    # ---- 5) Remove trailing duplicated image wall at end ----
    remove_trailing_image_wall(soup)

    # ---- 6) Drop/sanitize any external attributes and tags ----
    drop_or_sanitize_external_attrs(soup)

    html_out = f"{doctype}\n{str(soup)}\n"
    html_out = finalize_hard_no_external(html_out)

    (out_dir / "index.html").write_text(html_out, encoding="utf-8", errors="ignore")


def collect_html_files(folder: Path) -> list[Path]:
    files = []
    files.extend(folder.rglob("*.html"))
    files.extend(folder.rglob("*.htm"))
    # stable order
    files = sorted(set(files))
    return files


def main() -> None:
    in_path = Path(INPUT_PATH).expanduser().resolve()
    out_root = Path(OUTPUT_ROOT_DIR).expanduser().resolve()
    safe_mkdir(out_root)

    if not in_path.exists():
        raise FileNotFoundError(f"INPUT_PATH not found: {in_path}")
    if in_path.is_file():
        raise ValueError("INPUT_PATH must be a FOLDER now, not a file.")

    html_files = collect_html_files(in_path)
    if not html_files:
        print(f"No .html/.htm files found under: {in_path}")
        return

    print(f"Found {len(html_files)} HTML files under: {in_path}")

    for i, f in enumerate(html_files, start=1):
        print(f"[{i}/{len(html_files)}] Cleaning: {f}")
        try:
            process_one_file(f, out_root)
        except Exception as e:
            print(f"  [ERROR] Failed: {f}\n   -> {e}")

        # Random sleep between every 2 files
        if i < len(html_files) and (i % 2 == 0):
            t = random.uniform(10, 20)
            print(f"  Sleeping {t:.1f}s ...")
            time.sleep(t)

    print("All done.")
    print(f"Output root: {out_root}")


if __name__ == "__main__":
    main()
