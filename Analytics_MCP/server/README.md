# 🚀 MCP Server Explained - A Friendly Guide

## 🎯 What Does This Server Do?

This MCP server is like a **toolbox + library + template collection** that AI models can use. Instead of the AI trying to do everything itself, it can ask our server for help!

---

## 📦 Three Main Sections Explained

### 1. 🔧 **TOOLS** - Actions the AI Can Perform

**Purpose:** Tools are **functions that DO things**. When an AI needs to perform an action, it calls a tool.

**Think of it like:** A calculator, a database lookup, or sending an email.

#### Tools in Our Server:

| Tool Name | What It Does | Example |
|-----------|--------------|---------|
| `hello(name)` | Greets someone | `hello("Alice")` → `"Hello, Alice!"` |
| `square(x)` | Squares a number | `square(5)` → `25` |
| `calculate(op, a, b)` | Math operations | `calculate("add", 10, 5)` → `15` |
| `get_user_info(user_id)` | Looks up user data | `get_user_info(1)` → `{"name": "Alice", ...}` |

**When to use:** AI needs to calculate, fetch data, or perform any action.

---

### 2. 📄 **RESOURCES** - Read-Only Information

**Purpose:** Resources are **documents or data the AI can READ** (but not change). Like a library of reference materials.

**Think of it like:** Reading a company handbook, checking server stats, or viewing configuration files.

#### Resources in Our Server:

| Resource URI | What It Contains | Use Case |
|--------------|------------------|----------|
| `company://docs/welcome` | Welcome document | AI helping new employees |
| `company://policies/vacation` | Vacation policy | Answering HR questions |
| `data://statistics/summary` | Live server stats | Monitoring dashboard |
| `config://server/settings` | Server configuration | Technical support |

**When to use:** AI needs context, reference information, or documentation.

**Key Difference from Tools:**
- **Tools** = DO something (action)
- **Resources** = READ something (information)

---

### 3. 💬 **PROMPTS** - Reusable Templates

**Purpose:** Prompts are **pre-written templates** that help structure conversations with AI. Instead of writing the same instructions over and over, you use a template with placeholders.

**Think of it like:** Mad Libs, email templates, or form letters.

---

## 🌟 How PROMPTS Work - Clear Examples

### Example 1: Code Review Prompt (Simple)

**Without a prompt (manual way):**
```
You: "Hey AI, can you review this Python code: def greet(name): print(f'Hello {name}')"
AI: "Sure, what should I look for?"
You: "Check for bugs, style, performance..."
AI: "OK, let me review..."
```

**With a prompt (automated way):**
```python
# Just call the prompt:
get_prompt("code_review_prompt", {
    "language": "python",
    "code": "def greet(name): print(f'Hello {name}')"
})

# It automatically generates:
"""
# Code Review Request

## Language: python

## Code to Review:
```python
def greet(name): print(f'Hello {name}')
```

## Please Review For:
1. Correctness: Are there any bugs?
2. Performance: Can this be optimized?
3. Style: Does it follow python best practices?
4. Security: Any security concerns?
5. Maintainability: Is the code clear?

Provide specific feedback with examples.
"""
```

**Why this is useful:**
- ✅ Consistent format every time
- ✅ Don't forget what to check
- ✅ Professional structure
- ✅ Just fill in `language` and `code` - done!

---

### Example 2: Debug Helper Prompt (Step-by-Step)

**Scenario:** You get an error and need help.

**Step 1 - Call the prompt:**
```python
get_prompt("debug_helper_prompt", {
    "error_message": "TypeError: 'NoneType' object is not subscriptable",
    "context": "Trying to access data['name']"
})
```

**Step 2 - Prompt automatically generates:**
```
# Debugging Assistant

## Error/Issue:
TypeError: 'NoneType' object is not subscriptable

## Context:
Trying to access data['name']

## Help Needed:
1. Explain the error: What does this error mean?
2. Common causes: What typically causes this?
3. Solutions: Provide 2-3 potential fixes, ordered by likelihood
4. Prevention: How can I avoid this in the future?

Please provide clear, actionable advice with code examples.
```

**Step 3 - Send to AI:**
The AI receives this well-structured request and gives you organized answers!

**Without prompt:** "help me with this error TypeError..."
**With prompt:** Clear structure → better AI response!

---

### Example 3: User Story Prompt (Real-World Use)

**Scenario:** Product manager needs to create a user story.

```python
# Call the prompt
get_prompt("user_story_prompt", {
    "feature": "export data to CSV",
    "user_type": "analyst"
})

# Generates:
"""
# User Story Template

Create a detailed user story for:
**Feature**: export data to CSV
**User Type**: analyst

## Format:
As an [analyst]
I want to [export data to CSV]
So that [benefit/value]

## Include:
- Acceptance criteria (3-5 items)
- Edge cases to consider
- Dependencies on other features
- Estimated complexity (S/M/L/XL)
"""
```

**Result:** PM gets a structured template instead of blank page syndrome!

---

## 🎭 Prompts: The Full Picture

### What Makes a Prompt?

```python
@mcp.prompt()
def my_prompt(placeholder1: str, placeholder2: str) -> str:
    return f"""
    Some text with {placeholder1}
    More text with {placeholder2}
    Fixed structure that doesn't change
    """
```

**Three parts:**
1. **Fixed text** - The template structure (doesn't change)
2. **Placeholders** - Variables you fill in (changes each time)
3. **Output** - Final formatted text ready for AI

### Why Use Prompts Instead of Just Writing Text?

| Without Prompts | With Prompts |
|-----------------|--------------|
| ❌ Write same instructions repeatedly | ✅ Reuse template |
| ❌ Forget important details | ✅ Checklist built-in |
| ❌ Inconsistent format | ✅ Same format every time |
| ❌ Team uses different styles | ✅ Everyone uses same template |
| ❌ Hard to maintain | ✅ Update once, affects all uses |

---

## 🔄 Complete Workflow Example

Let's see all three sections work together:

**User asks:** "Review my Python code and tell me about vacation policy"

```python
# 1. AI uses a PROMPT to structure the code review
code_review = get_prompt("code_review_prompt", {
    "language": "python",
    "code": user_code
})
# Sends structured request to AI

# 2. AI uses a TOOL to analyze the code
result = call_tool("calculate", {"operation": "complexity", ...})
# Performs actual analysis

# 3. AI reads a RESOURCE for vacation info
policy = read_resource("company://policies/vacation")
# Gets the documentation

# 4. AI combines everything into final answer
"Your code looks good! Complexity score: 8/10
About vacation: You have 15 days available..."
```

---

## 🎯 Quick Reference

### When to Use Each:

| Need to... | Use... | Example |
|------------|--------|---------|
| **Perform action** | TOOL | Calculate, send email, save data |
| **Get information** | RESOURCE | Read docs, check config, view stats |
| **Structure AI request** | PROMPT | Code review template, debugging guide |

### Mental Model:

```
TOOLS     = Verbs  (do something)
RESOURCES = Nouns  (things to read)
PROMPTS   = Scripts (how to ask)
```

---

## 💡 Pro Tips

1. **Tools** are for when you need to change or compute something
2. **Resources** are for when you need to read reference material
3. **Prompts** are for when you want consistent, well-structured AI interactions
4. Use **prompts** to make your AI interactions more professional and reliable!

---

## 🚀 Try It Yourself!

Modify the server to add your own:
- **Tool:** `def send_email(to: str, subject: str)` - send emails
- **Resource:** `logs://today` - read today's logs  
- **Prompt:** `meeting_notes_prompt(topic, attendees)` - format meeting notes

The pattern is always the same: `@mcp.tool()`, `@mcp.resource("uri")`, or `@mcp.prompt()`!