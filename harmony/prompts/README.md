# Harmony Prompt Templates

This directory contains all system and user prompts used by Harmony's LLM agents.

## Directory Structure

- `system/` - System prompts that define agent behavior
- `user/` - User prompts for specific tasks

## Template Format

Templates use Jinja2 syntax with markdown formatting.

### Built-in Variables

All templates automatically receive:
- `current_date` - Today's date (YYYY-MM-DD)
- `current_time` - Current time (HH:MM:SS)
- `current_datetime` - Full timestamp
- `day_of_week` - Day name (Monday, Tuesday, etc.)
- `iso_timestamp` - ISO 8601 timestamp

### Custom Variables

Each template receives context-specific variables:
- `user_query` - The user's question
- `sources` - List of source documents
- `tools` - Available tools (in chat system prompt)
- `critique` - Critique feedback (in refinement)
- etc.

## Editing Prompts

1. Prompts are markdown files with Jinja2 templating
2. Use `{{ variable }}` for variable substitution
3. Use `{% for %}`, `{% if %}` for logic
4. In dev mode, changes reload automatically
5. In production, restart API to pick up changes

## Versioning Prompts

To version a prompt:
1. Save current as `chat_v1.md`
2. Create new version `chat_v2.md`
3. Update code to use `chat_v2.md`
4. A/B test if needed
