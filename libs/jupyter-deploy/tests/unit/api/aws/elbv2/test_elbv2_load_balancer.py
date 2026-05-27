import unittest
from unittest.mock import Mock

from botocore.exceptions import ClientError
from mypy_boto3_elbv2.client import ElasticLoadBalancingv2Client

from jupyter_deploy.api.aws.elbv2 import elbv2_load_balancer


def _not_found_error() -> ClientError:
    return ClientError(
        {"Error": {"Code": "LoadBalancerNotFound", "Message": "Load balancer not found"}},
        "DescribeLoadBalancers",
    )


class TestDescribeLoadBalancer(unittest.TestCase):
    def test_returns_load_balancer(self) -> None:
        mock_client: Mock = Mock(spec=ElasticLoadBalancingv2Client)
        mock_client.describe_load_balancers.return_value = {
            "LoadBalancers": [
                {
                    "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-west-2:123:loadbalancer/net/my-lb/abc",
                    "DNSName": "my-lb-abc.elb.us-west-2.amazonaws.com",
                    "Type": "network",
                    "Scheme": "internet-facing",
                    "State": {"Code": "active"},
                }
            ]
        }

        result = elbv2_load_balancer.describe_load_balancer(
            mock_client, "arn:aws:elasticloadbalancing:us-west-2:123:loadbalancer/net/my-lb/abc"
        )

        self.assertEqual(result["Type"], "network")
        self.assertEqual(result["Scheme"], "internet-facing")
        self.assertEqual(result["State"], {"Code": "active"})
        mock_client.describe_load_balancers.assert_called_once_with(
            LoadBalancerArns=["arn:aws:elasticloadbalancing:us-west-2:123:loadbalancer/net/my-lb/abc"]
        )

    def test_raises_on_client_error(self) -> None:
        mock_client: Mock = Mock(spec=ElasticLoadBalancingv2Client)
        mock_client.describe_load_balancers.side_effect = _not_found_error()

        with self.assertRaises(ClientError):
            elbv2_load_balancer.describe_load_balancer(
                mock_client, "arn:aws:elasticloadbalancing:us-west-2:123:loadbalancer/net/gone/xyz"
            )
