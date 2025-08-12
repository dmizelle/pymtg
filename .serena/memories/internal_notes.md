
# Internal Notes

## Tool Usage

### Serena Tools
- **Use Serena Tools**: Always prefer using Serena tools for file operations, searches, and edits. They are designed to make tasks easier and more efficient.
- **File Operations**: Use `serena_read_file`, `serena_create_text_file`, and `serena_replace_regex` for file operations.
- **Searches**: Use `serena_find_file`, `serena_search_for_pattern`, and `serena_get_symbols_overview` for searching and understanding the codebase.
- **Symbols**: Use `serena_find_symbol` and `serena_find_referencing_symbols` for symbol-related operations.
- **Insertions**: Use `serena_insert_after_symbol` and `serena_insert_before_symbol` for inserting code.
- **Memory**: Use `serena_write_memory`, `serena_read_memory`, `serena_list_memories`, and `serena_delete_memory` for managing memories.
- **Shell Commands**: Use `serena_execute_shell_command` for executing shell commands.
- **Project Management**: Use `serena_activate_project`, `serena_switch_modes`, `serena_check_onboarding_performed`, `serena_onboarding`, `serena_think_about_collected_information`, `serena_think_about_task_adherence`, `serena_think_about_whether_you_are_done`, and `serena_prepare_for_new_conversation` for project management and onboarding.
- **Fetch**: Use `fetch_fetch` for fetching URLs and extracting their contents.

### Sequential Thinking Tools
- **Use Sequential Thinking Tools**: Use the `sequentialthinking` tool for complex reasoning, planning, and problem-solving. It helps in breaking down tasks into manageable steps and ensures thorough analysis.

## Code Style and Conventions
- **Google Style Docstrings**: Use Google style docstrings for all classes, methods, and functions.
- **Attribute Docstrings**: Add docstrings for all attributes.
- **Type Hints**: Use type hints wherever possible. Prefer `str | None` over `Optional[str]`.

## Example

Here is an example of how to use Serena tools effectively:

1. **Search for a File**:
   ```plaintext
   serena_find_file("*.py", ".")
   ```

2. **Read a File**:
   ```plaintext
   serena_read_file("path/to/file.py")
   ```

3. **Replace Content in a File**:
   ```plaintext
   serena_replace_regex("path/to/file.py", "old_pattern", "new_pattern")
   ```

4. **Insert Code After a Symbol**:
   ```plaintext
   serena_insert_after_symbol("path/to/file.py", "symbol_name", "new_code")
   ```

5. **Use Sequential Thinking**:
   ```plaintext
   sequentialthinking(thought="Analyze the problem and break it down into steps.", nextThoughtNeeded=True, thoughtNumber=1, totalThoughts=5)
   ```

## Best Practices
- **Plan Ahead**: Use the sequential thinking tool to plan and break down tasks before starting.
- **Leverage Memories**: Use Serena memories to keep track of important information and changes.
- **Efficiency**: Use the right tool for the task to ensure efficiency and accuracy.
