output "sm_nuid_arn" {
  value = aws_secretsmanager_secret_version.nuid.arn
}

output "sm_ping_arn" {
  value = aws_secretsmanager_secret_version.ping.arn
}

output "jit_iam_role_arn" {
    value = aws_iam_role.domino-jit.arn
}