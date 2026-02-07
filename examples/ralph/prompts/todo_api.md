# Task: Build a Todo REST API

Build a complete REST API for a Todo application with comprehensive tests.

## Requirements
- Flask app with CRUD endpoints (GET, POST, PUT, DELETE)
- In-memory storage using Python dict
- Input validation (title required, max 200 chars)
- Unit tests with pytest
- Integration tests for all endpoints
- All tests must pass with >80% coverage
- README with API documentation

## Process
1. Create app.py with Flask routes:
   - GET /api/todos - list all todos
   - POST /api/todos - create todo
   - GET /api/todos/<id> - get todo by id
   - PUT /api/todos/<id> - update todo
   - DELETE /api/todos/<id> - delete todo

2. Create tests/test_app.py with comprehensive tests:
   - Test all CRUD operations
   - Test input validation
   - Test error cases (404, 400)
   - Test edge cases

3. Run tests: run_shell("pytest tests/test_app.py -v --cov=app")

4. If tests fail:
   - Read the test output carefully
   - Identify the failing test
   - Fix the bug in app.py
   - Run tests again
   - Repeat until all tests pass

5. Create README.md with:
   - Installation instructions
   - API endpoint documentation
   - Example requests/responses
   - How to run tests

## Success Criteria
- All CRUD operations work correctly
- Input validation prevents invalid data
- Tests pass with >80% coverage
- No errors when running pytest
- README is complete and accurate
- Code follows Python best practices

## Escape Hatch
After 15 iterations if not complete:
- Document blocking issues in STUCK.md
- List attempted approaches
- Suggest what's preventing completion

When all requirements are met and tests pass, output:

<promise>COMPLETE</promise>
