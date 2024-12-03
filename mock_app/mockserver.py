import asyncio
import json
import random
import logging
from websockets import serve
from typing import Dict, Any, Final
import os
from datetime import datetime


BASE_LOGS_DIR: Final[str] = "mock_logs"
BASE_DATA_DIR: Final[str] = "mock_data"

# Read the PRODUCT_ID environment variable
PRODUCT_ID: Final[str] = os.getenv("PRODUCT_ID")

# Setup for log and data file timestamps
APP_START_TIMESTAMP: Final[str] = datetime.now().strftime("%Y-%m-%d-%H%M%S")

# const number of how many records to update in one go
# level2_50 channel allows up to 50
L2UPDATE_COUNT: Final[int] = int(os.getenv("L2UPDATE_COUNT", 50))

# which port to run the pair specific mock instance
MOCK_PORT: Final[int] = int(os.getenv("MOCK_PORT", "8765"))

class MockServer:
    def __init__(self, product_id, update_count=50):
        self.product_id = product_id
        self.update_count = update_count

        self.history_file = self._setup_file(BASE_LOGS_DIR, log_file=True)
        self.output_file = self._setup_file(BASE_DATA_DIR) if os.getenv("DATA_STORE", "False").lower() == "true" else None
        self.logger = self._setup_logger()

    def _setup_file(self, base_folder: str, log_file: bool = False) -> str:
        """
        Create a folder structure based on product_id and date, and return the file path.
        """
        folder_path = os.path.join(base_folder, self.product_id)
        os.makedirs(folder_path, exist_ok=True)

        filename = (
            f"history-{APP_START_TIMESTAMP}.log" 
            if log_file else f"messages-{APP_START_TIMESTAMP}.json"
        )
        return os.path.join(folder_path, filename)

    def _write_to_output_file(self, message: dict):
        """Write a message to the output file in DATA_STORE mode."""
        if os.getenv("DATA_STORE", "False").lower() == "true" and self.output_file:
            try:
                with open(self.output_file, "a") as file:
                    json.dump(message, file)
                    file.write("\n")
            except Exception as e:
                self.logger.error(f"Failed to write message to file: {e}")


    def _setup_logger(self) -> logging.Logger:
        """
        Set up a logger for the application.
        """
        logger = logging.getLogger(self.product_id)
        logger.setLevel(logging.INFO)

        # Prevent propagation to the root logger
        logger.propagate = False

        # Check if handlers are already attached
        if not logger.handlers:
            # Console handler
            handler_console = logging.StreamHandler()
            # File handler
            handler_file = logging.FileHandler(self.history_file)

            # Formatter
            formatter = logging.Formatter(f"%(asctime)s - {self.product_id} - %(levelname)s - %(message)s")
            handler_console.setFormatter(formatter)
            handler_file.setFormatter(formatter)

            # Attach handlers
            logger.addHandler(handler_console)
            logger.addHandler(handler_file)
        return logger

    async def generate_subscribe_ack(self, product_id):
        # We emulate the protocol's disucssion with this subscribe_ack
        channels = {
            "name": "level2_50", 
            "product_ids": [product_id], 
            "account_ids": None
        }

        subscribe_ack = {
            "type": "subscriptions",
            "channels": channels
        }
        return subscribe_ack

    async def generate_snapshot(self, product_id):
        """Generate a snapshot with 50 bids and asks for the given product_id."""
        snapshot = {
            "type": "snapshot",
            "product_id": product_id,
            "bids": self.generate_level2(is_bid=True),
            "asks": self.generate_level2(is_bid=False)
        }
        return snapshot

    # Sort bids in descending order and asks in ascending order to guarantee that the highest bid is lower than the lowest ask
    def generate_level2(self, is_bid=True):
        """Generate random bid/ask data."""
        level2 = []
        for _ in range(self.update_count):
            price = round(
                random.uniform(30000, 42000) if is_bid else random.uniform(41000, 50000), 2
            )
            size = round(random.uniform(0.1, 5), 2)
            level2.append([str(price), str(size)])
        level2.sort(key=lambda x: float(x[0]), reverse=is_bid)
        return level2

    async def generate_update(self):
        """Generate random updates for bids/asks."""
        update = {
            "type": "l2update",
            "product_id": self.product_id,
            "changes": [
                [
                    random.choice(["buy", "sell"]),
                    str(round(random.uniform(30000, 50000), 2)),
                    str(round(random.uniform(0.1, 5), 2))
                ]
                for _ in range(self.update_count)
            ]
        }
        return update

    async def process_subscription_message(self, message: Dict[str, Any]) -> bool:
        """
        Process incoming messages from the WebSocket.
        """
        message_type = message.get("type")

        # Step 1: Check if type exists and equals "subscribe"
        if message_type != "subscribe":
            self.logger.warning(f"{self.product_id}: Unexpected message type: {message_type}")
            return False
        
        # Step 2: Validate the 'channels' field
        channels = message.get("channels")
        if not isinstance(channels, list):
            self.logger.warning(f"{self.product_id}: 'channels' is not a list")
            return False

        # Step 3: Validate each channel in the 'channels' list
        for channel in channels:
            # Ensure the channel has 'name' and 'product_ids'
            if not isinstance(channel, dict):
                self.logger.warning(f"{self.product_id}: Invalid channel format")
                return False

            channel_name = channel.get("name")
            product_ids = channel.get("product_ids")

            # Check that 'name' is present and is a string
            if not isinstance(channel_name, str):
                self.logger.warning(f"{self.product_id}: 'name' is missing or not a string in channel")
                return False

            # Check that 'product_ids' is present and is a list
            if not isinstance(product_ids, list):
                self.logger.warning(f"{self.product_id}: 'product_ids' is missing or not a list in channel")
                return False

            # Check if 'product_ids' contains at least one element
            if not product_ids:
                self.logger.warning(f"{self.product_id}: 'product_ids' is empty in channel")
                return False
            
            if PRODUCT_ID not in product_ids:
                self.logger.warning(f"{self.product_id}: is not in 'product_ids' list")
                return False

            if len(product_ids)>1:
                self.logger.warning(f"{self.product_id}: trying to subscribe to too many product_ids! \
                                    The application is prepared to allow only one type of Coinbase subscription in this instance")
                return False

        # At this point, the message structure is valid
        self.logger.info(f"{self.product_id}: Successfully validated subscription message")
        return True


    async def handle_connection(self, websocket):
        """Handle WebSocket connection and subscription."""
        self.logger.info(f"New connection established with client: {websocket.remote_address[0]}")
        
        try:

            self.logger.debug(f"Request headers: {websocket}")

            # Await the subscription request
            message = await websocket.recv()
            self.logger.debug(f"Received message: {message} from client {websocket.remote_address[0]}")
            message_data = json.loads(message)

            if await self.process_subscription_message(message_data):
                self.logger.info(f"Received subscription for product: {PRODUCT_ID}")

                # send subscribe_ack
                subscribe_ack = await self.generate_subscribe_ack(PRODUCT_ID)
                self._write_to_output_file(subscribe_ack)
                self.logger.info(f"Sending subscribe_ack for {PRODUCT_ID}")

                await websocket.send(json.dumps(subscribe_ack))

                # Send snapshot
                snapshot = await self.generate_snapshot(PRODUCT_ID)
                self._write_to_output_file(snapshot)
                self.logger.info(f"Sending snapshot for {PRODUCT_ID}")


                # Send updates periodically
                while True:
                    update = await self.generate_update()
                    self._write_to_output_file(update)
                    self.logger.info(f"Sending update for {PRODUCT_ID}")
                    await websocket.send(json.dumps(update))
                    await asyncio.sleep(5)  # Wait 5 seconds before the next update
            else:
                self.logger.error(f"Invalid subscription message: {message} from client {websocket.remote_address[0]}")
        except Exception as e:
            self.logger.error(f"Error handling connection: {e} from client {websocket.remote_address[0]}")
        finally:
            self.logger.info(f"Closing connection with client {websocket.remote_address[0]}")
            await websocket.close()


    async def start_server(self, port=8765):
        """Start the WebSocket server."""
        self.logger.info(f"Starting mock server on port {port}")
        async with serve(self.handle_connection, "0.0.0.0", port):
            await asyncio.get_running_loop().create_future()  # Run server until interrupted

if __name__ == "__main__":
    mock_server = MockServer(product_id=PRODUCT_ID, update_count=L2UPDATE_COUNT)
    asyncio.run(mock_server.start_server(port=MOCK_PORT))
