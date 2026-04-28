# Copyright 2025 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Simple metrics counters for dagent command paths."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MetricsCollector:
    """In-process metrics collector for command counters."""

    counters: dict[str, int] = field(default_factory=dict)

    def increment(self, name: str, value: int = 1) -> None:
        """Increment metric counter."""
        self.counters[name] = self.counters.get(name, 0) + value

    def snapshot(self) -> dict[str, int]:
        """Return a snapshot of current counters."""
        return dict(self.counters)


METRICS = MetricsCollector()
