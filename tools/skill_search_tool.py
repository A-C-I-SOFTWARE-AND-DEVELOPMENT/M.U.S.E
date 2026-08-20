"""Skill Search Tool — Full-text search across skills.

Provides the `skill_search` tool for agents to find skills by query, tags,
or category without loading full content.

Usage:
    result = skill_search(query="llm fine-tuning")
    result = skill_search(tag="mlops")
    result = skill_search(category="data-science")
"""

import json
import logging
from typing import Optional

from tools.registry import registry, tool_error
from tools.skill_cache import (
    search_skills,
    get_skills_by_tag,
    get_skills_by_category,
    get_skill_recommendations,
    get_all_tags,
    get_all_categories,
)

logger = logging.getLogger(__name__)


def skill_search(
    query: Optional[str] = None,
    tag: Optional[str] = None,
    category: Optional[str] = None,
    name: Optional[str] = None,
    limit: int = 20,
) -> str:
    """Search for skills by various criteria.

    Args:
        query: Full-text search query (searches name, description, tags)
        tag: Filter by specific tag
        category: Filter by category (e.g., "mlops", "devops")
        name: Get recommendations for a specific skill
        limit: Maximum results to return (default 20)

    Returns:
        JSON string with matching skills and metadata
    """
    try:
        if name:
            recommendations = get_skill_recommendations(name, limit=limit)
            if not recommendations:
                return json.dumps({
                    "success": True,
                    "mode": "recommendations",
                    "for_skill": name,
                    "skills": [],
                    "count": 0,
                    "hint": f"No similar skills found for '{name}'. Try skill_search(query='...') instead.",
                }, ensure_ascii=False)

            return json.dumps({
                "success": True,
                "mode": "recommendations",
                "for_skill": name,
                "skills": recommendations,
                "count": len(recommendations),
            }, ensure_ascii=False)

        if tag:
            skills = get_skills_by_tag(tag)[:limit]
            all_tags = get_all_tags()[:20]

            if not skills:
                return json.dumps({
                    "success": True,
                    "mode": "tag",
                    "tag": tag,
                    "skills": [],
                    "count": 0,
                    "available_tags": [t for t, _ in all_tags],
                    "hint": f"No skills found with tag '{tag}'. See available_tags for valid options.",
                }, ensure_ascii=False)

            return json.dumps({
                "success": True,
                "mode": "tag",
                "tag": tag,
                "skills": skills,
                "count": len(skills),
            }, ensure_ascii=False)

        if category:
            skills = get_skills_by_category(category)[:limit]
            all_categories = get_all_categories()[:20]

            if not skills:
                return json.dumps({
                    "success": True,
                    "mode": "category",
                    "category": category,
                    "skills": [],
                    "count": 0,
                    "available_categories": [c for c, _ in all_categories],
                    "hint": f"No skills found in category '{category}'. See available_categories.",
                }, ensure_ascii=False)

            return json.dumps({
                "success": True,
                "mode": "category",
                "category": category,
                "skills": skills,
                "count": len(skills),
            }, ensure_ascii=False)

        if query:
            skills = search_skills(query, limit=limit)

            if not skills:
                return json.dumps({
                    "success": True,
                    "mode": "search",
                    "query": query,
                    "skills": [],
                    "count": 0,
                    "hint": "No matching skills found. Try broader terms or check skills_list() for all available skills.",
                }, ensure_ascii=False)

            return json.dumps({
                "success": True,
                "mode": "search",
                "query": query,
                "skills": skills,
                "count": len(skills),
            }, ensure_ascii=False)

        all_tags = get_all_tags()[:15]
        all_categories = get_all_categories()[:15]

        return json.dumps({
            "success": True,
            "mode": "browse",
            "available_tags": [{"tag": t, "count": c} for t, c in all_tags],
            "available_categories": [{"category": c, "count": n} for c, n in all_categories],
            "hint": "Use query='...' for full-text search, tag='...' to filter by tag, or category='...' to browse by category.",
        }, ensure_ascii=False)

    except Exception as e:
        logger.error("skill_search failed: %s", e, exc_info=True)
        return tool_error(str(e), success=False)


SKILL_SEARCH_SCHEMA = {
    "name": "skill_search",
    "description": (
        "Search for skills by query, tag, or category. More efficient than skills_list() "
        "when you know what you're looking for. Returns matching skills with relevance scores.\n\n"
        "Modes:\n"
        "- query='llm fine-tuning': Full-text search on name/description/tags\n"
        "- tag='mlops': Filter by tag (returns all skills with that tag)\n"
        "- category='data-science': Browse skills in a category\n"
        "- name='axolotl': Get recommendations similar to a specific skill\n"
        "- (no args): List available tags and categories for browsing\n\n"
        "Use skill_view(name) to load the full content of a matching skill."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Full-text search query (searches name, description, tags)",
            },
            "tag": {
                "type": "string",
                "description": "Filter by specific tag (e.g., 'llm', 'fine-tuning', 'mlops')",
            },
            "category": {
                "type": "string",
                "description": "Filter by category (e.g., 'mlops', 'devops', 'data-science')",
            },
            "name": {
                "type": "string",
                "description": "Get recommendations similar to this skill name",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results to return (default 20)",
                "default": 20,
            },
        },
        "required": [],
    },
}


registry.register(
    name="skill_search",
    toolset="skills",
    schema=SKILL_SEARCH_SCHEMA,
    handler=lambda args, **kw: skill_search(
        query=args.get("query"),
        tag=args.get("tag"),
        category=args.get("category"),
        name=args.get("name"),
        limit=args.get("limit", 20),
    ),
    emoji="🔍",
)
