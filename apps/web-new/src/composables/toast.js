/**
 * Toast 通知工具 — 可在任意组件中调用，无需引入。
 *
 * 用法:
 *   toast("操作成功")                    // 默认 info, 4s
 *   toast.success("保存完成")            // 成功绿色, 3s
 *   toast.error("保存失败")              // 错误红色, 5s
 *   toast.warning("请先同步")            // 警告黄色, 5s
 *   toast.info("正在处理…", 2000)        // 蓝色, 2s
 */
export function toast(message, type = "info", duration) {
  if (!duration) {
    duration = type === "success" ? 3000 : type === "error" ? 5000 : 4000;
  }
  window.dispatchEvent(
    new CustomEvent("mind-toast", { detail: { message, type, duration } })
  );
}

toast.success = (msg, dur) => toast(msg, "success", dur);
toast.error = (msg, dur) => toast(msg, "error", dur);
toast.warning = (msg, dur) => toast(msg, "warning", dur);
toast.info = (msg, dur) => toast(msg, "info", dur);
