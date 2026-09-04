"""Loads application configuration from a YAML file.

The config file is a nested map of keys to strings, committed to the repo.
Every string value is evaluated once at startup as a Jinja template using a
restrictive sandboxed environment whose only extra variable is `env` - a
read-only view of the environment variables. This keeps the config file
public while secrets are interpolated from the environment at runtime.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from os import environ, getenv
from pathlib import Path

import structlog
import yaml
from dotenv import load_dotenv
from jinja2 import StrictUndefined, Undefined
from jinja2.sandbox import ImmutableSandboxedEnvironment

load_dotenv()

logger = structlog.get_logger()


class ConfigError(Exception):
    """Raised when the config file is missing, unrenderable, or invalid."""


jinja_environment = ImmutableSandboxedEnvironment(
    autoescape=False,
    undefined=StrictUndefined,
)


class EnvVars:
    """Read-only attribute-style access to environment variables for templates.

    Missing variables resolve to Jinja's undefined, so the `default` filter can
    supply a fallback while using the value directly fails fast.
    """

    def __getattr__(self, name: str) -> str | Undefined:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return environ[name]
        except KeyError:
            return jinja_environment.undefined(name=f"env.{name}")

    def __getitem__(self, name: str) -> str:
        return environ[name]


EVENT_SLUG_PATTERN = re.compile(r"[a-z0-9-]+")
LABEL_NAME_PATTERN = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")
# Values that cannot break out of a PromQL string literal
LABEL_VALUE_PATTERN = re.compile(r"[A-Za-z0-9_.:/-]+")


@dataclass(frozen=True)
class EventConfig:
    slug: str
    nephthys_db_url: str
    prometheus_labels: dict[str, str]

    @property
    def prometheus_selector(self) -> str:
        """PromQL label selector, e.g. 'job="support_watcher_stardance"'"""
        return ",".join(
            f'{name}="{value}"' for name, value in self.prometheus_labels.items()
        )


@dataclass(frozen=True)
class AppConfig:
    prometheus_url: str
    host: str
    port: int
    events: dict[str, EventConfig]


def render_string(template: str, path: str) -> str:
    try:
        return jinja_environment.from_string(template).render(env=EnvVars())
    except Exception as e:
        raise ConfigError(f"Config key '{path}' could not be evaluated: {e}") from e


def render_tree(node: object, path: str) -> object:
    if isinstance(node, dict):
        rendered: dict[str, object] = {}
        for key, value in node.items():
            if not isinstance(key, str):
                raise ConfigError(
                    f"Config keys must be strings, got {key!r} of type {type(key).__name__}"
                )
            child_path = f"{path}.{key}" if path else key
            rendered[key] = render_tree(value, child_path)
        return rendered
    if isinstance(node, str):
        return render_string(node, path)
    raise ConfigError(
        f"Config key '{path}' must be a quoted string, but YAML parsed it as {type(node).__name__}"
    )


def expect_keys(
    node: dict, path: str, required: set[str], optional: Iterable[str] = ()
) -> None:
    def display(key: str) -> str:
        return f"{path}.{key}" if path else key

    missing = sorted(required - node.keys())
    if missing:
        missing_keys = ", ".join(display(key) for key in missing)
        raise ConfigError(f"Missing required config key(s): {missing_keys}")

    unknown = sorted(node.keys() - required - set(optional))
    if unknown:
        unknown_keys = ", ".join(display(key) for key in unknown)
        allowed_keys = ", ".join(sorted(required | set(optional)))
        raise ConfigError(
            f"Unknown config key(s): {unknown_keys} (allowed: {allowed_keys})"
        )


def parse_event(slug: str, node: dict) -> EventConfig:
    expect_keys(node, f"events.{slug}", {"nephthys_db_url", "prometheus_labels"})

    nephthys_db_url = node["nephthys_db_url"]
    if not nephthys_db_url:
        raise ConfigError(
            f"Config key 'events.{slug}.nephthys_db_url' must not be empty"
        )

    labels_node = node["prometheus_labels"]
    if not isinstance(labels_node, dict) or not labels_node:
        raise ConfigError(
            f"Config key 'events.{slug}.prometheus_labels' must be a non-empty mapping of label names to values"
        )

    labels: dict[str, str] = {}
    for name, value in labels_node.items():
        if not LABEL_NAME_PATTERN.fullmatch(name):
            raise ConfigError(
                f"Prometheus label name '{name}' (events.{slug}) is not valid"
            )
        if not LABEL_VALUE_PATTERN.fullmatch(value):
            raise ConfigError(
                f"Prometheus label value '{value}' (events.{slug}, label '{name}')"
                " contains characters that cannot be used safely in a PromQL selector"
            )
        labels[name] = value

    return EventConfig(
        slug=slug, nephthys_db_url=nephthys_db_url, prometheus_labels=labels
    )


def load_config() -> AppConfig:
    path = Path(getenv("CONFIG_PATH") or "config.yaml")
    if not path.is_file():
        raise ConfigError(
            f"Config file not found at '{path}' (set CONFIG_PATH to override the location)"
        )

    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"Config file '{path}' is not valid YAML: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError(
            "Config file must contain a mapping of keys to strings at the top level"
        )

    rendered = render_tree(raw, "")
    expect_keys(rendered, "", {"prometheus_url", "events"}, {"host", "port"})

    prometheus_url = rendered["prometheus_url"]
    if not prometheus_url:
        raise ConfigError("Config key 'prometheus_url' must not be empty")

    host = rendered.get("host") or "0.0.0.0"
    port_raw = rendered.get("port") or "8000"
    try:
        port = int(port_raw)
    except ValueError:
        raise ConfigError(
            f"Config key 'port' must be an integer between 1 and 65535, got '{port_raw}'"
        ) from None
    if not 1 <= port <= 65535:
        raise ConfigError(f"Config key 'port' must be between 1 and 65535, got {port}")

    events_node = rendered["events"]
    if not isinstance(events_node, dict) or not events_node:
        raise ConfigError(
            "Config key 'events' must be a non-empty mapping of event slugs to their config"
        )

    events: dict[str, EventConfig] = {}
    for slug, event_node in events_node.items():
        if not EVENT_SLUG_PATTERN.fullmatch(slug):
            raise ConfigError(
                f"Event slug '{slug}' must contain only lowercase letters, digits, and dashes"
            )
        if not isinstance(event_node, dict):
            raise ConfigError(
                f"Config key 'events.{slug}' must be a mapping of keys to strings"
            )
        events[slug] = parse_event(slug, event_node)

    logger.info("Loaded configuration", config_path=str(path), events=sorted(events))
    return AppConfig(
        prometheus_url=prometheus_url,
        host=host,
        port=port,
        events=events,
    )
