# 项目开发约定

## 文风

- `README.md`、`AGENTS.md` 和笔记模板使用中文；`SKILL.md` 和 `references/` 等内容均使用简洁的英文。
- 每个正文段落写在同一行，让显示工具自动换行，不用手动断行。
- 以最新、唯一版本的口吻描述完整功能，让文档与当前实现保持同步，不要有歧义或旧信息。用正向、直接的表述说明行为和用途，不要在段落末尾添加多余内容，如辩解性的内容、删去也不影响内容的文字等。
- 目录与文件名称简短、直观，README 写安装和产品决策，`SKILL.md` 写 Agent 的命令与流程，`commands/` 写斜杠命令（中文描述、英文正文，只指向 `SKILL.md` 的流程），`references/files.md` 写文件格式，`references/notes.md` 写笔记模板，本文件写开发约束与代码结构。

## 实现范围

- 平台集成范围为课程元数据、视频、字幕和 PPT 截图。
- 功能按输入输出解耦，脚本承担省事的机械处理，如拼图、相似分组和批量替换，采用简单默认值与显式选项。`SKILL.md` 以工作流给出默认的调用顺序，Agent 按请求选用流程。
- 命令行统一在 `skills/yanhekit/scripts/yanhekit.py`，依赖集中写在它的 PEP 723 头部；其余模块只提供函数，新功能以子命令加入。
- 脚本在各平台和 Harness 中直接可用：文本读写显式指定 UTF-8，需要用户打开的地址打印到输出。
- 命令输出供 Agent 和人阅读：每项一行，从属内容缩进，课次内的路径相对课次目录。
- 工作区结构、产物路径和笔记模板固定遵循 `SKILL.md` 与 `references/`；Agent 在该框架内选择工具、分析方式和内容深度。
- 改动保持精小，采用单一实现路径；辅助函数以实际复用和清晰职责为依据。优先使用成熟库，但不要使用 Playwright 这样的大型依赖。
- 验证限于改动涉及的实际行为，测试与校验以功能必需为准。
- 登录依次尝试保存的登录态、统一认证会话和钥匙串密码，都失败时才打开本地登录页；凭证只经过本地页面与后端。
- 文字稿和字幕只做机械修正，够读即可，不逐句重写；Agent 的产出是笔记。

## 登录页

- 本地页面只负责登录。后端用 Flask，状态经 SSE 推送；`/api/` 校验 Host 和启动时生成的 token。下载管理页面保留在 `web-ui` 分支。
- 登录卡片的高度由 `useHeight` 测量并过渡，各步骤横向滑动。

## 命令

- 前端开发：在 `ui/` 运行 `pnpm dev`，再在登录态失效时用 `YANHEKIT_DEV=http://localhost:5173 uv run skills/yanhekit/scripts/yanhekit.py login` 启动后端，Vite 把 `/api` 代理到 5174 并提供热更新。
- 前端提交前运行 `pnpm format` 和 `pnpm check`，再用 `pnpm build` 把静态产物输出到 `skills/yanhekit/scripts/ui/`。
- Python 使用 `uvx ruff format skills/yanhekit/scripts` 和 `uvx ruff check skills/yanhekit/scripts`，风格由 `ruff.toml` 规定。
