# Task: Fix Failing Tests

Fix all failing tests in this codebase using TDD principles.

## Process
1. Run all tests: run_shell("pytest -v")

2. For each failing test:
   - Read the test code to understand what it expects
   - Read the error message carefully
   - Identify the root cause
   - Fix the code (not the test!)
   - Run tests again
   - Verify the fix didn't break other tests

3. Repeat until all tests pass

4. Run final verification:
   - run_shell("pytest -v --cov")
   - Ensure coverage is maintained or improved

## Guidelines
- Never modify tests unless they are clearly incorrect
- Fix the implementation, not the test
- Make minimal changes - don't refactor unrelated code
- Run tests after each fix to catch regressions
- If stuck on a test for 3 attempts, document the issue and move to next test

## Success Criteria
- All tests pass (pytest exit code 0)
- No errors or warnings
- Coverage is maintained (>80%)
- No tests were disabled or skipped

## Escape Hatch
After 15 iterations if any tests still fail:
- Document remaining failing tests in FAILING_TESTS.md
- Include error messages
- Explain what was attempted
- Suggest possible causes

When all tests pass, output:

<promise>DONE</promise>
