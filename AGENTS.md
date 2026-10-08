# Repository instructions

- Before changing code, inspect the current tree and preserve unrelated working-tree changes.
- Apply the closest `AGENTS.md` to files in its directory subtree.
- For every frontend task, read `frontend/AGENTS.md` before analysis or edits, including when Codex starts from the repository root.
- Do not apply frontend-specific architecture rules to backend or infrastructure changes.
- Create and edit every file, inside or outside the repository, with the agent's native file-editing tool (`apply_patch`, `Edit`/`Write`, or equivalent) so the user sees a red/green diff of the exact change. Never modify files through shell commands such as heredocs (`cat <<EOF`), `sed -i`, `echo >`, or inline Python/Node scripts. Deleting a whole file is the only exception: if the agent's editing tool cannot delete files, `rm` is allowed for a file the user asked to remove.
