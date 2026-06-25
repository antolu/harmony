You are generating a short status message describing an action in progress.

Describe what is happening in present tense, under 6 words, describing user-facing
intent only. Never mention tool names, function names, parameter names, or other
implementation details.

Examples:
- search_documents(query="vacation policy") -> Searching for vacation policy
- get_document_details(document_id="42") -> Reading document details
- fetch_url(url="https://example.com") -> Reading example.com

Tool: {{ function_name }}
Arguments: {{ function_args }}

Respond with only the status phrase, nothing else.
