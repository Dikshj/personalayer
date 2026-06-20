"""Slack API client."""

import httpx

SLACK_BASE = "https://slack.com/api"


def fetch_channel_activity(access_token: str, max_channels: int = 10) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    response = httpx.get(
        f"{SLACK_BASE}/conversations.list",
        params={"types": "public_channel,private_channel", "limit": max_channels, "exclude_archived": True},
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
    channels_data = response.json()
    if not channels_data.get("ok", False):
        raise RuntimeError(channels_data.get("error", "slack_api_error"))

    channels = [
        {
            "id": channel.get("id"),
            "is_member": channel.get("is_member", False),
            "num_members": channel.get("num_members", 0),
            "is_private": channel.get("is_private", False),
        }
        for channel in channels_data.get("channels", [])
    ]

    activity = []
    for channel in channels[:5]:
        if not channel.get("id"):
            continue
        history = httpx.get(
            f"{SLACK_BASE}/conversations.history",
            params={"channel": channel["id"], "limit": 20},
            headers=headers,
            timeout=10,
        )
        if history.status_code == 200 and history.json().get("ok"):
            messages = history.json().get("messages", [])
            user_messages = [message for message in messages if message.get("user")]
            activity.append({
                "channel_id": channel["id"],
                "is_private": channel["is_private"],
                "recent_message_count": len(messages),
                "user_message_count": len(user_messages),
            })

    return {"channel_activity": activity, "channel_count": len(channels)}

