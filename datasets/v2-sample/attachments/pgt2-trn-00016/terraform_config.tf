การตั้งค่า Terraform

provider "aws" { region = "ap-southeast-1" }
resource "aws_db_instance" "main" {
  engine         = "postgres"
  instance_class = "db.t3.medium"
  identifier = "auth-05.siam-meridian.internal"
  skip_final_snapshot = true
}
