import json
from datetime import timedelta

import pytest

from app.geographic_safety import (
    classify_geographic_safety,
    persist_geographic_evidence,
)
from app.models import (
    Collectible,
    GeographicSecurityAuditLog,
    GeographicSecurityEvidence,
    SpawnInstance,
    SpawnPoint,
    Zone,
    utcnow,
)
from app.spawn_worker import generate_dynamic_spawns
from .conftest import collect_request, create_player, create_spawn


def square(longitude=0, latitude=0, delta=0.01):
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [longitude - delta, latitude - delta],
                [longitude + delta, latitude - delta],
                [longitude + delta, latitude + delta],
                [longitude - delta, latitude + delta],
                [longitude - delta, latitude - delta],
            ]
        ],
    }


def add_evidence(
    db,
    *,
    geometry=None,
    status="safe",
    source_name="Reviewed source",
    source_identifier="source-record-1",
    license_terms="Verified use terms",
    access_status="public",
    confidence=0.99,
    validation_status="verified",
    verified_at=None,
    expires_at=None,
):
    record = GeographicSecurityEvidence(
        geometry_geojson=json.dumps(geometry if geometry is not None else square()),
        security_status=status,
        place_type="test_area",
        source_name=source_name,
        source_identifier=source_identifier,
        license_terms=license_terms,
        access_status=access_status,
        verified_at=verified_at or utcnow(),
        expires_at=expires_at or utcnow() + timedelta(days=1),
        confidence=confidence,
        validation_status=validation_status,
        rule_applied="test_rule",
        reason=f"Test {status} evidence",
    )
    persist_geographic_evidence(db, record, actor="tests")
    db.commit()
    return record


def test_classifies_safe_caution_restricted_and_no_evidence(client):
    factory = client.app.state.session_factory
    with factory() as db:
        add_evidence(db, status="safe")
        assert classify_geographic_safety(db, 0, 0).status == "safe"

        add_evidence(db, status="caution", source_identifier="caution-1")
        assert classify_geographic_safety(db, 0, 0).status == "caution"

        add_evidence(db, status="restricted", source_identifier="restricted-1")
        assert classify_geographic_safety(db, 0, 0).status == "restricted"

        unknown = classify_geographic_safety(db, 10, 10)
        assert unknown.status == "unknown"
        assert not unknown.allows_generation
        assert not unknown.allows_query
        assert not unknown.allows_collection


def test_restricted_and_unknown_evidence_override_overlapping_safe_evidence(client):
    factory = client.app.state.session_factory
    with factory() as db:
        add_evidence(db, status="safe")
        add_evidence(db, status="restricted", source_identifier="red-overlap")
        assert classify_geographic_safety(db, 0, 0).status == "restricted"

    with factory() as db:
        db.query(GeographicSecurityEvidence).delete()
        db.commit()
        add_evidence(db, status="safe")
        add_evidence(db, status="unknown", source_identifier="unknown-overlap")
        decision = classify_geographic_safety(db, 0, 0)
        assert decision.status == "unknown"
        assert decision.allows_generation is False


@pytest.mark.parametrize(
    "evidence_options",
    [
        {
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-0.01, -0.01], [0.01, 0.01], [-0.01, 0.01], [0.01, -0.01], [-0.01, -0.01]]
                ],
            }
        },
        {"expires_at": utcnow() - timedelta(seconds=1)},
        {"source_name": None, "license_terms": None},
        {"confidence": 0.89},
        {"validation_status": "unreviewed"},
    ],
)
def test_invalid_stale_unproven_or_low_confidence_evidence_is_unknown(
    client, evidence_options
):
    with client.app.state.session_factory() as db:
        add_evidence(db, **evidence_options)
        assert classify_geographic_safety(db, 0, 0).status == "unknown"


def test_polygon_boundary_is_included(client):
    with client.app.state.session_factory() as db:
        add_evidence(db, status="restricted")
        assert classify_geographic_safety(db, 0, -0.01).status == "restricted"


def test_safe_requires_verified_access_and_confidence_at_policy_threshold(client):
    with client.app.state.session_factory() as db:
        add_evidence(db, confidence=0.9, access_status="authorized")
        assert classify_geographic_safety(db, 0, 0).status == "safe"

    with client.app.state.session_factory() as db:
        db.query(GeographicSecurityEvidence).delete()
        db.commit()
        add_evidence(db, access_status="unknown")
        assert classify_geographic_safety(db, 0, 0).status == "unknown"


def test_restricted_access_evidence_cannot_become_safe(client):
    with client.app.state.session_factory() as db:
        add_evidence(db, access_status="restricted")
        assert classify_geographic_safety(db, 0, 0).status == "restricted"


def test_accuracy_radius_detects_a_nearby_restricted_perimeter(client):
    geometry = square(longitude=0.001, latitude=0, delta=0.0001)
    with client.app.state.session_factory() as db:
        add_evidence(db, geometry=geometry, status="restricted")
        outside = classify_geographic_safety(db, 0, 0, radius_meters=10)
        inside_uncertainty = classify_geographic_safety(
            db, 0, 0, radius_meters=120
        )
        assert outside.status == "unknown"
        assert inside_uncertainty.status == "restricted"


@pytest.mark.parametrize("status", ["caution", "restricted", "unknown", None])
def test_spawn_worker_never_generates_without_green_evidence(client, status):
    factory = client.app.state.session_factory
    with factory() as db:
        zone = Zone(name="Legacy enabled zone", enabled=True, boundary_geojson=json.dumps(square(delta=1)))
        collectible = Collectible(
            ticker="BTC",
            name="Bitcoin",
            symbol="B",
            rarity="common",
            points_reward=1,
            xp_reward=1,
        )
        db.add_all([zone, collectible])
        db.flush()
        if status is not None:
            add_evidence(db, geometry=square(delta=1), status=status)
        point = SpawnPoint(
            zone_id=zone.id,
            collectible_id=collectible.id,
            latitude=0,
            longitude=0,
            dynamic=True,
        )
        db.add(point)
        db.commit()

    assert generate_dynamic_spawns(factory) == 0
    with factory() as db:
        assert db.query(SpawnInstance).count() == 0


def test_nearby_query_hides_objects_when_player_location_is_not_green(client):
    create_player(client)
    create_spawn(client)
    with client.app.state.session_factory() as db:
        add_evidence(db, status="restricted")

    response = client.get("/api/v1/collectibles/nearby?latitude=0&longitude=0")
    assert response.status_code == 200
    assert response.json()["items"] == []
    zones = client.get("/api/v1/zones/nearby?latitude=0&longitude=0")
    assert zones.status_code == 200
    assert zones.json()["items"] == []


def test_nearby_query_omits_a_restricted_spawn_for_a_safe_player(client):
    create_player(client)
    create_spawn(client)
    with client.app.state.session_factory() as db:
        add_evidence(
            db,
            geometry=square(delta=0.0001),
            status="restricted",
            source_identifier="restricted-spawn-area",
        )

    response = client.get(
        "/api/v1/collectibles/nearby?"
        "latitude=0&longitude=0.005&radius_meters=1500"
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_collection_is_rejected_if_safety_classification_changes(client):
    create_player(client)
    spawn_id = create_spawn(client)
    with client.app.state.session_factory() as db:
        add_evidence(db, status="restricted")

    response = client.post(
        "/api/v1/collectibles/collect",
        headers={"Idempotency-Key": "changed-safety-classification"},
        json=collect_request(spawn_id),
    )
    assert response.status_code == 403
    with client.app.state.session_factory() as db:
        assert db.query(SpawnInstance).one().state == "available"


def test_collection_rejects_client_coordinates_whose_uncertainty_hits_restricted_area(
    client,
):
    create_player(client)
    spawn_id = create_spawn(client)
    with client.app.state.session_factory() as db:
        add_evidence(
            db,
            geometry=square(longitude=0.00005, latitude=0, delta=0.00001),
            status="restricted",
        )

    response = client.post(
        "/api/v1/collectibles/collect",
        headers={"Idempotency-Key": "coordinate-in-restricted-area"},
        json=collect_request(spawn_id, longitude=0.00005, accuracy=5),
    )
    assert response.status_code == 403
    assert "autorizada" in response.json()["detail"]


def test_legacy_enabled_zone_is_not_implicitly_safe(client):
    with client.app.state.session_factory() as db:
        zone = Zone(
            name="Historical enabled zone",
            enabled=True,
            boundary_geojson=json.dumps(square(delta=1)),
        )
        db.add(zone)
        db.commit()
        assert classify_geographic_safety(db, 0, 0).status == "unknown"


def test_evidence_creation_is_audited_with_geometry_fingerprint(client):
    with client.app.state.session_factory() as db:
        evidence = add_evidence(db)
        audit = (
            db.query(GeographicSecurityAuditLog)
            .filter_by(evidence_id=evidence.id)
            .one()
        )
        assert audit.action == "created"
        assert audit.actor == "tests"
        assert audit.new_value["geometry_sha256"]
