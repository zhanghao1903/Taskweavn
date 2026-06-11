"""Product 1.1 workspace inspection limits."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceInspectionLimits:
    status_default_max_files: int = 200
    status_hard_max_files: int = 500
    file_default_line_count: int = 200
    file_hard_line_count: int = 1000
    file_text_payload_bytes: int = 256 * 1024
    readable_text_file_bytes: int = 1024 * 1024
    single_line_bytes: int = 8 * 1024
    diff_default_context_lines: int = 3
    diff_hard_context_lines: int = 8
    diff_default_payload_bytes: int = 256 * 1024
    diff_hard_payload_bytes: int = 512 * 1024
    evidence_payload_bytes: int = 128 * 1024
    precision_search_default_max_files: int = 50
    precision_search_hard_max_files: int = 200
    precision_search_default_max_matches: int = 200
    precision_search_hard_max_matches: int = 1000
    precision_write_max_replacement_bytes: int = 256 * 1024
    precision_write_max_append_bytes: int = 128 * 1024

    def status_limit(self, requested: int | None) -> int:
        value = self.status_default_max_files if requested is None else requested
        return max(0, min(value, self.status_hard_max_files))

    def line_count_limit(self, requested: int | None) -> int:
        value = self.file_default_line_count if requested is None else requested
        return max(1, min(value, self.file_hard_line_count))

    def context_line_limit(self, requested: int | None) -> int:
        value = self.diff_default_context_lines if requested is None else requested
        return max(0, min(value, self.diff_hard_context_lines))

    def diff_payload_limit(self, requested: int | None) -> int:
        value = self.diff_default_payload_bytes if requested is None else requested
        return max(1, min(value, self.diff_hard_payload_bytes))

    def search_file_limit(self, requested: int | None) -> int:
        value = self.precision_search_default_max_files if requested is None else requested
        return max(0, min(value, self.precision_search_hard_max_files))

    def search_match_limit(self, requested: int | None) -> int:
        value = self.precision_search_default_max_matches if requested is None else requested
        return max(0, min(value, self.precision_search_hard_max_matches))
