"""Integration tests for pipeline.py stages — LLM calls are mocked."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent.parent


class TestStageIngest:
    def test_returns_events_catalogue_profiles(self):
        from src.pipeline import stage_ingest
        events, catalogue, profiles = stage_ingest()
        assert len(events) >= 500
        assert len(catalogue) == 100
        assert len(profiles) >= 48


class TestStageDetect:
    def test_returns_detections_list(self, sample_profiles):
        from src.pipeline import stage_detect
        detections = stage_detect(sample_profiles)
        assert isinstance(detections, list)
        assert len(detections) > 0

    def test_writes_occasion_detection_results(self, sample_profiles):
        from src.pipeline import stage_detect
        stage_detect(sample_profiles)
        out = ROOT / "outputs" / "occasion_detection_results.json"
        assert out.exists()
        with open(out) as f:
            data = json.load(f)
        assert isinstance(data, list)

    def test_hijri_detections_present(self, sample_profiles):
        from src.pipeline import stage_detect
        detections = stage_detect(sample_profiles)
        hijri = [d for d in detections if d.calendar_type == "hijri"]
        assert len(hijri) >= 2, f"Expected ≥2 Hijri detections, got {len(hijri)}"

    def test_low_confidence_detections_present(self, sample_profiles):
        from src.pipeline import stage_detect
        detections = stage_detect(sample_profiles)
        low = [d for d in detections if d.confidence == "low"]
        assert len(low) >= 1

    def test_future_dates_only(self, sample_profiles):
        from src.pipeline import stage_detect
        from datetime import date
        from src.occasion_detector import TODAY
        detections = stage_detect(sample_profiles)
        for d in detections:
            assert date.fromisoformat(d.predicted_date) >= TODAY


class TestStageGenerate:
    def test_returns_message_dict(self, sample_profiles):
        from src.pipeline import stage_detect, stage_generate, _MockLLMClient
        detections = stage_detect(sample_profiles)
        _, catalogue, _ = __import__("src.pipeline", fromlist=["stage_ingest"]).stage_ingest()
        messages = stage_generate(sample_profiles, detections, catalogue, _MockLLMClient())
        assert isinstance(messages, dict)
        assert len(messages) > 0

    def test_messages_keyed_by_detection_key(self, sample_profiles):
        from src.pipeline import stage_detect, stage_generate, stage_ingest, _MockLLMClient
        from src.campaign_engine import _detection_key
        _, catalogue, _ = stage_ingest()
        detections = stage_detect(sample_profiles)
        messages = stage_generate(sample_profiles, detections, catalogue, _MockLLMClient())
        for key in messages:
            assert "::" in key


class TestStageSchedule:
    def test_produces_minimum_30_sends(self, sample_profiles):
        from src.pipeline import stage_ingest, stage_detect, stage_generate, stage_schedule, _MockLLMClient
        _, catalogue, _ = stage_ingest()
        detections = stage_detect(sample_profiles)
        messages = stage_generate(sample_profiles, detections, catalogue, _MockLLMClient())
        schedule = stage_schedule(sample_profiles, detections, messages)
        assert len(schedule) >= 30, f"Only {len(schedule)} sends produced (need ≥30)"

    def test_writes_campaign_schedule_json(self, sample_profiles):
        from src.pipeline import stage_ingest, stage_detect, stage_generate, stage_schedule, _MockLLMClient
        _, catalogue, _ = stage_ingest()
        detections = stage_detect(sample_profiles)
        messages = stage_generate(sample_profiles, detections, catalogue, _MockLLMClient())
        stage_schedule(sample_profiles, detections, messages)
        out = ROOT / "outputs" / "campaign_schedule.json"
        assert out.exists()
        with open(out) as f:
            data = json.load(f)
        assert len(data) >= 30

    def test_no_consent_violations(self, sample_profiles):
        from src.pipeline import stage_ingest, stage_detect, stage_generate, stage_schedule, _MockLLMClient
        _, catalogue, _ = stage_ingest()
        detections = stage_detect(sample_profiles)
        messages = stage_generate(sample_profiles, detections, catalogue, _MockLLMClient())
        schedule = stage_schedule(sample_profiles, detections, messages)

        for s in schedule:
            cs = s.consent_status
            ch = s.channel
            if ch == "email":
                assert cs.email, f"Email sent to {s.customer_id} without consent"
            if ch == "whatsapp":
                assert cs.whatsapp, f"WA sent to {s.customer_id} without consent"
            if ch == "push":
                assert cs.push, f"Push sent to {s.customer_id} without consent"

    def test_fatigue_cap_respected(self, sample_profiles):
        from collections import defaultdict
        from datetime import datetime
        from src.pipeline import stage_ingest, stage_detect, stage_generate, stage_schedule, _MockLLMClient
        _, catalogue, _ = stage_ingest()
        detections = stage_detect(sample_profiles)
        messages = stage_generate(sample_profiles, detections, catalogue, _MockLLMClient())
        schedule = stage_schedule(sample_profiles, detections, messages)

        weekly: dict = defaultdict(int)
        for s in schedule:
            dt = datetime.fromisoformat(s.scheduled_send_time)
            iso = dt.isocalendar()
            key = (s.customer_id, f"{iso[0]}-W{iso[1]}")
            weekly[key] += 1

        violations = {k: v for k, v in weekly.items() if v > 2}
        assert not violations, f"Fatigue cap violated: {violations}"


class TestStageEvaluate:
    def test_writes_evaluation_report(self, sample_profiles):
        from src.pipeline import stage_ingest, stage_detect, stage_generate, stage_schedule, stage_evaluate, _MockLLMClient
        _, catalogue, _ = stage_ingest()
        detections = stage_detect(sample_profiles)
        messages = stage_generate(sample_profiles, detections, catalogue, _MockLLMClient())
        schedule = stage_schedule(sample_profiles, detections, messages)
        report = stage_evaluate(detections, schedule)

        assert "dimensions" in report
        assert len(report["dimensions"]) == 7
        for dim in report["dimensions"]:
            assert 1 <= dim["self_score"] <= 5
            assert dim["name"]
            assert dim["justification"]

    def test_evaluation_json_valid(self, sample_profiles):
        from src.pipeline import stage_ingest, stage_detect, stage_generate, stage_schedule, stage_evaluate, _MockLLMClient
        _, catalogue, _ = stage_ingest()
        detections = stage_detect(sample_profiles)
        messages = stage_generate(sample_profiles, detections, catalogue, _MockLLMClient())
        schedule = stage_schedule(sample_profiles, detections, messages)
        stage_evaluate(detections, schedule)

        out = ROOT / "outputs" / "evaluation_report.json"
        assert out.exists()
        with open(out) as f:
            data = json.load(f)
        assert "dimensions" in data


class TestMockLLMClient:
    def test_mock_client_returns_valid_json(self):
        from src.pipeline import _MockLLMClient
        client = _MockLLMClient()
        response = client.messages.create(model="test", max_tokens=100, messages=[])
        text = response.content[0].text
        parsed = json.loads(text)
        assert "email" in parsed
        assert "whatsapp" in parsed
        assert "push" in parsed

    def test_mock_whatsapp_has_opt_out(self):
        from src.pipeline import _MockLLMClient
        client = _MockLLMClient()
        response = client.messages.create(model="test", max_tokens=100, messages=[])
        text = response.content[0].text
        parsed = json.loads(text)
        assert "stop" in parsed["whatsapp"]["template_body"].lower()
