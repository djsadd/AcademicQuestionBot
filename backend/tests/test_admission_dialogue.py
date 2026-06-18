from __future__ import annotations

import unittest

from backend.agents.admission import run_admission_pipeline
from backend.langchain.llm import llm_client
from backend.langchain.tools.admission_info import get_required_documents, get_study_durations


class AdmissionDialogueTests(unittest.TestCase):
    def setUp(self) -> None:
        self._api_key = llm_client.api_key
        self._chat = llm_client.chat
        llm_client.api_key = None

    def tearDown(self) -> None:
        llm_client.api_key = self._api_key
        llm_client.chat = self._chat

    def test_tuition_collects_program_before_dispatch(self) -> None:
        first = run_admission_pipeline(
            query="Сколько стоит обучение?",
            language="ru",
            payload={},
        )

        self.assertEqual(first["classification"]["subdomain"], "tuition")
        self.assertFalse(first["orchestration"]["executed"])
        self.assertEqual(first["admission_state"]["missing"], ["program"])
        self.assertEqual(first["tool_data"]["status"], "needs_clarification")

        second = run_admission_pipeline(
            query="Искусственный интеллект",
            language="ru",
            payload={"context": {"admission_state": first["admission_state"]}},
        )

        self.assertEqual(second["classification"]["source"], "dialogue_state")
        self.assertTrue(second["orchestration"]["executed"])
        self.assertEqual(second["orchestration"]["tool"], "prices")
        self.assertEqual(second["admission_state"]["status"], "completed")
        self.assertEqual(second["tool_data"]["request_slots"]["program"], "AI")

    def test_international_adds_language_for_foreign_citizen(self) -> None:
        first = run_admission_pipeline(
            query="Я гражданин Китая, хочу поступить",
            language="ru",
            payload={},
        )

        self.assertEqual(first["classification"]["subdomain"], "international")
        self.assertEqual(first["admission_state"]["slots"]["citizenship"], "China")
        self.assertEqual(first["admission_state"]["missing"], ["degree", "language"])

        second = run_admission_pipeline(
            query="Бакалавриат",
            language="ru",
            payload={"context": {"admission_state": first["admission_state"]}},
        )
        self.assertEqual(second["admission_state"]["missing"], ["language"])

        third = run_admission_pipeline(
            query="На английском",
            language="ru",
            payload={"context": {"admission_state": second["admission_state"]}},
        )
        self.assertEqual(third["admission_state"]["status"], "completed")
        self.assertEqual(third["tool_data"]["request_slots"]["language"], "en")
        self.assertEqual(third["orchestration"]["tool"], "foreign_admission")

    def test_competition_accepts_score_before_program(self) -> None:
        first = run_admission_pipeline(
            query="Каковы мои шансы с 90 баллами?",
            language="ru",
            payload={},
        )

        self.assertEqual(first["classification"]["subdomain"], "competition")
        self.assertEqual(first["admission_state"]["slots"]["ent_score"], 90)
        self.assertEqual(first["admission_state"]["missing"], ["program"])

        second = run_admission_pipeline(
            query="Менеджмент",
            language="ru",
            payload={"context": {"admission_state": first["admission_state"]}},
        )
        self.assertEqual(second["admission_state"]["status"], "completed")
        self.assertEqual(second["orchestration"]["tool"], "passing_scores")

    def test_passing_scores_do_not_ask_for_ent_score(self) -> None:
        response = run_admission_pipeline(
            query="Какие пороговые баллы на Психология?",
            language="ru",
            payload={},
        )

        self.assertEqual(response["classification"]["subdomain"], "competition")
        self.assertTrue(response["orchestration"]["executed"])
        self.assertEqual(response["orchestration"]["tool"], "passing_scores")
        self.assertEqual(response["admission_state"]["missing"], [])
        self.assertEqual(response["tool_data"]["request_slots"]["program"], "Психология")

    def test_foreign_ent_question_routes_to_foreign_admission_without_score(self) -> None:
        response = run_admission_pipeline(
            query="Нужно ли мне сдавать ЕНТ для поступления я из РФ",
            language="ru",
            payload={},
        )

        self.assertEqual(response["classification"]["subdomain"], "international")
        self.assertTrue(response["orchestration"]["executed"])
        self.assertEqual(response["orchestration"]["tool"], "foreign_admission")
        self.assertEqual(response["admission_state"]["missing"], [])
        self.assertNotIn("ent_score", response["admission_state"]["required"])

    def test_distance_learning_routes_to_study_formats_without_program_slot(self) -> None:
        response = run_admission_pipeline(
            query="Есть ли дистанционное обучение?",
            language="ru",
            payload={},
        )

        self.assertEqual(response["classification"]["subdomain"], "study_formats")
        self.assertTrue(response["orchestration"]["executed"])
        self.assertEqual(response["orchestration"]["tool"], "study_formats")
        self.assertEqual(response["admission_state"]["missing"], [])
        self.assertIn("Дистанционное обучение", response["answer"])
        self.assertIn("не предусмотрено", response["answer"])

    def test_programs_are_filtered_by_ent_profile_subject_pair(self) -> None:
        response = run_admission_pipeline(
            query="У меня профильные предметы ЕНТ Английский и Всемирная история",
            language="ru",
            payload={},
        )

        self.assertEqual(response["classification"]["subdomain"], "programs")
        self.assertTrue(response["orchestration"]["executed"])
        self.assertEqual(response["orchestration"]["tool"], "programs")
        self.assertEqual(
            response["tool_data"]["requested_profile_subjects"],
            ["Иностранный язык", "Всемирная история"],
        )
        programs = {item["program"] for item in response["tool_data"]["results"]}
        self.assertEqual(programs, {"Переводческое дело"})
        self.assertEqual(len(response["tool_data"]["results"]), 1)
        self.assertEqual(response["tool_data"]["results"][0]["level"], "bachelor")

    def test_program_subject_question_does_not_collect_user_ent_subjects(self) -> None:
        response = run_admission_pipeline(
            query="Для переводческого дела какие предметы нужны",
            language="ru",
            payload={},
        )

        self.assertEqual(response["classification"]["subdomain"], "programs")
        self.assertTrue(response["orchestration"]["executed"])
        self.assertEqual(response["orchestration"]["tool"], "programs")
        self.assertEqual(response["admission_state"]["missing"], [])
        self.assertEqual(response["tool_data"]["request_slots"]["program"], "Переводческое дело")
        self.assertEqual(response["tool_data"]["requested_program"], "Переводческое дело")
        self.assertEqual(response["tool_data"]["results"][0]["program"], "Переводческое дело")
        self.assertEqual(response["tool_data"]["results"][0]["profile_subject_1"], "Иностранный язык")
        self.assertEqual(response["tool_data"]["results"][0]["profile_subject_2"], "Всемирная история")
        self.assertIn("Иностранный язык", response["answer"])
        self.assertIn("Всемирная история", response["answer"])

    def test_profile_subject_agent_collects_second_subject(self) -> None:
        first = run_admission_pipeline(
            query="У меня профильный предмет ЕНТ Английский",
            language="ru",
            payload={},
        )

        self.assertEqual(first["classification"]["subdomain"], "programs")
        self.assertFalse(first["orchestration"]["executed"])
        self.assertEqual(first["admission_state"]["missing"], ["profile_subject_2"])
        self.assertEqual(first["admission_state"]["slots"]["profile_subject_1"], "Иностранный язык")
        self.assertNotIn("language", first["admission_state"]["slots"])

        second = run_admission_pipeline(
            query="Всемирная история",
            language="ru",
            payload={"context": {"admission_state": first["admission_state"]}},
        )

        self.assertEqual(second["classification"]["source"], "dialogue_state")
        self.assertTrue(second["orchestration"]["executed"])
        self.assertEqual(
            second["tool_data"]["requested_profile_subjects"],
            ["Иностранный язык", "Всемирная история"],
        )
        self.assertEqual(
            [(item["program"], item["level"]) for item in second["tool_data"]["results"]],
            [("Переводческое дело", "bachelor")],
        )

    def test_profile_subjects_are_reused_from_admission_profile(self) -> None:
        first = run_admission_pipeline(
            query="У меня профильные предметы ЕНТ Английский и Всемирная история",
            language="ru",
            payload={},
        )
        second = run_admission_pipeline(
            query="Какие специальности мне доступны?",
            language="ru",
            payload={"context": {"admission_profile": first["admission_profile"]}},
        )

        self.assertTrue(second["orchestration"]["executed"])
        self.assertEqual(
            second["tool_data"]["requested_profile_subjects"],
            ["Иностранный язык", "Всемирная история"],
        )
        self.assertEqual(
            [(item["program"], item["level"]) for item in second["tool_data"]["results"]],
            [("Переводческое дело", "bachelor")],
        )

    def test_completed_program_slot_is_reused_for_price_followup(self) -> None:
        first = run_admission_pipeline(
            query="Какие пороговые баллы на Психология?",
            language="ru",
            payload={},
        )
        second = run_admission_pipeline(
            query="А цена?",
            language="ru",
            history=[
                {"role": "user", "content": "Какие пороговые баллы на Психология?"},
                {"role": "assistant", "content": first["answer"]},
            ],
            payload={"context": {"admission_state": first["admission_state"]}},
        )

        self.assertEqual(second["classification"]["subdomain"], "tuition")
        self.assertTrue(second["orchestration"]["executed"])
        self.assertEqual(second["orchestration"]["tool"], "prices")
        self.assertEqual(second["admission_state"]["missing"], [])
        self.assertEqual(second["tool_data"]["request_slots"]["program"], "Психология")

    def test_admission_profile_collects_important_session_facts(self) -> None:
        response = run_admission_pipeline(
            query="Меня зовут Ерасыл, я из РФ, после школы, хочу на Психология, у меня 90 баллов",
            language="ru",
            payload={},
        )

        profile_slots = response["admission_profile"]["slots"]
        self.assertEqual(profile_slots["full_name"], "Ерасыл")
        self.assertEqual(profile_slots["citizenship"], "Russia")
        self.assertEqual(profile_slots["education_level"], "school")
        self.assertEqual(profile_slots["degree"], "bachelor")
        self.assertEqual(profile_slots["program"], "Психология")
        self.assertEqual(profile_slots["ent_score"], 90)

    def test_admission_profile_is_used_when_state_is_not_present(self) -> None:
        first = run_admission_pipeline(
            query="Меня зовут Ерасыл, после школы хочу на Психология",
            language="ru",
            payload={},
        )
        second = run_admission_pipeline(
            query="А цена?",
            language="ru",
            payload={"context": {"admission_profile": first["admission_profile"]}},
        )

        self.assertEqual(second["classification"]["subdomain"], "tuition")
        self.assertTrue(second["orchestration"]["executed"])
        self.assertEqual(second["orchestration"]["tool"], "prices")
        self.assertEqual(second["admission_state"]["missing"], [])
        self.assertEqual(second["tool_data"]["request_slots"]["program"], "Психология")
        self.assertEqual(second["admission_profile"]["slots"]["full_name"], "Ерасыл")
        self.assertEqual(second["admission_profile"]["slots"]["education_level"], "school")

    def test_eligibility_requests_current_education_level(self) -> None:
        response = run_admission_pipeline(
            query="Могу ли я поступить?",
            language="ru",
            payload={},
        )

        self.assertEqual(response["classification"]["subdomain"], "eligibility")
        self.assertEqual(response["admission_state"]["missing"], ["education_level"])
        self.assertFalse(response["orchestration"]["executed"])

    def test_explicit_new_request_replaces_pending_dialogue(self) -> None:
        first = run_admission_pipeline(
            query="Сколько стоит обучение?",
            language="ru",
            payload={},
        )
        second = run_admission_pipeline(
            query="Какой адрес приемной комиссии?",
            language="ru",
            payload={"context": {"admission_state": first["admission_state"]}},
        )

        self.assertEqual(second["classification"]["domain"], "general_info")
        self.assertEqual(second["classification"]["subdomain"], "address")
        self.assertEqual(second["orchestration"]["tool"], "address")
        self.assertEqual(second["admission_state"]["status"], "completed")

    def test_llm_renders_follow_up_without_changing_slots(self) -> None:
        llm_client.api_key = "test-key"

        def fake_chat(messages, **kwargs):
            prompt = messages[-1]["content"]
            self.assertIn("mode: follow_up", prompt)
            self.assertIn('"missing": ["program"]', prompt)
            return "Чтобы точно назвать стоимость, уточните образовательную программу."

        llm_client.chat = fake_chat

        response = run_admission_pipeline(
            query="Сколько стоит обучение?",
            language="ru",
            payload={},
        )

        self.assertEqual(
            response["answer"],
            "Чтобы точно назвать стоимость, уточните образовательную программу.",
        )
        self.assertFalse(response["orchestration"]["executed"])
        self.assertEqual(response["admission_state"]["missing"], ["program"])
        self.assertTrue(response["llm"]["used"])
        self.assertEqual(response["llm"]["raw_request"]["stages"], ["response_render"])

    def test_llm_renders_final_answer_after_slots_are_ready(self) -> None:
        first = run_admission_pipeline(
            query="Сколько стоит обучение?",
            language="ru",
            payload={},
        )
        llm_client.api_key = "test-key"

        def fake_chat(messages, **kwargs):
            prompt = messages[-1]["content"]
            self.assertIn("mode: answer", prompt)
            self.assertIn("fallback_answer:", prompt)
            self.assertIn('"tool": "prices"', prompt)
            return "По магистратуре и программе ИИ стоимость нужно смотреть по выбранной образовательной программе."

        llm_client.chat = fake_chat

        response = run_admission_pipeline(
            query="Искусственный интеллект",
            language="ru",
            payload={"context": {"admission_state": first["admission_state"]}},
        )

        self.assertTrue(response["orchestration"]["executed"])
        self.assertEqual(response["orchestration"]["tool"], "prices")
        self.assertEqual(response["admission_state"]["status"], "completed")
        self.assertEqual(
            response["answer"],
            "По магистратуре и программе ИИ стоимость нужно смотреть по выбранной образовательной программе.",
        )
        self.assertTrue(response["llm"]["used"])

    def test_overview_honors_kazakh_language_alias(self) -> None:
        response = run_admission_pipeline(
            query="Расскажи про поступление",
            language="kz",
            payload={},
        )

        self.assertEqual(response["language"], "kk")
        self.assertEqual(response["tool_data"]["tool"], "overview")
        self.assertIn("Қолжетімді мамандықтар", response["answer"])
        self.assertIn("Бакалавриат", response["answer"])
        self.assertNotIn("Доступные специальности", response["answer"])

    def test_overview_supports_english_language(self) -> None:
        response = run_admission_pipeline(
            query="General admission information",
            language="en",
            payload={},
        )

        self.assertEqual(response["language"], "en")
        self.assertEqual(response["tool_data"]["tool"], "overview")
        self.assertIn("Available programs", response["answer"])
        self.assertIn("Bachelor", response["answer"])
        self.assertTrue(response["tool_data"]["source_path"].endswith("admission_info_en.json"))
        self.assertNotIn("Доступные специальности", response["answer"])

    def test_english_overlay_provides_english_context(self) -> None:
        documents = get_required_documents(level="bachelor", language="en")
        self.assertEqual(documents["language"], "en")
        self.assertTrue(documents["source_path"].endswith("admission_info_en.json"))
        self.assertEqual(documents["results"][0]["title"], "Admission for the 2026-2027 academic year")
        self.assertIn("UNT certificate", documents["results"][0]["variants"][0]["items"])

        durations = get_study_durations(program="Economics", language="en")
        self.assertEqual(durations["language"], "en")
        self.assertTrue(durations["source_path"].endswith("admission_info_en.json"))
        self.assertEqual(
            durations["results"][0]["duration"],
            "After school - 4 years; on a college basis - 3 years.",
        )

    def test_public_auto_language_detects_kazakh_overview(self) -> None:
        response = run_admission_pipeline(
            query="Қандай мамандықтар бар?",
            language="auto",
            payload={},
        )

        self.assertEqual(response["language"], "kk")
        self.assertEqual(response["tool_data"]["tool"], "programs")
        self.assertIn("Қолжетімді мамандықтар", response["answer"])


if __name__ == "__main__":
    unittest.main()
