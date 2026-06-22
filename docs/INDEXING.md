# Elasticsearch Indexing Guide

## 1. Start Elasticsearch with Docker

```bash
docker-compose up -d
```

This starts:
- Elasticsearch on http://localhost:9200
- Kibana on http://localhost:5601

Wait ~30 seconds for Elasticsearch to be ready:
```bash
curl http://localhost:9200
```

## 2. Install dependencies

Elasticsearch support is a core dependency — no separate extra needed:

```bash
pip install -e .
```

## 3. Index the crawled data

```bash
harmony-index \
  --data_dir output \
  --es_host http://localhost:9200 \
  --index_base_name harmony \
  --batch_size 100
```

This creates one index per detected language (e.g. `harmony-en`, `harmony-fr`) — see [ES_MIGRATION.md](ES_MIGRATION.md) for the per-language index model.

## 4. Verify indexing

```bash
# Check document count
curl http://localhost:9200/harmony-en/_count

# Search example
curl -X GET "http://localhost:9200/harmony-en/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match": {
      "content": "CERN"
    }
  },
  "size": 5
}'
```

## 5. Use Kibana for visualization

Open http://localhost:5601 in your browser to explore the data with Kibana's UI.

## Stop Elasticsearch

```bash
docker-compose down
```

## Index Structure

Each document contains:
- `url` - Page URL
- `title` - Page title
- `content` - Extracted text content
- `domain` - Domain name
- `path` - URL path
- `depth` - Crawl depth
- `crawled_at` - Timestamp
- `file_path` - Path to HTML file
