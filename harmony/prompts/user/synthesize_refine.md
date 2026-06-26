Improve this draft answer based on the critique feedback.

User question: {{ user_query }}

Previous draft:
{{ previous_draft }}

Critique:
Issues identified:
{% for issue in critique.issues|default([]) %}
- {{ issue }}
{% endfor %}

Suggestions for improvement:
{% for suggestion in critique.suggestions|default([]) %}
- {{ suggestion }}
{% endfor %}

Factual accuracy: {{ (critique.factual_accuracy|default(0.5) * 100)|round(0) }}%
Completeness: {{ (critique.completeness|default(0.5) * 100)|round(0) }}%
Hallucination risk: {{ (critique.hallucination_risk|default(0.5) * 100)|round(0) }}%

Source documents:
{% for source in sources[:10] %}
[{{ loop.index }}] {{ source.title|default('Untitled') }} ({{ source.url|default('no URL') }})
{{ source.content|default(source.snippet|default(''))|truncate(800) }}
{% if not loop.last %}

{% endif %}
{% endfor %}

Write an improved answer that:
- Addresses all issues raised in the critique
- Incorporates the suggestions
- Maintains or improves factual accuracy
- Cites sources appropriately using [1], [2], etc.
- When a claim is supported by more than one source, cites them together in a single marker,
  e.g. [2,5] — not as separate adjacent markers like [2][5]
- Is grounded only in the provided documents

Your improved answer:
