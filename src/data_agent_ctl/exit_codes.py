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

"""Exit codes used by the data-agent-ctl CLI."""

from enum import IntEnum


class ExitCode(IntEnum):
    """Stable machine-oriented exit codes for data-agent-ctl commands."""

    SUCCESS = 0
    FAILURE = 1
    VALIDATION_FAILED = 2
    DRIFT_DETECTED = 3
    FORBIDDEN_ACTION = 4
    AUTH_FAILURE = 5
    API_ERROR = 6
    STALE_PLAN = 7
    PARTIAL_APPLY_FAILURE = 8
