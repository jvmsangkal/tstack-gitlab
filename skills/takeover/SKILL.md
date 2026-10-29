---
name: takeover
description: Take over existing work. Use when the user asks to take over a merge request (MR) or PR, a branch, or an agent thread, or requests a takeover.
---

# Takeover

Take responsibility for finishing the original goal while preserving the
original contributors' credit. Do not defend an implementation just because
another agent already built it.

Read the source merge request (MR), branch, or thread, including review findings
and the user's later corrections. Resolve the handoff to the actual code and
current head, and account for uncommitted work. An MR's source project may be a
fork; fetch its head with `git fetch origin refs/merge-requests/<iid>/head`.
Treat the handoff as context, not proof.

For a replacement MR, import the original commits onto a new branch and add
your fixes separately. Honor an explicitly requested in-place or stacked
continuation instead. Do not overwrite unrelated work or change the original
MR without authorization.

Preserve Git authorship and existing co-author trailers. Credit the original
contributors in the MR description and link the original MR (`!123`, or
`group/project!123` across projects) when there is one. If the work will be
squashed, preserve human author/co-author credit in the squash commit too,
using verified identities rather than guessed emails. GitLab's default squash
message is only the MR title, so when merging, pass the `Co-authored-by:`
trailers with `glab mr merge --squash --squash-message`. Model attribution is
not a substitute for contributor credit.

Use `modernize` to update the continuation against its intended target branch
and current architecture. Rework what is necessary to finish the same goal, not
unrelated features. Simplify the implementation without dropping intended
behavior or surfaces. Recheck the source MR too: it may have improved while
you were working.

Independently verify the original failure and realistic workflows, following
repository guidance and permissions. Green mocked tests do not prove the user
experience works. State what remains unverified.

When the requested finish includes an MR, use `file-pr` to file or update it,
then `babysit-pr` rather than stopping at creation. Use `leaving-pr-comments`
for replies. Merge or close the original MR only when authorized.

Report what you inherited, what you changed, how you verified it, how credit
was preserved, and any remaining decision.
