from typing import Callable, TypeVar, Generic
from v20.instrument import Candlestick
from abc import ABC, abstractmethod

T = TypeVar('T')

class Event(Generic[T]):
     
    def __init__(self): 
        self.__callbacks: list[Callable[[T], None]] = []

    @property
    def _callbacks(self):
        return self.__callbacks
        
    def __iadd__(self, callback: Callable[[T], None]): 
        self.__callbacks.append(callback) 
        return self
    
    def __isub__(self, callback: Callable[[T], None]): 
        self.__callbacks.remove(callback) 
        return self
    
    @abstractmethod
    def __call__(self, *args, **kwargs):
        raise NotImplementedError()
            
class CandlestickEvent(Event[Candlestick]):

    def __init__(self):
        super().__init__()
    
    def __call__(self, candle: Candlestick):
        for callback in self._callbacks:
            callback(candle)