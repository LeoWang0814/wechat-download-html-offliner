# wechat-article-offliner

**批量将微信公众号文章 HTML 离线化 + 本地化图片 + 脱敏清外链**  
**Batch offline + localize images + sanitize external links for WeChat Official Account article HTML**

---

## 背景 / Background

本项目用于处理通过以下工具批量下载得到的公众号文章 HTML 文件：

- https://github.com/qiye45/wechatDownload

`wechatDownload` 会将公众号文章保存为 HTML，但其中通常仍包含外链资源（如图片、OG/Twitter meta 预览图、link/script 等）。  
本仓库提供一个 **离线净化器**：将文章转换为 **“零外链、纯本地、可离线打开”** 的结构，并将图片资源下载到本地 `image/` 文件夹，同时将图片命名脱敏为 `img001/img002/...`。

This project is designed to post-process WeChat Official Account article HTML files exported by:

- https://github.com/qiye45/wechatDownload

While `wechatDownload` can save articles as HTML, the output often still contains external resources (images, OG/Twitter meta previews, link/script tags, etc.).  
This repo provides a **fully-offline sanitizer** that converts each article into a **zero-external-link, local-only, offline-viewable** package. Images are downloaded into a local `image/` folder and renamed to privacy-friendly names like `img001/img002/...`.

---

## 特性 / Features

### ✅ 核心能力 / Core
- **批量处理**：输入一个文件夹，递归遍历所有 `.html/.htm`
- **图片本地化**：下载外链图片到 `image/` 并改写引用
- **脱敏命名**：图片统一命名为 `img001/img002/...`
- **零外链（纯本地）**：清除所有 `http(s)://` / `//` 外链引用（含 meta / link / iframe / script 等）
- **清除“文末图片墙”**：移除某些下载器在 HTML 文末追加的一大串重复图片列表
- **风控友好**：每处理 2 篇文章随机间隔 10–20 秒（可修改）

### ✅ Output Structure
每篇文章输出到独立文件夹（文件夹名=原 HTML 文件名不含扩展名）：

```

<OUTPUT_ROOT>/<article_name>/
index.html
image/
img001.jpg
img002.png
...

````

---

## 安装 / Installation

### Python 版本 / Python Version
- Python 3.9+ recommended

### 依赖 / Dependencies
```bash
pip install requests beautifulsoup4
````

> 不强制依赖 `lxml`。使用 Python 内置 `html.parser`，避免环境差异导致的解析器报错。
> `lxml` is not required. The script uses Python built-in `html.parser` to avoid parser dependency issues.

---

## 使用 / Usage

1. 将脚本放到任意位置（例如 `clean_batch.py`）
2. 修改脚本开头两个常量：

```python
INPUT_PATH = r"YOUR_INPUT_FOLDER_PATH_HERE"      # wechatDownload 导出的 HTML 文件夹
OUTPUT_ROOT_DIR = r"YOUR_OUTPUT_ROOT_DIR_HERE"   # 输出根目录
```

3. 运行：

```bash
python clean_batch.py
```

---

## 重要说明 / Notes

* 本工具的目标是 **隐私优先 + 可离线阅读**：会清除外链资源引用，确保输出 HTML 不再请求互联网资源。
* 若原文依赖外部字体/视频/iframe 等资源，离线后可能无法完全还原这些交互内容（这是“零外链”策略的必然代价）。

This tool is **privacy-first** and **offline-first**: it removes external references so the output HTML will not fetch any internet resource.
If the original article depends on external fonts/videos/iframes, those interactive parts may not be fully preserved offline (a natural tradeoff for strict zero-external policy).

---

## 适用对象 / Intended Users

* 需要将公众号文章归档到本地、内网或静态站点，并希望避免外链/隐私风险的用户
* 使用 `wechatDownload` 批量下载公众号文章后，想进一步做资源本地化与脱敏的用户

---

## License

**MIT License**

---

## Acknowledgements

* Article downloader: [https://github.com/qiye45/wechatDownload](https://github.com/qiye45/wechatDownload)
