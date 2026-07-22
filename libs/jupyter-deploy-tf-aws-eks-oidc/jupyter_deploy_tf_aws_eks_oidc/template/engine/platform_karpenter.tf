# === Karpenter node provisioner ===
#
# All Karpenter infrastructure in one file: IAM policy, SQS interruption queue,
# EventBridge rules, controller Helm chart, and the NodePool/EC2NodeClass chart.
# Follows the platform_*.tf convention — singleton resources that deploy helm
# charts and their supporting AWS infra onto the cluster.

# ── Karpenter controller IAM policy ──────────────────────────────────────────
# Transcribed from the upstream Karpenter v1 recommended controller policy
# (github.com/aws/karpenter-provider-aws, cloudformation.yaml). Provisioning and
# destructive actions are scoped to EC2 resources tagged for THIS cluster —
# kubernetes.io/cluster/<name>=owned + karpenter.sh/nodepool — which Karpenter
# injects on every RunInstances/CreateFleet. This closes the tag→terminate
# escalation possible under a region-only guard: CreateTags can only apply tags
# as part of a create (ec2:CreateAction), so an actor cannot retroactively tag an
# unrelated instance into this cluster's boundary and then terminate it.

locals {
  karpenter_ec2_arn_prefix = "arn:${data.aws_partition.current.partition}:ec2:${data.aws_region.current.id}"
}

data "aws_iam_policy_document" "karpenter_controller" {
  statement {
    sid     = "AllowScopedEC2InstanceAccessActions"
    actions = ["ec2:RunInstances", "ec2:CreateFleet"]
    resources = [
      "${local.karpenter_ec2_arn_prefix}::image/*",
      "${local.karpenter_ec2_arn_prefix}::snapshot/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:security-group/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:subnet/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:capacity-reservation/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:placement-group/*",
    ]
  }

  statement {
    sid       = "AllowScopedEC2LaunchTemplateAccessActions"
    actions   = ["ec2:RunInstances", "ec2:CreateFleet"]
    resources = ["${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:launch-template/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/kubernetes.io/cluster/${module.eks_cluster.cluster_name}"
      values   = ["owned"]
    }
    condition {
      test     = "StringLike"
      variable = "aws:ResourceTag/karpenter.sh/nodepool"
      values   = ["*"]
    }
  }

  statement {
    sid     = "AllowScopedEC2InstanceActionsWithTags"
    actions = ["ec2:RunInstances", "ec2:CreateFleet", "ec2:CreateLaunchTemplate"]
    resources = [
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:fleet/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:instance/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:volume/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:network-interface/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:launch-template/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:spot-instances-request/*",
    ]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/kubernetes.io/cluster/${module.eks_cluster.cluster_name}"
      values   = ["owned"]
    }
    condition {
      test     = "StringLike"
      variable = "aws:RequestTag/karpenter.sh/nodepool"
      values   = ["*"]
    }
  }

  statement {
    sid     = "AllowScopedResourceCreationTagging"
    actions = ["ec2:CreateTags"]
    resources = [
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:fleet/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:instance/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:volume/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:network-interface/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:launch-template/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:spot-instances-request/*",
    ]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/kubernetes.io/cluster/${module.eks_cluster.cluster_name}"
      values   = ["owned"]
    }
    condition {
      test     = "StringEquals"
      variable = "ec2:CreateAction"
      values   = ["RunInstances", "CreateFleet", "CreateLaunchTemplate"]
    }
    condition {
      test     = "StringLike"
      variable = "aws:RequestTag/karpenter.sh/nodepool"
      values   = ["*"]
    }
  }

  statement {
    sid       = "AllowScopedResourceTagging"
    actions   = ["ec2:CreateTags"]
    resources = ["${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:instance/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/kubernetes.io/cluster/${module.eks_cluster.cluster_name}"
      values   = ["owned"]
    }
    condition {
      test     = "StringLike"
      variable = "aws:ResourceTag/karpenter.sh/nodepool"
      values   = ["*"]
    }
    condition {
      test     = "ForAllValues:StringEquals"
      variable = "aws:TagKeys"
      values   = ["karpenter.sh/nodeclaim", "Name"]
    }
  }

  statement {
    sid     = "AllowScopedDeletion"
    actions = ["ec2:TerminateInstances", "ec2:DeleteLaunchTemplate"]
    resources = [
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:instance/*",
      "${local.karpenter_ec2_arn_prefix}:${data.aws_caller_identity.current.account_id}:launch-template/*",
    ]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/kubernetes.io/cluster/${module.eks_cluster.cluster_name}"
      values   = ["owned"]
    }
    condition {
      test     = "StringLike"
      variable = "aws:ResourceTag/karpenter.sh/nodepool"
      values   = ["*"]
    }
  }

  statement {
    sid = "AllowRegionalReadActions"
    actions = [
      "ec2:DescribeAvailabilityZones",
      "ec2:DescribeCapacityReservations",
      "ec2:DescribeImages",
      "ec2:DescribeInstances",
      "ec2:DescribeInstanceStatus",
      "ec2:DescribeInstanceTypeOfferings",
      "ec2:DescribeInstanceTypes",
      "ec2:DescribeLaunchTemplates",
      "ec2:DescribePlacementGroups",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeSpotPriceHistory",
      "ec2:DescribeSubnets",
    ]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [data.aws_region.current.id]
    }
  }

  statement {
    sid       = "AllowSSMGetParameter"
    actions   = ["ssm:GetParameter"]
    resources = ["arn:${data.aws_partition.current.partition}:ssm:${data.aws_region.current.id}::parameter/aws/service/*"]
  }

  statement {
    sid       = "AllowPricingGetProducts"
    actions   = ["pricing:GetProducts"]
    resources = ["*"]
  }

  statement {
    sid       = "AllowPassNodeRole"
    actions   = ["iam:PassRole"]
    resources = [module.karpenter_node_role.role_arn]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ec2.amazonaws.com"]
    }
  }

  statement {
    sid       = "AllowInstanceProfileGet"
    actions   = ["iam:GetInstanceProfile"]
    resources = [aws_iam_instance_profile.karpenter_node.arn]
  }

  statement {
    sid = "AllowInterruptionQueueActions"
    actions = [
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:ReceiveMessage",
    ]
    resources = [aws_sqs_queue.karpenter_interruption.arn]
  }

  statement {
    sid       = "AllowEKSClusterActions"
    actions   = ["eks:DescribeCluster"]
    resources = ["arn:${data.aws_partition.current.partition}:eks:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:cluster/${module.eks_cluster.cluster_name}"]
  }
}

resource "aws_iam_policy" "karpenter_controller" {
  name   = "${local.resource_name_prefix}-karpenter-controller"
  policy = data.aws_iam_policy_document.karpenter_controller.json
  tags   = local.combined_tags
}

locals {
  karpenter_controller_role_name = reverse(split("/", module.karpenter_controller_role.role_arn))[0]
}

resource "aws_iam_role_policy_attachment" "karpenter_controller" {
  role       = local.karpenter_controller_role_name
  policy_arn = aws_iam_policy.karpenter_controller.arn
}

# ── SQS interruption queue ────────────────────────────────────────────────────
# Karpenter polls this queue for EC2 spot interruption notices, instance health
# events, and scheduled maintenance events so it can cordon and drain nodes
# gracefully before termination. Scoped per-cluster via the queue name.

resource "aws_sqs_queue" "karpenter_interruption" {
  name                      = "${module.eks_cluster.cluster_name}-karpenter"
  message_retention_seconds = 300
  sqs_managed_sse_enabled   = true
  tags                      = local.combined_tags
}

data "aws_iam_policy_document" "karpenter_interruption_queue" {
  statement {
    sid     = "EC2InterruptionPolicy"
    effect  = "Allow"
    actions = ["sqs:SendMessage"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com", "sqs.amazonaws.com"]
    }
    resources = [aws_sqs_queue.karpenter_interruption.arn]
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values = [
        aws_cloudwatch_event_rule.karpenter_spot_interruption.arn,
        aws_cloudwatch_event_rule.karpenter_instance_rebalance.arn,
        aws_cloudwatch_event_rule.karpenter_instance_state_change.arn,
        aws_cloudwatch_event_rule.karpenter_scheduled_change.arn,
      ]
    }
  }
}

resource "aws_sqs_queue_policy" "karpenter_interruption" {
  queue_url = aws_sqs_queue.karpenter_interruption.url
  policy    = data.aws_iam_policy_document.karpenter_interruption_queue.json
}

# ── EventBridge rules → SQS ──────────────────────────────────────────────────

resource "aws_cloudwatch_event_rule" "karpenter_spot_interruption" {
  name        = "${module.eks_cluster.cluster_name}-karpenter-spot-interruption"
  description = "Karpenter: EC2 spot interruption notices for ${module.eks_cluster.cluster_name}"
  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Spot Instance Interruption Warning"]
  })
  tags = local.combined_tags
}

resource "aws_cloudwatch_event_target" "karpenter_spot_interruption" {
  rule      = aws_cloudwatch_event_rule.karpenter_spot_interruption.name
  target_id = "KarpenterInterruptionQueueTarget"
  arn       = aws_sqs_queue.karpenter_interruption.arn
}

resource "aws_cloudwatch_event_rule" "karpenter_instance_rebalance" {
  name        = "${module.eks_cluster.cluster_name}-karpenter-rebalance"
  description = "Karpenter: EC2 instance rebalance recommendations for ${module.eks_cluster.cluster_name}"
  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Instance Rebalance Recommendation"]
  })
  tags = local.combined_tags
}

resource "aws_cloudwatch_event_target" "karpenter_instance_rebalance" {
  rule      = aws_cloudwatch_event_rule.karpenter_instance_rebalance.name
  target_id = "KarpenterInterruptionQueueTarget"
  arn       = aws_sqs_queue.karpenter_interruption.arn
}

resource "aws_cloudwatch_event_rule" "karpenter_instance_state_change" {
  name        = "${module.eks_cluster.cluster_name}-karpenter-state-change"
  description = "Karpenter: EC2 instance state change notifications for ${module.eks_cluster.cluster_name}"
  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Instance State-change Notification"]
  })
  tags = local.combined_tags
}

resource "aws_cloudwatch_event_target" "karpenter_instance_state_change" {
  rule      = aws_cloudwatch_event_rule.karpenter_instance_state_change.name
  target_id = "KarpenterInterruptionQueueTarget"
  arn       = aws_sqs_queue.karpenter_interruption.arn
}

resource "aws_cloudwatch_event_rule" "karpenter_scheduled_change" {
  name        = "${module.eks_cluster.cluster_name}-karpenter-scheduled-change"
  description = "Karpenter: AWS health scheduled change events for ${module.eks_cluster.cluster_name}"
  event_pattern = jsonencode({
    source      = ["aws.health"]
    detail-type = ["AWS Health Event"]
  })
  tags = local.combined_tags
}

resource "aws_cloudwatch_event_target" "karpenter_scheduled_change" {
  rule      = aws_cloudwatch_event_rule.karpenter_scheduled_change.name
  target_id = "KarpenterInterruptionQueueTarget"
  arn       = aws_sqs_queue.karpenter_interruption.arn
}

# ── Karpenter controller Helm release ─────────────────────────────────────────

resource "helm_release" "karpenter" {
  name             = "karpenter"
  repository       = "oci://public.ecr.aws/karpenter"
  chart            = "karpenter"
  version          = var.karpenter_version
  namespace        = "karpenter"
  create_namespace = true

  set = [
    {
      name  = "settings.clusterName"
      value = module.eks_cluster.cluster_name
    },
    {
      name  = "settings.clusterEndpoint"
      value = module.eks_cluster.cluster_endpoint
    },
    {
      name  = "settings.interruptionQueue"
      value = aws_sqs_queue.karpenter_interruption.name
    },
    {
      name  = "controller.resources.requests.cpu"
      value = "200m"
    },
    {
      name  = "controller.resources.requests.memory"
      value = "256Mi"
    },
    {
      name  = "controller.resources.limits.cpu"
      value = "1000m"
    },
    {
      name  = "controller.resources.limits.memory"
      value = "1Gi"
    },
    {
      name  = "replicas"
      value = "2"
    },
    # Run Karpenter controller on platform nodes only
    {
      name  = "nodeSelector.jupyter-deploy/role"
      value = "platform"
    },
  ]

  depends_on = [
    null_resource.core_node_addons,
    aws_eks_node_group.platform,
    aws_iam_role_policy_attachment.karpenter_controller,
    aws_sqs_queue_policy.karpenter_interruption,
    aws_eks_access_policy_association.admin_role,
    aws_eks_access_policy_association.admin_user,
  ]
}

# Restart Karpenter pods after the Helm release so the Pod Identity credential
# chain is fully initialised before the EC2NodeClass RunInstances auth check runs.
# Without this restart, Karpenter's preflight dry-run fires within the first second
# of pod startup — before the Pod Identity agent has injected the credentials token
# — and the EC2NodeClass gets stuck in ValidationSucceeded=False indefinitely.
resource "null_resource" "karpenter_restart" {
  triggers = {
    karpenter_release = helm_release.karpenter.metadata.revision
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      aws eks update-kubeconfig --name "${module.eks_cluster.cluster_name}" --region "${var.region}" --kubeconfig /tmp/karpenter-restart-kubeconfig 2>/dev/null
      KUBECONFIG=/tmp/karpenter-restart-kubeconfig kubectl rollout restart deployment/karpenter -n karpenter
      KUBECONFIG=/tmp/karpenter-restart-kubeconfig kubectl rollout status deployment/karpenter -n karpenter --timeout=120s
      rm -f /tmp/karpenter-restart-kubeconfig
    EOT
  }

  depends_on = [helm_release.karpenter]
}

# Brief pause after SG tag so Karpenter's EC2NodeClass reconciler sees the tag
# before the NodePools are created. Without this, on re-apply Terraform briefly
# removes then re-adds the tag and Karpenter caches "no subnets found" for ~30s.
resource "time_sleep" "karpenter_tag_propagation" {
  create_duration = "15s"
  depends_on      = [aws_ec2_tag.karpenter_sg_discovery, null_resource.karpenter_restart]
}

# ── NodePool + EC2NodeClass chart ─────────────────────────────────────────────

# Strip Karpenter finalizers before helm uninstall. NodePool, EC2NodeClass, and
# NodeClaim resources carry a karpenter.k8s.aws/termination finalizer that only
# the controller can clear (it terminates EC2 instances first). During destroy,
# if helm tries to delete these CRs while the finalizer is present, the uninstall
# blocks indefinitely. Stripping finalizers lets the CRs delete instantly; the
# cluster (and its instances) is being destroyed anyway.
resource "null_resource" "karpenter_nodepools_finalizer_cleanup" {
  triggers = {
    cluster_name = module.eks_cluster.cluster_name
    region       = var.region
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      tmp_kubeconfig=$(mktemp)
      aws eks update-kubeconfig --name "${self.triggers.cluster_name}" --region "${self.triggers.region}" --kubeconfig "$tmp_kubeconfig" 2>/dev/null
      export KUBECONFIG="$tmp_kubeconfig"
      kubectl patch nodepools --all --type=merge -p '{"metadata":{"finalizers":null}}' 2>/dev/null || true
      kubectl patch ec2nodeclasses --all --type=merge -p '{"metadata":{"finalizers":null}}' 2>/dev/null || true
      kubectl patch nodeclaims --all --type=merge -p '{"metadata":{"finalizers":null}}' 2>/dev/null || true
      rm -f "$tmp_kubeconfig"
    EOT
  }

  depends_on = [
    helm_release.karpenter,
    aws_eks_access_policy_association.admin_role,
    aws_eks_access_policy_association.admin_user,
  ]
}

resource "helm_release" "karpenter_nodepools" {
  name             = "karpenter-nodepools"
  chart            = "${path.module}/../charts/karpenter-nodepools"
  namespace        = "karpenter"
  create_namespace = false
  wait             = false

  set = [
    {
      name  = "clusterName"
      value = module.eks_cluster.cluster_name
    },
    {
      name  = "nodeInstanceProfile"
      value = aws_iam_instance_profile.karpenter_node.name
    },
    {
      name  = "expireAfter"
      value = var.node_expire_after
    },
    # Routing NodePool
    {
      name  = "routingLimitsCpu"
      value = var.routing_max_cpu
    },
    {
      name  = "routingLimitsMemory"
      value = var.routing_max_memory
    },
    {
      name  = "routing.blockDevice.volumeSizeGi"
      value = tostring(var.routing_disk_size_gb)
    },
  ]

  values = [
    yamlencode({
      routing = {
        instanceCategories    = var.routing_instance_categories
        instanceGenerationMin = var.routing_instance_generation_min
      }
      workspaceNodepools = [
        for p in var.workspace_nodepools : {
          name             = p["name"]
          instanceFamilies = split(",", p["instance_families"])
          diskSizeGi       = tonumber(p["disk_size_gb"])
          maxCpu           = p["max_cpu"]
          maxMemory        = p["max_memory"]
        }
      ]
    })
  ]

  depends_on = [
    helm_release.karpenter,
    time_sleep.karpenter_tag_propagation,
    null_resource.karpenter_nodepools_finalizer_cleanup,
    aws_eks_access_policy_association.admin_role,
    aws_eks_access_policy_association.admin_user,
  ]
}

# Tag the EKS cluster security group for Karpenter node discovery.
# EKS creates this SG automatically; Karpenter's EC2NodeClass selects it via the
# karpenter.sh/discovery tag. No separate SG is needed — the cluster SG already
# allows the required node-to-cluster and inter-node traffic.
resource "aws_ec2_tag" "karpenter_sg_discovery" {
  resource_id = module.eks_cluster.cluster_security_group_id
  key         = "karpenter.sh/discovery"
  value       = module.eks_cluster.cluster_name
}

# EKS access entry for Karpenter-provisioned nodes.
# Nodes provisioned by Karpenter use the karpenter_node_role. They need an EKS
# access entry so the K8s API server trusts them and maps them to the
# system:bootstrappers group for node registration.
resource "aws_eks_access_entry" "karpenter_node" {
  cluster_name  = module.eks_cluster.cluster_name
  principal_arn = module.karpenter_node_role.role_arn
  type          = "EC2_LINUX"
  tags          = local.combined_tags
}
