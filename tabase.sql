psql "postgresql://postgres:new_password@localhost:5432/postgres"

\dt

SELECT * FROM users;

\x on
SELECT * FROM users ORDER BY created_at DESC;

#If many Rows 

SELECT id, first_name, last_name, email, phone, status, is_verified, created_at
FROM users
ORDER BY created_at DESC
LIMIT 100;

\q