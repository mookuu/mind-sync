import { markdownIt } from "../markdown-it.js";

export function renderMarkdown(text) {
  if (!text) return "";
  try {
    return markdownIt.render(text);
  } catch {
    return `<pre>${text}</pre>`;
  }
}
