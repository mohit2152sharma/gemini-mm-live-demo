# Validates if the tool is properly defined or not

import inspect
from typing import Protocol, cast, get_type_hints

from google.genai import types

from .tools.base_tool import BaseTool


def check_attr(instance: object, attr_name: str) -> bool:
    try:
        return bool(getattr(instance, attr_name))
    except AttributeError:
        return False


class ToolValidationError(Exception):
    """Raised when a tool is incorrectly defined or is invalid"""

    def __init__(
        self,
        rule_name: str,
        rule_description: str | None = None,
        details: str | None = None,
        *args,
        **kwargs,
    ):
        message = (
            f"The tool is incorrectly defined. "
            f"Validating rule: {rule_name}, Rule description: {rule_description}"
        )
        if details:
            message = f"{message}, Details: {details}"
        super().__init__(message)


class ValidationRule(Protocol):

    @staticmethod
    def validate(tool: BaseTool) -> None: ...


class IsBaseTool:
    """Checks if the passed object is an instance of BaseTool"""

    @classmethod
    def validate(cls, tool: BaseTool) -> None:
        if not isinstance(tool, BaseTool):
            raise ToolValidationError(
                cls.__name__,
                cls.__doc__,
                details=f"Expected BaseTool instance, got {type(tool).__name__}",
            )


class DeclarationHasNameField:
    """Checks if the function declaration has a name field or not"""

    @classmethod
    def validate(cls, tool: BaseTool) -> None:
        declaration = tool.declaration
        if not check_attr(declaration, "name"):
            raise ToolValidationError(
                cls.__name__,
                cls.__doc__,
                details="Missing field: 'name' in declaration",
            )


class DeclarationHasDescriptionField:
    """Checks if the function declaration has a description field or not"""

    @classmethod
    def validate(cls, tool: BaseTool) -> None:
        declaration = tool.declaration
        if not check_attr(declaration, "description"):
            raise ToolValidationError(
                cls.__name__,
                cls.__doc__,
                details="Missing field: 'description' in declaration",
            )


class DeclarationImplementationHasSameName:
    """Checks if both function declaration and function implementation have the same name"""

    @classmethod
    def validate(cls, tool: BaseTool) -> None:
        declaration = tool.declaration
        implementation = tool.implementation
        decl_name = declaration.name
        impl_name = implementation.__name__
        print(f"impl_name: {impl_name}")
        print(f"decl_name: {decl_name}")

        if impl_name != decl_name:
            raise ToolValidationError(
                cls.__name__,
                cls.__doc__,
                details=f"Declaration name '{decl_name}' != implementation name '{impl_name}'",
            )


class DeclarationImplementationHasSameArguments:
    """Checks if both declaration and implementation has same arguments"""

    @classmethod
    def validate(cls, tool: BaseTool) -> None:
        declaration = tool.declaration
        implementation = tool.implementation
        params = getattr(declaration, "parameters", None)
        props = getattr(params, "properties", None) if params is not None else None
        decl_args = set(props.keys()) if isinstance(props, dict) else set()
        impl_args = set(inspect.getfullargspec(implementation).args) - {
            "self",
            "session",
            "queue",
        }

        if decl_args != impl_args:
            missing_in_impl = sorted(decl_args - impl_args)
            extra_in_impl = sorted(impl_args - decl_args)
            parts = []
            if missing_in_impl:
                parts.append(f"missing in implementation: {missing_in_impl}")
            if extra_in_impl:
                parts.append(f"extra in implementation: {extra_in_impl}")
            raise ToolValidationError(
                cls.__name__,
                cls.__doc__,
                details="; ".join(parts) or "argument sets differ",
            )


class DeclarationImplementationArgsHasSameType:
    """Checks if the types of arguments declared in both declaration and implementation are the same"""

    @classmethod
    def validate(cls, tool: BaseTool) -> None:
        declaration = tool.declaration
        implementation = tool.implementation
        # Map declaration schema types to python types expected in annotations
        type_map = {
            types.Type.STRING: str,
            types.Type.NUMBER: float,
            types.Type.INTEGER: int,
            types.Type.BOOLEAN: bool,
            types.Type.OBJECT: dict,
            types.Type.ARRAY: list,
        }
        params = getattr(declaration, "parameters", None)
        props = getattr(params, "properties", None) if params is not None else None
        decl_props = props if isinstance(props, dict) else {}
        annotations = get_type_hints(implementation)

        for arg_name, schema in decl_props.items():
            schema_type = cast(types.Type, getattr(schema, "type", None))
            expected_py_type = type_map.get(schema_type)
            actual_ann = annotations.get(arg_name)

            if (
                expected_py_type is None
                or actual_ann is None
                or expected_py_type is not actual_ann
            ):
                exp = getattr(expected_py_type, "__name__", str(expected_py_type))
                got = getattr(actual_ann, "__name__", str(actual_ann))
                raise ToolValidationError(
                    cls.__name__,
                    cls.__doc__,
                    details=f"Param '{arg_name}' expected type {exp} but got {got}.\nRefer these type mappings: {type_map}",
                )


class DeclarationImplementationHasSameReqdArgs:
    """Checks if both declaration and implementation has same required arguments"""

    @classmethod
    def validate(cls, tool: BaseTool) -> None:
        declaration = tool.declaration
        implementation = tool.implementation
        params = getattr(declaration, "parameters", None)
        req = getattr(params, "required", None) if params is not None else None
        required = set(req or [])

        sig = inspect.signature(implementation)
        ignored = {"self", "session", "queue"}

        for arg in required:
            if arg not in sig.parameters:
                raise ToolValidationError(
                    cls.__name__,
                    cls.__doc__,
                    details=f"Required param '{arg}' declared but missing in implementation",
                )
            param = sig.parameters[arg]
            if param.default is not inspect._empty:
                raise ToolValidationError(
                    cls.__name__,
                    cls.__doc__,
                    details=f"Param '{arg}' is declared required but has a default in implementation",
                )

        impl_required = set(
            name
            for name, p in sig.parameters.items()
            if name not in ignored
            and p.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
            and p.default is inspect._empty
        )

        extra_required = impl_required - required
        if extra_required:
            raise ToolValidationError(
                cls.__name__,
                cls.__doc__,
                details=f"Implementation has extra required params not declared required: {sorted(extra_required)}",
            )


RULES = [
    IsBaseTool,
    DeclarationHasNameField,
    DeclarationHasDescriptionField,
    # DeclarationImplementationHasSameName,
    DeclarationImplementationHasSameArguments,
    DeclarationImplementationArgsHasSameType,
    DeclarationImplementationHasSameReqdArgs,
]


class ToolValidator:
    def __init__(
        self,
        tool: BaseTool,
        rules: list[ValidationRule] = RULES,
    ) -> None:
        self.tool = tool
        self.rules = rules

    def validate(self):
        for rule in self.rules:
            rule.validate(self.tool)
