# 待办事项

## 已实现 ✅

1. 关键字权重调整（2026-07-30）

   含"xxx基本用法"关键字匹配时权重提升 — 见 `services/fts.py:_boost_keyword_phrase()`
   支持模式：基本用法、入门、教程、指南、介绍、详解、入门指南、快速开始

2. 本地向量库检索入口（2026-07-30）

   本地存储向量库，提供 API 端点进行相似度检索。
   默认使用 TF-IDF 关键词向量，可替换为 sentence-transformers 等语义模型。
   - API: `GET /api/vector-search`
   - 管理: `POST /api/admin/vector-index/rebuild`、`GET /api/admin/vector-index/status`
   - 实现: `services/vector_store.py`
