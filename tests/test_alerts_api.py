import copy
import re
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.features.alerts import api as alerts_api
from app.features.alerts.api import router as alerts_router
from app.features.auth.api import get_current_user


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 5, 7, 12, 0, 0, tzinfo=tz or timezone.utc)


def _nested_value(doc, path):
    current = doc
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _matches_condition(value, condition):
    if isinstance(condition, dict) and any(key.startswith("$") for key in condition):
        regex = condition.get("$regex")
        if regex is not None:
            flags = re.IGNORECASE if condition.get("$options") == "i" else 0
            if value is None or re.search(regex, str(value), flags) is None:
                return False

        if "$gte" in condition and not (value is not None and value >= condition["$gte"]):
            return False
        if "$lte" in condition and not (value is not None and value <= condition["$lte"]):
            return False

        return True

    return value == condition


def _matches_query(doc, query):
    for key, condition in query.items():
        if key == "$or":
            if not any(_matches_query(doc, branch) for branch in condition):
                return False
            continue
        if key == "$and":
            if not all(_matches_query(doc, branch) for branch in condition):
                return False
            continue

        value = _nested_value(doc, key)
        if not _matches_condition(value, condition):
            return False

    return True


def _evaluate_aggregate_expression(expression, doc):
    if isinstance(expression, dict) and "$eq" in expression:
        left, right = expression["$eq"]
        return _evaluate_aggregate_expression(left, doc) == _evaluate_aggregate_expression(right, doc)

    if isinstance(expression, str) and expression.startswith("$"):
        return _nested_value(doc, expression[1:])

    return expression


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, spec, direction=None):
        if isinstance(spec, list):
            for field, field_direction in reversed(spec):
                reverse = field_direction in (-1, alerts_api.DESCENDING)
                self.docs.sort(key=lambda doc, field_name=field: _nested_value(doc, field_name), reverse=reverse)
            return self

        reverse = direction in (-1, alerts_api.DESCENDING)
        self.docs.sort(key=lambda doc: _nested_value(doc, spec), reverse=reverse)
        return self

    def skip(self, count):
        self.docs = self.docs[count:]
        return self

    def limit(self, count):
        self.docs = self.docs[:count]
        return self

    def __iter__(self):
        return iter(self.docs)


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []
        self.indexes = []

    def create_index(self, keys):
        self.indexes.append(keys)
        return str(keys)

    def find(self, query=None):
        query = query or {}
        return FakeCursor([copy.deepcopy(doc) for doc in self.docs if _matches_query(doc, query)])

    def find_one(self, query):
        for doc in self.docs:
            if _matches_query(doc, query):
                return copy.deepcopy(doc)
        return None

    def count_documents(self, query):
        return sum(1 for doc in self.docs if _matches_query(doc, query))

    def aggregate(self, pipeline):
        docs = [copy.deepcopy(doc) for doc in self.docs]

        for stage in pipeline:
            if "$match" in stage:
                docs = [doc for doc in docs if _matches_query(doc, stage["$match"])]
                continue

            if "$group" in stage:
                group_spec = stage["$group"]
                result = {"_id": group_spec.get("_id")}

                for field_name, accumulator in group_spec.items():
                    if field_name == "_id":
                        continue

                    total = 0
                    if isinstance(accumulator, dict) and "$sum" in accumulator:
                        sum_expression = accumulator["$sum"]
                        for doc in docs:
                            if sum_expression == 1:
                                total += 1
                            elif isinstance(sum_expression, dict) and "$cond" in sum_expression:
                                condition, true_value, false_value = sum_expression["$cond"]
                                total += true_value if _evaluate_aggregate_expression(condition, doc) else false_value

                    result[field_name] = total

                return iter([result])

        return iter([])


class FakeDatabase:
    def __init__(self, alerts_docs):
        self.alerts = FakeCollection(alerts_docs)


def _make_alert_doc(index, days_ago, *, tenant_id="tenant_1", camera_id="cam_1", alert_type="ppe_violation", label="NO-Safety Vest", severity="high", status="open", confidence=0.821):
    current_dt = FixedDateTime.now(timezone.utc) - timedelta(days=days_ago)
    alert_id = f"{tenant_id}_{camera_id}_{index:02d}"
    object_prefix = f"nexa-evidence/{tenant_id}/{camera_id}/alerts/{alert_id}"

    return {
        "_id": f"mongo_{index:02d}",
        "alert_id": alert_id,
        "tenant_id": tenant_id,
        "camera_id": camera_id,
        "frame_id": f"frame_{index:02d}",
        "alert_type": alert_type,
        "timestamp": current_dt.timestamp(),
        "pipeline_id": "ppe",
        "label": label,
        "severity": severity,
        "confidence": confidence,
        "details": {
            "bbox": [740, 419, 97, 178],
            "confidence": confidence,
            "label": label,
        },
        "status": status,
        "snapshot_path": f"{object_prefix}/snapshot.jpg",
        "clip_path": f"{object_prefix}/clip.webm",
    }


class AlertsPaginatedApiTests(unittest.TestCase):
    def setUp(self):
        alerts_api._ALERTS_INDEXES_READY = False

        alerts_docs = [
            _make_alert_doc(0, 0, camera_id="cam_1", alert_type="ppe_violation", label="NO-Safety Vest", severity="high", status="open", confidence=0.821),
            _make_alert_doc(1, 0, camera_id="cam_2", alert_type="motion_detected", label="Motion", severity="low", status="closed", confidence=0.41),
        ]

        for index, days_ago in enumerate(range(1, 12), start=2):
            alerts_docs.append(
                _make_alert_doc(
                    index,
                    days_ago,
                    camera_id="cam_1" if index % 2 == 0 else "cam_2",
                    alert_type="ppe_violation" if index % 3 == 0 else "motion_detected",
                    label=f"Label {index}",
                    severity=["low", "medium", "high"][index % 3],
                    status="open" if index % 2 == 0 else "closed",
                    confidence=0.5 + (index / 100),
                )
            )

        alerts_docs.append(
            _make_alert_doc(
                20,
                35,
                camera_id="cam_1",
                alert_type="archived_alert",
                label="Old Alert",
                severity="low",
                status="open",
                confidence=0.12,
            )
        )

        alerts_docs.extend(
            [
                _make_alert_doc(30, 1, tenant_id="tenant_2", camera_id="cam_9", alert_type="tenant_two", label="Tenant Two", severity="medium", status="open", confidence=0.9),
                _make_alert_doc(31, 2, tenant_id="tenant_2", camera_id="cam_9", alert_type="tenant_two_old", label="Tenant Two Old", severity="high", status="closed", confidence=0.8),
            ]
        )

        self.db = FakeDatabase(alerts_docs)
        self.app = FastAPI()
        self.app.include_router(alerts_router, prefix="/api/v1/alerts", tags=["alerts"])
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = lambda: {
            "tenant_id": "tenant_1",
            "role": "Admin",
            "permission_overrides": [],
            "_role_permissions": {"view_stream": True},
        }

        self.datetime_patch = patch("app.features.alerts.api.datetime", FixedDateTime)
        self.generate_url_patch = patch(
            "app.features.alerts.api.generate_presigned_url",
            side_effect=lambda object_path: (f"http://minio.local/{object_path}", 1800),
        )
        self.datetime_patch.start()
        self.generate_url_patch.start()

        self.client = TestClient(self.app)

    def tearDown(self):
        self.datetime_patch.stop()
        self.generate_url_patch.stop()
        self.app.dependency_overrides.clear()

    def test_pagination_returns_page_metadata_and_urls(self):
        response = self.client.get(
            "/api/v1/alerts/paginated",
            params={"preset": "all", "page": 1, "page_size": 10, "sort": "timestamp_desc"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body["pagination"]["page"], 1)
        self.assertEqual(body["pagination"]["page_size"], 10)
        self.assertEqual(body["pagination"]["total"], 14)
        self.assertEqual(body["pagination"]["total_pages"], 2)
        self.assertTrue(body["pagination"]["has_next"])
        self.assertFalse(body["pagination"]["has_prev"])
        self.assertEqual(len(body["items"]), 10)
        self.assertEqual(body["items"][0]["id"], body["items"][0]["alert_id"])
        self.assertIn("snapshot.jpg", body["items"][0]["snapshot_url"])
        self.assertIn("clip.webm", body["items"][0]["clip_url"])

        page_two = self.client.get(
            "/api/v1/alerts/paginated",
            params={"preset": "all", "page": 2, "page_size": 10, "sort": "timestamp_desc"},
        )
        self.assertEqual(page_two.status_code, 200)
        body_two = page_two.json()
        self.assertEqual(len(body_two["items"]), 4)
        self.assertFalse(body_two["pagination"]["has_next"])
        self.assertTrue(body_two["pagination"]["has_prev"])

    def test_alerts_timeline_returns_counts_for_tenant_and_camera(self):
        response = self.client.get(
            "/api/v1/alerts/timeline",
            params={"tenant_id": "tenant_1", "camera_id": "cam_1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "tenant_id": "tenant_1",
            "camera_id": "cam_1",
            "total": 8,
            "high": 3,
            "medium": 2,
            "low": 3,
        })

    def test_alerts_timeline_camera_id_is_optional(self):
        response = self.client.get(
            "/api/v1/alerts/timeline",
            params={"tenant_id": "tenant_1"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["tenant_id"], "tenant_1")
        self.assertIsNone(body["camera_id"])
        self.assertEqual(body["total"], 14)
        self.assertEqual(body["high"], 5)
        self.assertEqual(body["medium"], 3)
        self.assertEqual(body["low"], 6)

    def test_alerts_timeline_enforces_tenant_isolation(self):
        response = self.client.get(
            "/api/v1/alerts/timeline",
            params={"tenant_id": "tenant_2"},
        )

        self.assertEqual(response.status_code, 403)

    def test_alerts_timeline_missing_severity_categories_return_zero(self):
        self.app.dependency_overrides[get_current_user] = lambda: {
            "tenant_id": "tenant_2",
            "role": "Admin",
            "permission_overrides": [],
            "_role_permissions": {"view_stream": True},
        }

        response = self.client.get(
            "/api/v1/alerts/timeline",
            params={"camera_id": "cam_9"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "tenant_id": "tenant_2",
            "camera_id": "cam_9",
            "total": 2,
            "high": 1,
            "medium": 1,
            "low": 0,
        })

    def test_alerts_timeline_no_matching_alerts_returns_zero_counts(self):
        response = self.client.get(
            "/api/v1/alerts/timeline",
            params={"tenant_id": "tenant_1", "camera_id": "cam_999"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "tenant_id": "tenant_1",
            "camera_id": "cam_999",
            "total": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        })

    def test_date_presets_and_custom_ranges(self):
        today = self.client.get("/api/v1/alerts/paginated", params={"preset": "today", "page": 1, "page_size": 10})
        self.assertEqual(today.status_code, 200)
        today_body = today.json()
        self.assertEqual(today_body["pagination"]["total"], 2)
        self.assertTrue(all(item["date"] == "2026-05-07" for item in today_body["items"]))

        seven_day = self.client.get("/api/v1/alerts/paginated", params={"preset": "7d", "page": 1, "page_size": 25})
        self.assertEqual(seven_day.status_code, 200)
        self.assertEqual(seven_day.json()["pagination"]["total"], 9)

        thirty_day = self.client.get("/api/v1/alerts/paginated", params={"preset": "30d", "page": 1, "page_size": 25})
        self.assertEqual(thirty_day.status_code, 200)
        self.assertEqual(thirty_day.json()["pagination"]["total"], 13)

        custom = self.client.get(
            "/api/v1/alerts/paginated",
            params={"preset": "custom", "date_from": "2026-05-02", "date_to": "2026-05-04", "page": 1, "page_size": 25},
        )
        self.assertEqual(custom.status_code, 200)
        self.assertEqual(custom.json()["pagination"]["total"], 3)

    def test_camera_filter_search_and_tenant_isolation(self):
        camera_response = self.client.get(
            "/api/v1/alerts/paginated",
            params={"preset": "all", "camera_id": "cam_2", "page": 1, "page_size": 25},
        )
        self.assertEqual(camera_response.status_code, 200)
        camera_items = camera_response.json()["items"]
        self.assertGreater(len(camera_items), 0)
        self.assertTrue(all(item["camera_id"] == "cam_2" for item in camera_items))
        self.assertTrue(all(item["tenant_id"] == "tenant_1" for item in camera_items))

        search_terms = {
            "ppe": "alert_type",
            "vest": "label",
            "cam_2": "camera_id",
            "high": "severity",
            "open": "status",
        }
        for term, field_name in search_terms.items():
            with self.subTest(term=term):
                response = self.client.get(
                    "/api/v1/alerts/paginated",
                    params={"preset": "all", "search": term, "page": 1, "page_size": 25},
                )
                self.assertEqual(response.status_code, 200)
                items = response.json()["items"]
                self.assertGreater(len(items), 0)
                self.assertTrue(any(term.lower() in str(item[field_name]).lower() for item in items))
                self.assertTrue(all(item["tenant_id"] == "tenant_1" for item in items))

        indexes = self.db.alerts.indexes
        self.assertGreaterEqual(len(indexes), 4)


if __name__ == "__main__":
    unittest.main()