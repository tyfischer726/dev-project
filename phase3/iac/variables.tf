variable "region" {
  default = "us-east-1"
}

variable "db_name" {
  default = "devproject"
}

variable "db_username" {
  default = "ty"
}

variable "db_password" {
  sensitive = true
}
