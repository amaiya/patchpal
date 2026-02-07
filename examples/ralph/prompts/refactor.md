# Task: Refactor for Better Code Quality

Refactor the codebase to improve code quality while maintaining all functionality.

## Requirements
- All existing tests must continue to pass
- No behavior changes (this is a refactor, not a feature addition)
- Improve code organization and readability
- Remove code smells (duplication, long functions, etc.)
- Add type hints where missing
- Improve naming (variables, functions, classes)
- Extract magic numbers into named constants

## Constraints
- DO NOT modify test files (except to add new tests if needed)
- DO NOT change public APIs (function signatures, class interfaces)
- Make incremental changes - one refactoring at a time
- Run tests after EACH change to ensure nothing broke

## Process
1. Run tests to establish baseline: run_shell("pytest -v")
   - All tests must pass before starting

2. Identify refactoring opportunities:
   - Read through the code
   - Look for duplicated code
   - Find long functions (>50 lines)
   - Spot unclear variable names
   - Check for missing type hints

3. Apply ONE refactoring:
   - Make the change
   - Run tests immediately
   - If tests fail, revert and try different approach
   - If tests pass, commit the change

4. Repeat steps 2-3 until code quality is improved

5. Final verification:
   - Run tests: run_shell("pytest -v")
   - Check code with linter: run_shell("ruff check .")
   - Verify no regressions

## Refactoring Checklist
- [ ] No duplicated code blocks
- [ ] Functions under 50 lines
- [ ] Clear variable and function names
- [ ] Type hints on all functions
- [ ] Magic numbers extracted to constants
- [ ] Complex logic documented with comments
- [ ] All tests still passing

## Success Criteria
- All tests pass (no regressions)
- Code quality improved (fewer code smells)
- No linter errors
- Type hints coverage >90%
- No behavior changes

When all refactoring is complete and tests pass, output:

<promise>REFACTORED</promise>
