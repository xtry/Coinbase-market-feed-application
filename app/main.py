import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Final, Callable, Awaitable

import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

# Constants
BASE_LOGS_DIR: Final[str] = "logs"
BASE_DATA_DIR: Final[str] = "data"

COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"
if os.getenv("USE_MOCKED_FEED", "False").lower() == "true":
    port = os.getenv("MOCK_PORT", "8765")
    server = os.getenv("MOCK_SERVER", "mock_btc")
    COINBASE_WS_URL = f"ws://{server}:{port}"

# Read the PRODUCT_ID environment variable
PRODUCT_ID: Final[str] = os.getenv("PRODUCT_ID")

# Setup for log and data file timestamps
APP_START_TIMESTAMP: Final[str] = datetime.now().strftime("%Y-%m-%d-%H%M%S")

# explored BTC to require larger than 1 Mb socket for subscription
WEB_SOCKET_SIZE: Final[int] = 8 * 1024 * 1024  # 8 MB in bytes

class CoinbaseOrderBookClient:
    """
    A WebSocket client for subscribing to Coinbase's level2_50 order book channel for a single product_id.
    """
    def __init__(self, product_id: str, moving_average_period: int = 10) -> None:
        self.url = COINBASE_WS_URL
        self.product_id = product_id
        self.moving_average_period = moving_average_period
        self.date_format = "%Y-%m-%d"

        # File paths
        self.history_file = self._setup_file(BASE_LOGS_DIR, log_file=True)
        self.output_file = self._setup_file(BASE_DATA_DIR) if os.getenv("DATA_STORE", "False").lower() == "true" else None
        self.logger = self._setup_logger()

        # Order book data
        self.bids: Dict[str, str] = {}
        self.asks: Dict[str, str] = {}
        self.max_spread = 0.0
        self.mid_price_history: List[float] = []
        logging.info(f"{self.product_id} setup DONE.")

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

    def _write_to_output_file(self, message: dict):
        """Write a message to the output file in DATA_STORE mode."""
        if os.getenv("DATA_STORE", "False").lower() == "true" and self.output_file:
            try:
                with open(self.output_file, "a") as file:
                    json.dump(message, file)
                    file.write("\n")
            except Exception as e:
                self.logger.error(f"Failed to write message to file: {e}")

    def create_subscription_message(self) -> Dict[str, Any]:
        """
        Create a subscription message for the Coinbase WebSocket.
        """
        return {
            "type": "subscribe",
            "channels": [
                {
                    "name": "level2_50",
                    "product_ids": [self.product_id]
                }
            ]
        }

    def _subscriptions_check(self, message) -> None:
        channels = message.get("channels")
        if not isinstance(channels, list):
            raise ValueError(f"{self.product_id}: 'channels' is not a list")

        for channel in channels:
            if not isinstance(channel, dict):
                raise ValueError(f"{self.product_id}: Invalid channel format")

            channel_name = channel.get("name")
            product_ids = channel.get("product_ids")

            if not isinstance(channel_name, str):
                raise ValueError(f"{self.product_id}: 'name' is missing or not a string in channel")

            if not isinstance(product_ids, list):
                raise ValueError(f"{self.product_id}: 'product_ids' is missing or not a list in channel")

            if not product_ids:
                raise ValueError(f"{self.product_id}: 'product_ids' is empty in channel")

            if PRODUCT_ID not in product_ids:
                raise ValueError(f"{self.product_id}: '{PRODUCT_ID}' is not in 'product_ids' list")

            if len(product_ids) > 1:
                raise ValueError(f"{self.product_id}: Trying to subscribe to too many product_ids. Only one product is allowed.")


    def _snapshot_check(self, message):
    # Check if 'product_id' is a string
        
        product_id = message.get("product_id")
        if not product_id:
            raise ValueError(f"{self.product_id}: 'product_id' is empty")

        if not isinstance(product_id, str):
            raise ValueError("'product_id' should be a string")

        if PRODUCT_ID != product_id:
            raise ValueError(f"{self.product_id}: '{PRODUCT_ID}' shoud be equal")

        # Check if 'bids' is a list and not empty
        bids = message.get("bids")
        if not isinstance(bids, list):
            raise ValueError("'bids' should be a list")
        if not bids:
            raise ValueError("'bids' should not be empty")
        for bid in bids:
            if not isinstance(bid, list) or len(bid) != 2:
                raise ValueError("Each bid should be a list of two elements (price, amount)")

        # Check if 'asks' is a list and not empty
        asks = message.get("asks")
        if not isinstance(asks, list):
            raise ValueError("'asks' should be a list")
        if not asks:
            raise ValueError("'asks' should not be empty")
        for ask in asks:
            if not isinstance(ask, list) or len(ask) != 2:
                raise ValueError("Each ask should be a list of two elements (price, amount)")


    def _update_check(self, message):
        product_id = message.get("product_id")
        if not product_id:
            raise ValueError(f"{self.product_id}: 'product_id' is empty")

        if not isinstance(product_id, str):
            raise ValueError("'product_id' should be a string")

        if PRODUCT_ID != product_id:
            raise ValueError(f"{self.product_id}: '{PRODUCT_ID}' shoud be equal")

        # Check if 'changes' is a list and not empty
        changes = message.get("changes")
        if not isinstance(changes, list):
            raise ValueError("'changes' should be a list")
        if not changes:
            raise ValueError("'changes' should not be empty")
        
        # Check if each change is a list with three elements (side, price, amount)
        for change in changes:
            if not isinstance(change, list) or len(change) != 3:
                raise ValueError("Each change should be a list of three elements (side, price, amount)")
            # Check if side is either 'buy' or 'sell'
            side = change[0].lower()
            if side not in ["buy", "sell"]:
                raise ValueError("Side must be either 'buy' or 'sell'")            
                             

    async def process_message(self, message: Dict[str, Any]) -> None:
        """Processing the message with basic validation"""

        message_type = message.get("type")
        self._write_to_output_file(message)

        try:
            if message_type == "subscriptions":
                self.logger.info(f"{self.product_id}: Subscriptions ack received")
                self._subscriptions_check(message)

            elif message_type == "snapshot":                
                self.logger.info(f"{self.product_id}: Snapshot received")
                self._snapshot_check(message)
                self.bids = {price: size for price, size in message.get("bids", [])}
                self.asks = {price: size for price, size in message.get("asks", [])}
                self._calculations()

            elif message_type == "l2update":
                self.logger.info(f"{self.product_id}: L2 update received")
                changes = message.get("changes", [])
                for change in changes:
                    side, price, size = change
                    if side == "buy":
                        self.bids[price] = size
                    elif side == "sell":
                        self.asks[price] = size
                self._calculations()

        except ValueError as e:
            self.logger.error(f"Invalid subscription message: {message}, Error: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Error handling connection: {e}")
            raise


    def _calculations(self) -> None:
        """
        Calculate mid-price, max spread, and moving average.
        """
        highest_bid = max(self.bids, key=float, default=None)
        lowest_ask = min(self.asks, key=float, default=None)

        if highest_bid and lowest_ask:
            highest_bid_price = float(highest_bid)
            lowest_ask_price = float(lowest_ask)
            mid_price = (highest_bid_price + lowest_ask_price) / 2
            self.mid_price_history.append(mid_price)

            if len(self.mid_price_history) > self.moving_average_period:
                self.mid_price_history.pop(0)

            moving_avg = sum(self.mid_price_history) / len(self.mid_price_history)
            spread = lowest_ask_price - highest_bid_price
            # check both positive and negative differences
            self.max_spread = max(self.max_spread, abs(spread))

            self.logger.debug(f"{self.product_id}: Mid Price History: {self.mid_price_history}")
            self.logger.info(f"{self.product_id}: Mid Price: {mid_price:.2f}, Moving Average: {moving_avg:.2f}")
            self.logger.info(f"{self.product_id}: Highest Bid: {highest_bid_price:.2f}, Lowest Ask: {lowest_ask_price:.2f}")
            self.logger.debug(f"{self.product_id}: Spread: {spread:.2f}")
            self.logger.info(f"{self.product_id}: Max Spread: {self.max_spread:.2f}")

    async def exponential_backoff(
        self, coro: Callable[[], Awaitable[Any]], max_retries: int = 5, initial_delay: float = 1.0, factor: float = 2.0
    ) -> Any:
        retries = 0
        delay = initial_delay

        while retries < max_retries:
            try:
                return await coro()
            except Exception as e:
                retries += 1
                self.logger.warning(
                    f"{self.product_id}: Attempt {retries}/{max_retries} failed with error: {e}. Retrying in {delay:.2f} seconds..."
                )
                await asyncio.sleep(delay)
                delay *= factor

        self.logger.error(
            f"{self.product_id}: All {max_retries} retries failed. Operation could not be completed."
        )

    async def subscribe(self) -> None:
        subscription_message = self.create_subscription_message()
        self.logger.debug(f"Subscription message: {json.dumps(subscription_message)}")

        async with websockets.connect(
            self.url,
            max_size=WEB_SOCKET_SIZE
            ) as websocket:
            self.logger.info(f"{self.product_id}: Connected to WebSocket")

            await self.exponential_backoff(
                lambda: websocket.send(json.dumps(subscription_message))
            )
            self.logger.info(f"{self.product_id}: Subscription message sent")

            while True:
                try:
                    response = await self.exponential_backoff(websocket.recv)
                    message = json.loads(response)
                    await self.process_message(message)
                except json.JSONDecodeError:
                    self.logger.error(f"{self.product_id}: Failed to decode message")
                except (ConnectionClosedOK, ConnectionClosedError):
                    self.logger.warning(f"{self.product_id}: WebSocket connection closed")
                    break

    async def run(self) -> None:
        """
        Run the WebSocket client with reconnection logic.
        """
        while True:
            try:
                await self.subscribe()
            except Exception as e:
                self.logger.error(f"{self.product_id}: Error in subscription: {e}")
                self.logger.info(f"{self.product_id}: Reconnecting in 5 seconds...")
                await asyncio.sleep(5)


async def main() -> None:
    # Only create one client per product_id from environment
    client = CoinbaseOrderBookClient(PRODUCT_ID)
    await client.run()

if __name__ == "__main__":
    asyncio.run(main())
