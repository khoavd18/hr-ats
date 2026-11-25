\getenv app_password N8N_DB_PASSWORD
CREATE ROLE n8n LOGIN PASSWORD :'app_password';
ALTER DATABASE n8n OWNER TO n8n;
