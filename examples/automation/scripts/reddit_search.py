#!/usr/bin/env python
"""
Reddit Search Script for PatchPal

Searches Reddit for posts matching keywords and returns new posts only.
Uses PRAW (Python Reddit API Wrapper) for easy Reddit API access.

Setup:
1. Install: pip install praw
2. Create Reddit app: https://www.reddit.com/prefs/apps
3. Set environment variables:
   export REDDIT_CLIENT_ID="your-client-id"
   export REDDIT_CLIENT_SECRET="your-secret"
   export REDDIT_USER_AGENT="patchpal/1.0"
"""

import json
import os
import sys
from datetime import datetime

# Try to import praw
try:
    import praw
except ImportError:
    print(json.dumps({"error": "praw not installed", "message": "Install with: pip install praw"}))
    sys.exit(1)

# Import PatchPal cache for deduplication
try:
    from patchpal.claw.cache import add_to_set, is_duplicate
except ImportError:
    print(
        json.dumps(
            {
                "error": "patchpal[claw] not installed",
                "message": "Install with: pip install patchpal[claw]",
            }
        )
    )
    sys.exit(1)


def search_reddit(*queries, limit=25, time_filter="week"):
    """
    Search Reddit for posts matching queries.

    Args:
        *queries: Search queries (e.g., "AI agents", "Claude Code")
        limit: Max results per query
        time_filter: 'hour', 'day', 'week', 'month', 'year', 'all'

    Returns:
        List of new posts (deduplicated)
    """
    # Check configuration
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "patchpal/1.0")

    if not client_id or not client_secret:
        return {
            "error": "Reddit API not configured",
            "message": "Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables",
            "setup_url": "https://www.reddit.com/prefs/apps",
        }

    # Initialize Reddit client
    reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent)

    all_posts = []

    # Search for each query
    for query in queries:
        try:
            submissions = reddit.subreddit("all").search(
                query, sort="hot", time_filter=time_filter, limit=limit
            )

            for submission in submissions:
                # Check if we've seen this post before
                if is_duplicate("reddit_seen", submission.id):
                    continue

                # Extract relevant data
                post = {
                    "id": submission.id,
                    "title": submission.title,
                    "subreddit": str(submission.subreddit),
                    "author": str(submission.author) if submission.author else "[deleted]",
                    "score": submission.score,
                    "upvote_ratio": submission.upvote_ratio,
                    "num_comments": submission.num_comments,
                    "url": f"https://reddit.com{submission.permalink}",
                    "created_utc": submission.created_utc,
                    "created": datetime.fromtimestamp(submission.created_utc).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    "selftext": submission.selftext[:300] if submission.selftext else "",
                    "query": query,
                }

                all_posts.append(post)

                # Mark as seen
                add_to_set("reddit_seen", submission.id)

        except Exception as e:
            print(f"Error searching for '{query}': {e}", file=sys.stderr)

    # Sort by score (hotness)
    all_posts.sort(key=lambda x: x["score"], reverse=True)

    return all_posts


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: reddit_search.py <query1> [query2] [query3]")
        print("Example: reddit_search.py 'AI agents' 'coding assistants'")
        sys.exit(1)

    queries = sys.argv[1:]
    posts = search_reddit(*queries)

    # Check for errors
    if isinstance(posts, dict) and "error" in posts:
        print(json.dumps(posts, indent=2))
        sys.exit(1)

    # Format output
    result = {
        "found": len(posts),
        "queries": queries,
        "timestamp": datetime.now().isoformat(),
        "posts": posts,
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
