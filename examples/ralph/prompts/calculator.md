# Task: Create a Simple Calculator

Build a Python calculator module with tests.

## Requirements
- Create calculator.py with functions: add, subtract, multiply, divide
- Handle division by zero (raise ValueError)
- Create test_calculator.py with pytest tests
- All tests must pass

## Process
1. Create calculator.py with four functions:
   - add(a, b) - returns sum of a and b
   - subtract(a, b) - returns difference of a and b
   - multiply(a, b) - returns product of a and b
   - divide(a, b) - returns quotient of a and b, raises ValueError if b is zero

2. Create test_calculator.py with pytest test cases:
   - Test add() with positive numbers
   - Test subtract() with positive and negative numbers
   - Test multiply() with various numbers
   - Test divide() with valid inputs
   - Test divide() raises ValueError when dividing by zero
   - Test edge cases (zero, negative numbers, decimals)

3. Run tests: run_shell("pytest test_calculator.py -v")

4. If any tests fail:
   - Read the error message carefully
   - Identify which function has the bug
   - Fix the implementation in calculator.py
   - Run tests again
   - Repeat until all tests pass

5. Verify all tests pass with no errors or warnings

## Success Criteria
- calculator.py exists with all 4 functions
- test_calculator.py exists with at least 6 test cases
- All 4 functions work correctly
- Division by zero raises ValueError with a descriptive message
- All pytest tests pass (exit code 0)
- No errors or warnings

## Notes
- Use descriptive error messages for ValueError
- Test edge cases (0, negative numbers, decimals)
- Ensure functions work with both integers and floats

When all tests pass, output: <promise>COMPLETE</promise>
