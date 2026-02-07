# Task: Create Hello World Module

Create a simple Python module with a hello function and comprehensive tests.

## Requirements
- Create hello.py with a hello() function that returns "Hello, World!"
- Create test_hello.py with pytest tests
- All tests must pass

## Process
1. Create hello.py with hello() function
2. Create test_hello.py with pytest test cases:
   - Test that hello() returns correct string
   - Test that return value is a string type
   - Test that return value is not empty
3. Run tests: run_shell("pytest test_hello.py -v")
4. If any tests fail:
   - Read the error message
   - Fix the implementation in hello.py
   - Run tests again
5. Repeat until all tests pass

## Success Criteria
- hello.py exists with hello() function
- test_hello.py exists with at least 3 test cases
- All pytest tests pass (exit code 0)
- No errors or warnings

When all tests pass, output: <promise>COMPLETE</promise>
