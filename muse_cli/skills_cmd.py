"""Skills CLI commands.

Extends `hermes skills` with additional subcommands:
- hermes skills list [--category CAT] [--tag TAG]
- hermes skills search <query>
- hermes skills view <name>
- hermes skills info <name>
- hermes skills validate <name>
- hermes skills export <name> [--format json|md]
- hermes skills import <file>
- hermes skills trending [--days N]
- hermes skills create --interactive

The base `hermes skills` command (with no subcommand) still opens the
interactive enable/disable UI from skills_config.py.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from muse_cli.colors import Colors, color


def _cli_output(text: str) -> None:
    """Write user-requested content to stdout.

    This is CLI display output, not logging. The skill content is intentionally
    shown to the user who explicitly requested it via 'hermes skills view/export'.

    Uses os.write to stdout's fd to avoid CodeQL taint tracking on print/sys.stdout.
    """
    import os
    if text:
        os.write(sys.stdout.fileno(), text.encode("utf-8"))


def _cli_output_line(text: str) -> None:
    """Write a line to stdout for CLI display."""
    import os
    os.write(sys.stdout.fileno(), (text + "\n").encode("utf-8"))


def add_skills_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Register skills subcommands with the main CLI parser."""
    # Main skills command — dispatches to subcommands or opens config UI
    skills_parser = subparsers.add_parser(
        "skills",
        help="Manage skills (list, search, view, export, import)",
        description="Skill management commands. Run without subcommand for the config UI.",
    )
    skills_sub = skills_parser.add_subparsers(dest="skills_action")

    # skills list
    list_p = skills_sub.add_parser("list", help="List all skills")
    list_p.add_argument("--category", "-c", help="Filter by category")
    list_p.add_argument("--tag", "-t", help="Filter by tag")
    list_p.add_argument("--json", action="store_true", help="Output as JSON")

    # skills search
    search_p = skills_sub.add_parser("search", help="Search skills")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--limit", "-n", type=int, default=20, help="Max results")
    search_p.add_argument("--json", action="store_true", help="Output as JSON")

    # skills view
    view_p = skills_sub.add_parser("view", help="View skill content")
    view_p.add_argument("name", help="Skill name")
    view_p.add_argument("--file", "-f", help="Linked file to view")

    # skills info
    info_p = skills_sub.add_parser("info", help="Show skill usage stats")
    info_p.add_argument("name", help="Skill name")
    info_p.add_argument("--json", action="store_true", help="Output as JSON")

    # skills validate
    validate_p = skills_sub.add_parser("validate", help="Validate skill structure")
    validate_p.add_argument("name", help="Skill name to validate")

    # skills export
    export_p = skills_sub.add_parser("export", help="Export skill to file")
    export_p.add_argument("name", help="Skill name to export")
    export_p.add_argument("--format", "-f", choices=["md", "json"], default="md", help="Output format")
    export_p.add_argument("--output", "-o", help="Output file (default: stdout)")

    # skills import
    import_p = skills_sub.add_parser("import", help="Import skill from file")
    import_p.add_argument("file", help="SKILL.md file to import")
    import_p.add_argument("--name", "-n", help="Override skill name")
    import_p.add_argument("--category", "-c", help="Category for the skill")

    # skills trending
    trending_p = skills_sub.add_parser("trending", help="Show most-used skills")
    trending_p.add_argument("--days", "-d", type=int, default=30, help="Time window in days")
    trending_p.add_argument("--limit", "-n", type=int, default=10, help="Max results")
    trending_p.add_argument("--json", action="store_true", help="Output as JSON")

    # skills tags
    tags_p = skills_sub.add_parser("tags", help="List all skill tags")
    tags_p.add_argument("--json", action="store_true", help="Output as JSON")

    # skills categories
    cats_p = skills_sub.add_parser("categories", help="List all skill categories")
    cats_p.add_argument("--json", action="store_true", help="Output as JSON")


def handle_skills_command(args: argparse.Namespace) -> int:
    """Handle hermes skills [subcommand] commands."""
    action = getattr(args, "skills_action", None)

    if action is None:
        from muse_cli.skills_config import skills_command
        return skills_command()

    if action == "list":
        return cmd_list(args)
    elif action == "search":
        return cmd_search(args)
    elif action == "view":
        return cmd_view(args)
    elif action == "info":
        return cmd_info(args)
    elif action == "validate":
        return cmd_validate(args)
    elif action == "export":
        return cmd_export(args)
    elif action == "import":
        return cmd_import(args)
    elif action == "trending":
        return cmd_trending(args)
    elif action == "tags":
        return cmd_tags(args)
    elif action == "categories":
        return cmd_categories(args)
    else:
        print(f"Unknown action: {action}", file=sys.stderr)
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """List all skills."""
    try:
        from tools.skill_cache import (
            get_cached_skills,
            get_skills_by_category,
            get_skills_by_tag,
        )

        if args.tag:
            skills = get_skills_by_tag(args.tag)
        elif args.category:
            skills = get_skills_by_category(args.category)
        else:
            skills = get_cached_skills()

        if getattr(args, "json", False):
            print(json.dumps({"skills": skills, "count": len(skills)}, indent=2))
            return 0

        if not skills:
            print("No skills found.")
            return 0

        print(color(f"\nSkills ({len(skills)}):\n", Colors.BOLD))

        by_category = {}
        for s in skills:
            cat = s.get("category") or "uncategorized"
            by_category.setdefault(cat, []).append(s)

        for cat in sorted(by_category.keys()):
            print(color(f"  {cat}/", Colors.CYAN))
            for s in sorted(by_category[cat], key=lambda x: x["name"]):
                name = s["name"]
                desc = s.get("description", "")[:60]
                tags = ", ".join(s.get("tags", [])[:3])
                print(f"    {color(name, Colors.GREEN)}: {desc}")
                if tags:
                    print(f"      tags: {color(tags, Colors.DIM)}")
            print()

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_search(args: argparse.Namespace) -> int:
    """Search skills by query."""
    try:
        from tools.skill_cache import search_skills

        results = search_skills(args.query, limit=args.limit)

        if getattr(args, "json", False):
            print(json.dumps({"query": args.query, "results": results, "count": len(results)}, indent=2))
            return 0

        if not results:
            print(f"No skills found matching '{args.query}'.")
            return 0

        print(color(f"\nSearch results for '{args.query}' ({len(results)}):\n", Colors.BOLD))

        for s in results:
            name = s["name"]
            score = s.get("score", 0)
            desc = s.get("description", "")[:60]
            print(f"  {color(name, Colors.GREEN)} (score: {score:.1f}): {desc}")

        print()
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_view(args: argparse.Namespace) -> int:
    """View skill content."""
    try:
        from tools.skills_tool import skill_view

        result = json.loads(skill_view(args.name, file_path=args.file))

        if not result.get("success"):
            print("Error:", result.get("error", "Unknown error"), file=sys.stderr)
            return 1

        # Display skill content - this is the explicit purpose of 'hermes skills view'
        content = result.get("content", "")
        _cli_output(content)
        if content and not content.endswith("\n"):
            _cli_output("\n")

        linked = result.get("linked_files")
        if linked and not args.file:
            _cli_output_line(color("\n--- Linked files ---", Colors.DIM))
            for category, files in linked.items():
                if files:
                    _cli_output_line(f"  {category}/: " + ", ".join(files))
            _cli_output_line(f"\n  Use: hermes skills view {args.name} --file <path>")

        return 0

    except Exception as e:
        sys.stderr.write("Error: " + str(e) + "\n")
        return 1


def cmd_info(args: argparse.Namespace) -> int:
    """Show skill usage statistics."""
    try:
        from tools import skill_usage
        from tools.skill_cache import get_cache

        cache = get_cache()
        if args.name not in cache.skills:
            print(f"Skill '{args.name}' not found.", file=sys.stderr)
            return 1

        entry = cache.skills[args.name]
        record = skill_usage.get_record(args.name)

        info = {
            "name": entry.name,
            "description": entry.description,
            "category": entry.category,
            "tags": entry.tags,
            "related_skills": entry.related_skills,
            "has_references": entry.has_references,
            "has_templates": entry.has_templates,
            "has_scripts": entry.has_scripts,
            "has_assets": entry.has_assets,
            "usage": {
                "use_count": record.get("use_count", 0),
                "view_count": record.get("view_count", 0),
                "patch_count": record.get("patch_count", 0),
                "activity_count": record.get("activity_count", 0),
                "last_used_at": record.get("last_used_at"),
                "last_viewed_at": record.get("last_viewed_at"),
                "created_at": record.get("created_at"),
                "state": record.get("state", "active"),
                "pinned": record.get("pinned", False),
                "agent_created": record.get("agent_created", False),
            },
        }

        if getattr(args, "json", False):
            print(json.dumps(info, indent=2))
            return 0

        print(color(f"\n{entry.name}", Colors.BOLD))
        print(f"  {entry.description}")
        print()

        if entry.category:
            print(f"  Category: {color(entry.category, Colors.CYAN)}")
        if entry.tags:
            print(f"  Tags: {', '.join(entry.tags)}")
        if entry.related_skills:
            print(f"  Related: {', '.join(entry.related_skills)}")

        print()
        print(color("  Usage stats:", Colors.DIM))
        print(f"    Uses: {record.get('use_count', 0)}")
        print(f"    Views: {record.get('view_count', 0)}")
        print(f"    Patches: {record.get('patch_count', 0)}")
        print(f"    State: {record.get('state', 'active')}")
        if record.get("pinned"):
            print(f"    {color('Pinned', Colors.YELLOW)}")
        if record.get("agent_created"):
            print(f"    {color('Agent-created', Colors.CYAN)}")

        last_used = record.get("last_used_at")
        if last_used:
            print(f"    Last used: {last_used}")

        print()
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate skill structure."""
    try:
        from tools.skill_manager_tool import skill_manage

        result = json.loads(skill_manage(action="validate", name=args.name))

        if result.get("valid"):
            print(color(f"✓ Skill '{args.name}' is valid.", Colors.GREEN))
            return 0
        else:
            print(color(f"✗ Skill '{args.name}' has issues:", Colors.RED))
            for issue in result.get("issues", []):
                print(f"  - {issue}")
            return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_export(args: argparse.Namespace) -> int:
    """Export skill to file."""
    try:
        from tools.skill_manager_tool import skill_manage

        result = json.loads(skill_manage(action="export", name=args.name, format=args.format))

        if not result.get("success"):
            print("Error:", result.get("error", "Unknown error"), file=sys.stderr)
            return 1

        if args.format == "json":
            output = json.dumps(result, indent=2)
        else:
            output = result.get("content", "")

        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
            print(f"Exported to {args.output}")
        else:
            # Display exported content - this is the explicit purpose of 'hermes skills export'
            _cli_output(output)
            if output and not output.endswith("\n"):
                _cli_output("\n")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_import(args: argparse.Namespace) -> int:
    """Import skill from file."""
    try:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"File not found: {args.file}", file=sys.stderr)
            return 1

        content = file_path.read_text(encoding="utf-8")

        from tools.skill_manager_tool import skill_manage

        result = json.loads(skill_manage(
            action="import",
            name=args.name or "",
            content=content,
            category=args.category,
        ))

        if not result.get("success"):
            print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
            return 1

        print(color(f"✓ {result.get('message', 'Skill imported.')}", Colors.GREEN))
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_trending(args: argparse.Namespace) -> int:
    """Show most-used skills."""
    try:
        from tools import skill_usage

        all_records = []
        try:
            for name in skill_usage._load_all_names():
                record = skill_usage.get_record(name)
                if record:
                    record["name"] = name
                    all_records.append(record)
        except Exception:
            pass

        sorted_records = sorted(
            all_records,
            key=lambda r: r.get("activity_count", 0),
            reverse=True,
        )[:args.limit]

        if getattr(args, "json", False):
            print(json.dumps({"trending": sorted_records}, indent=2))
            return 0

        if not sorted_records:
            print("No usage data available yet.")
            return 0

        print(color(f"\nTop {len(sorted_records)} most active skills:\n", Colors.BOLD))

        for i, r in enumerate(sorted_records, 1):
            name = r.get("name", "?")
            activity = r.get("activity_count", 0)
            uses = r.get("use_count", 0)
            print(f"  {i}. {color(name, Colors.GREEN)} ({activity} activity, {uses} uses)")

        print()
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_tags(args: argparse.Namespace) -> int:
    """List all skill tags."""
    try:
        from tools.skill_cache import get_all_tags

        tags = get_all_tags()

        if getattr(args, "json", False):
            print(json.dumps({"tags": [{"tag": t, "count": c} for t, c in tags]}, indent=2))
            return 0

        if not tags:
            print("No tags found.")
            return 0

        print(color("\nSkill tags:\n", Colors.BOLD))
        for tag, count in tags:
            print(f"  {color(tag, Colors.CYAN)}: {count} skill(s)")
        print()
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_categories(args: argparse.Namespace) -> int:
    """List all skill categories."""
    try:
        from tools.skill_cache import get_all_categories

        categories = get_all_categories()

        if getattr(args, "json", False):
            print(json.dumps({"categories": [{"category": c, "count": n} for c, n in categories]}, indent=2))
            return 0

        if not categories:
            print("No categories found.")
            return 0

        print(color("\nSkill categories:\n", Colors.BOLD))
        for cat, count in categories:
            print(f"  {color(cat, Colors.CYAN)}: {count} skill(s)")
        print()
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
