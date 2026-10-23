import hashlib
import pytest

def test_merkle_chain_tamper_detection():
    block0 = hashlib.sha256(b"genesis_payload").hexdigest()
    block1 = hashlib.sha256((b"payload_1" + block0.encode())).hexdigest()
    
    # Simulate corruption
    tampered_block0 = hashlib.sha256(b"altered_genesis").hexdigest()
    recomputed = hashlib.sha256((b"payload_1" + tampered_block0.encode())).hexdigest()
    assert recomputed != block1
