---
name: cw-review
description: Review the work done for a Code Workbench task and file each real finding as a review-finding subtask.
---

# cw-review

Run the **Review** phase of the Code Workbench task flow against the task id given in `$ARGUMENTS`. If no id was given, ask for one — never guess which task is meant.

## Procedure

Work ONLY on task $ARGUMENTS on the shared cw-tasks board. Start by finding it via task_list or task_find_similar and re-reading its current title, description, memo, and subtasks — anything quoted to you may have gone stale.
Do the work of THIS phase and nothing else. Hand off by setting `phase` exactly as instructed below — never skip a phase, never set it past the next one, and never start the next phase's work yourself, even if it looks trivial or you can already see the answer. If this phase's work turns out to be unnecessary, still hand off; do not absorb the next phase.
If you get blocked and cannot finish this phase (missing information, impossible step, broken environment), write what blocks you into the task's memo via task_update (id: "$ARGUMENTS", memo: "...") and STOP — leave `phase` unchanged so the board still shows this phase as pending. Never advance `phase` or mark anything done to get unstuck.

Review the work done for this task: `git status --short`, `git diff`, `git diff --staged`, and this branch's commits vs its base (resolve origin/HEAD, else develop, else main/master). Read surrounding files for context. Look for correctness bugs, logic errors, missing error handling, type-safety escapes, security issues, and needless complexity.

You may NOT fix: change no code, not even a one-line typo or an obviously-correct rename. Every finding leaves this phase as a subtask, and the Fix phase applies it. A review that edits its own findings is a review nobody checked.

File each real finding as a subtask via task_create (parentId: "$ARGUMENTS", tags: ["review-finding"], priority reflecting severity, description: "file:line, what is wrong, why it matters, suggested fix"). Set `order` on each (0, 1, 2, ...) to fix the sequence the Fix phase should follow.

Then hand off via task_update on the task: if you filed any findings, id: "$ARGUMENTS", phase: "fix". If you filed none and no other subtasks are still open, id: "$ARGUMENTS", phase: "" (clear it), status: "done". If you filed none but other subtasks ARE still open, note in the memo what is left and set phase: "implement" so the remaining work gets picked up — never leave the task with no phase while it is unfinished.
