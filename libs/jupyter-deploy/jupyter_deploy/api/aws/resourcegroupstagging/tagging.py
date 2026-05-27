from mypy_boto3_resourcegroupstaggingapi.client import ResourceGroupsTaggingAPIClient
from mypy_boto3_resourcegroupstaggingapi.type_defs import TagFilterTypeDef


def find_resource_arns_by_tags(
    tagging_client: ResourceGroupsTaggingAPIClient,
    tags: dict[str, str],
    resource_type_filter: str,
) -> list[str]:
    """Find resource ARNs matching all specified tags via Resource Groups Tagging API."""
    tag_filters: list[TagFilterTypeDef] = [{"Key": k, "Values": [v]} for k, v in tags.items()]
    arns: list[str] = []

    paginator = tagging_client.get_paginator("get_resources")
    for page in paginator.paginate(
        TagFilters=tag_filters,
        ResourceTypeFilters=[resource_type_filter],
    ):
        for resource in page.get("ResourceTagMappingList", []):
            arn = resource.get("ResourceARN", "")
            if arn:
                arns.append(arn)

    return arns
