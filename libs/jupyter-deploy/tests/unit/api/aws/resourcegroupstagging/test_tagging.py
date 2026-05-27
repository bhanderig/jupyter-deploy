import unittest
from unittest.mock import Mock

from botocore.exceptions import ClientError
from mypy_boto3_resourcegroupstaggingapi.client import ResourceGroupsTaggingAPIClient

from jupyter_deploy.api.aws.resourcegroupstagging import tagging


class TestFindResourceArnsByTags(unittest.TestCase):
    def test_returns_matching_arns(self) -> None:
        mock_client: Mock = Mock(spec=ResourceGroupsTaggingAPIClient)
        mock_paginator: Mock = Mock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "ResourceTagMappingList": [
                    {"ResourceARN": "arn:aws:elasticloadbalancing:us-west-2:123:loadbalancer/net/my-lb/abc"},
                ]
            }
        ]

        result = tagging.find_resource_arns_by_tags(
            mock_client,
            tags={"kubernetes.io/cluster/my-cluster": "owned"},
            resource_type_filter="elasticloadbalancing:loadbalancer",
        )

        self.assertEqual(result, ["arn:aws:elasticloadbalancing:us-west-2:123:loadbalancer/net/my-lb/abc"])
        mock_client.get_paginator.assert_called_once_with("get_resources")
        mock_paginator.paginate.assert_called_once_with(
            TagFilters=[{"Key": "kubernetes.io/cluster/my-cluster", "Values": ["owned"]}],
            ResourceTypeFilters=["elasticloadbalancing:loadbalancer"],
        )

    def test_returns_empty_when_no_matches(self) -> None:
        mock_client: Mock = Mock(spec=ResourceGroupsTaggingAPIClient)
        mock_paginator: Mock = Mock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"ResourceTagMappingList": []}]

        result = tagging.find_resource_arns_by_tags(
            mock_client,
            tags={"kubernetes.io/cluster/gone": "owned"},
            resource_type_filter="elasticloadbalancing:loadbalancer",
        )

        self.assertEqual(result, [])

    def test_handles_multiple_pages(self) -> None:
        mock_client: Mock = Mock(spec=ResourceGroupsTaggingAPIClient)
        mock_paginator: Mock = Mock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "ResourceTagMappingList": [
                    {"ResourceARN": "arn:aws:elasticloadbalancing:us-west-2:123:loadbalancer/net/lb-1/aaa"},
                ]
            },
            {
                "ResourceTagMappingList": [
                    {"ResourceARN": "arn:aws:elasticloadbalancing:us-west-2:123:loadbalancer/net/lb-2/bbb"},
                ]
            },
        ]

        result = tagging.find_resource_arns_by_tags(
            mock_client,
            tags={"env": "prod"},
            resource_type_filter="elasticloadbalancing:loadbalancer",
        )

        self.assertEqual(len(result), 2)
        self.assertIn("arn:aws:elasticloadbalancing:us-west-2:123:loadbalancer/net/lb-1/aaa", result)
        self.assertIn("arn:aws:elasticloadbalancing:us-west-2:123:loadbalancer/net/lb-2/bbb", result)

    def test_multiple_tag_filters(self) -> None:
        mock_client: Mock = Mock(spec=ResourceGroupsTaggingAPIClient)
        mock_paginator: Mock = Mock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "ResourceTagMappingList": [
                    {"ResourceARN": "arn:aws:elasticloadbalancing:us-west-2:123:loadbalancer/net/my-lb/abc"},
                ]
            }
        ]

        result = tagging.find_resource_arns_by_tags(
            mock_client,
            tags={"kubernetes.io/cluster/my-cluster": "owned", "service.k8s.aws/stack": "traefik"},
            resource_type_filter="elasticloadbalancing:loadbalancer",
        )

        self.assertEqual(len(result), 1)
        call_kwargs = mock_paginator.paginate.call_args.kwargs
        self.assertEqual(len(call_kwargs["TagFilters"]), 2)

    def test_client_error_bubbles_up(self) -> None:
        mock_client: Mock = Mock(spec=ResourceGroupsTaggingAPIClient)
        mock_paginator: Mock = Mock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "not authorized"}},
            "GetResources",
        )

        with self.assertRaises(ClientError):
            tagging.find_resource_arns_by_tags(
                mock_client,
                tags={"env": "prod"},
                resource_type_filter="elasticloadbalancing:loadbalancer",
            )

    def test_skips_empty_arns(self) -> None:
        mock_client: Mock = Mock(spec=ResourceGroupsTaggingAPIClient)
        mock_paginator: Mock = Mock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "ResourceTagMappingList": [
                    {"ResourceARN": ""},
                    {"ResourceARN": "arn:aws:elasticloadbalancing:us-west-2:123:loadbalancer/net/my-lb/abc"},
                ]
            }
        ]

        result = tagging.find_resource_arns_by_tags(
            mock_client,
            tags={"env": "prod"},
            resource_type_filter="elasticloadbalancing:loadbalancer",
        )

        self.assertEqual(result, ["arn:aws:elasticloadbalancing:us-west-2:123:loadbalancer/net/my-lb/abc"])
