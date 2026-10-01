USE DbSistemTimbangan_Test;

SELECT username, role, LEFT(password, 20) AS awal_hash, LEN(password) AS panjang
FROM users WHERE username = 'ho';