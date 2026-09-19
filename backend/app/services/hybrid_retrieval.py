"""Local lexical + semantic retrieval. Ranking scores are not probabilities."""
import json
import logging
import re

from rank_bm25 import BM25Plus

from ..db.database import get_connection
from .rag_service import semantic_search

logger = logging.getLogger(__name__)
STOP_WORDS = set('a an the is are was were what how many much who which in on of for to and or me tell about please'.split())


def tokenize(text: str) -> list[str]:
    return [word for word in re.findall(r"\w+(?:-\w+)*", text.casefold()) if word not in STOP_WORDS]


def keyword_search(query: str, top_k: int = 10) -> list[dict]:
    tokens = tokenize(query)
    if not tokens or top_k <= 0:
        return []
    conn = get_connection()
    try:
        rows = conn.execute('''
            SELECT c.*, COALESCE(d.original_name, d.filename, 'Workforce DB') AS source_file
            FROM tabular_chunks c LEFT JOIN dataset_uploads d ON d.id = c.dataset_id
            ORDER BY c.id
        ''').fetchall()
    finally:
        conn.close()
    corpus = [tokenize(f"{r['chunk_text']} {r['sheet_name']} {r['source_file']}") for r in rows]
    if not rows or not any(corpus):
        return []
    scores = BM25Plus(corpus).get_scores(tokens)
    # BM25+ has a nonzero baseline; require actual token overlap.
    anchors = {token for token in tokens if any(char.isalpha() for char in token)}
    candidates = [i for i, words in enumerate(corpus) if anchors.intersection(words)]
    candidates.sort(key=lambda i: (-float(scores[i]), rows[i]['id']))
    results = []
    for i in candidates[:top_k]:
        row = rows[i]
        try:
            meta = json.loads(row['metadata_json'] or '{}')
        except (ValueError, TypeError):
            meta = {}
        results.append(dict(chunk_id=row['id'], text=row['chunk_text'],
                            sheet_name=row['sheet_name'], source_file=row['source_file'],
                            row_index=row['row_index'], metadata=meta,
                            keyword_score=float(scores[i]), relevance_score=0.0))
    return results


def hybrid_search(query: str, top_k: int = 7) -> list[dict]:
    if top_k <= 0 or not tokenize(query):
        return []
    lexical = keyword_search(query, top_k * 3)
    try:
        semantic = [item for item in semantic_search(query, top_k * 3)
                    if item['relevance_score'] >= 0.55]
    except Exception:
        logger.warning('Semantic retrieval unavailable; using keyword retrieval', exc_info=True)
        semantic = []
    # Reciprocal rank fusion avoids comparing incompatible BM25/cosine scores.
    merged, scores = {}, {}
    for method, results in [('keyword', lexical), ('semantic', semantic)]:
        for rank, item in enumerate(results, 1):
            key = item['chunk_id']
            if key not in merged:
                merged[key] = {**item, 'retrieval_methods': []}
            merged[key]['retrieval_methods'].append(method)
            scores[key] = scores.get(key, 0.0) + 1.0 / (60 + rank)
    keys = sorted(merged, key=lambda key: (-scores[key], key))[:top_k]
    return [{**merged[key], 'retrieval_score': scores[key]} for key in keys]
