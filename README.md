# tstack for GitLab

The agent skills from [tstack](https://github.com/t3dotgg/tstack), translated
to work with GitLab merge requests (MRs) on gitlab.com and self-hosted GitLab.
They work in Claude Code and Codex. Some use
[T3 Code](https://github.com/pingdotgg/t3code) features when they are available
and fall back to native tools when they are not.

## Skills

| Skill | Say | What it does |
|---|---|---|
| `full-send` | "full send" | Takes a change to a merged MR with nobody watching: proves it, reviews it, files it, babysits it, merges it. |
| `full-stop` | "full stop" | Same as `full-send`, but stops when the MR is ready for you to merge. |
| `council` | "council" | Gets review from three models from different providers, and loops until they agree. |
| `sol-loop` | "sol loop" | Reviews a change with GPT Sol in a loop until both agents agree. |
| `file-pr` | "file an MR" | Files a short MR that leads with the problem, not an inventory of changes. |
| `takeover` | "take over" | Finishes someone else's MR, branch, or agent thread, and keeps their credit. |
| `babysit-pr` | "babysit" | Watches an MR through its pipeline and review bots, and fixes the real findings. |
| `modernize` | "modernize" | Rebases an old MR and decides if it should still exist. |
| `leaving-pr-comments` | (automatic) | Formats comments that an agent posts on your behalf. |

The skill names keep upstream tstack's `pr` so the two stay easy to sync.

Some skills call others. Install the ones they need too:

- `full-send` uses `sol-loop`, `file-pr`, and `babysit-pr`.
- `full-stop` uses `full-send`.
- `takeover` uses `modernize`, `file-pr`, `babysit-pr`, and `leaving-pr-comments`.
- `file-pr`, `babysit-pr`, and `modernize` use `leaving-pr-comments`.

## Install

```bash
git clone https://github.com/jvmsangkal/tstack-gitlab
cp -R tstack-gitlab/skills/* ~/.claude/skills/   # Claude Code
cp -R tstack-gitlab/skills/* ~/.codex/skills/    # Codex
```

## Requirements

<!-- Placeholder: the pr-wait port sets the real minimum glab version. -->
- The [GitLab CLI](https://gitlab.com/gitlab-org/cli) (`glab`) 1.126.0 or
  later, signed in to each GitLab host you use. See [GitLab setup](#gitlab-setup).
- GitLab 16.0 or later, on any tier. See [Versions and tiers](#versions-and-tiers).
- `python3` for `babysit-pr`'s `pr-wait` script.
- `council` and `sol-loop` need subagents on other providers' models. T3 Code
  does this with `delegate_task`. Otherwise you need a harness that can run
  those models.

## GitLab setup

### Install glab

```bash
brew install glab   # macOS, Linux, and WSL
glab version
```

For other systems, see glab's
[installation options](https://gitlab.com/gitlab-org/cli/-/blob/main/docs/installation_options.md).

### Sign in

The skills get credentials from glab and nothing else. Sign in once per host:

```bash
glab auth login                                  # gitlab.com
glab auth login --hostname gitlab.example.com    # self-hosted
glab auth status --all
```

`--hostname` takes a bare hostname, with no scheme, port, or path. If the API
listens on another port, add `--api-host gitlab.example.com:8443`. glab keeps
the token in your OS keyring when one is available.

To use an environment variable instead, set `GITLAB_TOKEN` in the shell that
runs the agent. For a self-hosted instance, also set `GITLAB_HOST`:

```bash
export GITLAB_HOST=gitlab.example.com   # skip for gitlab.com
read -rs GITLAB_TOKEN && export GITLAB_TOKEN
```

glab sends `GITLAB_TOKEN` only to the `GITLAB_HOST` host and to hosts already
in its config. gitlab.com is in the config by default. Any other host gets no
token, and its calls fail as if you were signed out. One `GITLAB_TOKEN` covers
one host, so if you use several hosts, sign in to each with `glab auth login`.

Never put a token in a skill, `CLAUDE.md`, `AGENTS.md`, a repository, or a
command line. Pass it with `glab auth login` or `GITLAB_TOKEN` only. For a
cloud agent, store `GITLAB_TOKEN` as a secret.

### Token scopes

Create a
[personal access token](https://docs.gitlab.com/user/profile/personal_access_tokens/),
or a project or group access token if you want the agent to act as a bot user.

| Scope | Enough for |
|---|---|
| `api` | Everything the skills do: open MRs, comment, reply, resolve threads, merge, and cancel auto-merge. |
| `read_api` | Only `pr-wait`, which reads MRs and pipelines. |

The token's user needs the Developer role or higher on the project to push
branches, open MRs, and comment. Merging also needs whatever the target
branch's protection allows, which is Maintainer by default. Tokens expire, so
put the expiry date somewhere you'll see it.

Pushing branches is plain git. Use your usual SSH key or HTTPS credentials.

### Which host the skills use

`pr-wait` and the skills pick the GitLab host in this order:

1. The host in an MR or project URL you give them.
2. `GITLAB_HOST`.
3. The host of the current checkout's git remote, else gitlab.com.

Every host they reach must be signed in, as described above.

### Versions and tiers

Free tier on GitLab 16.0 or later is the baseline. Everything the skills need
is on Free: MRs, draft MRs, pipelines, threads, auto-merge, and the
"Pipelines must succeed" and "All threads must be resolved" merge checks. Turn
those two checks on so GitLab enforces the same gate that `full-send` waits
for.

Paid features are used when the project has them. A 403 or 404 from their API
means "not configured", not an error:

- Premium: approval rules and required approvals, and merge trains.
  `full-send` stays until a merge train merges the MR.
- Ultimate: external status checks, which count as required checks.

GitLab has no list of required checks. The skills treat every job in the MR's
head pipeline with `allow_failure: false` as required, plus any external status
checks.

Some behavior depends on the GitLab version:

- Reviewers can request changes from GitLab 16.9. On older instances, the
  skills fall back to approvals and unresolved threads.
- `> [!note]` callouts in agent comments render from GitLab 17.10. Older
  instances show a plain blockquote.

### Self-hosted notes

- If your instance uses a private CA, point glab at it:
  `glab config set ca_cert /path/to/ca.pem --host gitlab.example.com`.
- Instances served under a path, like `https://example.com/gitlab/`, are
  untested.
- Your admin sets the rate limits. `pr-wait` backs off when GitLab returns 429.

### Review bots

`pr-wait --until ready` waits for Greptile or Macroscope to review the current
head. CodeRabbit is advisory: it is reported but never waited for.

- [Greptile](https://www.greptile.com) and
  [CodeRabbit](https://www.coderabbit.ai) support GitLab.
- Macroscope doesn't support GitLab, so it never shows up. That's harmless.
- GitLab Duo Code Review is not counted as a review bot.

Without Greptile on the project, `ready` never comes. Use
`pr-wait --until green` instead.

## Make them yours

These are starting points. Edit them. Put personal settings, like which models
sit on your council, in your `CLAUDE.md` or `AGENTS.md`, so you can update the
skills without losing them.

## License

[MIT](LICENSE)
