from pcl.models import ContextLayer


def resolve_allowed_layers(
    app: dict | None,
    requested_layers: list[ContextLayer],
) -> tuple[list[ContextLayer], str]:
    if not app:
        return [], "unknown_app"
    if app.get("status") != "active":
        return [], "app_revoked"

    app_layers = set(app.get("allowed_layers", []))
    requested = set(requested_layers or app_layers)
    allowed = sorted(requested & app_layers)
    if not allowed:
        return [], "no_allowed_layers"
    return allowed, ""
