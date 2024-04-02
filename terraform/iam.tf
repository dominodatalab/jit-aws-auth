data "aws_iam_policy_document" "domino-eks-irsa-role-trust-policy" {
    statement {
      actions = ["sts:AssumeRoleWithWebIdentity"]
      effect = "Allow"
      principals {
        identifiers = [data.aws_iam_openid_connect_provider.domino-cluster-provider.arn]
        type = "Federated"
      }
      condition {
        test = "StringEquals"
        variable = "${replace(data.aws_eks_cluster.domino-cluster.identity[0].oidc[0].issuer,"https://","")}:sub"
        values = ["system:serviceaccount:domino-field:jit"]
      }
    }
}

resource "aws_iam_role" "domino-jit" {
    name = "${var.eks-cluster-name}-jit"
    assume_role_policy = data.aws_iam_policy_document.domino-eks-irsa-role-trust-policy.json
}

data "aws_iam_policy_document" "domino-jit-policy" {
    statement {
      sid = "JIT"
      actions = [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ]
      effect = "Allow"
      resources = [
        aws_secretsmanager_secret_version.nuid.arn,
        aws_secretsmanager_secret_version.ping.arn
      ]
    }
}

resource "aws_iam_policy" "domino-jit-policy" {
  name = "${var.eks-cluster-name}-jit-policy"
  policy = data.aws_iam_policy_document.domino-jit-policy.json
}

resource "aws_iam_role_policy_attachment" "domino-jit" {
  role = aws_iam_role.domino-jit.name
  policy_arn = aws_iam_policy.domino-jit-policy.arn
}