output "address" {
  value       = aws_db_instance.main.address
  description = "RDS hostname (no port)"
}

output "port" {
  value = aws_db_instance.main.port
}

output "db_name" {
  value = aws_db_instance.main.db_name
}
