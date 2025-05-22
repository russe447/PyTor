# PyTor - Python BitTorrent Client

A lightweight BitTorrent client implementation in Python that demonstrates the core functionality of the BitTorrent protocol.

## Features

- Torrent file parsing and bencoding support
- Tracker communication for peer discovery
- Peer protocol implementation
- Basic peer handshake and message processing
- Support for multiple pieces and piece verification

## Project Structure

- `main.py` - Main entry point and orchestration of the BitTorrent client
- `bencoding.py` - Implementation of Bencode encoding/decoding
- `torrent_parser.py` - Torrent file parsing functionality
- `tracker_client.py` - Tracker communication and peer discovery
- `peer_client.py` - Peer protocol implementation and message handling

## Requirements

- Python 3.x
- Required packages (see requirements.txt)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/pytor.git
cd pytor
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

1. Place your .torrent file in the project directory
2. Update the `torrent_file_path` in `main.py` if needed
3. Run the client:

```bash
python main.py
```

## Implementation Details

The client implements the following BitTorrent protocol components:

1. **Torrent File Parsing**

   - Bencode decoding
   - Info hash calculation
   - Piece hash extraction

2. **Tracker Communication**

   - HTTP/HTTPS tracker support
   - Peer list retrieval
   - Basic error handling

3. **Peer Protocol**
   - Peer handshake
   - Message processing
   - Basic piece management

## Limitations

This is a basic implementation and does not include:

- Full download/upload functionality
- DHT support
- PEX (Peer Exchange)
- Magnet link support
- GUI interface

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- BitTorrent Protocol Specification
- Python community for various libraries and tools
