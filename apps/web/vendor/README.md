# Web 前端 vendor 依赖

本地 bundled 文件（无需 CDN）：

- `highlight.min.js` — highlight.js 11.9（浏览器 UMD，含 Python/Java/Markdown 等）
- `github-dark.min.css` — 代码高亮主题
- `marked.min.js` — marked 12.0（GFM Markdown 解析）

## 更新依赖

```bash
bash scripts/vendor-web.sh
```

Docker 构建时也会在镜像内执行等效步骤（见 `apps/web/Dockerfile`）。
