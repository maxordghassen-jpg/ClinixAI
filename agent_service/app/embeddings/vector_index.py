"""
Vector Index Strategy — ClinixAI Semantic Memory

CURRENT STRATEGY: Python cosine similarity
==========================================

Embeddings are stored as float[] arrays inside user_memories MongoDB documents.
Semantic search is performed entirely in Python using EmbedService.rank_by_query().

Why this works well at current scale:
  - Each user has ≤ ~100 memory documents
  - Per-user retrieval fetches ≤ 50 vectors (get_memories_with_embeddings limit)
  - Cosine similarity over 50 × 384-dim vectors: ~0.2ms in Python
  - Zero additional infrastructure required
  - Works identically on local MongoDB and MongoDB Atlas

Identity isolation:
  Every query filters by user_id FIRST, then checks embedding presence.
  Cross-user vector leakage is impossible by design — the query predicate
  always includes {"user_id": user_id} before any vector operations.


ATLAS VECTOR SEARCH UPGRADE PATH
==================================

When to migrate:
  - More than ~10,000 memory documents per user (unlikely for healthcare app)
  - OR more than ~100,000 total users where memory lookups become a bottleneck

Migration steps:
  1. Create Atlas Vector Search index in Atlas UI or via API:

     Collection: user_memories
     Index name: user_memory_vector_idx
     Field:      embedding
     Dimensions: 384  (sentence_transformer) or 1536 (openai)
     Similarity: cosine

     Index definition (Atlas API / mongocli):
     {
       "fields": [{
         "type": "vector",
         "path": "embedding",
         "numDimensions": 384,
         "similarity": "cosine"
       }, {
         "type": "filter",
         "path": "user_id"
       }]
     }

  2. Replace get_memories_with_embeddings + Python cosine in MemoryManager
     with a $vectorSearch aggregation:

     pipeline = [
       {
         "$vectorSearch": {
           "index": "user_memory_vector_idx",
           "path": "embedding",
           "queryVector": query_vec,
           "numCandidates": 100,
           "limit": top_k,
           "filter": {"user_id": {"$eq": user_id}}
         }
       },
       {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
       {"$project": {"embedding": 0, "_id": 0}}
     ]

  3. No schema changes needed — embedding field already present.
  4. No application-layer changes beyond memory_manager.load_semantic().


FUTURE SCALING: PARTITIONED NAMESPACING
=========================================

For very large deployments, consider sharding by user_id prefix:
  - user_memories collection already indexed by (user_id, key)
  - MongoDB zone sharding on user_id range enables horizontal scaling
  - Vector index stays per-shard, queries remain user-scoped

No changes to application code required for shard-aware queries —
MongoDB driver handles shard routing transparently.


PROVIDER DIMENSION COMPATIBILITY
==================================

Stored embedding dimensions must match the active provider.
If the provider is swapped, existing embeddings become invalid.

Migration procedure:
  1. Update EMBEDDING_PROVIDER in .env
  2. Run a one-time backfill job:
     - Query all user_memories with embedding field present
     - Re-embed via new provider
     - Call update_embedding() for each document
  3. Existing documents without embeddings will be re-embedded naturally
     on next MemoryExtractionService turn for that user.

No index recreation needed for Python cosine similarity.
Atlas Vector Search index must be recreated with new numDimensions.
"""
