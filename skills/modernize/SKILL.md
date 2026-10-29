---
name: modernize
description: >-
  For getting old merge requests (MRs, PRs) up to date. Use when asked to rebase
  an MR or PR, or "modernize".
---

# Modernize

Modernize the idea, not just the branch. A clean rebase does not prove that the
merge request (MR) still belongs in the product.

## Guardrails

- Always check to make sure you have pulled latest origin for your branch, main
  branch, and any other branch related to your work before starting.
- Treat existing worktree changes as user-owned. Use a disposable worktree when
  the active worktree is dirty or is being used for other work.
- Modernizing authorizes rebasing and updating the MR's source branch. It does
  not authorize merging, closing, changing the target branch, or expanding
  scope.
- Never use an unqualified force push. Update a rebased branch with
  `--force-with-lease` against the head SHA observed before the rebase.
- Do not post an MR comment unless the user asked for one. Use the
  `leaving-pr-comments` skill for every comment posted on the user's behalf.

## Establish the MR's intent

Resolve the MR and record its URL, state, target branch, source project and
branch, current head SHA, author, pipeline, and approval state. Read
`glab api projects/:fullpath/merge_requests/<iid>` for `web_url`, `state`,
`draft`, `target_branch`, `source_branch`, `source_project_id`,
`target_project_id`, `sha`, `author`, `head_pipeline`, and
`detailed_merge_status`, and `.../merge_requests/<iid>/approvals` for
`approved_by`. For an MR in another project, use its URL-encoded path
(`projects/group%2Fsub%2Fproject/...`) and pass `--hostname <host>` for a
self-hosted instance. `--hostname` alone sends no token, so make sure that host
is authenticated first (`glab auth login --hostname <host>`, or set
`GITLAB_HOST=<host>`); it takes a bare host, not `host:port`. Read the title,
description, linked issues
(`.../merge_requests/<iid>/closes_issues` plus `Closes #n` in the description),
commits, threads (`.../merge_requests/<iid>/discussions`), and complete diff.
State the smallest coherent goal the MR was trying to accomplish before judging
its implementation.

Fetch the latest remote target branch and MR head. Fetch the head with
`git fetch origin refs/merge-requests/<iid>/head`, which works when the source
project is a fork; GitLab deletes that ref 14 days after an MR is closed or
merged, so fall back to the source branch then. Use the MR's actual target
branch, usually `main`, rather than assuming the local branch is current.
Record the merge base so the original MR and subsequent target-branch changes
can be compared separately.

## Check what changed around it

Inspect commits and diffs added to the target branch since the MR diverged.
Search merged and open MRs (`glab mr list --merged --search <text>`,
`glab mr list --search <text>`) when titles, code paths, or behavior suggest a
replacement or competing implementation.

Look beyond overlapping lines:

- Has the same user-facing problem already been solved?
- Did APIs, types, schemas, dependencies, or architectural boundaries change?
- Do both sides now claim ownership of the same behavior or invariant?
- Was the code being changed deleted, moved, or intentionally simplified?
- Would landing the MR restore an old behavior or create two ways to do the
  same thing?
- Is the original benefit still large enough to justify the maintenance cost?

Do not describe an MR as current merely because Git reports no conflicts.

## Choose a disposition before pushing

Use one of these recommendations:

- **MODERNIZE**: the goal is still useful and the implementation remains the
  right shape. Rebase, resolve conflicts, test, and update the branch.
- **REWORK**: the goal is still useful, but a mechanical rebase would preserve
  the wrong implementation. Explain the smallest credible rewrite and stop
  before pushing unless the user also asked for that rework.
- **CLOSE**: the MR is superseded, obsolete, directionally wrong, or no longer
  worth its cost. Cite concrete evidence and stop. Do not spend time rebasing an
  obsolete branch, and do not close it without explicit permission.

Be willing to recommend `CLOSE`. Age alone is not evidence, and sunk effort is
not a reason to keep an MR alive.

## Rebase without losing intent

For a `MODERNIZE` disposition:

1. Create a safe local branch or disposable worktree at the recorded MR head.
2. Rebase its commits onto the freshly fetched target branch.
3. Resolve each conflict according to the MR's current intent and the target
   branch's newer invariants. If a conflict reveals a product or architecture
   disagreement, stop and reconsider the disposition instead of guessing.
4. Compare the pre-rebase and post-rebase commit series with `git range-diff`
   and inspect the final diff. Confirm that no intentional behavior disappeared
   and no already-landed behavior was reintroduced.
5. Run the repository's focused checks for the touched area. Distinguish real
   failures from pre-existing or infrastructure failures.
6. Push the source branch with `--force-with-lease` tied to the previously
   observed remote head. The `refs/merge-requests/` ref is read-only, so push
   to the source project: when `source_project_id` differs from
   `target_project_id`, get its `ssh_url_to_repo` or `http_url_to_repo` from
   `glab api projects/<source_project_id>`. Pushing to someone else's fork needs
   `allow_collaboration` on the MR; if it is off, stop and report. If the lease
   fails, fetch and reassess rather than overwriting new work.

Do not merge the MR.

## Report

Lead with `MODERNIZE`, `REWORK`, or `CLOSE` and the reason. Then summarize:

- meaningful changes on the target branch;
- conceptual conflicts or confirmation that none were found;
- the rebase and push result, if performed;
- checks run and their results;
- the remaining decision or work, with a link to the MR.

Separate observed facts from judgment. Say what could not be verified instead
of manufacturing confidence.
