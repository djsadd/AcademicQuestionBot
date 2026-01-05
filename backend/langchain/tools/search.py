"""Search tool stub used by agents."""
from typing import List


async def search_documents(query: str) -> List[str]:
    """Return fake search results for the MVP skeleton."""
    return [f"Result for {query}"]
