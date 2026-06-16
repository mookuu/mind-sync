import MarkdownIt from "markdown-it";
import taskLists from "markdown-it-task-lists";

export const markdownIt = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
})
  .use(taskLists);
