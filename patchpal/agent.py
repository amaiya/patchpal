import os
from smolagents import ToolCallingAgent, LiteLLMModel, tool
from patchpal.tools import read_file, list_files, apply_patch, run_shell


def _is_bedrock_arn(model_id: str) -> bool:
    """Check if a model ID is a Bedrock ARN."""
    return (
        model_id.startswith('arn:aws') and
        ':bedrock:' in model_id and
        ':inference-profile/' in model_id
    )


def _normalize_bedrock_model_id(model_id: str) -> str:
    """Normalize Bedrock model ID to ensure it has the bedrock/ prefix.

    Args:
        model_id: Model identifier, may or may not have bedrock/ prefix

    Returns:
        Model ID with bedrock/ prefix if it's a Bedrock model
    """
    # If it already has bedrock/ prefix, return as-is
    if model_id.startswith('bedrock/'):
        return model_id

    # If it looks like a Bedrock ARN, add the prefix
    if _is_bedrock_arn(model_id):
        return f'bedrock/{model_id}'

    # If it's a standard Bedrock model ID (e.g., anthropic.claude-v2)
    # Check if it looks like a Bedrock model format
    if '.' in model_id and any(provider in model_id for provider in ['anthropic', 'amazon', 'meta', 'cohere', 'ai21']):
        return f'bedrock/{model_id}'

    return model_id


def _setup_bedrock_env():
    """Set up Bedrock-specific environment variables for LiteLLM.

    Configures custom region and endpoint URL for AWS Bedrock (including GovCloud and VPC endpoints).
    Maps PatchPal's environment variables to LiteLLM's expected format.
    """
    # Set custom region (e.g., us-gov-east-1 for GovCloud)
    bedrock_region = os.getenv('AWS_BEDROCK_REGION')
    if bedrock_region and not os.getenv('AWS_REGION_NAME'):
        os.environ['AWS_REGION_NAME'] = bedrock_region

    # Set custom endpoint URL (e.g., VPC endpoint or GovCloud endpoint)
    bedrock_endpoint = os.getenv('AWS_BEDROCK_ENDPOINT')
    if bedrock_endpoint and not os.getenv('AWS_BEDROCK_RUNTIME_ENDPOINT'):
        os.environ['AWS_BEDROCK_RUNTIME_ENDPOINT'] = bedrock_endpoint


def create_agent(model_id="anthropic/claude-sonnet-4-5"):
    """Create and configure the PatchPal agent.

    Args:
        model_id: LiteLLM model identifier (default: anthropic/claude-sonnet-4-5)

                  For AWS Bedrock, you can use:
                    - Standard model ID: "anthropic.claude-sonnet-4-5-20250929-v1:0"
                    - With bedrock/ prefix: "bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0"
                    - Full ARN (auto-detected): "arn:aws-us-gov:bedrock:us-gov-east-1:012345678901:inference-profile/..."

                  Note: bedrock/ prefix is automatically added for Bedrock ARNs and model IDs

                  Configure via environment variables:
                    - AWS_ACCESS_KEY_ID: AWS access key
                    - AWS_SECRET_ACCESS_KEY: AWS secret key
                    - AWS_BEDROCK_REGION: Custom region (e.g., us-gov-east-1)
                    - AWS_BEDROCK_ENDPOINT: Custom endpoint URL (e.g., VPC endpoint)
    """
    # Normalize model ID (auto-add bedrock/ prefix if needed)
    model_id = _normalize_bedrock_model_id(model_id)

    # Set up Bedrock environment if using Bedrock models
    if model_id.startswith('bedrock/'):
        _setup_bedrock_env()

    tools = [
        tool(read_file),
        tool(list_files),
        tool(apply_patch),
        tool(run_shell),
    ]

    # Configure model with Bedrock-specific settings if needed
    model_kwargs = {}
    if model_id.startswith('bedrock/'):
        # Enable drop_params for Bedrock to handle unsupported OpenAI params
        model_kwargs['drop_params'] = True

    model = LiteLLMModel(
        model_id=model_id,
        **model_kwargs,
    )

    agent = ToolCallingAgent(
        model=model,
        tools=tools,
        instructions="""You are an expert software engineer assistant helping with code tasks in a repository.

# Available Tools

- **read_file**: Read the contents of any file in the repository
- **list_files**: List all files in the repository
- **apply_patch**: Modify a file by providing the complete new content
- **run_shell**: Run safe shell commands (dangerous commands like rm, mv, sudo are blocked)

# Core Principles

## Professional Objectivity
Prioritize technical accuracy and truthfulness over validating the user's beliefs. Focus on facts and problem-solving. Provide direct, objective technical information without unnecessary superlatives or excessive praise. Apply rigorous standards to all ideas and disagree when necessary, even if it may not be what the user wants to hear.

## Read Before Modifying
NEVER propose changes to code you haven't read. If a user asks about or wants you to modify a file, read it first. Always understand existing code before suggesting modifications.

## Avoid Over-Engineering
Only make changes that are directly requested or clearly necessary. Keep solutions simple and focused.

- Don't add features, refactor code, or make "improvements" beyond what was asked
- A bug fix doesn't need surrounding code cleaned up
- A simple feature doesn't need extra configurability
- Don't add docstrings, comments, or type annotations to code you didn't change
- Only add comments where the logic isn't self-evident
- Don't add error handling, fallbacks, or validation for scenarios that can't happen
- Trust internal code and framework guarantees
- Only validate at system boundaries (user input, external APIs)
- Don't create helpers, utilities, or abstractions for one-time operations
- Don't design for hypothetical future requirements
- Three similar lines of code is better than a premature abstraction

## Avoid Backwards-Compatibility Hacks
Avoid backwards-compatibility hacks like renaming unused variables with `_`, re-exporting types, adding `// removed` comments for removed code, etc. If something is unused, delete it completely.

## Security Awareness
Be careful not to introduce security vulnerabilities such as command injection, XSS, SQL injection, and other OWASP top 10 vulnerabilities. If you notice insecure code, immediately fix it.

# How to Approach Tasks

## For Software Engineering Tasks
The user will primarily request software engineering tasks like solving bugs, adding functionality, refactoring code, or explaining code.

1. **Understand First**: Use read_file and list_files to understand the codebase before making changes
2. **Plan Carefully**: Think through the minimal changes needed
3. **Make Focused Changes**: Use apply_patch to update files with complete new content
4. **Test When Appropriate**: Use run_shell to test changes (run tests, check builds, etc.)
5. **Explain Your Actions**: Describe what you're doing and why

## Tool Usage Guidelines

- Use list_files to explore the repository structure
- Use read_file to examine specific files before modifying them
- When using apply_patch, provide the COMPLETE new file content (not just the changed parts)
- Use run_shell for safe commands only (testing, building, git operations, etc.)
- Never use run_shell for file operations - use read_file and apply_patch instead

## Code References
When referencing specific functions or code, include the pattern `file_path:line_number` to help users navigate.

Example: "The authentication logic is in src/auth.py:45"

# Important Notes

- Stop when the task is complete - don't continue working unless asked
- If you're unsure about requirements, ask for clarification
- Focus on what needs to be done, not when (don't suggest timelines)
- Maintain consistency with the existing codebase style and patterns
""",
    )

    return agent
