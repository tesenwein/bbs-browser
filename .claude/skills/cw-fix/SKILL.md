---
name: cw-fix
description: Fix the review-finding subtasks filed against a Code Workbench task, then re-run lint/typecheck/tests.
---

# cw-fix

Run the **Fix** phase of the Code Workbench task flow against the task id given in `$ARGUMENTS`. If no id was given, ask for one — never guess which task is meant.

## Procedure

Work ONLY on task $ARGUMENTS on the shared cw-tasks board. Start by finding it via task_list or task_find_similar and re-reading its current title, description, memo, and subtasks — anything quoted to you may have gone stale.
Do the work of THIS phase and nothing else. Hand off by setting `phase` exactly as instructed below — never skip a phase, never set it past the next one, and never start the next phase's work yourself, even if it looks trivial or you can already see the answer. If this phase's work turns out to be unnecessary, still hand off; do not absorb the next phase.
If you get blocked and cannot finish this phase (missing information, impossible step, broken environment), write what blocks you into the task's memo via task_update (id: "$ARGUMENTS", memo: "...") and STOP — leave `phase` unchanged so the board still shows this phase as pending. Never advance `phase` or mark anything done to get unstuck.

List the subtasks tagged "review-finding" that were open when you started, and fix each one strictly one at a time, in `order` (lower first, unordered last; ties break by creation time). Do the work yourself in THIS session — do not delegate findings to subagents. Mark each finding in-progress before you start it and done once fixed. Re-run lint, typecheck, and tests at the end.

You may NOT review: fix the findings already on the board and no more. If you spot a NEW problem while fixing, file it as another "review-finding" subtask but do NOT fix it — it belongs to the next Review/Fix round.

Then hand off via task_update on the task: if you filed any NEW findings (or had to change code beyond trivial finding fixes), id: "$ARGUMENTS", phase: "review" so the new work gets reviewed. Otherwise, once every "review-finding" subtask is done: id: "$ARGUMENTS", phase: "" (clear it), status: "done".
