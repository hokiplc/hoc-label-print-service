"""Template registry. Only explicitly registered, enabled templates can be used —
callers can never reference arbitrary code or files via the template name."""
from __future__ import annotations

from app.config import Settings

from .base import LabelTemplate
from .house_of_coffee_62mm import HouseOfCoffee62mmTemplate

_REGISTRY: dict[str, type[LabelTemplate]] = {
    HouseOfCoffee62mmTemplate.name: HouseOfCoffee62mmTemplate,
}


class UnknownTemplateError(ValueError):
    pass


class TemplateDisabledError(ValueError):
    pass


def list_templates(settings: Settings) -> list[str]:
    return [name for name in _REGISTRY if name in settings.enabled_templates]


def get_template(name: str, settings: Settings) -> LabelTemplate:
    if name not in _REGISTRY:
        raise UnknownTemplateError(f"Unknown template: {name}")
    if name not in settings.enabled_templates:
        raise TemplateDisabledError(f"Template not enabled: {name}")
    template_cls = _REGISTRY[name]
    return template_cls(settings.font_dir, settings.constants_for(name))
