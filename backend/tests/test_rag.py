from __future__ import annotations

import unittest

from backend.rag.loader import Segment, _normalize_pdf_text, chunk_id, chunk_segments, embedding_text
from backend.rag.service import lexical_score
from backend.services.knowledge_base import clean_metadata
from backend.services.permissions import is_admin

REGULATION = (
    "Студент, получивший оценку FX, имеет право на повторную сдачу без повторного прохождения курса. "
    "Пересдача проводится в течение двух недель после окончания сессии. "
    "Оценка F означает обязательное повторное изучение дисциплины. "
) * 6


class ChunkingTests(unittest.TestCase):
    def test_chunks_respect_sentence_boundaries_and_size(self) -> None:
        segments = [Segment(text="Глава 3. Пересдачи", page=1, is_heading=True), Segment(text=REGULATION, page=1), Segment(text=REGULATION, page=2)]
        chunks = chunk_segments(segments, base_metadata={"document_id": "doc1"}, chunk_size=500, chunk_overlap=120)
        self.assertGreater(len(chunks), 2)
        for chunk in chunks:
            self.assertLessEqual(len(chunk.content), 520)
            self.assertTrue(chunk.content.rstrip().endswith((".", "!", "?", "Пересдачи")), chunk.content[-40:])
            self.assertEqual(chunk.metadata["section"], "Глава 3. Пересдачи")
        self.assertEqual(chunks[0].metadata["page"], 1)
        self.assertEqual(chunks[-1].metadata["page_end"], 2)

    def test_chunk_ids_are_deterministic_for_reindexing(self) -> None:
        self.assertEqual(chunk_id("doc1", 3), chunk_id("doc1", 3))
        self.assertNotEqual(chunk_id("doc1", 3), chunk_id("doc2", 3))

    def test_pdf_normalisation_fixes_hyphenation_and_broken_lines(self) -> None:
        raw = "Студент обязан пройти пере-\nсдачу в установленные\nсроки.\n12\nСледующий абзац."
        text = _normalize_pdf_text(raw)
        self.assertIn("пересдачу в установленные сроки.", text)
        self.assertNotIn("\n12\n", text)

    def test_embedding_text_includes_title_and_section(self) -> None:
        chunk = chunk_segments([Segment(text=REGULATION[:300])], base_metadata={"document_id": "d", "title": "Положение о GPA"})[0]
        self.assertTrue(embedding_text(chunk).startswith("Положение о GPA"))


class HybridSearchTests(unittest.TestCase):
    def test_lexical_score_handles_word_forms(self) -> None:
        self.assertGreater(lexical_score("пересдача FX", REGULATION), 0.9)
        self.assertEqual(lexical_score("общежитие", REGULATION), 0.0)


class KnowledgeBaseTests(unittest.TestCase):
    def test_metadata_is_whitelisted_and_normalised(self) -> None:
        cleaned = clean_metadata({"title": " Положение ", "category": "hack", "audience": "students", "evil": "x"})
        self.assertEqual(cleaned, {"title": "Положение", "category": "other", "audience": "students"})


class AdminAccessTests(unittest.TestCase):
    def test_admin_by_role(self) -> None:
        self.assertTrue(is_admin({"platonus_role": "Admin", "telegram_id": 1}))
        self.assertFalse(is_admin({"platonus_role": "student", "telegram_id": 1}))
        self.assertFalse(is_admin(None))


if __name__ == "__main__":
    unittest.main()
