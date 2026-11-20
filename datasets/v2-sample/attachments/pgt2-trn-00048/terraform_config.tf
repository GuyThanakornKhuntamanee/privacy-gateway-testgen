การตั้งค่า Terraform

provider "aws" { region = "ap-southeast-1" }
resource "aws_db_instance" "main" {
  engine         = "postgres"
  instance_class = "db.t3.medium"
  password   = "Example-Fake-Passw0rd-0626!"
  skip_final_snapshot = true
}
