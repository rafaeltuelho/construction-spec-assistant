```
┌──────────────────────────────────────────────────────────────┐
│  Fact Extraction Pipeline                                    │
│  1. Extract facts from chunks (LLM)                          │
│  2. Normalize units                                          │
│  3. Deduplicate facts                                        │
│  4. Extract manufacturer mappings ← NEW                      │
│  5. Enrich facts with manufacturers ← NEW                    │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
        Facts now have manufacturer information!
        Example: entity.manufacturer = "ThyssenKrupp or equivalent"
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  Comparison Graph (when verdict is "unclear")                │
│  1. Web search triggered                                     │
│  2. build_web_search_query() extracts manufacturer           │
│  3. Handles "or equivalent" → "ThyssenKrupp"                 │
│  4. Builds query: "ThyssenKrupp elevator [attribute] specs"  │
│  5. Tavily search with specific query                        │
└──────────────────────────────────────────────────────────────┘
```