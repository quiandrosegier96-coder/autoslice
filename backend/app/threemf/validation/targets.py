"""Target-aware validation registry, independent from source parsing."""

from abc import ABC, abstractmethod

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.detection import detect_3mf
from app.threemf.domain.metadata import SlicerType
from app.threemf.validation.package import ValidationResult, validate_3mf


class TargetValidator(ABC):
    @abstractmethod
    def can_validate(self, target: SlicerType) -> bool:
        raise NotImplementedError

    @abstractmethod
    def validate(self, payload: bytes) -> ValidationResult:
        raise NotImplementedError


class AnycubicTargetValidator(TargetValidator):
    def can_validate(self, target: SlicerType) -> bool:
        return target is SlicerType.ANYCUBIC

    def validate(self, payload: bytes) -> ValidationResult:
        result = validate_3mf(payload)
        if not result.valid:
            return result
        container = ThreeMFContainer.from_bytes(payload)
        if detect_3mf(container).slicer is not SlicerType.ANYCUBIC:
            raise ValueError("Output is valid 3MF but not an identifiable Anycubic project.")
        return result


class TargetValidatorRegistry:
    def __init__(self, validators: tuple[TargetValidator, ...] = ()) -> None:
        self._validators = validators

    def validate(self, target: SlicerType, payload: bytes) -> ValidationResult:
        validator = next((item for item in self._validators if item.can_validate(target)), None)
        if validator is None:
            raise ValueError(f"No target validator registered for '{target.value}'.")
        return validator.validate(payload)


def default_target_validator_registry() -> TargetValidatorRegistry:
    return TargetValidatorRegistry((AnycubicTargetValidator(),))
