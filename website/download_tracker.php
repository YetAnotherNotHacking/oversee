<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST');
header('Access-Control-Allow-Headers: Content-Type');

// Configuration
$data_file = 'downloads_data.json';
$ip_api_url = 'http://ip-api.com/json/';

// Function to get country from IP
function getCountryFromIP($ip) {
    global $ip_api_url;
    
    // Don't lookup local IPs
    if ($ip === '127.0.0.1' || $ip === '::1' || strpos($ip, '192.168.') === 0 || strpos($ip, '10.') === 0) {
        return 'Local';
    }
    
    $response = @file_get_contents($ip_api_url . $ip);
    if ($response) {
        $data = json_decode($response, true);
        if ($data && $data['status'] === 'success') {
            return $data['country'];
        }
    }
    return 'Unknown';
}

// Function to get visitor's IP
function getVisitorIP() {
    $ip_keys = ['HTTP_X_FORWARDED_FOR', 'HTTP_X_REAL_IP', 'HTTP_CLIENT_IP', 'REMOTE_ADDR'];
    
    foreach ($ip_keys as $key) {
        if (!empty($_SERVER[$key])) {
            $ip = $_SERVER[$key];
            // Handle comma-separated IPs (from proxies)
            if (strpos($ip, ',') !== false) {
                $ip = trim(explode(',', $ip)[0]);
            }
            // Validate IP
            if (filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE)) {
                return $ip;
            }
        }
    }
    return $_SERVER['REMOTE_ADDR'] ?? '127.0.0.1';
}

// Initialize data structure
$default_data = [
    'downloads' => [
        'macos' => 0,
        'windows' => 0,
        'linux' => 0
    ],
    'last_downloads' => [
        'macos' => ['country' => 'None', 'timestamp' => null],
        'windows' => ['country' => 'None', 'timestamp' => null],
        'linux' => ['country' => 'None', 'timestamp' => null]
    ],
    'total' => 0
];

// Load existing data or create new
if (file_exists($data_file)) {
    $data = json_decode(file_get_contents($data_file), true);
    if (!$data) {
        $data = $default_data;
    }
} else {
    $data = $default_data;
}

// Handle requests
$method = $_SERVER['REQUEST_METHOD'];

if ($method === 'POST') {
    // Track download
    $input = json_decode(file_get_contents('php://input'), true);
    $platform = $input['platform'] ?? '';
    
    if (in_array($platform, ['macos', 'windows', 'linux'])) {
        // Get visitor info
        $visitor_ip = getVisitorIP();
        $country = getCountryFromIP($visitor_ip);
        
        // Update counters
        $data['downloads'][$platform]++;
        $data['total']++;
        
        // Update last download info
        $data['last_downloads'][$platform] = [
            'country' => $country,
            'timestamp' => time()
        ];
        
        // Save data
        file_put_contents($data_file, json_encode($data, JSON_PRETTY_PRINT));
        
        echo json_encode([
            'success' => true,
            'platform' => $platform,
            'count' => $data['downloads'][$platform],
            'country' => $country,
            'total' => $data['total']
        ]);
    } else {
        http_response_code(400);
        echo json_encode(['error' => 'Invalid platform']);
    }
    
} else if ($method === 'GET') {
    // Return current stats
    echo json_encode([
        'success' => true,
        'data' => $data
    ]);
    
} else {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
}
?>