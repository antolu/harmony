Evaluate this draft answer against the source documents.

User question: {{ user_query }}

Draft answer:
{{ draft }}

Source documents:
{% for source in sources[:5] %}
Source {{ loop.index }}: {{ source.title|default('Untitled') }}
{{ source.content|default(source.snippet|default(''))|truncate(500) }}
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

Output only the JSON object, no additional text.
