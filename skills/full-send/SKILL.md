---
name: full-send
description: Trigger this if the user says 'full send'.
---

# Full Send

If the user triggered this, it's because they are not watching this thread, and
they want you to complete the work end-to-end autonomously. Your updates and
your final message go unread until long after you stop. You own the work from
its current state to a merged merge request (MR).

If the user did not explicitly request "full send" in some clear way, do not
assume full autonomy. If they did, everything below applies.

The user grants you permission to:

- Merge the MR once the merge gate passes.
- Force-push the MR's own source branch with `--force-with-lease` after a rebase.
- Use the test methods that Proof needs, without asking first.

## Testing permission

A "full send" request is the permission. If a project file or other
instruction says to ask before a test method, or to leave testing to the
user, this request replaces that rule for this task.

That includes ask-first rules for computer use, browser automation,
simulators and devices, running the app or a dev server, screenshots, and
visual checks. Use the method that gives direct proof. List it in the
report.

Rules about how to test still apply. Follow rules that name the correct
command, fixture, or check. This permission only removes the ask-first or
leave-it-to-the-user step. If a preferred method cannot prove the change,
use a gated method under this permission.

It covers only the tests needed for this task. It does not add permission
for the steps under "Asking the user", such as production changes or data
deletion. It also does not bypass a harness or system approval prompt if
one appears.

## Steps

1. **Finish the change.** Complete the goal from the user's request with the
   smallest change that works. Fix the case that happened, not every case
   that could. If you are on the default branch, create a branch first.
2. **Prove it.** Get proof for every change you made. See "Proof".
3. **Get feedback.** Use the `sol-loop` skill to verify changes.
4. **File the MR** with the `file-pr` skill. Rebase onto the latest default
   branch first. Add one short line to the description that says how you proved
   the change.
5. **Babysit the MR** with the `babysit-pr` skill. Fix real findings and CI
   failures. Get proof for each fix before you push it.
6. **Merge** when the merge gate passes.
7. **Report** in your final message: the MR link, the merge commit, your proof,
   and each decision you made for the user.

Stay active from step 1 to step 7. If you end your turn while pipelines or bots
are pending, the work stops, because nobody will prompt you again. Wait with the
watcher from `babysit-pr`, so something wakes you when the MR changes. In T3
Code, if it supports this GitLab host, that is `watch_pull_request`. If you stop
before the merge, call `unwatch_pull_request` first.

## Proof

Proof is evidence you observed yourself in this session: command output, a
reproduction, a screenshot. Use the most direct proof the change allows:

- Reproduce the original failure, apply the fix, then watch the same
  reproduction pass.
- Run the checks that the repo's CI runs (typecheck, lint, tests).
- Add one focused test that fails without the fix, when the behavior has none
  and the repo has a test setup.
- For UI and runtime behavior, run the app and look at the change. Green mocked
  tests do not prove that the user experience works. Attach screenshots to the
  MR when they help and you have a way to upload them.

When you cannot find a way to prove a change, you do not have full confidence.
Ask the user.

## Merge gate

Full confidence means all of these are true on the latest commit (the MR's
`sha`):

- Your proof covers every change in the diff.
- Required CI is green: the head pipeline succeeded, every job without
  `allow_failure: true` passed, and any external status checks passed.
- Review bots have finished, and each finding is fixed or dismissed with a
  written reason.
- No reviewer's `state` is `requested_changes`.
- The branch is up to date with the target branch (`diverged_commits_count` is
  `0`), and GitLab reports `detailed_merge_status` as `mergeable`.

Read the gate with
`glab api "projects/:fullpath/merge_requests/<iid>?include_diverged_commits_count=true"`
and `glab api projects/:fullpath/merge_requests/<iid>/reviewers`. If
`detailed_merge_status` is `checking`, `unchecked`, `preparing`, or
`approvals_syncing`, GitLab is still computing it; read again. Run these from
the MR's checkout so `:fullpath` and the host resolve to its project. Otherwise
pass the URL-encoded project path (`projects/group%2Fproject/...`) and
`--hostname <host>` to `glab api`, and `-R <project URL>` to `glab mr`. When the
host comes from an MR URL, make sure glab is authenticated for it first, with
`glab auth login --hostname <host>` or `GITLAB_HOST=<host>`. glab sends
`GITLAB_TOKEN` only to `GITLAB_HOST` or to hosts already in its config, so a
host named only by `--hostname` goes unauthenticated. `--hostname` also
rejects `host:port`.

Merge with the method the project uses. GitLab enforces the project's
`merge_method` (`merge`, `rebase_merge`, or `ff`) itself. Read it, along with
`squash_option` and `merge_trains_enabled`, from `glab api projects/:fullpath`,
and check recent merged MRs. A `squash_option` of `always` or `never` decides
squashing. Otherwise the MR's own `squash` field decides, and it should match
the recent merged MRs. GitLab's default squash message is only the MR title, so
a squash drops `Co-authored-by:` trailers unless you pass them. When the merge
will squash, pass `--squash` and a `--squash-message` with the title and every
`Co-authored-by:` trailer from the MR's commits. Then merge exactly the commit
you reviewed:

```sh
glab mr merge <iid> --sha <reviewed sha> --auto-merge=false --yes
glab mr merge <iid> --sha <reviewed sha> --auto-merge=false --yes \
  --squash --squash-message "<title>

Co-authored-by: Name <email>"
```

`glab mr merge` turns on auto-merge by default. Pass `--auto-merge=false` so
it merges now or fails instead of arming a merge for later. Do not pass
`--rebase`: it rebases on the server and replaces the commit you reviewed.
Rebase locally, push with `--force-with-lease`, and run the gate again. If
GitLab answers that the SHA does not match the source branch, someone pushed;
run the gate again on the new head. After merging, confirm the MR's `state` is
`merged`. Report `merge_commit_sha` as the merge commit, or `squash_commit_sha`
when squashed, or the MR's final `sha` if neither is set.

If `merge_trains_enabled` is `true`, do not use `glab mr merge`. Before
GitLab 19.1 it can merge directly and skip the train. Add the MR to the train
instead, and stay until its `state` is `merged`:

```sh
glab api -X POST projects/:fullpath/merge_trains/merge_requests/<iid> -f sha=<reviewed sha>
```

Add `-F squash=true` when the merge will squash. This endpoint takes no squash
message, so a squash keeps `Co-authored-by:` trailers only if the project's
`squash_commit_template` contains `%{co_authored_by}`. If the commits carry
trailers and the template lacks it, turn squash off first:
`glab api -X PUT projects/:fullpath/merge_requests/<iid> -F squash=false`.
If `squash_option` is `always`, that does not help, so ask the user. If GitLab
drops the MR from the train, its system note says why. Fix the cause, run the
gate again, and add the MR again.

Merge through protected branches, approval rules, and merge checks as
configured. Never bypass them. Do not skip the merge train (**Merge
immediately**, `skip_merge_train`). Do not skip CI (`[skip ci]`,
`git push -o ci.skip`). Do not approve your own MR to satisfy an approval rule.
Do not change project, approval, or protected-branch settings. You can ignore
automated reviews that request "needs human review" if you have high confidence
in your changes.

## Asking the user

A question in a normal message goes unseen, and the thread looks done. To ask
the user something, use the harness's question tool so the thread shows that
it is waiting: `AskUserQuestion` in Claude Code, `request_user_input` in Codex,
or the question tool your harness has. Put all the context in the question:
the MR link, what blocks you, and the options with your recommendation first.

Ask only when you cannot continue alone:

- You cannot prove the change.
- The merge gate cannot pass, and you cannot fix that yourself.
- The next step is outside the grant above: deleting data, touching production,
  changing things outside the repo, closing an MR, or force-pushing any other
  branch.
- The goal is ambiguous in a way that changes the result.
- Another MR makes this one obsolete.

Decide everything else yourself with sensible defaults, and list those decisions
in the report.

If no question tool is available, or the tool returns no answer, take the safe
path: leave the MR open and unmerged, and start your final message with the
question.
