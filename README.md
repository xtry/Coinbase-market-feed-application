# Introduction
I investigated the Coinbase market feeds, and found that it offeres multiple channels with various details of market data. 

I choose to implement the `level2_50` channel for practical reasons:
* Gives complete `snapshot` of the order book
* Promotes efficient bandwidth use: is a compact representation of the `order book` and shows the top 50 `bids` and `asks` at each updates
  * Updates are continuous stream that follow the `snapshot`
* Focuses on relevant data by looking on the `highest bids` and `lowests asks`
  * These are closest to the mid-price which are the most interesting for trading
  * We can fit analytics: i.e. `max spread`, `moving averages` and other most important indicators
* Performance: this is computationally/storage-wise more optimal, other than processing the entire `order book` at each updates
* It's also easier to mock and make tests with the limitation of `level 50`

Caveat: I also considered `level2_batch`, which should 1:1 representation of `level2_50` however it is not online at the moment. `Level2_batch` can appealing as it also offers the every 5 seconds updates, which would be good enough to be analogous to the mock's expectations. Therefore, I decided to go ahead with `level2_50` for this case study.

# Build up of the application
I design the application in mind of portability and extensibility. I wanted to make sure that my client:
* Can connect both to the real data feed from Coinbase and also to my mock one
* Can process different `product_id`s in separate instances. This means `btc client` can connect to the `mock server btc` mock server only, I designed this way for simplicity.
  * the `product_id`s are `BTC`, `ETH` and `LTC`.
* therefore i.e. the `BTC` client can connect either the `real data feed btc`, or the `mock data feed btc` as the picture shows below

<p align="center">
  <img src="https://github.com/user-attachments/assets/9c403be3-9ab9-4cde-986b-fd41d3247e72" alt="arch drawio">
</p>

# Communication protocol
For connecting the real data feeds I used `wss` secure protocol, whereas for the mock data feeds I used `ws` for simplicity (and also considering the fact it is used local tests only). Experimenting wit the protocol communication in the real data feed, we can state the following _oversimplified_ flow:
1. The client establish a connection to the host and send `subscribe` message
2. Once the server accepts, it responds with a `subscriptions` message most probably giving a status update & confirmation
3. The server sends a `snapshot` of the `order book`. The real data feed will send over the complete `order book` (most likely fitting to a 8 Mb payload), the mock data feed will send over a payload with the cap of 50 pairs. 
5. The server sends `l2update` containing the updates only. The real data feed will send up till 50 updates of pairs, the mock data feed sends an update of exactly 50 pairs 

# Corner cases

# Logs
* data/`PRODUCT_ID`: stores the raw data of the client instances
* logs/`PRODUCT_ID`: stores the console output for keeping the history of the client instances
* mock_data/`PRODUCT_ID`: stores the raw data of the mock server instances
* mock_logs/`PRODUCT_ID`: stores the console output for keeping the history of the mock server instances
* can be cleaned up with the `cleanup.sh` bash script

# Docs



# communication
{"type": "subscribe", "channels": [{"name": "level2_50", "product_ids": ["BTC-USD"]}]}

{"type": "subscriptions", "channels": [{"name": "level2_50", "product_ids": ["BTC-USD"], "account_ids": null}]}

{"type": "snapshot", "product_id": "BTC-USD", "bids": [["42484.5", "2.0"], ["49280.44", "4.01"], ["46179.68", "2.44"], ["32118.84", "3.91"], ["34798.21", "4.97"], ["39967.16", "0.87"], ["32746.6", "4.51"], ["32659.64", "4.92"], ["49079.78", "4.31"], ["39639.77", "1.44"], ["32836.24", "4.35"], ["36959.72", "4.23"], ["39333.47", "2.14"], ["39962.25", "0.55"], ["39423.3", "4.84"], ["40161.21", "2.04"], ["33254.92", "4.29"], ["42169.34", "2.67"], ["33542.35", "3.94"], ["33192.02", "2.72"], ["39336.82", "4.66"], ["34352.72", "3.5"], ["49832.53", "3.03"], ["45447.32", "3.4"], ["36664.74", "3.49"], ["34697.64", "2.11"], ["44512.28", "4.03"], ["43609.45", "2.73"], ["43571.71", "3.88"], ["47561.76", "3.49"], ["41101.66", "0.6"], ["43370.91", "4.71"], ["46607.58", "1.58"], ["35271.17", "3.36"], ["33134.38", "4.85"], ["35116.23", "1.71"], ["37385.66", "0.21"], ["39012.23", "2.84"], ["37527.72", "4.14"], ["40954.91", "4.76"], ["47157.26", "4.92"], ["43879.71", "0.31"], ["42383.01", "3.85"], ["41570.99", "4.89"], ["41026.6", "0.91"], ["31981.19", "2.77"], ["34377.7", "1.72"], ["32697.35", "2.2"], ["43369.75", "1.78"], ["36904.03", "1.1"]], "asks": [["39998.92", "0.17"], ["46801.35", "2.39"], ["39382.04", "4.84"], ["35080.49", "1.83"], ["38751.31", "3.65"], ["35713.94", "3.89"], ["32420.78", "4.73"], ["38331.61", "3.19"], ["39153.66", "0.17"], ["35388.41", "1.56"], ["39407.87", "2.24"], ["41599.63", "1.82"], ["38916.82", "0.73"], ["30591.29", "2.48"], ["35765.48", "0.45"], ["43339.97", "4.21"], ["37872.26", "4.7"], ["46995.61", "4.13"], ["47541.97", "2.52"], ["40982.8", "0.63"], ["39021.31", "3.36"], ["40687.78", "3.23"], ["40220.6", "1.07"], ["34146.59", "3.11"], ["40515.9", "4.12"], ["43222.49", "3.46"], ["34456.31", "1.01"], ["41129.05", "0.73"], ["33276.38", "2.95"], ["30871.83", "3.27"], ["38624.06", "2.05"], ["48020.19", "1.35"], ["39947.17", "4.1"], ["41556.68", "2.14"], ["33426.19", "4.94"], ["39731.48", "2.49"], ["32666.76", "3.82"], ["32513.25", "3.69"], ["30848.14", "1.61"], ["39118.55", "0.86"], ["46602.94", "1.73"], ["38856.72", "3.7"], ["30589.98", "3.43"], ["33663.3", "0.6"], ["48516.32", "3.78"], ["31582.42", "2.39"], ["32979.62", "2.06"], ["41997.0", "3.32"], ["36980.53", "3.95"], ["47381.53", "4.64"]]}

{"type": "l2update", "product_id": "BTC-USD", "changes": [["buy", "37479.69", "1.96"], ["buy", "46082.75", "2.63"], ["sell", "39954.43", "4.64"], ["sell", "44771.54", "4.01"], ["sell", "42235.47", "3.8"], ["sell", "34902.74", "1.23"], ["buy", "44208.14", "3.66"], ["sell", "37822.86", "2.17"], ["sell", "37915.98", "3.01"], ["buy", "41022.14", "0.9"], ["sell", "41427.26", "2.24"], ["sell", "36398.81", "1.01"], ["sell", "46306.47", "2.95"], ["sell", "37098.76", "1.11"], ["sell", "39400.29", "0.15"], ["buy", "44415.66", "2.84"], ["buy", "49660.5", "1.96"], ["buy", "36068.34", "2.49"], ["sell", "37626.05", "2.14"], ["buy", "31660.58", "4.37"], ["buy", "39002.4", "1.21"], ["buy", "34716.39", "1.23"], ["sell", "43605.66", "2.39"], ["buy", "39517.63", "2.04"], ["sell", "42918.41", "4.17"], ["buy", "34047.44", "2.46"], ["buy", "36582.25", "1.43"], ["buy", "40034.08", "1.54"], ["buy", "42185.57", "4.84"], ["sell", "40268.0", "3.99"], ["sell", "38717.56", "2.9"], ["sell", "44723.61", "1.37"], ["buy", "40253.62", "1.58"], ["sell", "38356.86", "2.03"], ["sell", "35455.77", "3.71"], ["sell", "47269.79", "4.15"], ["buy", "31340.22", "2.36"], ["sell", "47500.5", "4.53"], ["sell", "38235.93", "3.44"], ["buy", "44835.57", "0.94"], ["buy", "44062.94", "2.76"], ["buy", "41453.67", "3.11"], ["buy", "49040.94", "3.47"], ["sell", "45801.1", "4.05"], ["sell", "33907.35", "2.0"], ["sell", "45626.49", "1.16"], ["sell", "44290.5", "4.41"], ["buy", "30908.2", "3.59"], ["sell", "34122.6", "0.4"], ["sell", "34938.25", "3.7"]]}
