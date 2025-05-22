# main.py

import random
from torrent_parser import parse_torrent_file
from tracker_client import get_peers_from_tracker
from peer_client import perform_peer_handshake, process_peer_messages

if __name__ == "__main__":
    torrent_file_path = 'lubuntu.iso.torrent' 

    # Generate a random 20-byte peer ID for this client
    # Typically starts with client identifier (e.g., '-TR2940-') followed by random bytes
    my_peer_id = b'-PY0001-' + bytes([random.randint(0, 255) for _ in range(12)])
    print(f"My Peer ID: {my_peer_id.hex()}")

    try:
        # 1. Parse the .torrent file
        decoded_torrent_data, announce_url, info_hash = parse_torrent_file(torrent_file_path)

        # Calculate total number of pieces from the pieces field
        info_dict = decoded_torrent_data[b'info']
        pieces_hash = info_dict[b'pieces']
        total_pieces = len(pieces_hash) // 20  # Each piece hash is 20 bytes
        print(f"Total pieces: {total_pieces}")

        # Extract piece hashes
        piece_hashes = []
        for i in range(total_pieces):
            piece_hash = pieces_hash[i*20:(i+1)*20]
            piece_hashes.append(piece_hash)

        # 2. Get peers from the tracker
        peers = get_peers_from_tracker(announce_url, info_hash, my_peer_id)

        if not peers:
            print("No peers found or error with tracker. Exiting.")
        else:
            # 3. Attempt handshake with the first peer found
            # In a real client, you'd try multiple peers concurrently.
            first_peer_ip, first_peer_port = peers[0]
            peer_socket = perform_peer_handshake(first_peer_ip, first_peer_port, info_hash, my_peer_id)

            if peer_socket:
                print("\nHandshake successful, processing peer messages...")
                process_peer_messages(peer_socket, total_pieces, piece_hashes)
                peer_socket.close()
                print("\nBasic BitTorrent connection flow completed successfully with one peer.")
            else:
                print("\nBasic BitTorrent connection flow failed with the first peer.")

    except FileNotFoundError:
        print(f"Error: Torrent file not found at '{torrent_file_path}'. Please update the path.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

