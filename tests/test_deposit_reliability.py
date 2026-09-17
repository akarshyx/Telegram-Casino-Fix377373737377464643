import asyncio
import hashlib
import hmac
import json
import time
import unittest
from unittest.mock import patch

import main


class DepositReliabilityTests(unittest.TestCase):
    """Provider-facing deposit tests with no live credentials or blockchain calls."""

    def setUp(self):
        self.pending = dict(main.nowpayments_pending_deposits)
        self.processed = set(main.processed_payment_ids)
        self.txids = set(main.processed_deposit_txids)
        main.nowpayments_pending_deposits.clear()
        main.processed_payment_ids.clear()
        main.processed_deposit_txids.clear()

    def tearDown(self):
        main.nowpayments_pending_deposits.clear()
        main.nowpayments_pending_deposits.update(self.pending)
        main.processed_payment_ids.clear()
        main.processed_payment_ids.update(self.processed)
        main.processed_deposit_txids.clear()
        main.processed_deposit_txids.update(self.txids)

    @staticmethod
    def _pending(payment_id="p-1", address="TEXACT", currency="usdttrc20"):
        return {
            "user_id": "123456",
            "crypto": currency,
            "pay_currency": currency,
            "network": "TRX",
            "order_id": "dep_123456_1",
            "payment_id": payment_id,
            "pay_address": address,
            "amount_usd": 10.0,
            "expected_coin_amount": 10.0,
            "created_at": time.time() - 5,
            "expires_at": time.time() + 3600,
            "status": "waiting",
            "state": "WAITING_FOR_PAYMENT",
        }

    @staticmethod
    def _provider(
        payment_id="p-1",
        address="TEXACT",
        currency="usdttrc20",
        network="TRX",
        usd=10.0,
        status="finished",
    ):
        return {
            "payment_id": payment_id,
            "order_id": "dep_123456_1",
            "payment_status": status,
            "pay_address": address,
            "pay_currency": currency,
            "network": network,
            "actually_paid": 1.0,
            "pay_amount": 10.0,
            "outcome": {"amount_received_usd": usd, "txid": "tx-1"},
            "payin_hash": "tx-1",
        }

    def test_received_amount_uses_actual_under_and_overpayment(self):
        under = main._nowpayments_received_amount(
            self._provider(usd=4.25), self._pending()
        )
        over = main._nowpayments_received_amount(
            self._provider(usd=25.75), self._pending()
        )
        self.assertEqual(under[0], 4.25)
        self.assertEqual(over[0], 25.75)

        no_amount = dict(self._provider(usd=0))
        no_amount["actually_paid"] = 0
        no_amount["outcome"] = {"txid": "tx-1"}
        self.assertEqual(
            main._nowpayments_received_amount(no_amount, self._pending())[0], 0.0
        )
        self.assertFalse(main._nowpayments_has_received_transaction(no_amount))

    def test_exact_poll_credits_confirmed_payment_once_and_persists_state(self):
        main.nowpayments_pending_deposits["p-1"] = self._pending()
        calls = []
        provider = self._provider(usd=12.0)

        with patch.object(main, "nowpayments_get_payment_status", return_value=(provider, None)), \
             patch.object(main, "_process_confirmed_deposit", side_effect=lambda **kwargs: calls.append(kwargs) or True), \
             patch.object(main, "_tg_send_deposit_processing_notification", return_value=True), \
             patch.object(main, "save_data_critical"):
            first = asyncio.run(main._run_nowpayments_monitor_once())
            main.processed_payment_ids.add("p-1")
            second = asyncio.run(main._run_nowpayments_monitor_once())

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["user_id"], "123456")
        self.assertEqual(calls[0]["usd_amount"], 12.0)
        self.assertEqual(main.nowpayments_pending_deposits["p-1"]["state"], "CREDITED")

    def test_poll_timeout_leaves_payment_retryable(self):
        main.nowpayments_pending_deposits["p-1"] = self._pending()
        with patch.object(
            main, "nowpayments_get_payment_status", return_value=(None, "timeout")
        ), patch.object(main, "_process_confirmed_deposit") as processor, patch.object(
            main, "save_data_critical"
        ):
            self.assertEqual(asyncio.run(main._run_nowpayments_monitor_once()), 0)
        processor.assert_not_called()
        self.assertEqual(main.nowpayments_pending_deposits["p-1"]["status"], "waiting")

    def test_poll_rejects_address_and_network_mismatches(self):
        main.nowpayments_pending_deposits["p-1"] = self._pending()
        wrong_address = self._provider(address="TWRONG")
        with patch.object(main, "nowpayments_get_payment_status", return_value=(wrong_address, None)), \
             patch.object(main, "_process_confirmed_deposit") as processor, \
             patch.object(main, "save_data_critical"):
            asyncio.run(main._run_nowpayments_monitor_once())
        processor.assert_not_called()
        self.assertEqual(
            main.nowpayments_pending_deposits["p-1"]["status"], "address_mismatch"
        )

        main.nowpayments_pending_deposits["p-1"] = self._pending()
        wrong_network = self._provider(network="ETH")
        with patch.object(main, "nowpayments_get_payment_status", return_value=(wrong_network, None)), \
             patch.object(main, "_process_confirmed_deposit") as processor, \
             patch.object(main, "save_data_critical"):
            asyncio.run(main._run_nowpayments_monitor_once())
        processor.assert_not_called()
        self.assertEqual(
            main.nowpayments_pending_deposits["p-1"]["status"], "network_mismatch"
        )

    def test_signed_ipn_still_requires_provider_and_saved_record_match(self):
        main.nowpayments_pending_deposits["p-1"] = self._pending()
        original_secret = main.NOWPAYMENTS_IPN_SECRET
        main.NOWPAYMENTS_IPN_SECRET = "test-secret"
        provider = self._provider(usd=9.5)
        payload = {
            "payment_id": "p-1",
            "order_id": "dep_123456_1",
            "payment_status": "finished",
            # Deliberately false values: callback must ignore these.
            "pay_currency": "BTC",
            "actually_paid": 999999,
        }
        signature = hmac.new(
            main.NOWPAYMENTS_IPN_SECRET.encode(),
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(),
            hashlib.sha512,
        ).hexdigest()
        calls = []
        try:
            with patch.object(main, "nowpayments_get_payment_status", return_value=(provider, None)), \
                 patch.object(main, "_process_confirmed_deposit", side_effect=lambda **kwargs: calls.append(kwargs) or True), \
                 patch.object(main, "save_data_critical"):
                response = main.app.test_client().post(
                    "/nowpayments_callback",
                    json=payload,
                    headers={"x-nowpayments-sig": signature},
                )
        finally:
            main.NOWPAYMENTS_IPN_SECRET = original_secret

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["user_id"], "123456")
        self.assertEqual(calls[0]["pay_currency"], "USDTTRC20")
        self.assertEqual(calls[0]["usd_amount"], 9.5)


if __name__ == "__main__":
    unittest.main()