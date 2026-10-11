import urllib.request
import json

def test(name, url, post_data=None):
    try:
        data_bytes = json.dumps(post_data).encode('utf-8') if post_data else None
        req = urllib.request.Request(url, data=data_bytes, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=5) as res:
            raw = res.read().decode('utf-8')
            try:
                res_json = json.loads(raw)
            except Exception:
                res_json = {"raw_length": len(raw), "type": "HTML/TEXT"}

            print(f"[PASS] {name} ({url}) -> HTTP {res.status}")
            if 'sweet_spot' in res_json:
                ss = res_json['sweet_spot']
                print(f"       Sweet Spot: {ss.get('session_label')} @ NPR {ss.get('target_price')} | Conf: {ss.get('confidence_pct')}% | Gain: +{ss.get('gain_pct')}%")
            if 'status' in res_json:
                print(f"       Status: {res_json.get('status')} | Ticket: {res_json.get('ticket_id', 'N/A')}")
            if 'sha256_seal' in res_json:
                print(f"       SHA-256 Provenance Seal: {res_json.get('sha256_seal')[:16]}...")
            if 'friction_breakdown' in res_json:
                fb = res_json['friction_breakdown']
                print(f"       Broker Comm: NPR {fb.get('broker_commission_npr')} ({fb.get('broker_rate_pct')}%) | Net: NPR {fb.get('net_settlement_cost_npr')}")
            return res_json
    except Exception as e:
        print(f"[FAIL] {name} ({url}): {e}")
        return None

if __name__ == '__main__':
    print("Testing Master Terminal API Endpoints on Port 8088...")
    test("Index HTML Page", "http://localhost:8088/")
    test("Audit Ledger", "http://localhost:8088/api/centaur/audit_ledger")
    test("Chart Series SAHAS", "http://localhost:8088/api/charts/series/SAHAS")
    test("Sweet Spot SAHAS", "http://localhost:8088/api/sweet_spot/SAHAS")
    test("Symbol Brain SAHAS", "http://localhost:8088/api/symbol_brain/SAHAS")
    stage_res = test("Stage Order SAHAS", "http://localhost:8088/api/centaur/stage_order", {
        "symbol": "SAHAS", 
        "quantity": 50, 
        "limit_price": 690.0, 
        "side": "BUY"
    })
    if stage_res and stage_res.get("status") == "STAGED":
        confirm_res = test("Confirm Order SAHAS", "http://localhost:8088/api/centaur/confirm_order", {
            "symbol": "SAHAS",
            "quantity": 50,
            "limit_price": 690.0,
            "side": "BUY",
            "staged_price": 690.0,
            "ticket_id": stage_res.get("ticket_id")
        })
        # Verify it now shows in audit ledger
        test("Audit Ledger After Execution", "http://localhost:8088/api/centaur/audit_ledger")
