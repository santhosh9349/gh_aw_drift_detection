output "instance_id" {
  description = "ID of the demo EC2 instance"
  value       = aws_instance.demo.id
}

output "private_ip" {
  description = "Private IP of the demo EC2 instance"
  value       = aws_instance.demo.private_ip
}
