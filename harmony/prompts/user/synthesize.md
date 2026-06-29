Answer this question using the provided source documents.

User question: {{ user_query }}

Source documents:
{% for source in sources %}
[{{ loop.index }}] {{ source.title|default('Untitled') }} ({{ source.url|default('no URL') }})
{{ source.content|default(source.snippet|default('')) }}
{% if not loop.last %}

{% endif %}
{% endfor %}

Write a clear, accurate answer that:
- Directly addresses the user's question
- Cites sources using [1], [2], etc. notation
- When a claim is supported by more than one source, cites them together in a single marker,
  e.g. [2,5] — not as separate adjacent markers like [2][5]
- Only makes claims supported by the sources
- Provides sufficient detail without being verbose
- Uses natural, conversational language

Your answer:
