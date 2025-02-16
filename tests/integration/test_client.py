# from pytrade.instruments import FxInstrument, Granularity

# from oanda_client.oanda import Oanda


import pytest
from pytrade.instruments import Candlestick, FxInstrument, Granularity

from oanda_client.models import Position
from oanda_client.oanda import Oanda


@pytest.fixture(scope="module")
def client():
    return Oanda()


def test_get_equity(client: Oanda):
    account = client.account
    assert account.equity > 0


def test_get_margin(client: Oanda):
    account = client.account
    assert account.margin_available > 0


def test_get_leverage(client: Oanda):
    account = client.account
    assert account.leverage == 50


def test_get_candle(client: Oanda):
    candle = client.get_candle(FxInstrument.EURUSD, Granularity.M1)
    assert isinstance(candle, Candlestick)


def test_get_candles(client: Oanda):
    candles = client.get_candles(FxInstrument.EURUSD, Granularity.M1, 30)
    assert len(candles) == 30


def test_order(client: Oanda):
    pass


def test_get_position(client: Oanda):
    position = client.get_position(FxInstrument.EURUSD)
    assert isinstance(position, Position)
