import MarkdownIt from "markdown-it";
import taskLists from "markdown-it-task-lists";

window.MindSyncMarkdown = {
  MarkdownIt,
  taskLists,
  createRenderer(options = {}) {
    return MarkdownIt("default", {
      html: false,
      linkify: true,
      breaks: false,
      typographer: false,
      ...options,
    }).use(taskLists);
  },
};
