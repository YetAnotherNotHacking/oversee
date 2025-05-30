<?php
require_once '.env.php';

class Database {
    private $conn;
    
    public function __construct() {
        try {
            $this->conn = new PDO(
                "mysql:host=" . DB_HOST . ";dbname=" . DB_NAME,
                DB_USER,
                DB_PASS
            );
            $this->conn->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        } catch(PDOException $e) {
            die("Connection failed: " . $e->getMessage());
        }
    }
    
    public function getDevices() {
        $stmt = $this->conn->prepare("SELECT * FROM devices ORDER BY last_seen DESC");
        $stmt->execute();
        return $stmt->fetchAll(PDO::FETCH_ASSOC);
    }
    
    public function addDevice($data) {
        $stmt = $this->conn->prepare("
            INSERT INTO devices (
                ip, port, device_type, device_name, location,
                status, last_seen, notes
            ) VALUES (
                :ip, :port, :device_type, :device_name, :location,
                :status, NOW(), :notes
            )
        ");
        
        return $stmt->execute([
            ':ip' => $data['ip'],
            ':port' => $data['port'],
            ':device_type' => $data['device_type'],
            ':device_name' => $data['device_name'],
            ':location' => $data['location'],
            ':status' => 'Unknown',
            ':notes' => $data['notes']
        ]);
    }
    
    public function updateDevice($id, $data) {
        $stmt = $this->conn->prepare("
            UPDATE devices SET
                ip = :ip,
                port = :port,
                device_type = :device_type,
                device_name = :device_name,
                location = :location,
                notes = :notes,
                last_seen = NOW()
            WHERE id = :id
        ");
        
        return $stmt->execute([
            ':id' => $id,
            ':ip' => $data['ip'],
            ':port' => $data['port'],
            ':device_type' => $data['device_type'],
            ':device_name' => $data['device_name'],
            ':location' => $data['location'],
            ':notes' => $data['notes']
        ]);
    }
    
    public function deleteDevice($id) {
        $stmt = $this->conn->prepare("DELETE FROM devices WHERE id = :id");
        return $stmt->execute([':id' => $id]);
    }
}

// Start session at the very beginning
session_start();

// Debug function
function debug_to_file($message) {
    $log_file = __DIR__ . '/debug.log';
    $timestamp = date('Y-m-d H:i:s');
    file_put_contents($log_file, "[$timestamp] $message\n", FILE_APPEND);
}

// Handle API requests
if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action'])) {
    header('Content-Type: application/json');
    
    // Verify API key
    if (!isset($_GET['api_key']) || $_GET['api_key'] !== API_KEY) {
        http_response_code(401);
        echo json_encode(['error' => 'Unauthorized']);
        exit;
    }
    
    $db = new Database();
    
    switch ($_GET['action']) {
        case 'get_devices':
            echo json_encode($db->getDevices());
            break;
            
        default:
            http_response_code(400);
            echo json_encode(['error' => 'Invalid action']);
    }
    exit;
}

// Handle web interface
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    debug_to_file("POST request received");
    
    // Handle login
    if (isset($_POST['login'])) {
        debug_to_file("Login attempt detected");
        
        $input_password = $_POST['password'];
        $input_hash = md5($input_password);
        
        debug_to_file("Input password: " . $input_password);
        debug_to_file("Input hash: " . $input_hash);
        debug_to_file("Expected hash: " . ADMIN_PASSWORD_HASH);
        
        // Strict comparison
        if (strcmp($input_hash, ADMIN_PASSWORD_HASH) === 0) {
            debug_to_file("Password match - setting session");
            $_SESSION['authenticated'] = true;
            debug_to_file("Session authenticated set to: " . ($_SESSION['authenticated'] ? 'true' : 'false'));
            
            // Force session write
            session_write_close();
            session_start();
            
            debug_to_file("Redirecting after successful login");
            header('Location: ' . $_SERVER['PHP_SELF']);
            exit;
        } else {
            debug_to_file("Password mismatch");
            $error = "Invalid password";
        }
    }
    
    // Handle device operations
    if (isset($_SESSION['authenticated'])) {
        debug_to_file("User is authenticated, processing device operations");
        $db = new Database();
        
        if (isset($_POST['add_device'])) {
            $db->addDevice($_POST);
            header('Location: ' . $_SERVER['PHP_SELF']);
            exit;
        }
        
        if (isset($_POST['update_device'])) {
            $db->updateDevice($_POST['id'], $_POST);
            header('Location: ' . $_SERVER['PHP_SELF']);
            exit;
        }
        
        if (isset($_POST['delete_device'])) {
            $db->deleteDevice($_POST['id']);
            header('Location: ' . $_SERVER['PHP_SELF']);
            exit;
        }
    }
}

// Debug session state
debug_to_file("Session state: " . print_r($_SESSION, true));

// Display web interface
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IoT Device Management</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        :root {
            --dark-bg: #1a1a1a;
            --darker-bg: #141414;
            --card-bg: #2d2d2d;
            --border-color: #404040;
            --text-color: #e0e0e0;
            --accent-color: #0d6efd;
        }
        
        body { 
            background-color: var(--dark-bg);
            color: var(--text-color);
        }
        
        .device-form, .table-container { 
            background-color: var(--card-bg);
            padding: 1.5rem;
            border-radius: 4px;
            border: 1px solid var(--border-color);
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        
        .form-control, .form-select {
            background-color: var(--darker-bg);
            border: 1px solid var(--border-color);
            color: var(--text-color);
        }
        
        .form-control:focus, .form-select:focus {
            background-color: var(--darker-bg);
            border-color: var(--accent-color);
            color: var(--text-color);
            box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.25);
        }
        
        .table {
            color: var(--text-color);
        }
        
        .table-striped > tbody > tr:nth-of-type(odd) {
            background-color: rgba(255, 255, 255, 0.05);
        }
        
        .table-striped > tbody > tr:nth-of-type(even) {
            background-color: rgba(255, 255, 255, 0.02);
        }
        
        .btn-primary {
            background-color: var(--accent-color);
            border: none;
        }
        
        .btn-primary:hover {
            background-color: #0b5ed7;
        }
        
        .btn-danger {
            background-color: #dc3545;
            border: none;
        }
        
        .btn-danger:hover {
            background-color: #bb2d3b;
        }
        
        .modal-content {
            background-color: var(--card-bg);
            color: var(--text-color);
        }
        
        .modal-header {
            border-bottom: 1px solid var(--border-color);
        }
        
        .modal-footer {
            border-top: 1px solid var(--border-color);
        }
        
        .alert {
            background-color: rgba(220, 53, 69, 0.2);
            border: 1px solid #dc3545;
            color: #ff6b6b;
        }
        
        .badge {
            padding: 0.5em 0.75em;
        }
        
        .badge.bg-success {
            background-color: #198754 !important;
        }
        
        .badge.bg-secondary {
            background-color: #6c757d !important;
        }
    </style>
</head>
<body>
    <div class="container py-5">
        <?php if (!isset($_SESSION['authenticated']) || $_SESSION['authenticated'] !== true): ?>
            <!-- Login Form -->
            <div class="row justify-content-center">
                <div class="col-md-4">
                    <div class="device-form">
                        <h2 class="text-center mb-4">Login</h2>
                        <?php if (isset($error)): ?>
                            <div class="alert alert-danger"><?php echo htmlspecialchars($error); ?></div>
                        <?php endif; ?>
                        <form method="POST" action="<?php echo htmlspecialchars($_SERVER['PHP_SELF']); ?>">
                            <div class="mb-3">
                                <label for="password" class="form-label">Password</label>
                                <input type="password" class="form-control" id="password" name="password" required>
                            </div>
                            <button type="submit" name="login" class="btn btn-primary w-100">Login</button>
                        </form>
                    </div>
                </div>
            </div>
        <?php else: ?>
            <!-- Device Management Interface -->
            <div class="row">
                <div class="col-md-4">
                    <div class="device-form">
                        <h2 class="mb-4">Add Device</h2>
                        <form method="POST" action="<?php echo $_SERVER['PHP_SELF']; ?>">
                            <div class="mb-3">
                                <label for="ip" class="form-label">IP Address</label>
                                <input type="text" class="form-control" id="ip" name="ip" required>
                            </div>
                            <div class="mb-3">
                                <label for="port" class="form-label">Port</label>
                                <input type="number" class="form-control" id="port" name="port" value="80" required>
                            </div>
                            <div class="mb-3">
                                <label for="device_type" class="form-label">Device Type</label>
                                <select class="form-select" id="device_type" name="device_type" required>
                                    <option value="">Select Type</option>
                                    <option value="Billboards">Billboards</option>
                                    <option value="EV Charges">EV Charges</option>
                                    <option value="Electricity Meters">Electricity Meters</option>
                                    <option value="Wind Turbines">Wind Turbines</option>
                                    <option value="Road Signs">Road Signs</option>
                                    <option value="Vacuuming robots">Vacuuming robots</option>
                                    <option value="Mowing robots">Mowing robots</option>
                                    <option value="GPS Data">GPS Data</option>
                                    <option value="Industrial Control Systems">Industrial Control Systems</option>
                                    <option value="Gas Pumps">Gas Pumps</option>
                                    <option value="License Plate Readers">License Plate Readers</option>
                                    <option value="Wiretaps">Wiretaps</option>
                                    <option value="Battery backups">Battery backups</option>
                                    <option value="Building refrigeration units">Building refrigeration units</option>
                                    <option value="Door locks">Door locks</option>
                                    <option value="Video Conferencing Gear">Video Conferencing Gear</option>
                                    <option value="Network Storage">Network Storage</option>
                                    <option value="Stereo Systems">Stereo Systems</option>
                                    <option value="Smart Home">Smart Home</option>
                                    <option value="3D Printers">3D Printers</option>
                                </select>
                            </div>
                            <div class="mb-3">
                                <label for="device_name" class="form-label">Device Name</label>
                                <input type="text" class="form-control" id="device_name" name="device_name">
                            </div>
                            <div class="mb-3">
                                <label for="location" class="form-label">Location</label>
                                <input type="text" class="form-control" id="location" name="location">
                            </div>
                            <div class="mb-3">
                                <label for="notes" class="form-label">Notes</label>
                                <textarea class="form-control" id="notes" name="notes" rows="3"></textarea>
                            </div>
                            <button type="submit" name="add_device" class="btn btn-primary w-100">Add Device</button>
                        </form>
                    </div>
                </div>
                <div class="col-md-8">
                    <div class="table-container">
                        <h2 class="mb-4">Device List</h2>
                        <div class="table-responsive">
                            <table class="table table-striped">
                                <thead>
                                    <tr>
                                        <th>IP:Port</th>
                                        <th>Type</th>
                                        <th>Name</th>
                                        <th>Location</th>
                                        <th>Status</th>
                                        <th>Last Seen</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php
                                    $db = new Database();
                                    $devices = $db->getDevices();
                                    foreach ($devices as $device):
                                    ?>
                                    <tr>
                                        <td><?php echo htmlspecialchars($device['ip'] . ':' . $device['port']); ?></td>
                                        <td><?php echo htmlspecialchars($device['device_type']); ?></td>
                                        <td><?php echo htmlspecialchars($device['device_name']); ?></td>
                                        <td><?php echo htmlspecialchars($device['location']); ?></td>
                                        <td>
                                            <span class="badge bg-<?php echo $device['status'] === 'Online' ? 'success' : 'secondary'; ?>">
                                                <?php echo htmlspecialchars($device['status']); ?>
                                            </span>
                                        </td>
                                        <td><?php echo htmlspecialchars($device['last_seen']); ?></td>
                                        <td>
                                            <button class="btn btn-sm btn-primary" onclick="editDevice(<?php echo htmlspecialchars(json_encode($device)); ?>)">
                                                <i class="bi bi-pencil"></i>
                                            </button>
                                            <form method="POST" style="display: inline;">
                                                <input type="hidden" name="id" value="<?php echo $device['id']; ?>">
                                                <button type="submit" name="delete_device" class="btn btn-sm btn-danger" onclick="return confirm('Are you sure?')">
                                                    <i class="bi bi-trash"></i>
                                                </button>
                                            </form>
                                        </td>
                                    </tr>
                                    <?php endforeach; ?>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Edit Device Modal -->
            <div class="modal fade" id="editModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Edit Device</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <form method="POST" id="editForm">
                                <input type="hidden" name="id" id="edit_id">
                                <div class="mb-3">
                                    <label for="edit_ip" class="form-label">IP Address</label>
                                    <input type="text" class="form-control" id="edit_ip" name="ip" required>
                                </div>
                                <div class="mb-3">
                                    <label for="edit_port" class="form-label">Port</label>
                                    <input type="number" class="form-control" id="edit_port" name="port" required>
                                </div>
                                <div class="mb-3">
                                    <label for="edit_device_type" class="form-label">Device Type</label>
                                    <select class="form-select" id="edit_device_type" name="device_type" required>
                                        <option value="">Select Type</option>
                                        <option value="Billboards">Billboards</option>
                                        <option value="EV Charges">EV Charges</option>
                                        <option value="Electricity Meters">Electricity Meters</option>
                                        <option value="Wind Turbines">Wind Turbines</option>
                                        <option value="Road Signs">Road Signs</option>
                                        <option value="Vacuuming robots">Vacuuming robots</option>
                                        <option value="Mowing robots">Mowing robots</option>
                                        <option value="GPS Data">GPS Data</option>
                                        <option value="Industrial Control Systems">Industrial Control Systems</option>
                                        <option value="Gas Pumps">Gas Pumps</option>
                                        <option value="License Plate Readers">License Plate Readers</option>
                                        <option value="Wiretaps">Wiretaps</option>
                                        <option value="Battery backups">Battery backups</option>
                                        <option value="Building refrigeration units">Building refrigeration units</option>
                                        <option value="Door locks">Door locks</option>
                                        <option value="Video Conferencing Gear">Video Conferencing Gear</option>
                                        <option value="Network Storage">Network Storage</option>
                                        <option value="Stereo Systems">Stereo Systems</option>
                                        <option value="Smart Home">Smart Home</option>
                                        <option value="3D Printers">3D Printers</option>
                                    </select>
                                </div>
                                <div class="mb-3">
                                    <label for="edit_device_name" class="form-label">Device Name</label>
                                    <input type="text" class="form-control" id="edit_device_name" name="device_name">
                                </div>
                                <div class="mb-3">
                                    <label for="edit_location" class="form-label">Location</label>
                                    <input type="text" class="form-control" id="edit_location" name="location">
                                </div>
                                <div class="mb-3">
                                    <label for="edit_notes" class="form-label">Notes</label>
                                    <textarea class="form-control" id="edit_notes" name="notes" rows="3"></textarea>
                                </div>
                                <button type="submit" name="update_device" class="btn btn-primary">Save Changes</button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
            
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            <script>
                function editDevice(device) {
                    document.getElementById('edit_id').value = device.id;
                    document.getElementById('edit_ip').value = device.ip;
                    document.getElementById('edit_port').value = device.port;
                    document.getElementById('edit_device_type').value = device.device_type;
                    document.getElementById('edit_device_name').value = device.device_name;
                    document.getElementById('edit_location').value = device.location;
                    document.getElementById('edit_notes').value = device.notes;
                    
                    new bootstrap.Modal(document.getElementById('editModal')).show();
                }
            </script>
        <?php endif; ?>
    </div>
</body>
</html>
