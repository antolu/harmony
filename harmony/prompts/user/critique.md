Evaluate this draft answer against the source documents.

User question: {{ user_query }}

Draft answer:
{{ draft }}

Source documents:
{% for source in sources %}
Source {{ loop.index }}: {{ source.title|default('Untitled') }}
{{ source.content|default(source.snippet|default('')) }}
{% if not loop.last %}

{% endif %}
{% endfor %}

Provide a JSON critique with these exact fields:
- "factual_accuracy": float (0-1) - Are claims supported by sources?
- "completeness": float (0-1) - Does it address the full question?
- "hallucination_risk": float (0-1) - Contains unsupported claims?
- "issues": list[str] - Specific problems found
- "suggestions": list[str] - Improvements to make
- "consensus_reached": bool - Is the answer good enough? (true if factual_accuracy > 0.8 and completeness > 0.7)
- "missing_information": list[str] - For each distinct gap in the draft, ONE plain natural-language sentence describing what is missing or unclear. Write sentences a researcher would read (e.g. "It is unclear which protocol pyda uses for device access."), NOT search keywords. Empty list ONLY if the answer is complete. If "consensus_reached" is false, this list MUST contain at least one entry describing why.

Output only the JSON object, no additional text.
