Given this user question, generate 2-4 diverse search queries that would help find relevant information.

User question: {{ user_query }}
{% if context %}

Context: {{ context }}
{% endif %}

Output a JSON array of search queries, each targeting different aspects of the question. Include:
- A direct query matching the user's words
- A rephrased query using synonyms
- A more specific query focusing on key entities
- (Optional) A broader contextual query

Example output: ["direct query", "rephrased version", "specific query", "contextual query"]

Output only the JSON array, no additional text.
