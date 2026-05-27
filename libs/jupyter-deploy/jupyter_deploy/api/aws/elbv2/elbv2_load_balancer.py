from mypy_boto3_elbv2.client import ElasticLoadBalancingv2Client
from mypy_boto3_elbv2.type_defs import LoadBalancerTypeDef


def describe_load_balancer(
    client: ElasticLoadBalancingv2Client,
    lb_arn: str,
) -> LoadBalancerTypeDef:
    """Call DescribeLoadBalancers filtering by ARN, return response."""
    lb_response = client.describe_load_balancers(LoadBalancerArns=[lb_arn])
    return lb_response["LoadBalancers"][0]
