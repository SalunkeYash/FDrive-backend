variable "project_name" {
  type    = string
  default = "fdrive"
}

variable "environment" {
  type    = string
  default = "staging"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "db_username" {
  type    = string
  default = "fdrive"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "spa_origin" {
  type    = string
  default = "https://app.example.com"
}
