---
name: leaving-pr-comments
description: Use whenever leaving comments on GitLab, including merge request (MR) comments, threads, and replies.
---

# Leaving MR Comments

Prefix every agent-authored comment left on the user's behalf with this GitLab
note alert:

```md
> [!note]
> 🤖 **<model> responding on behalf of <user>**

Actual comment starts here.
```

GitLab 17.10 and later render it as a note alert; older versions show a plain
blockquote, which is fine.

Use the verified public name of the model that wrote the comment, and the
user's name or GitLab username.

If the harness does not expose a model name, use the harness name. Do not guess.

Before posting, check the entire comment, including quoted text and
attachments, for secrets and private details.

Keep the attribution inside the note and the actual reply outside it. The
context line must start with the robot emoji. Do not add a horizontal rule,
Setext underline, heading, signature footer, or a second attribution.

Apply this format to top-level merge request (MR) comments, diff threads,
replies to bots or reviewers, and written explanations used before resolving
threads or dismissing feedback. Do not add it to MR descriptions, commit
messages, or text the user explicitly asked to post verbatim without
attribution.

Write the comment itself in a direct style:

- Lead with the conclusion.
- Cite the relevant code, behavior, check, or reproduction.
- Keep it concise and avoid filler, canned thanks, or status narration.
- Distinguish verified facts from judgment.

Preview the final Markdown before posting so quoting and blank lines render as
shown. Write it to a file and post it through the REST API with `glab api`:

- MR comment: `glab api projects/:fullpath/merge_requests/<iid>/notes -F body=@<file>`
- Reply in a thread: `glab api projects/:fullpath/merge_requests/<iid>/discussions/<discussion_id>/notes -F body=@<file>`
- Diff thread: `glab api projects/:fullpath/merge_requests/<iid>/discussions -F body=@<file> -F 'position={"position_type":"text","base_sha":"...","start_sha":"...","head_sha":"...","old_path":"...","new_path":"...","new_line":<n>}'`.
  Take the three SHAs from `diff_refs` in `glab api projects/:fullpath/merge_requests/<iid>`.
  Use `new_line` for an added line, `old_line` for a removed line, and both for
  an unchanged line.
- Resolve a thread: `glab api -X PUT projects/:fullpath/merge_requests/<iid>/discussions/<discussion_id> -F resolved=true`

`:fullpath` is the project of the current repository. For another project, use
its URL-encoded path, such as `projects/group%2Fsubgroup%2Fproject/...`. When
the MR is on a different host than the current repository, make sure glab is
authenticated for that host with `glab auth login --hostname <host>` and pass
`--hostname <host>`, or run with `GITLAB_HOST=<host>`. glab sends no token to
other hosts, and `:fullpath` does not work across hosts.

After posting, verify that GitLab returned the note `id` (for a new thread, the
first entry in `notes`); its URL is `<MR web_url>#note_<id>`. Resolve a thread
only after its response was posted successfully.
