data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = "t2.micro"
  subnet_id              = aws_subnet.public_a.id
  vpc_security_group_ids = [aws_security_group.ec2.id]

  user_data = templatefile("${path.module}/user_data.sh", {
    db_host     = aws_db_instance.main.address
    db_name     = var.db_name
    db_username = var.db_username
    db_password = var.db_password
  })

  tags = { Name = "dev-project-ec2" }
}
