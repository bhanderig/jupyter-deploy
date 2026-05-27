import json
from enum import Enum

import boto3
from mypy_boto3_elbv2.client import ElasticLoadBalancingv2Client
from mypy_boto3_resourcegroupstaggingapi.client import ResourceGroupsTaggingAPIClient

from jupyter_deploy.api.aws.elbv2 import elbv2_load_balancer
from jupyter_deploy.api.aws.resourcegroupstagging import tagging
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.exceptions import InstructionNotFoundError
from jupyter_deploy.provider.instruction_runner import InstructionRunner
from jupyter_deploy.provider.resolved_argdefs import (
    ResolvedInstructionArgument,
    StrResolvedInstructionArgument,
    require_arg,
)
from jupyter_deploy.provider.resolved_resultdefs import (
    ResolvedInstructionResult,
    StrResolvedInstructionResult,
)


class AwsElbv2Instruction(str, Enum):
    """AWS ELBv2 instructions accessible from manifest.commands[].sequence[].api-name."""

    DESCRIBE_LOAD_BALANCER_HEALTH = "describe-load-balancer-health"


class AwsElbv2Runner(InstructionRunner):
    """Runner class for AWS ELBv2 service API instructions."""

    def __init__(self, display_manager: DisplayManager, region_name: str | None) -> None:
        super().__init__(display_manager)
        self.region_name = region_name
        self.elbv2_client: ElasticLoadBalancingv2Client = boto3.client("elbv2", region_name=region_name)
        self.tagging_client: ResourceGroupsTaggingAPIClient = boto3.client(
            "resourcegroupstaggingapi", region_name=region_name
        )

    def _describe_load_balancer_health(
        self, resolved_arguments: dict[str, ResolvedInstructionArgument]
    ) -> dict[str, ResolvedInstructionResult]:
        tags_arg = require_arg(resolved_arguments, "tags", StrResolvedInstructionArgument)
        resource_type_filter_arg = require_arg(
            resolved_arguments, "resource_type_filter", StrResolvedInstructionArgument
        )

        tags: dict[str, str] = json.loads(tags_arg.value)
        resource_type_filter = resource_type_filter_arg.value

        self.display_manager.info("Looking up load balancer by tags")
        lb_arns = tagging.find_resource_arns_by_tags(self.tagging_client, tags, resource_type_filter)

        if not lb_arns:
            return {
                "State": StrResolvedInstructionResult(result_name="State", value="not-found"),
                "Label": StrResolvedInstructionResult(result_name="Label", value=""),
                "Scheme": StrResolvedInstructionResult(result_name="Scheme", value=""),
            }

        self.display_manager.info("Checking load balancer state")
        try:
            lb = elbv2_load_balancer.describe_load_balancer(self.elbv2_client, lb_arns[0])
        except self.elbv2_client.exceptions.LoadBalancerNotFoundException:
            return {
                "State": StrResolvedInstructionResult(result_name="State", value="not-found"),
                "Label": StrResolvedInstructionResult(result_name="Label", value=""),
                "Scheme": StrResolvedInstructionResult(result_name="Scheme", value=""),
            }

        state_obj = lb.get("State", {})
        state = state_obj.get("Code", "unknown") if isinstance(state_obj, dict) else "unknown"
        lb_type = lb.get("Type", "")
        scheme = lb.get("Scheme", "")

        lb_type_labels = {"network": "AWS NLB", "application": "AWS ALB", "gateway": "AWS GWLB"}
        label = lb_type_labels.get(lb_type, f"AWS {lb_type}")

        return {
            "State": StrResolvedInstructionResult(result_name="State", value=state),
            "Label": StrResolvedInstructionResult(result_name="Label", value=label),
            "Scheme": StrResolvedInstructionResult(result_name="Scheme", value=scheme),
        }

    def execute_instruction(
        self,
        instruction_name: str,
        resolved_arguments: dict[str, ResolvedInstructionArgument],
    ) -> dict[str, ResolvedInstructionResult]:
        try:
            instruction = AwsElbv2Instruction(instruction_name)
        except ValueError:
            raise InstructionNotFoundError(f"Unknown ELBv2 instruction: '{instruction_name}'") from None

        if instruction == AwsElbv2Instruction.DESCRIBE_LOAD_BALANCER_HEALTH:
            return self._describe_load_balancer_health(resolved_arguments)

        raise InstructionNotFoundError(f"Unknown ELBv2 instruction: '{instruction_name}'")
