import unittest
from v4_engine.options_engine import get_options_intelligence

class TestOptionsIntelligence(unittest.TestCase):
    def test_neutral_signal_has_no_contract_recommendation(self):
        result = get_options_intelligence(
            "SPX", "NEUTRAL", 5850, 5850, 5825, 5875, 5900, 5925, 20, "15m"
        )
        self.assertIsNone(result["recommended_contract"])

    def test_spx_index_options_recommendation(self):
        opts = get_options_intelligence(
            symbol="SPX",
            direction="CALL",
            current_price=5842.30,
            entry_price=5842.0,
            stop_loss=5820.0,
            target_1=5870.0,
            target_2=5895.0,
            target_3=5920.0,
            atr_val=18.5,
            timeframe="15m"
        )
        self.assertTrue(opts["is_index"])
        self.assertEqual(opts["atm_strike"], 5840.0) # Rounded to nearest 5.0
        self.assertIn("SPX", opts["recommended_contract"])
        self.assertIn("CALL", opts["recommended_contract"])
        self.assertIn("Cash-Settled", opts["contract_type"])

    def test_ndx_index_options_recommendation(self):
        opts = get_options_intelligence(
            symbol="NDX",
            direction="PUT",
            current_price=20412.0,
            entry_price=20410.0,
            stop_loss=20480.0,
            target_1=20300.0,
            target_2=20200.0,
            target_3=20100.0,
            atr_val=85.0,
            timeframe="15m"
        )
        self.assertTrue(opts["is_index"])
        self.assertEqual(opts["atm_strike"], 20400.0) # Rounded to nearest 25.0
        self.assertIn("NDX", opts["recommended_contract"])
        self.assertIn("PUT", opts["recommended_contract"])

if __name__ == "__main__":
    unittest.main()
