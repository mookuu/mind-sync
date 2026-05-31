#!/usr/bin/env node
/** Smoke test: markdown-it built-in GFM + task-lists plugin */

import MarkdownIt from "markdown-it";
import taskLists from "markdown-it-task-lists";

const md = MarkdownIt("default", {
  html: false,
  linkify: true,
  breaks: false,
  typographer: false,
}).use(taskLists);

const sample = [
  "### 标题",
  "",
  "| 字符 | 写法 | `\\s` | `strip()` 默认 |",
  "|------|------|:----:|:--------------:|",
  "| 空格 | ` ` | ✅ | ✅ |",
  "",
  "~~删除~~ **粗体**",
  "",
  "- [x] 完成",
  "",
  "```python",
  "print(1)",
  "```",
].join("\n");

const html = md.render(sample);

const checks = [
  ["heading", /<h3>/.test(html)],
  ["table", /<table/.test(html)],
  ["center", /text-align:\s*center|align="center"/.test(html)],
  ["strikethrough", /<(s|del)>/.test(html)],
  ["task", /task-list-item|<input[^>]+checkbox/i.test(html)],
  ["fence", /<pre/.test(html)],
];

const failed = checks.filter(([, ok]) => !ok).map(([name]) => name);
if (failed.length) {
  console.error("markdown-it GFM smoke test failed:", failed.join(", "));
  console.error(html);
  process.exit(1);
}

console.log("markdown-it GFM smoke test passed");
