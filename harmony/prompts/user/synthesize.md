Answer this question using the provided source documents.

User question: {{ user_query }}

Source documents:
{% for source in sources[:10] %}
[{{ loop.index }}] {{ source.title|default('Untitled') }} ({{ source.url|default('no URL') }})
{{ source.content|default(source.snippet|default(''))|truncate(800) }}
{% if not loop.last %}

{% endif %}
{% endfor %}

Write a clear, accurate answer that:
- Directly addresses the user's question
- Cites sources using [1], [2], etc. notation
- Only makes claims supported by the sources
- Provides sufficient detail without being verbose
- Uses natural, conversational language

Your answer:
