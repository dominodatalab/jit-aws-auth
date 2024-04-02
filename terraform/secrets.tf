
resource "random_string" "nuid-un" {
    length = 8
    special = false
}

resource "random_password" "nuid-pw" {
    length = 20
    special = false
}

locals {
    nuid-dict = {
     "username" = "${random_string.nuid-un.result}"
     "password" = "${random_password.nuid-pw.result}"
    }
}

resource "aws_secretsmanager_secret" "nuid" {
    name = "/dev/${var.eks-cluster-name}-nuid"
}

resource "aws_secretsmanager_secret_version" "nuid" {
    secret_id = aws_secretsmanager_secret.nuid.id
    secret_string = jsonencode(local.nuid-dict)
}

resource "random_string" "ping-id" {
    length = 8
    special = false
}

resource "random_password" "ping-pw" {
    length = 20
    special = false
}

locals { 
  ping-dict = {
     "client-id" = "${random_string.ping-id.result}"
     "client-secret" = "${random_password.ping-pw.result}"
     "auth-server-url" = "https://domino.ai" # No, this isn't the real site.
  }
}

resource "aws_secretsmanager_secret" "ping" {
    name = "/dev/${var.eks-cluster-name}-ping"
}

resource "aws_secretsmanager_secret_version" "ping" {
    secret_id = aws_secretsmanager_secret.ping.id
    secret_string = jsonencode(local.ping-dict)
}