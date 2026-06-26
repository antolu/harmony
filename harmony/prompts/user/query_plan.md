Given this user question, produce a search plan with two parts.

User question: {{ user_query }}
{% if context %}

Context (use this to resolve what to search for — it may describe gaps to fill): {{ context }}
{% endif %}

Output a JSON object with exactly these two keys:
- "semantic_query": ONE natural-language sentence that restates the information need, optimized for vector/semantic embedding. Write it as a full, context-resolved sentence — NOT keywords.
- "keyword_variants": a list of 2-4 terse, dense keyword strings optimized for BM25/Elasticsearch retrieval. Each variant is space-separated key terms targeting a different facet of the question. NOT questions, NOT full sentences.

Example output:
{"semantic_query": "How does the pyda Python library access CERN accelerator devices?", "keyword_variants": ["pyda CERN device access", "pyda python accelerator controls", "pyda device protocol CERN"]}

Output only the JSON object, no additional text.
