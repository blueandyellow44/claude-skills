---
name: cross-session-port
description: Move this session's commits onto a branch another Claude session owns (one production branch to another and back) without touching that session's worktree or uncommitted files, then hand the merge and the deploy to the owner. Use when the owner says a change should go to the other site, when another session deployed your commits, or when "coordinate with the other sessions" comes up.
---

# cross-session-port

## Goal

The change lands on the other branch, the owning session merges and deploys it in its own sequence, nothing it was holding is overwritten, and the owner gets one deployment id back.

## Why this exists

2026-10-06. Several parallel sessions were working on two sites built from one repo, and the ask was to communicate with the first and coordinate. The first message went to the wrong session (it was on unrelated work); the deploy in question had already gone out from another session carrying this session's commits; the owning session's worktree held an uncommitted edit to the very file the port changed; `git cherry-pick`, `git apply` and `git revert` are all stopped by this plugin's piece gate.

## Steps

1. **Find out what already happened.** The project's log (other sessions record their deploys there), `git tag --points-at <your HEAD>`, and `git merge-base --is-ancestor <sha> <branch>` before claiming anything is or is not deployed. Check the live bundle for your change.
2. **Find the owner by evidence.** `ListAgents`, then the project notes that name sessions and branches. Ask one session; if it says it is not the owner, take its pointer and move on.
3. **Never write in someone else's worktree.** Read it (`git status --short`, `git log`) only.
4. **Build the port in a scratch worktree** on a new branch from the target branch's HEAD. Per file: if the target's blob equals your commit's parent blob, `git checkout <sha> -- <file>`; otherwise three-way merge it by name with `git merge-file -p <target> <base> <theirs>`. Commit one commit per original concern, with "(cherry picked from commit …)" in the body.
5. **Prove it there.** Typecheck app and functions, build, run the project's checks; name any failure that also fails on the untouched target.
6. **Hand off.** Message the owning session: the owner's words verbatim, the branch, the commits, the files, the exact hunks in any file its uncommitted edit touches, and that the merge and deploy are its to sequence. Remove the scratch worktree; keep the branch.
7. **Verify the reply.** `git merge-base --is-ancestor` on the owning session's branch, then the live site after its deploy.

## Rules

1. One session merges and deploys a branch. Offer to do it; do not do it unasked.
2. The owner's ruling travels verbatim, and so do reversals: when the owner cuts something, tell the owning session before reverting anything yourself, so two sessions do not revert the same commit.
3. No `git stash` and no `reset --hard` anywhere near a shared tree.
