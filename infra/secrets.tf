resource "random_password" "db" {
  length  = 32
  special = false
}

resource "random_password" "secret_key" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "app" {
  name                    = "${var.app_name}/${var.environment}/app"
  description             = "NordIQ application secrets"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    database_url      = "postgresql+asyncpg://${var.db_username}:${random_password.db.result}@${aws_db_instance.main.address}:5432/${var.db_name}"
    sync_database_url = "postgresql://${var.db_username}:${random_password.db.result}@${aws_db_instance.main.address}:5432/${var.db_name}"
    secret_key        = random_password.secret_key.result
    # Generate a Fernet key and update this value:
    # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    encryption_key    = "REPLACE_WITH_FERNET_KEY"
  })
}
