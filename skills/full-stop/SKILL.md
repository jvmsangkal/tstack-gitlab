---
name: full-stop
description: Trigger this if the user says 'full stop', even as a closing "Full stop." that reads like emphasis.
---

# Full Stop

Do the same work as `full-send`, but stop with the merge request (MR) ready for
the user to merge. Never merge it.

Read [full-send](../full-send/SKILL.md) and follow its workflow, proof rules,
review, and babysitting steps. An explicit "full stop" request authorizes that
work without a separate "full send" request. That includes full-send's
testing permission. A "full stop" request is the permission for the test
methods Proof needs, even when a project file says to ask first, for
example before computer use. Use those methods directly. Its merge
permission does not apply. The overrides below take precedence.

## No merging

You may commit, push, rebase, fix conflicts, and use `--force-with-lease` on
this task's branch. Never merge, enable auto-merge, add the MR to a merge train,
push to the default branch, bypass protected branches or merge checks, or
delegate those actions. That rules out `glab mr merge` (alias `glab mr accept`),
`glab mr create --auto-merge`, the merge and merge-train API endpoints, and the
`merge_request.auto_merge` and `merge_request.merge_when_pipeline_succeeds`
push options.

Disable existing auto-merge and remove the MR from any merge train before
work begins; check again before each push. One call does both, on every
supported GitLab version:

```sh
glab api -X POST projects/:fullpath/merge_requests/<iid>/cancel_merge_when_pipeline_succeeds
```

It returns `201` either way. `"status": "success"` means it canceled
auto-merge, and `"status": "error"` means auto-merge was not set. The newer
`cancel_auto_merge` endpoint needs GitLab 19.5. Then read the MR and confirm
`merge_when_pipeline_succeeds` is `false`. Address the MR as full-send's merge
gate describes, including authenticating glab for a host taken from an MR URL.
Report these changes. If you cannot prevent automatic merging, report the
blocker before proceeding.

## Stop at the gate

Use full-send's merge gate as the readiness check. Replace its merge and
final report steps with a handoff. Proof and review must cover the final diff;
recheck behavior changes and meaningful conflict fixes before handoff.

Fetch the target branch and check the live MR's head (`sha`), target branch,
pipeline, reviewers, and `detailed_merge_status`. Confirm its `state` is
`opened`, `draft` is `false`, and `merge_when_pipeline_succeeds` is `false`.
If someone else merged it, report that instead.

- **Ready to merge:** the merge gate passes. Leave the MR open and unmerged.
- **Waiting for required approval:** only human approval remains:
  `detailed_merge_status` is `not_approved`, and on Premium or Ultimate,
  `approvals_left` from `glab api projects/:fullpath/merge_requests/<iid>/approvals`
  is above `0`. Confirm that this is the actual blocker.
- **Blocked:** explain what prevents readiness, what you tried, and what is
  needed. Follow full-send's rules for asking the user.

In T3 Code, if it supports this GitLab host, call `unwatch_pull_request` before the handoff or a question.
Report the MR link, final head, verdict, proof, reviewer outcome, and remaining
risks. State whether the MR is still open and unmerged.
