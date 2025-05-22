# peer_client.py

import socket
import struct
import hashlib
import random

# Module-level state variables
peer_choking = True  # Initially, we are choked by the peer
am_interested = False  # Initially, we are not interested
available_pieces = set()  # Track available pieces
downloaded_pieces = {}  # Track downloaded pieces and their data

def perform_peer_handshake(peer_ip, peer_port, info_hash, peer_id):
    """
    Connects to a peer and performs the BitTorrent handshake.
    Automatically detects IPv4 or IPv6 and creates the appropriate socket.
    Returns the socket if handshake is successful, None otherwise.
    """
    print(f"\n--- Attempting Handshake with Peer: {peer_ip}:{peer_port} ---")
    try:
        # Determine address family (IPv4 or IPv6)
        try:
            socket.inet_pton(socket.AF_INET, peer_ip)
            addr_family = socket.AF_INET
            print(f"Detected IPv4 address: {peer_ip}")
        except socket.error:
            try:
                socket.inet_pton(socket.AF_INET6, peer_ip)
                addr_family = socket.AF_INET6
                print(f"Detected IPv6 address: {peer_ip}")
            except socket.error:
                print(f"Invalid IP address format: {peer_ip}")
                return None

        peer_socket = socket.socket(addr_family, socket.SOCK_STREAM)
        peer_socket.settimeout(5) # Set a timeout for connection and operations
        peer_socket.connect((peer_ip, peer_port))
        print(f"Connected to {peer_ip}:{peer_port}")

        # Construct handshake message
        # pstrlen (1 byte): length of protocol string (19 for "BitTorrent protocol")
        # pstr (19 bytes): "BitTorrent protocol"
        # reserved (8 bytes): all zeros
        # info_hash (20 bytes): SHA1 hash of the info dictionary
        # peer_id (20 bytes): client's peer ID
        pstrlen = 19
        pstr = b"BitTorrent protocol"
        reserved = b"\x00" * 8 # 8 null bytes
        
        handshake_message = struct.pack(
            f">B{pstrlen}s8s20s20s",
            pstrlen, pstr, reserved, info_hash, peer_id
        )
        
        peer_socket.sendall(handshake_message)
        print("Sent handshake message.")

        # Receive handshake response
        received_handshake = peer_socket.recv(68) # 1 + 19 + 8 + 20 + 20 = 68 bytes
        
        if len(received_handshake) < 68:
            print("Received incomplete handshake.")
            peer_socket.close()
            return None

        # Unpack received handshake
        received_pstrlen, received_pstr, received_reserved, received_info_hash, received_peer_id = \
            struct.unpack(f">B19s8s20s20s", received_handshake)

        print(f"Received handshake from peer ID: {received_peer_id.hex()}")

        # Verify info hash
        if received_info_hash != info_hash:
            print("Handshake failed: Info hash mismatch.")
            peer_socket.close()
            return None

        print("Handshake successful! Info hash matched.")
        return peer_socket

    except socket.timeout:
        print(f"Connection to {peer_ip}:{peer_port} timed out.")
        return None
    except ConnectionRefusedError:
        print(f"Connection to {peer_ip}:{peer_port} refused.")
        return None
    except Exception as e:
        print(f"An error occurred during handshake with {peer_ip}:{peer_port}: {e}")
        return None

def process_peer_messages(sock, total_pieces, piece_hashes, timeout=10):
    """
    Process initial peer messages after a successful handshake.
    Handles bitfield, choke/unchoke, and interested/not interested messages.
    
    Args:
        sock: Socket connected to the peer
        total_pieces: Total number of pieces in the torrent
        piece_hashes: List of SHA1 hashes for all pieces from the torrent file
        timeout: Socket timeout in seconds
    """
    print("\n--- Processing Peer Messages ---")
    
    # Set a timeout for receiving messages
    sock.settimeout(timeout)
    
    # Message IDs in the BitTorrent protocol
    MESSAGE_CHOKE = 0
    MESSAGE_UNCHOKE = 1
    MESSAGE_INTERESTED = 2
    MESSAGE_NOT_INTERESTED = 3
    MESSAGE_HAVE = 4
    MESSAGE_BITFIELD = 5
    MESSAGE_REQUEST = 6
    MESSAGE_PIECE = 7
    MESSAGE_CANCEL = 8
    
    # Use global state variables
    global peer_choking, am_interested, available_pieces, downloaded_pieces
    
    try:
        # Process messages in a loop
        while True:
            # Read message length (4 bytes)
            length_prefix = sock.recv(4)
            if not length_prefix:
                print("Connection closed by peer.")
                break
                
            # Unpack the length prefix
            message_length = struct.unpack(">I", length_prefix)[0]
            
            # Keep-alive message (length = 0)
            if message_length == 0:
                print("Received keep-alive message")
                continue
                
            # Read message ID and payload
            message_data = sock.recv(message_length)
            if len(message_data) < 1:
                print("Received incomplete message")
                break
                
            message_id = message_data[0]
            payload = message_data[1:] if message_length > 1 else b''
            
            # Process message based on ID
            if message_id == MESSAGE_CHOKE:
                peer_choking = True
                print("Peer sent CHOKE message")
                
            elif message_id == MESSAGE_UNCHOKE:
                peer_choking = False
                print("Peer sent UNCHOKE message")
                
                # If we're interested and now unchoked, we can start requesting pieces
                if am_interested:
                    print("We can now request pieces!")
                    # Request a piece that the peer has
                    request_piece(sock, available_pieces)
                
            elif message_id == MESSAGE_INTERESTED:
                print("Peer sent INTERESTED message")
                
            elif message_id == MESSAGE_NOT_INTERESTED:
                print("Peer sent NOT INTERESTED message")
                
            elif message_id == MESSAGE_HAVE:
                if len(payload) == 4:
                    piece_index = struct.unpack(">I", payload)[0]
                    if piece_index < total_pieces:  # Validate piece index
                        available_pieces.add(piece_index)
                        print(f"Peer has piece {piece_index}")
                        
                        # If we're not already interested, send interested message
                        if not am_interested:
                            send_interested_message(sock)
                            am_interested = True
                    else:
                        print(f"Received invalid piece index: {piece_index}")
                
            elif message_id == MESSAGE_BITFIELD:
                print("Received BITFIELD message")
                process_bitfield(payload, available_pieces, total_pieces)
                
                # If peer has any pieces we want, express interest
                if available_pieces and not am_interested:
                    send_interested_message(sock)
                    am_interested = True
                    
            elif message_id == MESSAGE_REQUEST:
                print("Peer sent REQUEST message (we don't support uploading yet)")
                
            elif message_id == MESSAGE_PIECE:
                print("Received PIECE message")
                process_piece_message(payload, piece_hashes)
                
                # Request another block if we're not choked and interested
                if not peer_choking and am_interested:
                    # Find the current piece we're downloading
                    current_piece = None
                    for piece_index in downloaded_pieces:
                        if not downloaded_pieces[piece_index]['is_complete']:
                            current_piece = piece_index
                            break
                    
                    if current_piece is not None:
                        # Continue requesting blocks for the current piece
                        request_piece(sock, available_pieces)
                    else:
                        # Start a new piece
                        request_piece(sock, available_pieces)
                
            elif message_id == MESSAGE_CANCEL:
                print("Peer sent CANCEL message (unexpected at this stage)")
                
            else:
                print(f"Received unknown message ID: {message_id}")
            
            # For demonstration purposes, break after downloading a few pieces
            if len(downloaded_pieces) >= 3:
                print(f"Downloaded {len(downloaded_pieces)} pieces successfully.")
                break
                
    except socket.timeout:
        print("Timeout while waiting for peer messages")
    except Exception as e:
        print(f"Error processing peer messages: {e}")
    
    return downloaded_pieces

def request_piece(sock, available_pieces, block_size=16384):
    """
    Send a REQUEST message to the peer for a piece we don't have yet.
    
    Args:
        sock: Socket connected to the peer
        available_pieces: Set of piece indices the peer has
        block_size: Size of each block to request (typically 16KB)
    """
    # Find a piece to request (one we don't have but the peer does)
    pieces_to_request = [p for p in available_pieces if p not in downloaded_pieces]
    
    if not pieces_to_request:
        print("No new pieces to request")
        return
    
    # Select a piece to request
    piece_index = pieces_to_request[0]
    
    # Initialize piece tracking if not already done
    if piece_index not in downloaded_pieces:
        downloaded_pieces[piece_index] = {
            'blocks': {},
            'total_blocks': 0,
            'piece_length': 262144,  # Standard piece size (256KB)
            'is_complete': False,
            'requested_blocks': set()  # Track which blocks we've requested
        }
    
    # Find the next block to request
    piece_info = downloaded_pieces[piece_index]
    current_offset = 0
    
    # Find the first block we haven't requested or received
    while current_offset < piece_info['piece_length']:
        if (current_offset not in piece_info['blocks'] and 
            current_offset not in piece_info['requested_blocks']):
            # Send REQUEST message: <len=0013><id=6><index><begin><length>
            message = struct.pack(">IBIII", 13, 6, piece_index, current_offset, block_size)
            sock.sendall(message)
            print(f"Requesting block {current_offset//block_size + 1} of piece {piece_index} (offset: {current_offset}, length: {block_size})")
            
            # Mark this block as requested
            piece_info['requested_blocks'].add(current_offset)
            return  # Request one block at a time
            
        current_offset += block_size
    
    print(f"No more blocks to request for piece {piece_index}")

def verify_piece(piece_index, piece_data, piece_hashes):
    """
    Verify a completed piece against its expected hash.
    
    Args:
        piece_index: Index of the piece to verify
        piece_data: Complete piece data (concatenated blocks)
        piece_hashes: List of SHA1 hashes for all pieces from the torrent file
    
    Returns:
        bool: True if piece hash matches, False otherwise
    """
    if piece_index >= len(piece_hashes):
        print(f"Invalid piece index {piece_index} for verification (max: {len(piece_hashes)-1})")
        return False
        
    # Calculate SHA1 hash of the piece data
    piece_hash = hashlib.sha1(piece_data).digest()
    expected_hash = piece_hashes[piece_index]
    
    print(f"\nVerifying piece {piece_index}:")
    print(f"  Piece size: {len(piece_data)} bytes")
    print(f"  Expected hash: {expected_hash.hex()}")
    print(f"  Actual hash:   {piece_hash.hex()}")
    
    if piece_hash == expected_hash:
        print(f"[SUCCESS] Piece {piece_index} hash verification successful")
        return True
    else:
        print(f"[FAILED] Piece {piece_index} hash verification failed")
        return False

def combine_piece_blocks(piece_index):
    """
    Combine all blocks of a piece in order.
    
    Args:
        piece_index: Index of the piece to combine
        
    Returns:
        bytes: Combined piece data, or None if piece is incomplete
    """
    if piece_index not in downloaded_pieces:
        print(f"Piece {piece_index} not found in downloaded pieces")
        return None
        
    piece_info = downloaded_pieces[piece_index]
    if not piece_info['blocks']:
        print(f"Piece {piece_index} has no blocks to combine")
        return None
        
    # Sort blocks by offset to ensure correct order
    sorted_offsets = sorted(piece_info['blocks'].keys())
    print(f"Combining {len(sorted_offsets)} blocks for piece {piece_index}")
    print(f"Block offsets in order: {sorted_offsets}")
    
    # Combine blocks in order
    piece_data = b''
    total_size = 0
    for offset in sorted_offsets:
        block_data = piece_info['blocks'][offset]
        piece_data += block_data
        total_size += len(block_data)
        print(f"  Added block at offset {offset}, length {len(block_data)}")
        
    print(f"Successfully combined piece {piece_index} - Total size: {total_size} bytes")
    return piece_data

def process_piece_message(payload, piece_hashes):
    """
    Process a PIECE message from the peer.
    
    Args:
        payload: The message payload (excluding message ID)
        piece_hashes: List of SHA1 hashes for all pieces from the torrent file
    """
    if len(payload) < 8:
        print("Received invalid PIECE message (too short)")
        return
    
    # Extract piece index, begin offset, and block data
    piece_index, begin = struct.unpack(">II", payload[:8])
    block_data = payload[8:]
    
    print(f"Received block for piece {piece_index}, offset {begin}, length {len(block_data)}")
    
    # Store the piece data
    if piece_index not in downloaded_pieces:
        downloaded_pieces[piece_index] = {
            'blocks': {},  # Dictionary to store blocks by their offset
            'total_blocks': 0,  # Total number of blocks expected for this piece
            'piece_length': 262144,  # Standard piece size (256KB)
            'is_complete': False,  # Flag to track if all blocks are received
            'requested_blocks': set()  # Track which blocks we've requested
        }
    
    # Store the block data
    downloaded_pieces[piece_index]['blocks'][begin] = block_data
    
    # Remove from requested blocks since we received it
    downloaded_pieces[piece_index]['requested_blocks'].discard(begin)
    
    # Calculate expected number of blocks for this piece
    # Each block is typically 16KB (16384 bytes) except possibly the last one
    block_size = 16384
    piece_length = downloaded_pieces[piece_index]['piece_length']
    
    # Calculate total expected blocks
    total_blocks = (piece_length + block_size - 1) // block_size
    downloaded_pieces[piece_index]['total_blocks'] = total_blocks
    
    # Check if we have all blocks for this piece
    received_blocks = len(downloaded_pieces[piece_index]['blocks'])
    if received_blocks == total_blocks:
        # Verify all blocks are present and in order
        expected_offsets = set(range(0, piece_length, block_size))
        actual_offsets = set(downloaded_pieces[piece_index]['blocks'].keys())
        
        if expected_offsets == actual_offsets:
            # Combine blocks into complete piece
            piece_data = combine_piece_blocks(piece_index)
            if piece_data is None:
                print(f"Failed to combine blocks for piece {piece_index}")
                return
                
            # Verify piece hash
            if verify_piece(piece_index, piece_data, piece_hashes):
                downloaded_pieces[piece_index]['is_complete'] = True
                print(f"[SUCCESS] Piece {piece_index} is complete and verified")
                
                # Write verified piece to disk
                try:
                    # Calculate the file offset for this piece
                    piece_offset = piece_index * piece_length
                    
                    # Open the file in binary mode for writing
                    with open("downloaded_file", "r+b") as f:
                        # Seek to the correct position
                        f.seek(piece_offset)
                        # Write the piece data
                        f.write(piece_data)
                        print(f"Wrote piece {piece_index} to disk at offset {piece_offset}")
                except Exception as e:
                    print(f"Error writing piece {piece_index} to disk: {e}")
            else:
                print(f"[FAILED] Piece {piece_index} failed verification - will need to be re-downloaded")
                # Clear the piece data
                downloaded_pieces[piece_index] = {
                    'blocks': {},
                    'total_blocks': 0,
                    'piece_length': 262144,  # Standard piece size (256KB)
                    'is_complete': False,
                    'requested_blocks': set()
                }
        else:
            print(f"[ERROR] Piece {piece_index} has incorrect block offsets")
    else:
        print(f"Piece {piece_index}: {received_blocks}/{total_blocks} blocks received")

def process_bitfield(bitfield_payload, available_pieces, total_pieces):
    """
    Process a bitfield message to determine which pieces the peer has.
    Updates the available_pieces set.
    """
    print("Processing bitfield of length:", len(bitfield_payload))
    
    for byte_index, byte in enumerate(bitfield_payload):
        for bit_index in range(8):
            piece_index = byte_index * 8 + bit_index
            if piece_index < total_pieces:  # Only process valid piece indices
                # Check if the bit is set (1)
                if byte & (128 >> bit_index):
                    available_pieces.add(piece_index)
                
    print(f"Peer has {len(available_pieces)}/{total_pieces} pieces available")

def send_interested_message(sock):
    """
    Send an INTERESTED message to the peer.
    """
    # INTERESTED message: <len=0001><id=2>
    message = struct.pack(">IB", 1, 2)
    sock.sendall(message)
    print("Sent INTERESTED message to peer")