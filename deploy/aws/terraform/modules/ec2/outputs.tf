output "instance_id" {
  value = aws_instance.api.id
}

output "elastic_ip" {
  value       = aws_eip.api.public_ip
  description = "Point api.yourdomain.com A record here"
}

output "instance_role_arn" {
  value = aws_iam_role.ec2.arn
}
