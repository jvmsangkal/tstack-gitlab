---
name: file-pr
description: File a concise GitLab merge request. Use when the user asks to file, open, or create an MR, merge request, or PR.
---

# File MR

Before filing, check whether a merge request (MR) for this branch already exists
with `glab mr list --source-branch <branch>`. Review the diff locally against the
target branch (usually `origin/main`) to make sure its contents match the goal.

MR titles usually become commit messages, so follow the project's title
conventions. Look at recently merged MRs, Git history, and any templates in
`.gitlab/merge_request_templates/` for examples. Prefer a concise,
human-readable title that explains why the change matters:

BAD

> ❌ perf(server): negotiate permessage-deflate on the websocket

GOOD

> ✅ perf(server): cut websocket frame size by 70%+ with gzipping

Open the description with a simple explanation of the problem based on the
user's original prompt, then briefly explain the solution. Do not lead with an
implementation inventory:

BAD

> ❌ Removed implicit workspace carry-over from every "new thread" entry point (cmd+n / cmd+shift+o, sidebar v1/v2 buttons, command palette). New threads inherit only the project from context; branch, worktree, and env mode always come from the configured defaults. Deleted buildContextualThreadOptions, startNewThreadInProjectFromContext, and the v1 sidebar's seed-context machinery.

GOOD

> ✅ My "new worktree" default was ignored when starting new threads on existing worktrees. Super unintuitive. Now your preferences always apply.

End the description with the public model name and harness that made the
changes, for example `Created with <model> in <harness>.` Include subagent
models that wrote part of the change. Use the model name the harness reports.
If model identity is unavailable, name the harness without guessing a model.

Before submission, check the title, description, quotes, and attachments for
secrets and private details.

Open a real MR rather than a draft so review bots run. Do not pass `--draft`,
`--wip`, `--auto-merge`, or `--fill`. Push the branch, write the description to
a file, and run
`glab mr create --source-branch <branch> --target-branch <target> --title <title> --description-file <file> --yes`.
If that fails, or glab predates `--description-file` (added in 1.115), open it
through REST with
`glab api projects/:fullpath/merge_requests -f source_branch=... -f target_branch=... -f title=... -F description=@<file>`. If the user also asked
to babysit it, continue with the `babysit-pr` skill.

Do not post a follow-up MR comment unless it serves the user's request. When a
comment is needed, use the `leaving-pr-comments` skill.
