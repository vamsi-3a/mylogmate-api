Review recent changes for quality and security:

1. Run `git diff HEAD~1` to see changes
2. Check against the code-reviewer agent checklist
3. Run `ruff check .` and report issues
4. Run `mypy app/` and report type errors
5. Check: user_id filters on all queries, content encryption, no hardcoded secrets
6. Report: CRITICAL / WARNING / SUGGESTION categorized findings
7. Suggest specific fixes for each issue

Scope: $ARGUMENTS
