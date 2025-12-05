# Code by DHT@Matthew

from config import Config
from helper.ws_helper import ws_server
from receive_server import RelayServer


def main():
    # Validate configuration
    Config.validate()

    # Initialize SIP server with WebSocket server
    server = RelayServer(ws_server=ws_server)
    server_process = server.start()

    print(f"SIP Server started on {Config.SIP_LOCAL_IP}:{Config.SIP_LOCAL_PORT}")
    print(f"WebSocket Server started on {Config.WS_HOST}:{Config.WS_PORT}")
    print("Press Ctrl+C to stop...")

    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\nStopping servers...")
        server.stop(server_process)
        ws_server.stop_ws()
        print("Servers stopped")


if __name__ == "__main__":
    main()
