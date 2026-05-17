output "ec2_public_ip" {
  value       = aws_instance.app.public_ip
  description = "Set EC2_IP to this value in client.py"
}

output "rds_endpoint" {
  value       = aws_db_instance.main.address
  description = "RDS hostname (already baked into EC2 .env via user_data)"
}
