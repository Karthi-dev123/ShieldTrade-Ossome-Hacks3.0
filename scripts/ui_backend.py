import sys
import os
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import policy_engine
from scripts import alpaca_bridge

app = Flask(__name__)
CORS(app)

@app.route('/api/execute', methods=['POST'])
def execute_trade():
    try:
        data = request.json
        ticker = data.get('ticker', 'AAPL')
        qty = int(data.get('qty', 1))
        amount_usd = float(data.get('amount_usd', 150.0))

        # 1. Create a dummy delegation token representing Risk Manager -> Trader approval
        issue_time = datetime.now(timezone.utc).isoformat()
        token_id = f"tok_{uuid.uuid4().hex[:8]}"
        
        trade_request = {
            "agent": "trader",
            "tool": "place_order",
            "ticker": ticker,
            "shares": qty,
            "amount_usd": amount_usd,
            "domain": "paper-api.alpaca.markets",
            "delegation": {
                "issued_by": "risk_manager",
                "issued_to": "trader",
                "ticker": ticker,
                "max_usd": amount_usd * 1.5,
                "max_shares": qty + 5,
                "issued_at": issue_time,
                "token_id": token_id
            }
        }

        # 2. Policy Engine Verification (ArmorIQ check)
        policy = policy_engine.load_policy()
        validation_result = policy_engine.validate_trade(trade_request, policy)
        
        if validation_result.get("decision") != "ALLOW":
            return jsonify({
                "status": "error", 
                "message": f"Policy rejected: {validation_result.get('reason')}",
                "validation": validation_result
            }), 403

        policy_check_id = validation_result.get("audit_id")

        # 3. Alpaca Execution
        order_result = alpaca_bridge.cmd_order(ticker, qty, "buy", policy_check_id)

        return jsonify({
            "status": "success",
            "order": order_result,
            "validation": validation_result,
            "token": trade_request["delegation"]
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Run on port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)
