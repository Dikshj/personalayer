"""Linear API client."""

import httpx

LINEAR_BASE = "https://api.linear.app/graphql"


def fetch_assigned_issues(access_token: str) -> dict:
    query = """
    query {
      viewer {
        assignedIssues(first: 50) {
          nodes {
            id
            state { name type }
            priority
            createdAt
            updatedAt
            completedAt
            team { id }
          }
        }
      }
    }
    """
    headers = {"Authorization": access_token, "Content-Type": "application/json"}
    response = httpx.post(LINEAR_BASE, json={"query": query}, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    if data.get("errors"):
        raise RuntimeError(str(data["errors"][:1]))

    issues = data.get("data", {}).get("viewer", {}).get("assignedIssues", {}).get("nodes", [])
    return {
        "issues": [
            {
                "id": issue.get("id"),
                "state_type": issue.get("state", {}).get("type"),
                "priority": issue.get("priority"),
                "created_at": issue.get("createdAt"),
                "updated_at": issue.get("updatedAt"),
                "completed_at": issue.get("completedAt"),
            }
            for issue in issues
        ]
    }

