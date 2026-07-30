from typing import List, Optional, Dict
from models import ToolDefinition, PromptContext, PromptMode
from prompt_registry import prompt_registry


def validate_tool(tool: ToolDefinition) -> None:
    errors = []

    if not tool.id:
        errors.append("id is required")
    if not tool.name:
        errors.append("name is required")
    if not tool.workflow:
        errors.append("workflow is required")
    if not tool.prompt_builder_id:
        errors.append("prompt_builder_id is required")
    if tool.daily_limit <= 0:
        errors.append(f"daily_limit must be > 0, got {tool.daily_limit}")

    if tool.workflow:
        if not tool.workflow.id:
            errors.append("workflow.id is required")
        if not tool.workflow.steps:
            errors.append("workflow.steps is required")

        step_ids = {step.id for step in tool.workflow.steps}
        for step in tool.workflow.steps:
            if not step.id:
                errors.append(f"step.id is required in workflow '{tool.workflow.id}'")
            if not step.field:
                errors.append(f"step.field is required in step '{step.id}'")
            if step.next_step_id and step.next_step_id not in step_ids:
                errors.append(f"Step '{step.id}' references unknown next_step_id '{step.next_step_id}'")
            for transition in step.transitions:
                if transition.next_step_id not in step_ids:
                    errors.append(f"Transition from '{step.id}' references unknown step '{transition.next_step_id}'")

    if not tool.category:
        errors.append("category is required")

    if tool.prompt_builder_id:
        builder = prompt_registry.get(tool.prompt_builder_id)
        if not builder:
            errors.append(f"prompt_builder_id '{tool.prompt_builder_id}' not found in PromptRegistry")

    if tool.required_fields and not tool.input_adapter:
        errors.append("input_adapter is required when required_fields is defined")

    if tool.provider_type not in ["text", "image"]:
        errors.append(f"Unknown provider_type: {tool.provider_type}")

    if errors:
        raise ValueError(f"Invalid tool definition '{tool.id}':\n" + "\n".join(f"  - {e}" for e in errors))


def validate_all_tools(tools: List[ToolDefinition]) -> bool:
    for tool in tools:
        validate_tool(tool)
    return True


def validate_prompt_builder(tool: ToolDefinition) -> None:
    builder_class = prompt_registry.get(tool.prompt_builder_id)
    if not builder_class:
        raise ValueError(f"Builder '{tool.prompt_builder_id}' not found for '{tool.id}'")

    try:
        builder = builder_class()
        context = PromptContext(
            mode=PromptMode.INITIAL,
            data=tool.test_input or {}
        )
        result = builder.build(context)
        if not isinstance(result, str):
            raise ValueError(f"Builder '{tool.prompt_builder_id}' returned {type(result)}, expected str")
    except Exception as e:
        raise ValueError(f"Builder '{tool.prompt_builder_id}' failed: {e}")