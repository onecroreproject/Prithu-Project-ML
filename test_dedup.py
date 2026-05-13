import unittest

def mock_add_to_recos(reco_map, fid, cat, score, reason):
    fid_str = str(fid)
    if fid_str not in reco_map or score > reco_map[fid_str]["score"]:
        reco_map[fid_str] = {
            "feed_id": fid_str,
            "category": cat,
            "score": round(float(score), 2),
            "reason": reason
        }

class TestDedup(unittest.TestCase):
    def test_deduplication_highest_score(self):
        reco_map = {}
        # Add feed 1 with low score
        mock_add_to_recos(reco_map, "1", "Art", 0.5, "Source A")
        # Add feed 1 with high score
        mock_add_to_recos(reco_map, "1", "Art", 0.9, "Source B")
        # Add feed 2
        mock_add_to_recos(reco_map, "2", "Tech", 0.8, "Source C")
        # Add feed 1 again with medium score
        mock_add_to_recos(reco_map, "1", "Art", 0.7, "Source D")

        self.assertEqual(len(reco_map), 2)
        self.assertEqual(reco_map["1"]["score"], 0.9)
        self.assertEqual(reco_map["1"]["reason"], "Source B")
        self.assertEqual(reco_map["2"]["score"], 0.8)

if __name__ == "__main__":
    unittest.main()
