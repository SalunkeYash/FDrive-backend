terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "network" {
  source       = "./modules/network"
  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr
}

module "data" {
  source             = "./modules/data"
  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids
  db_username        = var.db_username
  db_password        = var.db_password
  spa_origin         = var.spa_origin
}

module "compute" {
  source             = "./modules/compute"
  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids
  public_subnet_ids  = module.network.public_subnet_ids
}

output "vpc_id" {
  value = module.network.vpc_id
}

output "s3_bucket" {
  value = module.data.s3_bucket_name
}

output "sqs_queue_url" {
  value = module.data.sqs_queue_url
}

output "ecs_cluster_name" {
  value = module.compute.ecs_cluster_name
}
