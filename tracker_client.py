# tracker_client.py

import requests
import socket
import struct
import random
from urllib.parse import urlencode, urlparse, quote_from_bytes
from bencoding import bdecode # Import bdecode for tracker response

# --- UDP Tracker Constants ---
# These are standard values for the UDP BitTorrent tracker protocol
CONNECT_ACTION = 0
ANNOUNCE_ACTION = 1
ERROR_ACTION = 3
# Transaction ID and Connection ID are random and managed per request/connection

def get_peers_from_tracker(announce_url, info_hash, peer_id, port=6881):
    """
    Communicates with the tracker to get a list of peers.
    Handles both HTTP(S) and UDP trackers.
    Returns a list of (ip, port) tuples.
    """
    print("\n--- Communicating with Tracker ---")
    
    parsed_url = urlparse(announce_url)
    scheme = parsed_url.scheme

    if scheme.startswith('http'):
        # --- HTTP(S) Tracker Communication ---
        print(f"Detected HTTP(S) tracker: {announce_url}")
        
        params = {
            'info_hash': info_hash, # Pass raw bytes
            'peer_id': peer_id,     # Pass raw bytes
            'port': port,
            'uploaded': 0,
            'downloaded': 0,
            'left': 0,
            'compact': 1,
            'event': 'started'
        }

        # Custom quoting function for urlencode to handle bytes correctly
        # This prevents double-encoding of info_hash and peer_id
        # It now accepts *args and **kwargs to handle extra arguments from urlencode
        def byte_quoter(s, *args, **kwargs):
            if isinstance(s, bytes):
                return quote_from_bytes(s)
            # Use requests.utils.quote for strings, passing along any relevant kwargs like 'safe'
            return requests.utils.quote(str(s), **kwargs) 

        # Construct the URL
        # urlencode will now use byte_quoter for byte strings
        query_string = urlencode(params, quote_via=byte_quoter)
        tracker_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{query_string}"
        print(f"Tracker URL: {tracker_url}")

        try:
            response = requests.get(tracker_url, timeout=10)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            tracker_response = bdecode(response.content)

            if b'failure reason' in tracker_response:
                print(f"Tracker Error: {tracker_response[b'failure reason'].decode('utf-8')}")
                return []

            peers = []
            if b'peers' in tracker_response:
                peers_data = tracker_response[b'peers']
                if isinstance(peers_data, bytes):
                    for i in range(0, len(peers_data), 6):
                        ip_bytes = peers_data[i:i+4]
                        port_bytes = peers_data[i+4:i+6]
                        ip = socket.inet_ntoa(ip_bytes)
                        port = struct.unpack('>H', port_bytes)[0]
                        peers.append((ip, port))
                elif isinstance(peers_data, list):
                    for peer_info in peers_data:
                        ip = peer_info[b'ip'].decode('utf-8')
                        port = peer_info[b'port']
                        peers.append((ip, port))
            
            print(f"Found {len(peers)} peers.")
            return peers

        except requests.exceptions.RequestException as e:
            print(f"Error communicating with HTTP(S) tracker: {e}")
            return []

    elif scheme == 'udp':
        # --- UDP Tracker Communication ---
        print(f"Detected UDP tracker: {announce_url}")
        tracker_host = parsed_url.hostname
        tracker_port = parsed_url.port

        if not tracker_host or not tracker_port:
            print(f"Invalid UDP tracker URL: {announce_url}")
            return []

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(10) # Timeout for UDP responses

            # 1. Connect Request
            connection_id = 0x41727101980 # Magic constant
            transaction_id = random.randint(0, 0xFFFFFFFF)

            # struct.pack: ! = network byte order (big-endian), Q = unsigned long long, I = unsigned int
            connect_request = struct.pack("!QII", connection_id, CONNECT_ACTION, transaction_id)
            
            sock.sendto(connect_request, (tracker_host, tracker_port))
            print("Sent UDP connect request.")

            response_data, _ = sock.recvfrom(2048) # Max UDP packet size for BitTorrent is typically 2048 bytes
            
            # Parse Connect Response (16 bytes)
            # ! = network byte order, I = unsigned int, Q = unsigned long long
            response_action, response_transaction_id, new_connection_id = struct.unpack("!IIQ", response_data[:16])

            if response_action != CONNECT_ACTION or response_transaction_id != transaction_id:
                print("UDP Connect response mismatch or error.")
                return []
            
            print(f"Received UDP connect response. New Connection ID: {new_connection_id}")

            # 2. Announce Request
            transaction_id = random.randint(0, 0xFFFFFFFF) # New transaction ID for announce
            
            # Event: 0=none, 1=completed, 2=started, 3=stopped
            event = 2 # 'started'

            # IP address: 0 for default
            ip_address = 0 
            
            # Key: random 4-byte value for client identification
            key = random.randint(0, 0xFFFFFFFF)

            # Num_want: -1 for default (50 peers)
            num_want = -1 

            # Port: client's listening port
            client_port = port

            announce_request = struct.pack(
                "!QII20s20sQQQIIiH",
                new_connection_id,
                ANNOUNCE_ACTION,
                transaction_id,
                info_hash,
                peer_id,
                0, # downloaded
                0, # left
                0, # uploaded
                event,
                ip_address,
                key,
                num_want,
                client_port
            )

            sock.sendto(announce_request, (tracker_host, tracker_port))
            print("Sent UDP announce request.")

            response_data, _ = sock.recvfrom(2048)

            # Parse Announce Response
            # ! = network byte order, I = unsigned int, i = signed int
            response_action, response_transaction_id, interval, leechers, seeders = \
                struct.unpack("!IIIII", response_data[:20])

            if response_action != ANNOUNCE_ACTION or response_transaction_id != transaction_id:
                print("UDP Announce response mismatch or error.")
                return []
            
            print(f"Received UDP announce response. Interval: {interval}, Leechers: {leechers}, Seeders: {seeders}")

            peers = []
            # Peers start after the initial 20 bytes of the announce response
            peers_data_start = 20
            for i in range(peers_data_start, len(response_data), 6):
                ip_bytes = response_data[i:i+4]
                port_bytes = response_data[i+4:i+6]
                ip = socket.inet_ntoa(ip_bytes)
                port = struct.unpack("!H", port_bytes)[0]
                peers.append((ip, port))
            
            print(f"Found {len(peers)} peers.")
            return peers

        except socket.timeout:
            print(f"UDP tracker communication timed out with {tracker_host}:{tracker_port}.")
            return []
        except Exception as e:
            print(f"An error occurred during UDP tracker communication with {tracker_host}:{tracker_port}: {e}")
            return []
    else:
        print(f"Unsupported tracker scheme: {scheme}. Only http(s) and udp are supported.")
        return []

