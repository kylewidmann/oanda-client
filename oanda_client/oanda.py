import asyncio
import os
import sys
from abc import abstractmethod
from datetime import datetime, timezone
from typing import Callable, Tuple

import pandas as pd
from pytrade.instruments import (
    MINUTES_MAP,
    Candlestick,
    FxInstrument,
    Granularity,
    Instrument,
)
from pytrade.interfaces.account import IAccount
from pytrade.interfaces.client import IClient
from pytrade.models import Order
from pytrade.logging import get_logger
from v20.account import Account
from v20.instrument import Candlestick as v20Candlestick
from v20.order import MarketOrderRequest  # type: ignore
from v20.position import Position as v20Position

from oanda_client.config import DEFAULT_PATH, Config
from oanda_client.events import CandlestickEvent
from oanda_client.models import Position


def price_to_string(price):
    return "{} ({}) {}/{}".format(
        price.instrument, price.time, price.bids[0].price, price.asks[0].price
    )


def heartbeat_to_string(heartbeat):
    return "HEARTBEAT ({})".format(heartbeat.time)


class OandaAccount(IAccount):

    def __init__(self, v20Account: Account):
        self._account = v20Account

    @property
    def equity(self) -> float:
        return self._account.NAV

    @property
    def margin_available(self) -> float:
        return self._account.marginAvailable

    @property
    def leverage(self) -> float:
        return 1 / self._account.marginRate


class Oanda(IClient):

    def __init__(self, config_path: str = os.environ.get("V20_CONFIG", DEFAULT_PATH)):

        if not os.path.exists(os.path.expanduser(config_path)):
            raise RuntimeError(
                f"Oanda configuraton file does not exist at {os.path.expanduser(config_path)}"
            )

        self._config = Config()
        self._config.load(config_path)
        self._api = self._config.create_context()
        self._stream_api = self._config.create_streaming_context()
        self._candle_events: dict[Tuple[Instrument, Granularity], CandlestickEvent] = (
            dict()
        )
        self._stream_tasks: list[asyncio.Task] = []
        self.logger = get_logger()

    @property
    def account(self) -> IAccount:
        response = self._api.account.get(self._config.active_account)
        return OandaAccount(response.body.get("account"))

    @abstractmethod
    def order(self, order: Order):

        if not isinstance(order.instrument, FxInstrument):
            raise RuntimeError(
                f"Oanda only supports order for Forex pairs.  Received {order.instrument}"
            )

        _instrument: FxInstrument = order.instrument

        order_args = {
            "instrument": _instrument.value.replace("/", "_"),
            "units": order.size,
        }

        if order.take_profit_on_fill:
            order_args["takeProfitOnFill"] = {
                "price": f"{order.take_profit_on_fill:.5f}"
            }

        if order.stop_loss_on_fill:
            order_args["stopLossOnFill"] = {"price": f"{order.stop_loss_on_fill:.5f}"}

        order_request = MarketOrderRequest(**order_args)
        response = self._api.order.create(
            self._config.active_account, order=order_request
        )
        if response.body and response.body.get("errorMessage"):
            raise RuntimeError(response.body.get("errorMessage"))

    @abstractmethod
    def get_position(self, instrument: Instrument) -> Position:

        if isinstance(instrument, str):
            raise RuntimeError(
                f"Oanda only support Forex instruments.  Received {instrument}"
            )

        _instrument: FxInstrument = instrument

        response = self._api.position.get(
            self._config.active_account, _instrument.value.replace("/", "_")
        )
        position: v20Position = response.body.get("position")
        return Position(instrument, position)

    @abstractmethod
    def close_position(self, instrument: Instrument):

        if isinstance(instrument, str):
            raise RuntimeError(
                f"Oanda only support Forex instruments.  Received {instrument}"
            )

        _instrument: FxInstrument = instrument
        _position = self.get_position(instrument)

        args = {}
        if _position.size > 0:
            args["longUnits"] = "ALL"
        elif _position.size < 0:
            args["shortUnits"] = "ALL"
        else:
            raise RuntimeError(
                f"Requested to close position for {instrument} with size 0."
            )

        response = self._api.position.close(
            self._config.active_account, _instrument.value.replace("/", "_"), **args
        )
        if response.body.get("errorMessage"):
            raise RuntimeError(response.body.get("errorMessage"))

    def get_candles(
        self, instrument: Instrument, granularity: Granularity, count: int
    ) -> list[Candlestick]:

        if isinstance(instrument, str):
            raise RuntimeError(
                f"Oanda only support Forex instruments.  Received {instrument}"
            )

        _instrument: FxInstrument = instrument

        response = self._api.instrument.candles(
            accountID=self._config.active_account,
            instrument=_instrument.value.replace("/", "_"),
            price="B",
            granularity=granularity.value,
            count=count + 1,
        )

        if not response.body:
            raise RuntimeError()

        v20candles: list[v20Candlestick] = response.body.get("candles")
        completed_candles = [candle for candle in v20candles if candle.complete]
        candles = [
            Candlestick(
                _instrument,
                granularity,
                c.bid.o,
                c.bid.h,
                c.bid.l,
                c.bid.c,
                pd.Timestamp(c.time),
            )
            for c in completed_candles
        ]
        return candles[-count:]

    def get_candle(
        self, instrument: Instrument, granularity: Granularity
    ) -> Candlestick:

        if isinstance(instrument, str):
            raise RuntimeError(
                f"Oanda only support Forex instruments.  Received {instrument}"
            )

        _instrument: FxInstrument = instrument

        response = self._api.instrument.candles(
            accountID=self._config.active_account,
            instrument=_instrument.value.replace("/", "_"),
            price="B",
            granularity=granularity.value,
            count=2,
        )

        if not response.body:
            raise RuntimeError()

        candles: list[v20Candlestick] = response.body.get("candles")
        completed_candles = [candle for candle in candles if candle.complete]
        last_candle = completed_candles[-1]
        _bid = last_candle.bid
        return Candlestick(
            _instrument,
            granularity,
            _bid.o,
            _bid.h,
            _bid.l,
            _bid.c,
            pd.Timestamp(last_candle.time),
        )

    def subscribe(
        self,
        instrument: Instrument,
        granularity: Granularity,
        callback: Callable[[Candlestick], None],
    ):
        key = (instrument, granularity)
        if key in self._candle_events:
            self._candle_events[key] += callback
        else:
            candle_event = CandlestickEvent()
            self._candle_events[key] = candle_event
            candle_event += callback
            stream_task = asyncio.create_task(
                self._stream_candles(instrument, granularity, callback)
            )
            self._stream_tasks.append(stream_task)

    async def _stream_candles(
        self,
        instrument: Instrument,
        granularity: Granularity,
        callback: Callable[[Candlestick], None],
    ):
        while True:
            try:
                interval = 60 * MINUTES_MAP[granularity]
                previous_candle = None
                candle = self.get_candle(instrument, granularity)
                previous_candle = candle
                initial_delay = (2 * interval) - (
                    (datetime.now(timezone.utc) - candle.timestamp).seconds
                )
                callback(candle)
                await asyncio.sleep(initial_delay)
                while True:
                    candle = self.get_candle(instrument, granularity)

                    # Handle clase where we grab previous candle again
                    if candle.timestamp == previous_candle.timestamp:
                        await asyncio.sleep(1)
                        continue

                    previous_candle = candle
                    callback(candle)
                    await asyncio.sleep(interval)

            except asyncio.CancelledError:
                pass
            except Exception as err:
                self.logger.error("Exception encountered streaming candles", exc_info=err)
