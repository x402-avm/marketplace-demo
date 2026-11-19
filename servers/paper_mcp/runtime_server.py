import asyncio
from collections import OrderedDict
import time
import arxiv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Shared module-level arxiv client and lock for request serialization
arxiv_client = arxiv.Client(page_size=100, delay_seconds=3.0, num_retries=3)
arxiv_lock = asyncio.Lock()

# In-memory TTL cache: (query.strip().lower(), max_results) -> (papers, expires_at)
CACHE_TTL = 600.0
CACHE_MAX_ENTRIES = 256
cache: OrderedDict[tuple[str, int], tuple[list[dict], float]] = OrderedDict()


class PaperSearchRequest(BaseModel):
    query: str
    max_results: int = 3


def _fetch_from_arxiv(query: str, max_results: int) -> list[dict]:
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )
    papers = []
    for result in arxiv_client.results(search):
        papers.append({
            "title": result.title,
            "authors": [a.name for a in result.authors],
            "summary": result.summary[:300] + "...",
            "pdf_url": result.pdf_url,
        })
    return papers


@app.post("/search_papers")
async def search_papers(req: PaperSearchRequest):
    cache_key = (req.query.strip().lower(), req.max_results)
    now = time.time()

    # Check cache before acquiring lock
    if cache_key in cache:
        papers, expires_at = cache[cache_key]
        if now < expires_at:
            cache.move_to_end(cache_key)
            return {"papers": papers}
        else:
            cache.pop(cache_key, None)

    # Acquire lock to serialize arXiv requests and prevent transient rate-limiting
    async with arxiv_lock:
        # Check cache again in case another coroutine fetched it while waiting
        now = time.time()
        if cache_key in cache:
            papers, expires_at = cache[cache_key]
            if now < expires_at:
                cache.move_to_end(cache_key)
                return {"papers": papers}
            else:
                cache.pop(cache_key, None)

        try:
            papers = await asyncio.to_thread(_fetch_from_arxiv, req.query, req.max_results)
        except Exception as e:
            short_reason = str(e)
            if len(short_reason) > 200:
                short_reason = short_reason[:197] + "..."
            raise HTTPException(
                status_code=503,
                detail=f"arXiv temporarily unavailable: {short_reason}",
            )

        # Store in cache
        if len(cache) >= CACHE_MAX_ENTRIES and cache_key not in cache:
            cache.popitem(last=False)
        cache[cache_key] = (papers, now + CACHE_TTL)

        return {"papers": papers}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8125)
