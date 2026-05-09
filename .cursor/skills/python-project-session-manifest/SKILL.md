---
name: python-project-session-manifest
description: >-
  本 Python 仓库：会话预加载顺序、「用过的 skill」记录，以及同伴 skill 存放约定（与引导合一）。
  含 design-notes（Agent 指令/设计真源）、高聚合门面、Python 文档注释、callback api/impl 与 sink 日志分层。
---

# Python 项目 · 会话清单与引导

## 初始化加载（Session preload）

在本仓库开展实质性工作前，按顺序 **Read**（`~` 为用户主目录下 `.cursor/skills`）：

1. `~/.cursor/skills/python-project-ai/SKILL.md`
2. `~/.cursor/skills/project-skill-manifest-policy/SKILL.md`
3. `.cursor/skills/python-project-design-notes/SKILL.md`（本仓库：给 Agent 的指令/要求/设计备忘，**不**抄进代码与对外文档）
4. `~/.cursor/skills/cohesive-main-class-api/SKILL.md`
5. `~/.cursor/skills/python-doc-comments/SKILL.md`
6. `~/.cursor/skills/callback-api-impl-layers/SKILL.md`
7. `~/.cursor/skills/impl-sink-rich-logging/SKILL.md`

可选（代码生成自查，改动较多时使用）：

8. `~/.cursor/skills/agent-codegen-self-review/SKILL.md`

**新增**需要预加载的 skill 时：将路径**追加**到本节。

## Agent：设计笔记维护义务（无需用户提醒）

- 在本仓库开展实质性工作时，若用户**提出或变更**产品设计、功能范围、验收口径、架构边界或折中方案，Agent 在**同一轮或交付前**须**主动**更新 **`.cursor/skills/python-project-design-notes/SKILL.md`**（调整「设计意图」「设计与验收要求」「与实现的对齐与折中」「备忘与待定」等节），保持与代码决议一致。
- **不要**等待用户说「记下来」才写；也**不要**把同一段长篇需求抄进源码注释或对外 README（仍遵守 design-notes 的「禁止回流」）。
- 若本轮仅为微小修复且无需求/设计含义变化，可不改 design-notes。

## 同伴 skill 存放约定

- **默认**：新建或补充的 skill 写在 **`~/.cursor/skills/<skill-name>/SKILL.md`**，不要放进本仓库，除非用户**明确要求**写在项目下。
- 本仓库在 **`.cursor/skills/`** 保留 **manifest**（本文件）与 **`python-project-design-notes`**（Agent 设计真源）；通用 Python 约定见 **`python-project-ai`**。
- 从 **`~/.cursor/skills/`** 查找需要加载的同伴；预加载变更只改**本文件**的「初始化加载」节即可。

## 用过的 skill（追加记录）

- 在本仓库对话中**首次**实际 Read、且未列入上面预加载列表的 skill，在此**追加**一行（名称 + 完整路径）；去重。

- agent-codegen-self-review | `C:\Users\Administrator\.cursor\skills\agent-codegen-self-review\SKILL.md`
