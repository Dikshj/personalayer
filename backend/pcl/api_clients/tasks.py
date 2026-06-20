"""Task and project-management API clients."""

import httpx

TODOIST_BASE = "https://api.todoist.com/rest/v2"
TRELLO_BASE = "https://api.trello.com/1"
ASANA_BASE = "https://app.asana.com/api/1.0"
JIRA_BASE = "https://api.atlassian.com/ex/jira"


def fetch_todoist_tasks(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    response = httpx.get(f"{TODOIST_BASE}/tasks", headers=headers, timeout=10)
    response.raise_for_status()
    tasks = []
    for task in response.json():
        tasks.append({
            "id": task.get("id"),
            "project_id": task.get("project_id"),
            "priority": task.get("priority"),
            "created_at": task.get("created_at"),
            "due_recurring": bool((task.get("due") or {}).get("is_recurring", False)),
        })
    return {"tasks": tasks}


def fetch_trello_cards(access_token: str, api_key: str | None = None) -> dict:
    params = {"token": access_token}
    if api_key:
        params["key"] = api_key
    response = httpx.get(f"{TRELLO_BASE}/members/me/cards", params=params, timeout=10)
    response.raise_for_status()
    cards = []
    for card in response.json():
        cards.append({
            "id": card.get("id"),
            "board_id": card.get("idBoard"),
            "list_id": card.get("idList"),
            "due": card.get("due"),
            "due_complete": card.get("dueComplete"),
            "label_count": len(card.get("labels", [])),
        })
    return {"cards": cards}


def fetch_asana_tasks(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    response = httpx.get(
        f"{ASANA_BASE}/tasks",
        params={"assignee": "me", "completed_since": "now", "limit": 50, "opt_fields": "gid,completed,created_at,due_on,memberships.project.gid"},
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
    tasks = []
    for task in response.json().get("data", []):
        tasks.append({
            "id": task.get("gid"),
            "completed": task.get("completed", False),
            "created_at": task.get("created_at"),
            "due_on": task.get("due_on"),
            "project_count": len(task.get("memberships", [])),
        })
    return {"tasks": tasks}


def fetch_jira_issues(access_token: str, cloud_id: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    response = httpx.get(
        f"{JIRA_BASE}/{cloud_id}/rest/api/3/search/jql",
        params={"jql": "assignee = currentUser() ORDER BY updated DESC", "maxResults": 50, "fields": "status,priority,created,updated"},
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
    issues = []
    for issue in response.json().get("issues", []):
        fields = issue.get("fields", {})
        issues.append({
            "id": issue.get("id"),
            "status": fields.get("status", {}).get("statusCategory", {}).get("key"),
            "priority": fields.get("priority", {}).get("name"),
            "created_at": fields.get("created"),
            "updated_at": fields.get("updated"),
        })
    return {"issues": issues}

