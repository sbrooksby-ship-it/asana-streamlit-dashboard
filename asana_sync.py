"""Fetch tasks from one Asana project and upsert them into PostgreSQL."""

import json
import os
import re
from datetime import datetime
from pathlib import Path

import psycopg2
import requests
from dotenv import load_dotenv

ASANA_API_URL = "https://app.asana.com/api/1.0"
OPT_FIELDS = ",".join(
    [
        "gid",
        "name",
        "notes",
        "permalink_url",
        "created_at",
        "modified_at",
        "completed",
        "due_on",
        "due_at",
        "assignee.gid",
        "assignee.name",
        "projects.gid",
        "projects.name",
        "tags.gid",
        "tags.name",
        "memberships.section.gid",
        "memberships.section.name",
        "memberships.project.gid",
    ]
)


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be set")
    return value


def fetch_tasks(token: str, project_gid: str) -> list[dict]:
    tasks = []
    url = f"{ASANA_API_URL}/projects/{project_gid}/tasks"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"limit": 100, "opt_fields": OPT_FIELDS}

    while url:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        tasks.extend(payload.get("data", []))
        next_page = payload.get("next_page") or {}
        url = next_page.get("uri")
        params = None

    return tasks


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def task_category(task: dict) -> str:
    notes = task.get("notes", "")
    request_type = re.search(
        r"(?im)(?:type\s+of\s+request|request\s+type)\s*:\s*([^\r\n\*_]+)",
        notes,
    )
    category = "Uncategorized"
    if request_type and request_type.group(1).strip():
        category = " ".join(request_type.group(1).split()).title()
    else:
        tags = task.get("tags") or []
        if tags:
            category = (tags[0].get("name") or "Uncategorized").strip().title()
        else:
            match = re.match(r"^\[([^\]]+)\]", task.get("name", ""))
            category = match.group(1).strip().title() if match else "Uncategorized"

    if "Continuous Improvement" in category:
        return "Continuous Improvement"

    return category


def extract_section(task: dict, project_gid: str) -> tuple[str | None, str]:
    for membership in task.get("memberships", []):
        proj = membership.get("project") or {}
        if proj.get("gid") == project_gid:
            sec = membership.get("section") or {}
            return sec.get("gid"), sec.get("name") or "No Section"
    return None, "No Section"


def sync_tasks(database_url: str, tasks: list[dict], project_gid: str) -> None:
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    
    upsert = """
        INSERT INTO tasks (
            gid, name, description, category, asana_url, active, removed_at, last_seen_at, created_at, modified_at, completed, due_on, due_at,
            assignee_gid, assignee_name, projects, tags, raw, synced_at, section_gid, section_name
        ) VALUES (
            %(gid)s, %(name)s, %(description)s, %(category)s, %(asana_url)s, TRUE, NULL, NOW(), %(created_at)s, %(modified_at)s, %(completed)s,
            %(due_on)s, %(due_at)s, %(assignee_gid)s, %(assignee_name)s,
            %(projects)s::jsonb, %(tags)s::jsonb, %(raw)s::jsonb, NOW(), %(section_gid)s, %(section_name)s
        )
        ON CONFLICT (gid) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            category = EXCLUDED.category,
            asana_url = EXCLUDED.asana_url,
            active = TRUE,
            removed_at = NULL,
            last_seen_at = NOW(),
            created_at = EXCLUDED.created_at,
            modified_at = EXCLUDED.modified_at,
            completed = EXCLUDED.completed,
            due_on = EXCLUDED.due_on,
            due_at = EXCLUDED.due_at,
            assignee_gid = EXCLUDED.assignee_gid,
            assignee_name = EXCLUDED.assignee_name,
            projects = EXCLUDED.projects,
            tags = EXCLUDED.tags,
            raw = EXCLUDED.raw,
            synced_at = NOW(),
            section_gid = EXCLUDED.section_gid,
            section_name = EXCLUDED.section_name
    """

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema)
            # Ensure columns exist
            cursor.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS section_gid TEXT;")
            cursor.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS section_name TEXT;")
            
            cursor.execute("INSERT INTO sync_runs (status) VALUES ('running') RETURNING id")
            run_id = cursor.fetchone()[0]
            try:
                for task in tasks:
                    sec_gid, sec_name = extract_section(task, project_gid)
                    assignee = task.get("assignee") or {}
                    
                    cursor.execute(upsert, {
                        "gid": task["gid"], 
                        "name": task.get("name", ""), 
                        "description": task.get("notes", ""),
                        "category": task_category(task), 
                        "asana_url": task.get("permalink_url"),
                        "created_at": parse_timestamp(task.get("created_at")), 
                        "modified_at": parse_timestamp(task.get("modified_at")),
                        "completed": task.get("completed", False), 
                        "due_on": task.get("due_on"), 
                        "due_at": parse_timestamp(task.get("due_at")),
                        "assignee_gid": assignee.get("gid"), 
                        "assignee_name": assignee.get("name"),
                        "projects": json.dumps(task.get("projects", [])), 
                        "tags": json.dumps(task.get("tags", [])), 
                        "raw": json.dumps(task),
                        "section_gid": sec_gid,
                        "section_name": sec_name
                    })
                    
                gids = [task["gid"] for task in tasks]
                missing_query = "UPDATE tasks SET active = FALSE, removed_at = COALESCE(removed_at, NOW()) WHERE active = TRUE"
                if gids:
                    missing_query += " AND NOT (gid = ANY(%s))"
                    cursor.execute(missing_query + " RETURNING gid", (gids,))
                else:
                    cursor.execute(missing_query + " RETURNING gid")
                for (gid,) in cursor.fetchall():
                    cursor.execute("INSERT INTO task_history (task_gid, change_type, details) VALUES (%s, 'removed', '{}'::jsonb)", (gid,))
                cursor.execute("UPDATE sync_runs SET status = 'success', finished_at = NOW(), task_count = %s WHERE id = %s", (len(tasks), run_id))
            except Exception as error:
                cursor.execute("UPDATE sync_runs SET status = 'failed', finished_at = NOW(), error_message = %s WHERE id = %s", (str(error), run_id))
                raise
        connection.commit()


def main() -> None:
    load_dotenv()
    token = os.environ.get("ASANA_TOKEN") or required_env("ASANA_TOKEN")
    database_url = os.environ.get("DATABASE_URL") or required_env("DATABASE_URL")
    project_gid = os.environ.get("PROJECT_GID") or required_env("PROJECT_GID")
    tasks = fetch_tasks(token, project_gid)
    sync_tasks(database_url, tasks, project_gid)
    print(f"Synced {len(tasks)} tasks from project {project_gid}")


if __name__ == "__main__":
    main()
