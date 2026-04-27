data "aws_ami" "amazon_linux_2023_arm64" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-arm64"]
  }

  filter {
    name   = "architecture"
    values = ["arm64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ---- IAM: EC2 instance role -----------------------------------------------

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name               = "${var.app_name}-ec2"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
  tags               = { Name = "${var.app_name}-ec2" }
}

# SSM Session Manager — enables shell access without SSH keys
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "ec2_permissions" {
  # ECR: authenticate and pull images
  statement {
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]
    resources = ["*"]
  }

  # Secrets Manager: read app secrets
  statement {
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = var.secret_arns
  }
}

resource "aws_iam_role_policy" "ec2_permissions" {
  name   = "${var.app_name}-ec2-permissions"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.ec2_permissions.json
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.app_name}-ec2"
  role = aws_iam_role.ec2.name
}

# ---- EC2 instance ----------------------------------------------------------

resource "aws_instance" "api" {
  ami           = data.aws_ami.amazon_linux_2023_arm64.id
  instance_type = var.instance_type
  key_name      = var.key_pair_name

  subnet_id              = var.subnet_id
  vpc_security_group_ids = [var.ec2_sg_id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name

  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    app_name       = var.app_name
    aws_region     = var.aws_region
    api_subdomain  = var.api_subdomain
    ecr_registry   = var.ecr_registry
    ecr_repo_url   = var.ecr_repo_url
  })

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 20
    delete_on_termination = true
    encrypted             = true
  }

  tags = { Name = "${var.app_name}-api" }

  lifecycle {
    # Avoid replacing the instance when AMI is updated — use SSM to patch in place.
    ignore_changes = [ami, user_data]
  }
}

resource "aws_eip" "api" {
  instance = aws_instance.api.id
  domain   = "vpc"
  tags     = { Name = "${var.app_name}-api" }
}
