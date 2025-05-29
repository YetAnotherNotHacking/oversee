<?php
// Move this file to .env.php and fill in the values with your production info.
// Database Configuration
define('DB_HOST', 'localhost:3306');
define('DB_NAME', 'seetheworld');
define('DB_USER', 'seetheworld');
define('DB_PASS', 'YOURDATABASEPASSWORDHERE');

// Security Configuration
define('ADMIN_PASSWORD_HASH', 'AN MD5 HASH OF YOUR PASSWORD');

// API Keys
define('PUBLIC_API_KEY', 'A PUBLIC ACCESS TOKEN');
define('PRIVATE_API_KEY', 'A PRIVATE ACCESS TOKEN');