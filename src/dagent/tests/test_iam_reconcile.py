"""IAM operation tests using in-memory provider transport."""
# pylint: disable=E1120,E1123

from __future__ import annotations

from dagent.models import DataAgentSpec, IAMBinding, IAMMode
from dagent.providers.google_gemini_data_analytics import (
    GoogleGeminiDataAnalyticsProvider,
    InMemoryProviderTransport,
)


def test_provider_sets_and_gets_iam_policy() -> None:
    provider = GoogleGeminiDataAnalyticsProvider(transport=InMemoryProviderTransport())
    resource = "projects/analytics-dev/locations/global/dataAgents/agent-one"
    bindings = (IAMBinding(role="roles/viewer", members=("group:analytics@example.com",)),)
    result = provider.set_iam_policy(resource=resource, bindings=bindings)
    assert result.success
    loaded = provider.get_iam_policy(resource=resource)
    assert loaded == bindings


def test_provider_upsert_and_list() -> None:
    provider = GoogleGeminiDataAnalyticsProvider(transport=InMemoryProviderTransport())
    spec = DataAgentSpec(
        name="agent-one",
        project_id="analytics-dev",
        location="global",
        instructions="Answer questions.",
        iam_mode=IAMMode.IGNORE,
    )
    result = provider.upsert_agent(spec=spec)
    assert result.success
    agents = provider.list_agents(project_id="analytics-dev", location="global")
    assert len(agents) == 1
    assert agents[0].name == "agent-one"
