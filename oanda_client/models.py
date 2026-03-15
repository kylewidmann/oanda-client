from pytrade.instruments import Instrument
from pytrade.interfaces.position import IPosition
from v20.position import Position as v20Position
from v20.position import PositionSide


class Position(IPosition):
    def __init__(self, instrument: Instrument, position: v20Position):
        self._instrument = instrument
        self._short: PositionSide = position.short
        self._long: PositionSide = position.long

    @property
    def size(self) -> float:
        return self._short.units + self._long.units

    @property
    def pl(self) -> float:
        """Profit (positive) or loss (negative) of the current position in cash units."""
        return self._short.unrealizedPL + self._long.unrealizedPL

    @property
    def is_long(self) -> bool:
        """True if the position is long (position size is positive)."""
        return self.size > 0

    @property
    def is_short(self) -> bool:
        """True if the position is short (position size is negative)."""
        return self.size < 0
