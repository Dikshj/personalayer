import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def test_privacy_scrubber_removes_pii_from_nested_data():
    from pcl.privacy import scrub_pii

    data = {
        "content": "Email me at user@example.com or call +1 415 555 1212",
        "nested": ["token sk-testsecret123456789"],
    }

    scrubbed = scrub_pii(data)

    assert "user@example.com" not in str(scrubbed)
    assert "415 555 1212" not in str(scrubbed)
    assert "sk-testsecret" not in str(scrubbed)
    assert "[email]" in scrubbed["content"]


def test_strip_raw_content_keeps_behavioral_fields_only():
    from pcl.privacy import strip_raw_content

    signal = {
        "source": "gmail",
        "signal_type": "feature_use",
        "feature_id": "smart_reply",
        "raw_email_body": "secret",
        "name": "smart_reply",
        "confidence": 0.8,
    }

    filtered = strip_raw_content(signal)

    assert filtered == {
        "source": "gmail",
        "signal_type": "feature_use",
        "feature_id": "smart_reply",
        "name": "smart_reply",
        "confidence": 0.8,
    }


def test_sanitize_integration_metadata_drops_secret_fields():
    from pcl.privacy import sanitize_integration_metadata

    sanitized = sanitize_integration_metadata({
        "username": "octocat",
        "access_token": "ghp_secretsecretsecret",
        "nested": {
            "refresh_token": "ya29_secretsecretsecret",
            "labels": ["Work"],
        },
    })

    assert sanitized == {
        "username": "octocat",
        "nested": {"labels": ["Work"]},
    }


def test_local_embedding_shape_and_similarity():
    from pcl.embeddings import (
        DIMENSION,
        cosine_similarity,
        deserialize_embedding,
        embed_label,
        serialize_embedding,
    )

    design_system = embed_label("design system")
    design_systems = embed_label("design systems")
    unrelated = embed_label("calendar meeting")
    blob = serialize_embedding(design_system)

    assert len(design_system) == DIMENSION
    assert len(blob) == DIMENSION * 4
    assert deserialize_embedding(blob)[:3] == design_system[:3]
    assert cosine_similarity(design_system, design_systems) >= 0.92
    assert cosine_similarity(design_system, unrelated) < 0.92


def test_decision_bundle_ranks_features_and_exposes_typed_context():
    from pcl.composer import compose_decision_bundle
    from pcl.models import (
        ActiveContext,
        AppFeature,
        CapabilitySignal,
        ContextQuery,
        IdentityRole,
        UserContextProfile,
    )

    profile = UserContextProfile(
        user_id="user_1",
        identity=IdentityRole(role="founder", expertise=["email"]),
        active_context=ActiveContext(current_project="PCL"),
        capabilities=[
            CapabilitySignal(
                feature_id="inbox_zero",
                feature_name="Inbox Zero",
                use_count=10,
                recency_weight=0.9,
                confidence=0.8,
            ),
            CapabilitySignal(
                feature_id="calendar_digest",
                feature_name="Calendar Digest",
                use_count=1,
                recency_weight=0.1,
                confidence=0.5,
            ),
        ],
    )
    query = ContextQuery(
        app_id="mail_app",
        user_id="user_1",
        features=[
            AppFeature(feature_id="calendar_digest", name="Calendar Digest"),
            AppFeature(feature_id="inbox_zero", name="Inbox Zero"),
        ],
    )

    bundle = compose_decision_bundle(query, profile)

    assert bundle.ranked_features[0].feature_id == "inbox_zero"
    assert bundle.audit["raw_data_shared"] is False
    assert "active_context" in bundle.context


def test_explicit_disabled_preference_suppresses_feature():
    from pcl.composer import compose_decision_bundle
    from pcl.models import (
        AppFeature,
        CapabilitySignal,
        ContextQuery,
        ExplicitPreference,
        UserContextProfile,
    )

    profile = UserContextProfile(
        user_id="user_1",
        capabilities=[
            CapabilitySignal(
                feature_id="ai_summary",
                feature_name="AI Summary",
                use_count=100,
                recency_weight=1.0,
                confidence=0.9,
            ),
        ],
        explicit_preferences=[
            ExplicitPreference(key="AI Summary", value=False),
        ],
    )
    query = ContextQuery(
        app_id="docs_app",
        user_id="user_1",
        features=[AppFeature(feature_id="ai_summary", name="AI Summary")],
    )

    bundle = compose_decision_bundle(query, profile)

    assert bundle.ranked_features[0].score < 0
    assert "explicitly_disabled" in bundle.ranked_features[0].reason_codes


def test_onboarding_seed_builds_five_layer_profile_seed():
    from pcl.onboarding import build_onboarding_seed

    seed = build_onboarding_seed({
        "identity": "Founder, developer tools, Python",
        "features": "Inbox Zero, Smart Reply",
        "behavior": "quick minimal flows",
        "active_context": "building a personal context layer",
        "preferences": "never show AI Summary, compact UI",
    })

    assert seed["identity"]["role"] == "Founder"
    assert seed["identity"]["domain"] == "developer tools"
    assert seed["capabilities"][0]["feature_id"] == "inbox_zero"
    assert seed["behavior"]["preferred_depth"] == "minimal"
    assert seed["active_context"]["current_goal"] == "building a personal context layer"
    assert seed["explicit_preferences"][0]["value"] is False
