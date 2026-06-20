# Claude Code Configuration

## Permissions

Claude has access to files within this repository only. Do not read, write, or
reference paths outside the project root.

## Tool Use Policy

Always ask for explicit approval before running any of the following:

- Shell commands (`Bash` tool)
- Creating, moving, or deleting files
- Installing packages or modifying lockfiles
- Running tests or build scripts
- Making network requests
- Accessing environment variables or secrets

When proposing a command, show the exact command and explain what it does and
why it's needed. Wait for a yes before proceeding.

## What Claude May Do Without Asking

- Read files within the repository
- Propose code edits and explain reasoning
- Search within the repository
- Run `git` commands (status, log, diff, checkout, pull, push, commit, branch, rm, etc.)
- Run `gh` commands (pr create, pr view, issue, etc.)
- Run `docker` / `docker compose` commands scoped to this project (up, down, ps, logs, exec, build, etc.)

## Testing

Always run tests inside the app container, not on the host. The host has no
Python environment; pytest and all dependencies live inside the container.

```
docker compose exec app python -m pytest <test_path> -v
```

Because source code is baked into the image (not volume-mounted), any code
changes require a rebuild before running tests:

```
docker compose build app && docker compose up -d app
```

## General Behavior

- Prefer targeted, minimal changes over broad rewrites
- Do not add dependencies without approval
- If uncertain whether an action requires approval, ask
