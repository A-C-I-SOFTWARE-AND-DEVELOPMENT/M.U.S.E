"""Skills REST API endpoints.

Provides HTTP endpoints for browsing, searching, and managing skills:
- GET  /api/skills              — List all skills
- GET  /api/skills/search       — Search skills by query/tag/category
- GET  /api/skills/tags         — List all tags with counts
- GET  /api/skills/categories   — List all categories with counts
- GET  /api/skills/{name}       — Get skill details
- GET  /api/skills/{name}/recommendations — Get similar skills
- POST /api/skills/{name}/toggle — Enable/disable a skill
- GET  /api/curator/status      — Get curator status

These endpoints are mounted at /api/skills/* by the main API server.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    web = None  # type: ignore


def create_skills_routes() -> List:
    """Create aiohttp routes for skills API. Returns empty list if aiohttp unavailable."""
    if not AIOHTTP_AVAILABLE:
        return []

    routes = [
        web.get("/api/skills", handle_list_skills),
        web.get("/api/skills/search", handle_search_skills),
        web.get("/api/skills/tags", handle_list_tags),
        web.get("/api/skills/categories", handle_list_categories),
        web.get("/api/skills/{name}", handle_get_skill),
        web.get("/api/skills/{name}/recommendations", handle_get_recommendations),
        web.post("/api/skills/{name}/toggle", handle_toggle_skill),
        web.get("/api/curator/status", handle_curator_status),
    ]
    return routes


async def handle_list_skills(request: "web.Request") -> "web.Response":
    """GET /api/skills — List all skills with optional category filter."""
    try:
        category = request.query.get("category")

        from tools.skill_cache import get_cached_skills, get_skills_by_category

        if category:
            skills = get_skills_by_category(category)
        else:
            skills = get_cached_skills()

        return web.json_response({
            "success": True,
            "skills": skills,
            "count": len(skills),
        })

    except Exception as e:
        logger.error("Failed to list skills: %s", e, exc_info=True)
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500,
        )


async def handle_search_skills(request: "web.Request") -> "web.Response":
    """GET /api/skills/search — Search skills by query, tag, or category."""
    try:
        query = request.query.get("q") or request.query.get("query")
        tag = request.query.get("tag")
        category = request.query.get("category")
        limit = int(request.query.get("limit", "20"))

        from tools.skill_cache import (
            search_skills,
            get_skills_by_tag,
            get_skills_by_category,
        )

        if query:
            skills = search_skills(query, limit=limit)
            mode = "search"
        elif tag:
            skills = get_skills_by_tag(tag)[:limit]
            mode = "tag"
        elif category:
            skills = get_skills_by_category(category)[:limit]
            mode = "category"
        else:
            skills = []
            mode = "empty"

        return web.json_response({
            "success": True,
            "mode": mode,
            "query": query,
            "tag": tag,
            "category": category,
            "skills": skills,
            "count": len(skills),
        })

    except Exception as e:
        logger.error("Failed to search skills: %s", e, exc_info=True)
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500,
        )


async def handle_list_tags(request: "web.Request") -> "web.Response":
    """GET /api/skills/tags — List all tags with usage counts."""
    try:
        from tools.skill_cache import get_all_tags

        tags = get_all_tags()

        return web.json_response({
            "success": True,
            "tags": [{"tag": t, "count": c} for t, c in tags],
            "count": len(tags),
        })

    except Exception as e:
        logger.error("Failed to list tags: %s", e, exc_info=True)
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500,
        )


async def handle_list_categories(request: "web.Request") -> "web.Response":
    """GET /api/skills/categories — List all categories with skill counts."""
    try:
        from tools.skill_cache import get_all_categories

        categories = get_all_categories()

        return web.json_response({
            "success": True,
            "categories": [{"category": c, "count": n} for c, n in categories],
            "count": len(categories),
        })

    except Exception as e:
        logger.error("Failed to list categories: %s", e, exc_info=True)
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500,
        )


async def handle_get_skill(request: "web.Request") -> "web.Response":
    """GET /api/skills/{name} — Get full skill content."""
    try:
        name = request.match_info["name"]
        file_path = request.query.get("file")

        from tools.skills_tool import skill_view

        result = json.loads(skill_view(name, file_path=file_path))

        if not result.get("success"):
            return web.json_response(result, status=404)

        return web.json_response(result)

    except Exception as e:
        logger.error("Failed to get skill %s: %s", request.match_info.get("name"), e, exc_info=True)
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500,
        )


async def handle_get_recommendations(request: "web.Request") -> "web.Response":
    """GET /api/skills/{name}/recommendations — Get similar skills."""
    try:
        name = request.match_info["name"]
        limit = int(request.query.get("limit", "5"))

        from tools.skill_cache import get_skill_recommendations

        recommendations = get_skill_recommendations(name, limit=limit)

        return web.json_response({
            "success": True,
            "for_skill": name,
            "recommendations": recommendations,
            "count": len(recommendations),
        })

    except Exception as e:
        logger.error("Failed to get recommendations for %s: %s", request.match_info.get("name"), e, exc_info=True)
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500,
        )


async def handle_toggle_skill(request: "web.Request") -> "web.Response":
    """POST /api/skills/{name}/toggle — Enable or disable a skill."""
    try:
        name = request.match_info["name"]

        try:
            body = await request.json()
        except Exception:
            body = {}

        enabled = body.get("enabled", True)

        from hermes_cli.config import load_config, save_config

        config = load_config()
        skills_cfg = config.setdefault("skills", {})
        disabled = set(skills_cfg.get("disabled", []))

        if enabled:
            disabled.discard(name)
        else:
            disabled.add(name)

        skills_cfg["disabled"] = sorted(disabled)
        save_config(config)

        from tools.skill_cache import invalidate_cache
        invalidate_cache()

        return web.json_response({
            "success": True,
            "name": name,
            "enabled": enabled,
            "message": f"Skill '{name}' {'enabled' if enabled else 'disabled'}.",
        })

    except Exception as e:
        logger.error("Failed to toggle skill %s: %s", request.match_info.get("name"), e, exc_info=True)
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500,
        )


async def handle_curator_status(request: "web.Request") -> "web.Response":
    """GET /api/curator/status — Get curator status and recent activity."""
    try:
        from agent.curator import (
            load_state,
            is_enabled,
            is_paused,
            get_interval_hours,
            get_stale_after_days,
            get_archive_after_days,
        )
        from tools import skill_usage

        state = load_state()

        agent_created = []
        try:
            agent_created = skill_usage.agent_created_report()
        except Exception:
            pass

        active_count = sum(1 for s in agent_created if s.get("state") == "active")
        stale_count = sum(1 for s in agent_created if s.get("state") == "stale")
        archived_count = sum(1 for s in agent_created if s.get("state") == "archived")
        pinned_count = sum(1 for s in agent_created if s.get("pinned"))

        return web.json_response({
            "success": True,
            "enabled": is_enabled(),
            "paused": is_paused(),
            "interval_hours": get_interval_hours(),
            "stale_after_days": get_stale_after_days(),
            "archive_after_days": get_archive_after_days(),
            "last_run_at": state.get("last_run_at"),
            "last_run_summary": state.get("last_run_summary"),
            "last_run_duration_seconds": state.get("last_run_duration_seconds"),
            "last_report_path": state.get("last_report_path"),
            "run_count": state.get("run_count", 0),
            "agent_created_skills": {
                "total": len(agent_created),
                "active": active_count,
                "stale": stale_count,
                "archived": archived_count,
                "pinned": pinned_count,
            },
        })

    except Exception as e:
        logger.error("Failed to get curator status: %s", e, exc_info=True)
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500,
        )


def get_skills_api_spec() -> Dict[str, Any]:
    """Return OpenAPI spec fragment for skills endpoints."""
    return {
        "/api/skills": {
            "get": {
                "summary": "List all skills",
                "parameters": [
                    {"name": "category", "in": "query", "schema": {"type": "string"}, "description": "Filter by category"},
                ],
                "responses": {"200": {"description": "List of skills"}},
            }
        },
        "/api/skills/search": {
            "get": {
                "summary": "Search skills",
                "parameters": [
                    {"name": "q", "in": "query", "schema": {"type": "string"}, "description": "Search query"},
                    {"name": "tag", "in": "query", "schema": {"type": "string"}, "description": "Filter by tag"},
                    {"name": "category", "in": "query", "schema": {"type": "string"}, "description": "Filter by category"},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 20}, "description": "Max results"},
                ],
                "responses": {"200": {"description": "Search results"}},
            }
        },
        "/api/skills/tags": {
            "get": {
                "summary": "List all tags",
                "responses": {"200": {"description": "List of tags with counts"}},
            }
        },
        "/api/skills/categories": {
            "get": {
                "summary": "List all categories",
                "responses": {"200": {"description": "List of categories with counts"}},
            }
        },
        "/api/skills/{name}": {
            "get": {
                "summary": "Get skill details",
                "parameters": [
                    {"name": "name", "in": "path", "required": True, "schema": {"type": "string"}},
                    {"name": "file", "in": "query", "schema": {"type": "string"}, "description": "Optional linked file path"},
                ],
                "responses": {"200": {"description": "Skill content"}, "404": {"description": "Skill not found"}},
            }
        },
        "/api/skills/{name}/recommendations": {
            "get": {
                "summary": "Get similar skills",
                "parameters": [
                    {"name": "name", "in": "path", "required": True, "schema": {"type": "string"}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 5}},
                ],
                "responses": {"200": {"description": "Recommended skills"}},
            }
        },
        "/api/skills/{name}/toggle": {
            "post": {
                "summary": "Enable or disable a skill",
                "parameters": [
                    {"name": "name", "in": "path", "required": True, "schema": {"type": "string"}},
                ],
                "requestBody": {
                    "content": {"application/json": {"schema": {"type": "object", "properties": {"enabled": {"type": "boolean"}}}}}
                },
                "responses": {"200": {"description": "Toggle result"}},
            }
        },
        "/api/curator/status": {
            "get": {
                "summary": "Get curator status",
                "responses": {"200": {"description": "Curator status and stats"}},
            }
        },
    }
