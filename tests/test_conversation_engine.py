from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ConversationEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.location_patch = patch.dict(os.environ, {"NETOPS_LOCATION_ENABLED": "0"})
        self.location_patch.start()
        from netops_one_engine import NetOpsOneEngine

        self.temp_dir = tempfile.TemporaryDirectory()
        self.project = Path(self.temp_dir.name)
        self.engine = NetOpsOneEngine(
            project_dir=self.project,
            internet_enabled=True,
            max_sources=3,
        )

    def tearDown(self) -> None:
        self.location_patch.stop()
        self.temp_dir.cleanup()

    def test_basic_math_stays_local(self) -> None:
        result = self.engine.answer("2+2")
        self.assertIn("4", result.text)
        self.assertEqual(result.intent, "quick_chat")

    def test_small_talk_stays_local_and_clean(self) -> None:
        self.engine.search_client.search = lambda query, limit=3: self.fail("small talk should not search")

        result = self.engine.answer("nasılsın")
        capability = self.engine.answer("ne yapıyosun")
        bored = self.engine.answer("canım sıkılıyor")

        self.assertEqual(result.intent, "quick_chat")
        self.assertIn("İyiyim", result.text)
        self.assertEqual(capability.intent, "quick_chat")
        self.assertIn("konuşma motorunu", capability.text)
        self.assertEqual(bored.intent, "quick_chat")
        self.assertIn("arama konusu yapmıyorum", bored.text)
        self.assertNotIn("[STATUS:", result.text)
        self.assertNotIn("[THINKING_PROCESS]", result.text)

    def test_conversation_recall_remembers_first_message(self) -> None:
        self.engine.search_client.search = lambda query, limit=3: []

        self.engine.answer("canım sıkılıyor")
        result = self.engine.answer("ilk yazdığımı hatırlıyor musun")

        self.assertEqual(result.intent, "conversation_memory")
        self.assertIn("canım sıkılıyor", result.text)

    def test_conversation_recall_survives_engine_restart(self) -> None:
        from netops_one_engine import NetOpsOneEngine

        self.engine.answer("canım sıkılıyor")
        restarted = NetOpsOneEngine(project_dir=self.project, internet_enabled=False)
        result = restarted.answer("ilk yazdığımı hatırlıyor musun")

        self.assertEqual(result.intent, "conversation_memory")
        self.assertIn("canım sıkılıyor", result.text)

    def test_fallback_does_not_use_apology_word(self) -> None:
        self.engine.search_client.search = lambda query, limit=3: []

        result = self.engine.answer("bulunamayacak garip konu")

        self.assertEqual(result.intent, "search_empty")
        self.assertNotIn("Üzgünüm", result.text)
        self.assertNotIn("uzgunum", result.text.casefold())

    def test_word_core_is_created_on_startup(self) -> None:
        core_path = self.project / "netops_word_core.json"

        self.assertTrue(core_path.exists())
        data = json.loads(core_path.read_text(encoding="utf-8"))
        self.assertEqual(data.get("engine"), "netops_harbilig")
        self.assertIn("knowledge", data["intents"])
        self.assertIn("nedir", data["intents"]["knowledge"])

    def test_legacy_netops_one_name_routes_to_harbilig(self) -> None:
        self.assertEqual(type(self.engine).__name__, "NetOpsHarbiligEngine")
        files = __import__("netops_one_engine").ensure_files(self.project)
        self.assertEqual(files.get("engine"), "netops_harbilig")

    def test_commands_are_resolved_before_search(self) -> None:
        calls: list[str] = []
        self.engine.command_detector = lambda _message: "__KOMUT__:hesap_makinesi"
        self.engine.search_client.search = lambda query, limit=3: calls.append(query) or []

        result = self.engine.answer("hesap makinesi aç")

        self.assertEqual(result.intent, "command")
        self.assertEqual(calls, [])

    def test_question_mark_is_not_required_for_web_search(self) -> None:
        from netops_one_engine import SearchItem

        calls: list[str] = []

        def search(query: str, limit: int = 3) -> list[SearchItem]:
            calls.append(query)
            return [SearchItem("Domates çorbası tarifi", "Domates çorbası için domates, soğan ve su kullanılır.")]

        self.engine.search_client.search = search
        result = self.engine.answer("domates çorbası tarifi")

        self.assertTrue(result.ok)
        self.assertEqual(calls, ["domates çorbası tarifi"])
        self.assertNotIn("http", result.text.casefold())
        self.assertNotIn("Web'de", result.text)

    def test_irrelevant_results_are_dropped(self) -> None:
        from netops_one_engine import NetOpsOneStructuredSearch, SearchItem

        items = [
            SearchItem(
                "Microsoft Corporation",
                "Microsoft Corporation is an American multinational technology company.",
                "https://example.com/microsoft",
            )
        ]
        filtered = NetOpsOneStructuredSearch()._filter(items, "domates çorbası tarifi")
        self.assertEqual(filtered, [])

    def test_follow_up_query_uses_last_topic(self) -> None:
        from netops_one_engine import SearchItem

        calls: list[str] = []

        def search(query: str, limit: int = 3) -> list[SearchItem]:
            calls.append(query)
            return [SearchItem("Python bilgisi", "Python genel amaçlı bir programlama dilidir.")]

        self.engine.search_client.search = search
        self.engine.answer("Python nedir")
        self.engine.answer("Peki fiyatı?")

        self.assertGreaterEqual(len(calls), 2)
        self.assertIn("python", calls[-1].casefold())

    def test_explicit_correction_is_saved_but_chat_is_not(self) -> None:
        from netops_one_engine import SearchItem

        self.engine.search_client.search = lambda query, limit=3: [
            SearchItem("Python", "Python genel amaçlı bir programlama dilidir.")
        ]
        self.engine.answer("Python nedir")
        result = self.engine.answer("Doğrusu: Python bir programlama dilidir.")

        self.assertEqual(result.intent, "correction")
        self.assertTrue(result.learned)
        self.assertEqual(self.engine.memory_lookup("python"), "Python bir programlama dilidir.")
        memory = json.loads((self.project / "netops_memory.json").read_text(encoding="utf-8"))
        self.assertNotIn("quick_chat", {str(item.get("source")) for item in memory["items"].values()})

    def test_abusive_input_and_memory_are_blocked(self) -> None:
        result = self.engine.answer("amk")
        self.assertEqual(result.intent, "safety_filter")

        stored = self.engine.memory_store(
            "kirli bilgi",
            "Bu cevap amk içeriyor.",
            source="structured_search",
            query="kirli bilgi",
            title="Kirli",
        )

        self.assertFalse(stored)
        memory = json.loads((self.project / "netops_memory.json").read_text(encoding="utf-8"))
        self.assertEqual(memory["items"], {})

    def test_abusive_search_results_are_dropped(self) -> None:
        from netops_one_engine import NetOpsOneStructuredSearch, SearchItem

        items = [
            SearchItem(
                "Temiz başlık",
                "Bu sonuç amk gibi hakaret içeriyor ve hafızaya girmemeli.",
                "https://example.com/bad",
            )
        ]

        filtered = NetOpsOneStructuredSearch()._filter(items, "temiz başlık")
        self.assertEqual(filtered, [])

    def test_bad_memory_is_quarantined(self) -> None:
        memory_path = self.project / "netops_memory.json"
        memory_path.write_text(
            json.dumps(
                {
                    "version": "old",
                    "items": {
                        "domates": {
                            "question": "domates çorbası",
                            "query": "domates çorbası",
                            "answer": "Microsoft Corporation is an American multinational technology company.",
                            "source": "web_page",
                        },
                        "python": {
                            "question": "python nedir",
                            "query": "python",
                            "answer": "Python, genel amaçlı bir programlama dilidir.",
                            "source": "explicit_user_correction",
                        },
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        from netops_one_engine import NetOpsOneEngine

        engine = NetOpsOneEngine(project_dir=self.project, internet_enabled=False)
        data = json.loads(memory_path.read_text(encoding="utf-8"))

        self.assertIn("python", data["items"])
        self.assertNotIn("domates", data["items"])
        self.assertTrue((self.project / "netops_memory.quarantine.json").exists())
        self.assertEqual(engine.memory_lookup("python"), "Python, genel amaçlı bir programlama dilidir.")

    def test_recipe_is_structured_and_opens_internal_video(self) -> None:
        from netops_one_engine import SearchItem

        opened: list[tuple[str, bool]] = []
        self.engine.internal_opener = (
            lambda url, autoplay: opened.append((url, autoplay))
            or {"ok": True, "status": "opened"}
        )
        self.engine.search_client.search = lambda query, limit=3: [
            SearchItem(
                "Tarhana çorbası tarifi",
                "Malzemeler: 2 kaşık tarhana; 1 litre su; tuz. "
                "Hazırlanışı: Tarhanayı suyla karıştırın. Kaynayana kadar pişirin.",
                "https://example.com/tarif",
            )
        ]
        self.engine.search_client.search_youtube_video = (
            lambda query, limit=6: "https://www.youtube.com/watch?v=abc123"
        )

        result = self.engine.answer("tarhana çorbası tarifi")

        self.assertEqual(result.intent, "recipe")
        self.assertIn("Malzemeler", result.text)
        self.assertIn("Hazırlanışı", result.text)
        self.assertNotIn("http", result.text.casefold())
        self.assertEqual(opened, [("https://www.youtube.com/watch?v=abc123", False)])
        self.assertEqual(result.action, "open_youtube_video")
        memory = json.loads((self.project / "netops_memory.json").read_text(encoding="utf-8"))
        self.assertNotIn("video açılıyor", json.dumps(memory, ensure_ascii=False))

    def test_music_requires_explicit_play_intent_and_uses_internal_adapter(self) -> None:
        import neto_music_search

        opened: list[tuple[str, bool]] = []
        self.engine.internal_opener = (
            lambda url, autoplay: opened.append((url, autoplay))
            or {"ok": True, "status": "queued"}
        )
        self.engine.search_client.search = lambda query, limit=3: []

        with patch.object(neto_music_search, "search_and_play") as search_and_play:
            search_and_play.side_effect = lambda query, **kwargs: {
                "ok": bool(kwargs["open_url"]("https://music.youtube.test/watch", True)),
                "opened": True,
                "title": "Tarkan - Dudu",
                "action_status": "queued",
            }
            plain = self.engine.answer("Tarkan")
            self.assertNotEqual(plain.intent, "music_play")
            self.assertEqual(search_and_play.call_count, 0)

            result = self.engine.answer("Tarkan çal")

        self.assertEqual(result.intent, "music_play")
        self.assertIn("YouTube Music", result.text)
        self.assertEqual(opened, [("https://music.youtube.test/watch", True)])
        self.assertEqual(search_and_play.call_count, 1)

    def test_media_follow_up_reuses_previous_recipe(self) -> None:
        from netops_one_engine import SearchItem

        opened: list[tuple[str, bool]] = []
        self.engine.internal_opener = (
            lambda url, autoplay: opened.append((url, autoplay))
            or {"ok": True, "status": "opened"}
        )
        self.engine.search_client.search = lambda query, limit=3: [
            SearchItem(
                "Köfte tarifi",
                "Malzemeler: kıyma; soğan. Hazırlanışı: Yoğurun ve pişirin.",
            )
        ]
        self.engine.search_client.search_youtube_video = (
            lambda query, limit=6: "https://www.youtube.com/watch?v=kofta"
        )

        self.engine.answer("köfte tarifi")
        follow_up = self.engine.answer("onu aç")

        self.assertEqual(follow_up.intent, "recipe")
        self.assertEqual(len(opened), 2)
        self.assertEqual(opened[-1][1], False)


if __name__ == "__main__":
    unittest.main()
