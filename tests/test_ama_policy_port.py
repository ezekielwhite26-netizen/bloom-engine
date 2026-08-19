from bloom_engine.ama import (
    AmaActionClass,
    AmaIntent,
    AmaPermissionDecision,
    PersonalAmaPolicyV03,
)


def test_ordinary_requested_live_play_gets_one_run_capability():
    grant = PersonalAmaPolicyV03().authorize(
        AmaIntent(
            mode="LIVE_PLAY",
            project="ASTER_HOLLOW",
            action_class=AmaActionClass.ORDINARY_LIVE_PLAY,
            command="continue Episode 7",
            requested_commit=True,
        ),
        nonce="fixture-nonce",
    )
    assert grant.decision is AmaPermissionDecision.ALLOW
    assert grant.capability_token is not None
    assert grant.capability_token.startswith("AMA-CAP::")
    assert grant.expires_after_run is True


def test_protected_creative_fulcrum_is_returned_to_user():
    grant = PersonalAmaPolicyV03().authorize(
        AmaIntent(
            mode="LIVE_PLAY",
            project="ASTER_HOLLOW",
            action_class=AmaActionClass.PROTECTED_CREATIVE_DECISION,
            command="lock Florence's relationship route",
            protected_domain="FLORENCE_DURABLE_RELATIONSHIP_COMMITMENT",
        ),
        nonce="fixture-nonce",
    )
    assert grant.decision is AmaPermissionDecision.ASK
    assert grant.capability_token is None


def test_destructive_action_never_self_authorizes():
    grant = PersonalAmaPolicyV03().authorize(
        AmaIntent(
            mode="IMPLEMENTATION",
            project="BLOOM",
            action_class=AmaActionClass.DESTRUCTIVE,
            command="wipe the canon tables",
        ),
        nonce="fixture-nonce",
    )
    assert grant.decision is AmaPermissionDecision.DENY
    assert grant.capability_token is None
