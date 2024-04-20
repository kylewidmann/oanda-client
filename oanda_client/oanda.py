import asyncio
from datetime import datetime
import sys
from typing import Callable
from oanda_client.config import Config
from v20.instrument import Candlestick
from fx_lib.models.instruments import Instrument
from fx_lib.models.granularity import Granularity

def price_to_string(price):
    return "{} ({}) {}/{}".format(
        price.instrument,
        price.time,
        price.bids[0].price,
        price.asks[0].price
    )


def heartbeat_to_string(heartbeat):
    return "HEARTBEAT ({})".format(
        heartbeat.time
    )

class Oanda:

    def __init__(self, config: Config):
        self.config = config
        self.api = config.create_context()
        self.stream_api = config.create_streaming_context()

    # def buy(self):
    #     self.api.order.limit()

    def stream(self, instruments: list[str]):
        response = self.stream_api.pricing.stream(
            accountID=self.config.active_account,
            snapshot=True,
            instruments=','.join(instruments)
        )

        for msg_type, msg in response.parts():
            print(msg_type)
            if msg_type == "pricing.Heartbeat":
                print(heartbeat_to_string(msg))
            elif msg_type == "pricing.ClientPrice":
                print(price_to_string(msg))


    def get_candle(self, instrument: Instrument, granularity: Granularity) -> Candlestick:
        print(f"Get candle for {instrument}")
        response = self.api.pricing.candles(
            accountID = self.config.active_account,
            instrument = instrument.value,
            price="B",
            granularity=granularity.value,
            count=2
        )

        if response.body:
            candles: list[Candlestick] = response.body.get("candles")
            completed_candles = [candle for candle in candles if candle.complete]
            return completed_candles[-1]

    async def _stream_candles(self, instrument: Instrument, granularity: Granularity, callback: Callable[[Instrument, Granularity, Candlestick], None]):
        try:
            interval = 1*60
            previous_candle = None
            candle = self.get_candle(instrument, granularity)
            previous_candle = candle
            initial_delay = (2 * interval) - ((datetime.utcnow() - datetime.strptime(candle.time[:19], "%Y-%m-%dT%H:%M:%S")).seconds)
            callback(instrument, granularity, candle)
            await asyncio.sleep(initial_delay)
            while True:
                candle = self.get_candle(instrument, granularity)
                
                # Handle clase where we grab previous candle again
                if candle.time == previous_candle.time:
                    await asyncio.sleep(10)
                    continue

                previous_candle = candle
                callback(instrument, granularity, candle)
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            pass
        except Exception as err:
            print(err)
            sys.exit(1)


