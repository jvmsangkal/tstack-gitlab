---
name: babysit-pr
description: Monitor a GitLab merge request (MR) through review and CI. Use when the user asks to monitor, watch, or babysit an MR or PR.
---

# Babysit MR

Many projects have AI review bots. They're helpful, even if they are not always
right.

## Waiting

Never write your own watcher, polling loop, or `sleep` loop. Use one watcher
per merge request (MR): `watch_pull_request` in T3 Code, `pr-wait` everywhere
else. Never run both on the same MR. Every watcher on a GitLab account shares
one rate limit.

### In T3 Code: `watch_pull_request`

Use it only when T3 Code's watcher supports this GitLab host. Otherwise use
`pr-wait`. Handle the existing jobs and comments first. Then call
`watch_pull_request` and end your turn. T3 Code wakes you with a message when
a job fails, the required jobs pass, someone comments or reviews, or the
branch conflicts.

- **Only the thread that owns the MR watches it.** If you are a delegated
  child task (a reviewer, a Sol round, any `delegate_task` child), never call
  `watch_pull_request`. The parent owns the MR. Do not watch MRs you are not
  working on.
- **A wake is news, not a merge decision.** Check the merge gate yourself.
- **Unwatch when you hand off.** A watched thread stays in Working and out of
  the user's inbox. When you stop (ready, blocked, or asking the user a question),
  call `unwatch_pull_request` first. A merge or close ends the watch on its
  own.
- **"Stopped watching, could not read it"** usually means GitLab's rate limit
  is used up (HTTP 429). Run `glab api --include user` and read the
  `RateLimit-Remaining` and `RateLimit-Reset` headers before you watch again.
  If `RateLimit-Remaining` is near 0, wait for `RateLimit-Reset` with one
  background command, then watch again. Never watch again in a tight loop.

### Everywhere else: `pr-wait`

Wait with `scripts/pr-wait` from this skill's directory (use its absolute
path).

```bash
pr-wait <mr> [--repo group/project] [--until ready|green|any-change]
```

It prints one line per real event. It exits 0 when the `--until` condition is
met or the MR merges, 1 when it needs you (a required job failed, conflicts,
unresolved threads, MR closed), and 2 on bad input.

- `ready` (default): required jobs green, Greptile or Macroscope reviewed the
  head, and no unresolved threads. Use this to babysit.
- `green`: required jobs only. Use it when the project has no Greptile or
  Macroscope.
- `any-change`: exit on the first event.

`<mr>` is an MR URL, `!123`, or `group/project!123`. Required jobs are the
head pipeline's jobs that are not allowed to fail (manual jobs excluded), plus
external commit statuses and MR status checks. The host comes from the MR URL,
else `GITLAB_HOST`, else the checkout's remote. glab must be logged in to that
host (`glab auth login --hostname <host>`), or the host must be `GITLAB_HOST`
with `GITLAB_TOKEN` set. Otherwise `pr-wait` exits 2 and prints the fix. A
host with a port works only through `GITLAB_HOST`. Never pass a token on the
command line.

In Claude Code, run it with the Monitor tool (`timeout_ms: 3600000`), so each
line wakes you. Without a monitor, run it as one long command. It ends on its
own.

Start it again after you push, after you handle an exit 1, and after a resume.
It remembers what it already reported, so nothing that arrived in between is
lost. If it says another pid already watches the MR, do not start a second one.
Kill the old one only if its events do not reach you.

With either watcher: when an event needs no action, end your turn without a
message. Never post or say "still waiting".

## GitLab rate limits

GitLab has one rate limit for REST and GraphQL together, so there is no
separate budget to switch to. On HTTP 429, wait for `Retry-After` or
`RateLimit-Reset` (see them with `glab api --include user`), then continue.
`pr-wait` backs off on 429 by itself. On self-hosted GitLab, the instance
admin sets the limits.

## Reviews

Only act on jobs and comments newer than the latest push. Verify every bot
finding against the source before changing code. Fix real findings and CI
failures, distinguish repository failures from infrastructure flakes, and reply
with a written reason when dismissing false positives.

If the project has `.macroscope/check-run-agents/*.md`, read those rules before
you reply to a Macroscope finding. Its findings cite them.

CodeRabbit is advisory. Treat its findings like any other finding, but never
wait for it and never hold a merge for it.

If a review bot leaves feedback you believe is not worth addressing, reply with
a written reason and resolve the thread. Use the `leaving-pr-comments` skill
for every comment posted on the user's behalf.

Screenshots and videos help as well, when you have a way to upload them.

Keep the MR at the size the user's goal needs. Review loops tend to grow an
MR one cheap-looking fix at a time. Fix real bugs in the intended case.
Decline the rest with a written reason, and list them as follow-ups:
unneeded tests, guards for edge cases that do not matter, extra integration
or compatibility, and small performance costs. Prefer the fix that deletes or
narrows code.

## Target branch and merging

Keep an eye on changes to the target branch (usually `main`) and rebase when
needed. `pr-wait` reports when new target branch commits touch this MR's
files, and when the MR becomes BEHIND (`need_rebase`) or DIRTY (`conflict`).
GitLab reports `need_rebase` only in projects that use fast-forward or
semi-linear merges. Elsewhere, read the "N commits behind" part of the
`pr-wait` green or ready line.
`watch_pull_request` reports conflicts only, so check for BEHIND yourself
before you call the MR ready.
If an overlapping MR makes this one obsolete, stop monitoring, report it to the
user, and ask before closing the MR unless closure was explicitly authorized.

If nothing has changed, stay quiet rather than posting filler comments. Stop
when `pr-wait` exits 0, or in T3 Code when the merge gate passes on the latest
head. Merge only when the user explicitly requested it;
otherwise report that the MR is ready. Right before a merge, run `git fetch` and
check the MR again. Never merge when it is BEHIND or DIRTY, or when target
branch commits that landed after the last green run touch this MR's files.
Rebase, push, and wait for green again.
