"""Skill descriptor registry and configured-root scanner."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

from taskweavn.skills.models import (
    SkillDescriptor,
    SkillRegistrySnapshot,
    SkillResourceKind,
    SkillResourceRef,
    SkillSourceScope,
    SkillToolPolicy,
    SkillTrustLevel,
)


class SkillRegistryError(ValueError):
    """Raised when a skill descriptor cannot be parsed or validated."""


@dataclass(frozen=True)
class SkillRootConfig:
    root_path: Path
    source_scope: SkillSourceScope = "workspace"
    trust_level: SkillTrustLevel = "repo_trusted"
    enabled: bool = True
    implicit_invocation_default: bool = True


@dataclass(frozen=True)
class SkillRegistryConfig:
    roots: tuple[SkillRootConfig, ...] = ()
    workspace_id: str | None = None
    allow_untrusted: bool = False
    max_skills: int = 100


@dataclass(frozen=True)
class SkillRegistry:
    """Immutable registry snapshot plus deterministic lookup helpers."""

    snapshot: SkillRegistrySnapshot

    @classmethod
    def from_descriptors(
        cls,
        descriptors: tuple[SkillDescriptor, ...],
        *,
        workspace_id: str | None = None,
        warnings: tuple[str, ...] = (),
    ) -> SkillRegistry:
        ordered = tuple(
            sorted(
                descriptors,
                key=lambda descriptor: (
                    descriptor.source_scope,
                    descriptor.name,
                    descriptor.source_ref,
                    descriptor.skill_id,
                ),
            )
        )
        return cls(
            SkillRegistrySnapshot(
                workspace_id=workspace_id,
                descriptors=ordered,
                warnings=warnings,
            )
        )

    @classmethod
    def scan(cls, config: SkillRegistryConfig) -> SkillRegistry:
        descriptors: list[SkillDescriptor] = []
        warnings: list[str] = []
        for root in config.roots:
            root_path = root.root_path.expanduser()
            if not root_path.exists():
                warnings.append(f"skill_root_missing:{root_path}")
                continue
            if not root_path.is_dir():
                warnings.append(f"skill_root_not_directory:{root_path}")
                continue
            for skill_file in sorted(root_path.glob("*/SKILL.md")):
                if len(descriptors) >= config.max_skills:
                    warnings.append("max_skills_exceeded")
                    break
                try:
                    descriptor = _descriptor_from_skill_file(
                        skill_file,
                        root=root,
                        allow_untrusted=config.allow_untrusted,
                    )
                except SkillRegistryError as exc:
                    warnings.append(f"{skill_file}:{exc}")
                    continue
                descriptors.append(descriptor)
        return cls.from_descriptors(
            tuple(descriptors),
            workspace_id=config.workspace_id,
            warnings=tuple(warnings),
        )

    def list_descriptors(self) -> tuple[SkillDescriptor, ...]:
        return self.snapshot.descriptors

    def get(self, skill_id: str) -> SkillDescriptor | None:
        for descriptor in self.snapshot.descriptors:
            if descriptor.skill_id == skill_id:
                return descriptor
        return None

    def find_candidates(self, capability: str | None) -> tuple[SkillDescriptor, ...]:
        if not capability:
            return ()
        needle = capability.strip().lower()
        if not needle:
            return ()
        candidates = [
            descriptor
            for descriptor in self.snapshot.descriptors
            if descriptor.enabled
            and descriptor.implicit_invocation
            and _descriptor_matches_capability(descriptor, needle)
        ]
        return tuple(
            sorted(
                candidates,
                key=lambda descriptor: (
                    descriptor.source_scope,
                    descriptor.name,
                    descriptor.skill_id,
                ),
            )
        )


def precision_file_editing_descriptor() -> SkillDescriptor:
    """Built-in internal skill proof for precision file tools."""

    name = "precision-file-editing"
    description = (
        "Use when executing coding tasks that should prefer bounded line-range "
        "read, search, replace, and append operations over full-file writes."
    )
    source_ref = "internal://skills/precision-file-editing"
    content_hash = _hash_text(f"{name}\n{description}\n{source_ref}")
    return SkillDescriptor(
        skill_id="internal:precision-file-editing",
        name=name,
        description=description,
        source_scope="internal",
        source_ref=source_ref,
        content_hash=content_hash,
        trust_level="trusted",
        tool_policy=SkillToolPolicy(
            requested_tools=(
                "read_file_range",
                "search_workspace",
                "replace_file_range",
                "append_file",
            ),
            requires_approval=("replace_file_range", "append_file"),
        ),
        context_requirements=("coding", "precision_file_tools"),
        risk_tags=("file_write", "workspace_mutation"),
        output_contract="Prefer line-scoped file operations and report changed line ranges.",
    )


def _descriptor_from_skill_file(
    skill_file: Path,
    *,
    root: SkillRootConfig,
    allow_untrusted: bool,
) -> SkillDescriptor:
    skill_file = skill_file.resolve()
    root_path = root.root_path.expanduser().resolve()
    if not _is_relative_to(skill_file, root_path):
        raise SkillRegistryError("skill_file_outside_root")
    raw = skill_file.read_text(encoding="utf-8")
    frontmatter, _body = _parse_frontmatter(raw)
    name = _required_str(frontmatter, "name")
    description = _required_str(frontmatter, "description")
    metadata_enabled = cast(bool, _optional_bool(frontmatter, "enabled", default=True))
    metadata_implicit = _optional_bool(frontmatter, "implicit_invocation", default=None)
    openai_metadata = _load_openai_metadata(skill_file.parent)
    if metadata_implicit is None:
        metadata_implicit = _openai_implicit_invocation(openai_metadata)
    if metadata_implicit is None:
        metadata_implicit = root.implicit_invocation_default
    trust_level = root.trust_level
    if trust_level == "untrusted" and not allow_untrusted:
        raise SkillRegistryError("skill_untrusted")
    skill_id = _optional_str(frontmatter, "skill_id") or (
        f"{root.source_scope}:{_slug(name)}:{_short_hash(str(skill_file))}"
    )
    content_hash = _hash_files((skill_file, *tuple(_metadata_files(skill_file.parent))))
    resource_refs = _resource_refs(skill_file.parent, skill_id=skill_id)
    return SkillDescriptor(
        skill_id=skill_id,
        name=name,
        description=description,
        source_scope=root.source_scope,
        source_ref=str(skill_file),
        root_path=str(skill_file.parent),
        skill_file_path=str(skill_file),
        content_hash=content_hash,
        enabled=root.enabled and metadata_enabled,
        implicit_invocation=metadata_implicit,
        trust_level=trust_level,
        tool_policy=SkillToolPolicy(
            requested_tools=_string_tuple(
                frontmatter.get("requested_tools", frontmatter.get("tool_requirements"))
            ),
            denied_tools=_string_tuple(
                frontmatter.get("denied_tools", frontmatter.get("tool_denials"))
            ),
            requires_approval=_string_tuple(
                frontmatter.get("requires_approval", frontmatter.get("approval_requirements"))
            ),
            file_scopes=_string_tuple(frontmatter.get("file_scopes")),
        ),
        context_requirements=_string_tuple(frontmatter.get("context_requirements")),
        resource_refs=resource_refs,
        risk_tags=_string_tuple(frontmatter.get("risk_tags")),
        output_contract=_optional_str(frontmatter, "output_contract"),
    )


def _parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---\n"):
        raise SkillRegistryError("frontmatter_missing")
    end = raw.find("\n---", 4)
    if end == -1:
        raise SkillRegistryError("frontmatter_unclosed")
    header = raw[4:end]
    body = raw[end + 4 :].lstrip("\n")
    loaded = yaml.safe_load(header) or {}
    if not isinstance(loaded, dict):
        raise SkillRegistryError("frontmatter_not_mapping")
    return loaded, body


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SkillRegistryError(f"{key}_missing")
    return value.strip()


def _optional_str(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SkillRegistryError(f"{key}_invalid")
    return value.strip()


def _optional_bool(data: dict[str, Any], key: str, *, default: bool | None) -> bool | None:
    value = data.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise SkillRegistryError(f"{key}_invalid")
    return value


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, list):
        values: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise SkillRegistryError("string_list_invalid")
            values.append(item.strip())
        return tuple(values)
    raise SkillRegistryError("string_list_invalid")


def _load_openai_metadata(skill_root: Path) -> dict[str, Any]:
    path = skill_root / "agents" / "openai.yaml"
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return loaded if isinstance(loaded, dict) else {}


def _openai_implicit_invocation(metadata: dict[str, Any]) -> bool | None:
    policy = metadata.get("policy")
    if not isinstance(policy, dict):
        return None
    value = policy.get("allow_implicit_invocation")
    return value if isinstance(value, bool) else None


def _metadata_files(skill_root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    openai_metadata = skill_root / "agents" / "openai.yaml"
    if openai_metadata.exists():
        files.append(openai_metadata)
    return tuple(files)


def _resource_refs(skill_root: Path, *, skill_id: str) -> tuple[SkillResourceRef, ...]:
    refs: list[SkillResourceRef] = []
    for folder, kind in (
        ("references", "reference"),
        ("scripts", "script"),
        ("assets", "asset"),
        ("templates", "template"),
    ):
        root = skill_root / folder
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            resolved = path.resolve()
            if not _is_relative_to(resolved, skill_root.resolve()):
                continue
            relative = resolved.relative_to(skill_root.resolve()).as_posix()
            refs.append(
                SkillResourceRef(
                    ref_id=f"{skill_id}:{relative}",
                    kind=cast(SkillResourceKind, kind),
                    path=relative,
                    content_hash=_hash_file(resolved),
                    can_act_as_instruction=(kind in {"reference", "template"}),
                )
            )
    return tuple(refs)


def _descriptor_matches_capability(descriptor: SkillDescriptor, needle: str) -> bool:
    haystack = " ".join(
        (
            descriptor.skill_id,
            descriptor.name,
            descriptor.description,
            " ".join(descriptor.context_requirements),
            " ".join(descriptor.risk_tags),
        )
    ).lower()
    normalized_needle = needle.replace("-", "_")
    return needle in haystack or normalized_needle in haystack.replace("-", "_")


def _slug(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "-" for char in value.strip()]
    slug = "-".join(part for part in "".join(chars).split("-") if part)
    return slug or "skill"


def _hash_files(paths: tuple[Path, ...]) -> str:
    hasher = hashlib.sha256()
    for path in paths:
        hasher.update(path.as_posix().encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return f"sha256:{hasher.hexdigest()}"


def _hash_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _hash_text(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
