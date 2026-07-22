---
name: cw-implement
description: Work a Code Workbench task's plan-step subtasks in order, keeping the board in sync, until lint/typecheck/tests pass.
---

# cw-implement

Run the **Implement** phase of the Code Workbench task flow against the task id given in `$ARGUMENTS`. If no id was given, ask for one — never guess which task is meant.

## Procedure

Work ONLY on task $ARGUMENTS on the shared cw-tasks board. Start by finding it via task_list or task_find_similar and re-reading its current title, description, memo, and subtasks — anything quoted to you may have gone stale.
Do the work of THIS phase and nothing else. Hand off by setting `phase` exactly as instructed below — never skip a phase, never set it past the next one, and never start the next phase's work yourself, even if it looks trivial or you can already see the answer. If this phase's work turns out to be unnecessary, still hand off; do not absorb the next phase.
If you get blocked and cannot finish this phase (missing information, impossible step, broken environment), write what blocks you into the task's memo via task_update (id: "$ARGUMENTS", memo: "...") and STOP — leave `phase` unchanged so the board still shows this phase as pending. Never advance `phase` or mark anything done to get unstuck.

Work its subtasks tagged "plan-step" strictly one at a time, in `order` (lower first, unordered last; ties break by creation time — if there are none, work the task's description directly). Do the work yourself in THIS session — do not delegate subtasks to subagents. Mark each subtask in-progress before you start it and done when it passes. Run whatever lint, typecheck, and test scripts the project has; treat a failure as unfinished work, not a separate finding.

You may NOT review: do not audit the diff for findings, do not file "review-finding" subtasks, and do not clear `phase` or mark the task done. A failing check is yours to fix; a code smell you notice in passing is the Review phase's to find.

When every "plan-step" subtask (or the task itself, if it had none) is done, task_update the task: id: "$ARGUMENTS", phase: "review".
