import json
import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import InstructionNotFoundError
from jupyter_deploy.provider.aws.aws_elbv2_runner import AwsElbv2Runner
from jupyter_deploy.provider.resolved_argdefs import StrResolvedInstructionArgument


def _make_args(tags: dict[str, str], resource_type_filter: str = "elasticloadbalancing:loadbalancer") -> dict:
    return {
        "tags": StrResolvedInstructionArgument(argument_name="tags", value=json.dumps(tags)),
        "resource_type_filter": StrResolvedInstructionArgument(
            argument_name="resource_type_filter", value=resource_type_filter
        ),
    }


class _LoadBalancerNotFoundException(ClientError):
    pass


def _access_denied_error() -> ClientError:
    return ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "Access Denied"}},
        "DescribeLoadBalancers",
    )


class TestAwsElbv2RunnerDescribeHealth(unittest.TestCase):
    @patch("jupyter_deploy.provider.aws.aws_elbv2_runner.tagging")
    @patch("jupyter_deploy.provider.aws.aws_elbv2_runner.elbv2_load_balancer")
    @patch("jupyter_deploy.provider.aws.aws_elbv2_runner.boto3")
    def test_returns_active_nlb(self, mock_boto3: Mock, mock_elbv2_lb: Mock, mock_tagging: Mock) -> None:
        mock_client: Mock = Mock()
        mock_boto3.client.return_value = mock_client
        mock_tagging.find_resource_arns_by_tags.return_value = ["arn:aws:elasticloadbalancing:us-west-2:123:lb/net/x/y"]
        mock_elbv2_lb.describe_load_balancer.return_value = {
            "Type": "network",
            "Scheme": "internet-facing",
            "State": {"Code": "active"},
        }

        runner = AwsElbv2Runner(NullDisplay(), region_name="us-west-2")
        result = runner.execute_instruction("describe-load-balancer-health", _make_args({"k": "v"}))

        self.assertEqual(result["State"].value, "active")
        self.assertEqual(result["Label"].value, "AWS NLB")
        self.assertEqual(result["Scheme"].value, "internet-facing")

    @patch("jupyter_deploy.provider.aws.aws_elbv2_runner.tagging")
    @patch("jupyter_deploy.provider.aws.aws_elbv2_runner.elbv2_load_balancer")
    @patch("jupyter_deploy.provider.aws.aws_elbv2_runner.boto3")
    def test_returns_alb_label(self, mock_boto3: Mock, mock_elbv2_lb: Mock, mock_tagging: Mock) -> None:
        mock_boto3.client.return_value = Mock()
        mock_tagging.find_resource_arns_by_tags.return_value = ["arn:lb"]
        mock_elbv2_lb.describe_load_balancer.return_value = {
            "Type": "application",
            "Scheme": "internal",
            "State": {"Code": "active"},
        }

        runner = AwsElbv2Runner(NullDisplay(), region_name="us-west-2")
        result = runner.execute_instruction("describe-load-balancer-health", _make_args({"k": "v"}))

        self.assertEqual(result["Label"].value, "AWS ALB")

    @patch("jupyter_deploy.provider.aws.aws_elbv2_runner.tagging")
    @patch("jupyter_deploy.provider.aws.aws_elbv2_runner.boto3")
    def test_returns_not_found_when_no_arns(self, mock_boto3: Mock, mock_tagging: Mock) -> None:
        mock_boto3.client.return_value = Mock()
        mock_tagging.find_resource_arns_by_tags.return_value = []

        runner = AwsElbv2Runner(NullDisplay(), region_name="us-west-2")
        result = runner.execute_instruction("describe-load-balancer-health", _make_args({"k": "v"}))

        self.assertEqual(result["State"].value, "not-found")
        self.assertEqual(result["Label"].value, "")
        self.assertEqual(result["Scheme"].value, "")

    @patch("jupyter_deploy.provider.aws.aws_elbv2_runner.tagging")
    @patch("jupyter_deploy.provider.aws.aws_elbv2_runner.elbv2_load_balancer")
    @patch("jupyter_deploy.provider.aws.aws_elbv2_runner.boto3")
    def test_returns_not_found_on_load_balancer_not_found_exception(
        self, mock_boto3: Mock, mock_elbv2_lb: Mock, mock_tagging: Mock
    ) -> None:
        mock_client: Mock = Mock()
        mock_client.exceptions.LoadBalancerNotFoundException = _LoadBalancerNotFoundException
        mock_boto3.client.return_value = mock_client
        mock_tagging.find_resource_arns_by_tags.return_value = ["arn:lb/deleted"]
        mock_elbv2_lb.describe_load_balancer.side_effect = _LoadBalancerNotFoundException(
            {"Error": {"Code": "LoadBalancerNotFound", "Message": "Not found"}},
            "DescribeLoadBalancers",
        )

        runner = AwsElbv2Runner(NullDisplay(), region_name="us-west-2")
        result = runner.execute_instruction("describe-load-balancer-health", _make_args({"k": "v"}))

        self.assertEqual(result["State"].value, "not-found")
        self.assertEqual(result["Label"].value, "")
        self.assertEqual(result["Scheme"].value, "")

    @patch("jupyter_deploy.provider.aws.aws_elbv2_runner.tagging")
    @patch("jupyter_deploy.provider.aws.aws_elbv2_runner.elbv2_load_balancer")
    @patch("jupyter_deploy.provider.aws.aws_elbv2_runner.boto3")
    def test_raises_on_other_client_error(self, mock_boto3: Mock, mock_elbv2_lb: Mock, mock_tagging: Mock) -> None:
        mock_client: Mock = Mock()
        mock_client.exceptions.LoadBalancerNotFoundException = _LoadBalancerNotFoundException
        mock_boto3.client.return_value = mock_client
        mock_tagging.find_resource_arns_by_tags.return_value = ["arn:lb/exists"]
        mock_elbv2_lb.describe_load_balancer.side_effect = _access_denied_error()

        runner = AwsElbv2Runner(NullDisplay(), region_name="us-west-2")

        with self.assertRaises(ClientError) as ctx:
            runner.execute_instruction("describe-load-balancer-health", _make_args({"k": "v"}))

        self.assertEqual(ctx.exception.response["Error"]["Code"], "AccessDeniedException")

    @patch("jupyter_deploy.provider.aws.aws_elbv2_runner.boto3")
    def test_unknown_instruction_raises(self, mock_boto3: Mock) -> None:
        mock_boto3.client.return_value = Mock()

        runner = AwsElbv2Runner(NullDisplay(), region_name="us-west-2")

        with self.assertRaises(InstructionNotFoundError):
            runner.execute_instruction("bogus-instruction", {})
