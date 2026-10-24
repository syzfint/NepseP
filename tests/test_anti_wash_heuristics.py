import pytest

def test_same_broker_wash_detection():
    trade = {
        "buyerBroker": 58,
        "sellerBroker": 58,
        "price": 315.0,
        "qty": 500
    }
    is_wash = (trade["buyerBroker"] == trade["sellerBroker"])
    assert is_wash is True

def test_clean_trade_accepted():
    trade = {
        "buyerBroker": 58,
        "sellerBroker": 44,
        "price": 315.0,
        "qty": 500
    }
    is_wash = (trade["buyerBroker"] == trade["sellerBroker"])
    assert is_wash is False
