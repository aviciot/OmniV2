# prompts/basic_prompts.py
"""Simple example prompts demonstrating MCP prompt functionality."""

from mcp_app import mcp


@mcp.prompt(description="Generate a code review checklist for any programming language")
def code_review_checklist(language: str = "Python", focus_area: str = "general") -> str:
    """
    Creates a structured code review checklist.
    
    Args:
        language: Programming language (default: "Python")
        focus_area: Specific focus like "security", "performance", "readability" (default: "general")
        
    Returns:
        Formatted prompt string for code review
    """
    return f"""# Code Review Checklist for {language}

## Focus Area: {focus_area.title()}

Please review the code with attention to:

### 1. Code Quality
- [ ] Is the code readable and well-structured?
- [ ] Are variable and function names descriptive?
- [ ] Is the code properly formatted according to {language} standards?

### 2. Functionality
- [ ] Does the code accomplish its intended purpose?
- [ ] Are edge cases handled?
- [ ] Is error handling appropriate?

### 3. {focus_area.title()} Considerations
- [ ] Are there any {focus_area}-related concerns?
- [ ] Could the code be improved in terms of {focus_area}?

### 4. Best Practices
- [ ] Does it follow {language} best practices?
- [ ] Is the code maintainable?
- [ ] Are there adequate comments where needed?

Please provide specific feedback for each item that needs attention.
"""


@mcp.prompt(description="Create a debugging strategy for troubleshooting issues")
def debug_strategy(issue_description: str, context: str = "") -> str:
    """
    Generates a systematic debugging approach.
    
    Args:
        issue_description: Description of the problem
        context: Additional context about the system (optional)
        
    Returns:
        Formatted debugging strategy prompt
    """
    context_section = f"\n## Context\n{context}\n" if context else ""
    
    return f"""# Debugging Strategy

## Issue
{issue_description}
{context_section}
## Systematic Approach

### Step 1: Reproduce the Issue
- What are the exact steps to reproduce?
- Can you consistently reproduce it?
- What is the expected vs actual behavior?

### Step 2: Gather Information
- What error messages or logs are available?
- When did this issue start?
- What changed recently?

### Step 3: Isolate the Problem
- Can you narrow down where the issue occurs?
- Is it environment-specific?
- What components are involved?

### Step 4: Form Hypotheses
- What could be causing this issue?
- List possible root causes from most to least likely

### Step 5: Test & Verify
- Test each hypothesis systematically
- Verify the fix works and doesn't break anything else

Please work through this strategy and provide your findings.
"""


@mcp.prompt(description="Generate an explanation template for technical concepts")
def explain_concept(concept: str, audience: str = "beginner") -> str:
    """
    Creates a structured explanation framework.
    
    Args:
        concept: The technical concept to explain
        audience: Target audience level: "beginner", "intermediate", "advanced"
        
    Returns:
        Formatted explanation prompt
    """
    return f"""# Explain: {concept}

## Audience Level: {audience.title()}

Please provide a clear explanation of "{concept}" structured as follows:

### 1. Simple Definition
Explain {concept} in one or two sentences that a {audience} can understand.

### 2. Why It Matters
Why is {concept} important? What problems does it solve?

### 3. How It Works
Break down the key mechanics or principles. Use analogies if helpful for a {audience} audience.

### 4. Real-World Example
Provide a concrete, practical example showing {concept} in action.

### 5. Common Pitfalls
What mistakes do people commonly make when working with {concept}?

### 6. Next Steps
What should someone learn next after understanding {concept}?

Keep the language appropriate for a {audience} level audience.
"""
