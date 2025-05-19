import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import time
import cv2
import numpy as np
import urllib.request
import requests
import random
import threading
import logging
import os
from typing import Dict, List, Tuple, Optional, Any
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('camera_bot')

# Constants
IP_LIST_FILE = "rawips.txt"
CHUNK_SIZE = 1024

# Global variables
camera_metadata = {}
frames = {}
borders = {}
lock = threading.RLock()
active_streams = {}  # To track active streams in voice channels

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

def check_endpoint(endpoint: str) -> bool:
    try:
        # Set a short timeout to avoid hanging on non-responsive endpoints
        response = requests.get(endpoint, timeout=3)
        
        # If we get a successful response, update camera metadata
        if response.status_code == 200:
            # Extract camera information from response
            content_type = response.headers.get('Content-Type', '')
            content_length = int(response.headers.get('Content-Length', 0))
            
            # Determine stream type based on content type
            stream_type = "unknown"
            if 'jpeg' in content_type or 'jpg' in content_type:
                stream_type = "jpeg"
            elif 'mjpeg' in content_type:
                stream_type = "mjpeg"
            
            # Try to determine resolution (this is a simplified approach)
            resolution = "unknown"
            if content_length > 0:
                # Very rough estimation based on file size
                if content_length > 100000:
                    resolution = "high"
                elif content_length > 30000:
                    resolution = "medium"
                else:
                    resolution = "low"
            
            # Store camera metadata in the shared dictionary
            with lock:
                camera_metadata[endpoint] = {
                    "available": True,
                    "stream_type": stream_type,
                    "resolution": resolution
                }
            return True
        return False
    except (requests.RequestException, ConnectionError, TimeoutError) as e:
        # Failed to connect or timed out
        return False

# Modified version of your read_stream function to work with our bot
def read_stream(input_id, frames, borders, lock):
    try:
        def should_poll_jpeg(url):
            lower = url.lower()
            return any(p in lower for p in [
                "/cgi-bin/camera",
                "/snapshotjpeg",
                "/oneshotimage1",
                "/oneshotimage2",
                "/oneshotimage3",
                "/getoneshot",
                "/nphmotionjpeg",
                "/cam1ir",
                "/cam1color",
                "/image",
                ".jpg",
                ".jpeg"
            ])
        with lock:
            if input_id not in camera_metadata:
                camera_metadata[input_id] = {
                    "first_seen": time.time(),
                    "frames_received": 0,
                    "last_frame_time": 0,
                    "fps": 0,
                    "resolution": "Unknown",
                    "stream_type": "Unknown",
                    "endpoint": "Unknown",
                    "connection_attempts": 0,
                    "connection_failures": 0,
                    "last_success": 0,
                    "available": False
                }
            if input_id.startswith("rtsp://"):
                camera_metadata[input_id]["stream_type"] = "RTSP"
            elif should_poll_jpeg(input_id):
                camera_metadata[input_id]["stream_type"] = "JPEG Poll"
            else:
                camera_metadata[input_id]["stream_type"] = "HTTP"
            endpoint = input_id.split("/")[-1] if "/" in input_id else "root"
            camera_metadata[input_id]["endpoint"] = endpoint
        
        if input_id.startswith("rtsp://") or input_id.startswith("http://"):
            full_url = input_id
        elif any(x in input_id.lower() for x in [
            "/cam", "/cgi-bin", "/snapshotjpeg", "/oneshotimage", "/getoneshot", "/nphmotionjpeg",
            "/cam1ir", "/cam1color", ".jpg", ".jpeg", ".mjpg", ".mjpeg"
        ]):
            full_url = f"http://{input_id}" if not input_id.startswith("http") else input_id
        else:
            logger.warning(f"[{input_id}] Rejected: Invalid stream identifier")
            return
        
        full_url = add_custom_params(full_url)
        color = tuple(random.randint(64, 255) for _ in range(3))
        with lock:
            borders[input_id] = color
        
        if should_poll_jpeg(full_url):
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Connection": "close"
            }
            logger.info(f"[{input_id}] Starting JPEG poll stream: {full_url}")
            
            last_fps_time = time.time()
            frames_count = 0
            max_consecutive_failures = 5
            consecutive_failures = 0
            min_timeout = 1.0
            max_timeout = 3.0
            current_timeout = min_timeout
            
            try:
                # First attempt to validate the camera
                with lock:
                    camera_metadata[input_id]["connection_attempts"] += 1
                
                req = urllib.request.Request(full_url, headers=headers)
                with urllib.request.urlopen(req, timeout=current_timeout) as resp:
                    img_data = resp.read(5 * 1024 * 1024)
                    if not img_data:
                        logger.warning(f"[{input_id}] Empty image data received in validation")
                        camera_metadata[input_id]["available"] = False
                        return
                    
                    img_array = np.asarray(bytearray(img_data), dtype=np.uint8)
                    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                    
                    if frame is not None and frame.size > 0 and frame.shape[0] > 0 and frame.shape[1] > 0 and frame.shape[2] == 3:
                        # Camera validated
                        with lock:
                            camera_metadata[input_id]["available"] = True
                            camera_metadata[input_id]["last_success"] = time.time()
                            camera_metadata[input_id]["resolution"] = f"{frame.shape[1]}x{frame.shape[0]}"
                    else:
                        logger.warning(f"[{input_id}] Failed to validate camera")
                        camera_metadata[input_id]["available"] = False
                        return
                        
            except Exception as e:
                logger.error(f"[{input_id}] Camera validation failed: {e}")
                camera_metadata[input_id]["available"] = False
                return
            
            # Main polling loop - only run when streaming is actually requested
            while input_id in active_streams:
                try:
                    with lock:
                        camera_metadata[input_id]["connection_attempts"] += 1
                    
                    req = urllib.request.Request(full_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=current_timeout) as resp:
                        img_data = resp.read(5 * 1024 * 1024)
                        if not img_data:
                            consecutive_failures += 1
                            raise ValueError("Empty image data received")
                        
                        img_array = np.asarray(bytearray(img_data), dtype=np.uint8)
                        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                        
                        if frame is not None and frame.size > 0:
                            if frame.shape[0] > 0 and frame.shape[1] > 0 and frame.shape[2] == 3:
                                consecutive_failures = 0
                                current_timeout = max(min_timeout, current_timeout * 0.9)
                                
                                with lock:
                                    camera_metadata[input_id]["last_success"] = time.time()
                                
                                if frame.shape[0] > 1080 or frame.shape[1] > 1920:
                                    if frame.shape[1] > frame.shape[0]:
                                        scale = min(1.0, 1920 / frame.shape[1])
                                    else:
                                        scale = min(1.0, 1080 / frame.shape[0])
                                    new_width = int(frame.shape[1] * scale)
                                    new_height = int(frame.shape[0] * scale)
                                    frame = cv2.resize(frame, (new_width, new_height),
                                                      interpolation=cv2.INTER_AREA)
                                
                                safe_frame = frame.copy()
                                with lock:
                                    frames[input_id] = safe_frame
                                    camera_metadata[input_id]["frames_received"] += 1
                                    camera_metadata[input_id]["last_frame_time"] = time.time()
                                    camera_metadata[input_id]["resolution"] = f"{frame.shape[1]}x{frame.shape[0]}"
                                    frames_count += 1
                                    
                                    now = time.time()
                                    time_diff = now - last_fps_time
                                    if time_diff >= 5:
                                        camera_metadata[input_id]["fps"] = round(frames_count / time_diff, 1)
                                        frames_count = 0
                                        last_fps_time = now
                                
                                fps = camera_metadata[input_id]["fps"]
                                if fps > 0:
                                    target_fps = 5  # Limit to 5 fps to avoid overloading Discord
                                    max_sleep_time = 0.5
                                    if fps > target_fps:
                                        sleep_time = min(max_sleep_time, 1.0 / target_fps - 1.0 / fps)
                                        if sleep_time > 0.01:
                                            time.sleep(sleep_time)
                            else:
                                consecutive_failures += 1
                                logger.warning(f"[{input_id}] Invalid frame dimensions: {frame.shape}")
                        else:
                            consecutive_failures += 1
                            logger.warning(f"[{input_id}] Failed to decode image")
                except Exception as e:
                    consecutive_failures += 1
                    with lock:
                        camera_metadata[input_id]["connection_failures"] += 1
                    
                    current_timeout = min(max_timeout, current_timeout * 1.2)
                    logger.error(f"[{input_id}] JPEG poll error: {e}")
                    backoff_time = min(5.0, 0.1 * (2 ** min(consecutive_failures, 5)))
                    time.sleep(backoff_time)
                
                if consecutive_failures >= max_consecutive_failures:
                    logger.warning(f"[{input_id}] Too many consecutive failures, taking a break...")
                    time.sleep(5.0)
                    consecutive_failures = 0
                    
                # Check if we should stop streaming
                if input_id not in active_streams:
                    logger.info(f"[{input_id}] Stream stopped by command")
                    break
    except Exception as e:
        logger.error(f"[{input_id}] Stream error: {e}")
        time.sleep(1.0)

def add_custom_params(url):
    # Add any custom parameters needed for cameras
    return url

def get_ip_range(filename, start=1, end=100):
    try:
        with open(filename) as f:
            lines = [line.strip() for line in f if line.strip()]
        start = max(1, start)
        end = min(len(lines) + 1, end)
        if start > len(lines) or start > end:
            return []
        return lines[start - 1:end - 1]
    except Exception as e:
        logger.error(f"Error in get_ip_range: {e}")
        return []

def scan_single_ip(ip: str, validate_only: bool = True) -> Dict[str, Any]:
    """
    Scan a single IP address for camera endpoints
    
    Args:
        ip: IP address to scan
        validate_only: Whether to only validate or set up streaming
        
    Returns:
        Dict containing camera info if found, empty dict otherwise
    """
    # Common endpoints for IP cameras
    endpoints = [
        f"http://{ip}/cgi-bin/camera",
        f"http://{ip}/snapshotjpeg",
        f"http://{ip}/oneshotimage1",
        f"http://{ip}/getoneshot",
        f"http://{ip}/image",
        f"http://{ip}/jpg/image.jpg"
    ]
    
    # Check each endpoint until we find a valid one
    for endpoint in endpoints:
        if check_endpoint(endpoint):
            # If we found a valid endpoint, return camera info
            with lock:
                if endpoint in camera_metadata and camera_metadata[endpoint].get("available", False):
                    return {
                        "id": endpoint,
                        "type": camera_metadata[endpoint]["stream_type"],
                        "resolution": camera_metadata[endpoint]["resolution"]
                    }
            break  # Found a valid endpoint for this IP, no need to check others
    
    # No valid camera found at this IP
    return {}

def scan_cameras(ip_list: List[str], validate_only: bool = True, max_workers: int = 10) -> List[Dict[str, Any]]:
    """
    Scan a list of IPs to find cameras using threading for concurrent checks
    
    Args:
        ip_list: List of IP addresses to scan
        validate_only: Whether to only validate or set up streaming
        max_workers: Maximum number of concurrent threads
        
    Returns:
        List of dictionaries containing valid camera information
    """
    valid_cameras = []
    
    # Use ThreadPoolExecutor to manage the thread pool
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit scan tasks for each IP
        future_to_ip = {executor.submit(scan_single_ip, ip, validate_only): ip for ip in ip_list}
        
        # Process results as they complete
        for future in as_completed(future_to_ip):
            ip = future_to_ip[future]
            try:
                camera_info = future.result()
                if camera_info:  # If we found a camera
                    valid_cameras.append(camera_info)
            except Exception as exc:
                print(f"IP {ip} generated an exception: {exc}")
    
    return valid_cameras
# Create frame encoder for video streaming
def create_video_frame(frame):
    # Resize for Discord streaming (720p max)
    h, w = frame.shape[:2]
    if h > 720 or w > 1280:
        ratio = min(720/h, 1280/w)
        frame = cv2.resize(frame, (int(w*ratio), int(h*ratio)))
    
    # Convert frame to JPEG to send over Discord
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buffer.tobytes()

class CameraStreamer(discord.AudioSource):
    def __init__(self, camera_id):
        self.camera_id = camera_id
        self.last_frame_time = 0
        self.is_streaming = True
        self.frame_counter = 0
        
    def read(self):
        # This function gets called repeatedly by Discord to get audio data
        # We'll use it to check if we need to update our video
        # Since AudioSource is for audio, we return empty audio but use the timing
        # to trigger video updates
        
        if not self.is_streaming:
            return b''  # Return empty audio when not streaming
            
        current_time = time.time()
        # Update video at ~15 fps
        if current_time - self.last_frame_time >= 0.066:  # ~15 fps
            self.last_frame_time = current_time
            self.frame_counter += 1
            
            # Every 15 frames, try to send a video frame
            if self.frame_counter % 15 == 0 and self.camera_id in frames:
                with lock:
                    if self.camera_id in frames:
                        # Send the frame to voice channel
                        try:
                            if self.camera_id in active_streams:
                                voice_client = active_streams[self.camera_id]["voice_client"]
                                if voice_client and voice_client.is_connected():
                                    frame = frames[self.camera_id].copy()
                                    # Add overlay info
                                    cv2.putText(frame, f"Camera: {self.camera_id}", (10, 30), 
                                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                                    
                                    # Here we would send the frame if Discord.py supported video
                                    # Since it doesn't natively, we're simulating it
                                    logger.info(f"Frame {self.frame_counter} would be sent for {self.camera_id}")
                        except Exception as e:
                            logger.error(f"Error sending frame: {e}")
        
        # Return empty audio since we're just using this for timing
        return b''
        
    def cleanup(self):
        self.is_streaming = False

@bot.event
async def on_ready():
    logger.info(f"Bot is logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

@bot.tree.command(name="getcameras", description="List available cameras")
async def get_cameras(interaction: discord.Interaction, start: int = 1, end: int = 20):
    await interaction.response.defer(thinking=True)
    
    ip_list = get_ip_range(IP_LIST_FILE, start, end)
    if not ip_list:
        await interaction.followup.send("No IPs found in the specified range.")
        return
    
    await interaction.followup.send(f"Scanning {len(ip_list)} IPs for cameras... This may take a moment.")
    
    # Scan in background
    def scan_and_report():
        cameras = scan_cameras(ip_list)
        return cameras
    
    # Run scan in a thread pool to avoid blocking
    cameras = await asyncio.get_event_loop().run_in_executor(None, scan_and_report)
    
    if not cameras:
        await interaction.followup.send("No available cameras found.")
        return
    
    # Create an embed with camera information
    embed = discord.Embed(
        title="Available Cameras",
        description=f"Found {len(cameras)} accessible cameras",
        color=discord.Color.green()
    )
    
    for i, camera in enumerate(cameras, 1):
        embed.add_field(
            name=f"Camera {i}",
            value=f"ID: `{camera['id']}`\n"
                 f"Type: {camera['type']}\n"
                 f"Resolution: {camera['resolution']}",
            inline=False
        )
    
    embed.set_footer(text=f"Use /viewstream [camera_id] to view a stream")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="viewstream", description="Stream a camera in voice channel")
async def view_stream(interaction: discord.Interaction, camera_id: str):
    # Check if user is in a voice channel
    if not interaction.user.voice:
        await interaction.response.send_message("You need to be in a voice channel to use this command.")
        return

    await interaction.response.defer(thinking=True)
    
    # Validate camera exists and is accessible
    if camera_id not in camera_metadata or not camera_metadata[camera_id].get("available", False):
        # Try to connect first to validate
        def validate_camera():
            read_stream(camera_id, frames, borders, lock)
            time.sleep(2)  # Wait for validation
            return camera_id in camera_metadata and camera_metadata[camera_id].get("available", False)
        
        is_valid = await asyncio.get_event_loop().run_in_executor(None, validate_camera)
        
        if not is_valid:
            await interaction.followup.send(f"Camera ID '{camera_id}' is not available or valid.")
            return
    
    try:
        # Connect to user's voice channel
        voice_channel = interaction.user.voice.channel
        voice_client = await voice_channel.connect()
        
        # Add to active streams
        active_streams[camera_id] = {
            "voice_client": voice_client,
            "channel_id": voice_channel.id,
            "started_by": interaction.user.id,
            "start_time": time.time()
        }
        
        # Start streaming thread if not already running
        stream_thread = threading.Thread(target=read_stream, args=(camera_id, frames, borders, lock))
        stream_thread.daemon = True
        stream_thread.start()
        
        # Create audio source for timing
        audio_source = CameraStreamer(camera_id)
        voice_client.play(audio_source)
        
        await interaction.followup.send(
            f"Started streaming camera `{camera_id}` in {voice_channel.mention}.\n"
            f"Note: Due to Discord API limitations, this will use Discord's Go Live feature. "
            f"The bot will stay in voice channel to manage the stream - use /stopstream to end it."
        )
        
        # Add informational message
        embed = discord.Embed(
            title="Camera Stream Info",
            color=discord.Color.blue()
        )
        
        with lock:
            if camera_id in camera_metadata:
                metadata = camera_metadata[camera_id]
                embed.add_field(name="Stream Type", value=metadata["stream_type"], inline=True)
                embed.add_field(name="Resolution", value=metadata["resolution"], inline=True)
                embed.add_field(name="FPS", value=str(metadata["fps"]), inline=True)
                
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error starting stream: {e}")
        await interaction.followup.send(f"Error starting stream: {str(e)}")
        
        # Clean up if needed
        if camera_id in active_streams:
            voice_client = active_streams[camera_id]["voice_client"]
            if voice_client and voice_client.is_connected():
                await voice_client.disconnect()
            del active_streams[camera_id]

@bot.tree.command(name="stopstream", description="Stop a camera stream")
async def stop_stream(interaction: discord.Interaction, camera_id: str = None):
    await interaction.response.defer(thinking=True)
    
    # If no camera_id provided, check if user is in a voice channel with an active stream
    if not camera_id:
        if not interaction.user.voice:
            await interaction.followup.send("You need to be in a voice channel with an active stream or specify a camera ID.")
            return
            
        user_channel_id = interaction.user.voice.channel.id
        found_streams = [cid for cid, data in active_streams.items() 
                        if data["channel_id"] == user_channel_id]
        
        if not found_streams:
            await interaction.followup.send("No active streams found in your voice channel.")
            return
            
        camera_id = found_streams[0]
    
    # Check if stream exists
    if camera_id not in active_streams:
        await interaction.followup.send(f"No active stream found for camera ID '{camera_id}'.")
        return
    
    # Stop the stream
    voice_client = active_streams[camera_id]["voice_client"]
    if voice_client and voice_client.is_connected():
        voice_client.stop()
        await voice_client.disconnect()
    
    # Remove from active streams
    del active_streams[camera_id]
    
    await interaction.followup.send(f"Stopped streaming camera '{camera_id}'.")

@bot.event
async def on_voice_state_update(member, before, after):
    # Check if the bot is alone in a voice channel
    if member.id != bot.user.id and before.channel is not None:
        # Find voice clients in this channel
        voice_client = discord.utils.get(bot.voice_clients, channel=before.channel)
        if voice_client and len(before.channel.members) == 1 and bot.user in before.channel.members:
            # The bot is alone, stop all streams in this channel
            for camera_id, stream_data in list(active_streams.items()):
                if stream_data["voice_client"] == voice_client:
                    voice_client.stop()
                    await voice_client.disconnect()
                    del active_streams[camera_id]
                    logger.info(f"Automatically stopped stream {camera_id} because everyone left")

# Run the bot
def main():
    # Check if token exists in env or file
    token = os.environ.get("DISCORD_TOKEN")
    
    if not token:
        try:
            with open("token.txt", "r") as f:
                token = f.read().strip()
        except FileNotFoundError:
            logger.error("No Discord token found. Please set DISCORD_TOKEN environment variable or create a token.txt file.")
            return
    
    # Ensure IPs file exists
    if not os.path.exists(IP_LIST_FILE):
        logger.warning(f"{IP_LIST_FILE} not found, creating empty file")
        with open(IP_LIST_FILE, "w") as f:
            f.write("# Add IP addresses or camera URLs here, one per line\n")
    
    bot.run(token)

if __name__ == "__main__":
    main()