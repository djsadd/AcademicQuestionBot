"""Structured admission tools backed by a local JSON knowledge file."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "admission_info.json"
)
DEFAULT_LANGUAGE = "ru"
SUPPORTED_LANGUAGES = {"ru", "kk", "en"}

TEXTS = {
    "ru": {
        "overview_title": "Информация приемной комиссии:",
        "missing_data_file": "Не найден файл данных для приемной комиссии: {data_path}.",
        "invalid_data_file": "Файл данных приемной комиссии поврежден или заполнен некорректно. Путь: {data_path}. Ошибка: {detail}.",
        "not_found": "Подходящие данные не найдены по указанным параметрам.",
        "not_found_contacts_hint": "Если вам нужна точная консультация, свяжитесь с приемной комиссией:",
        "available_levels": "Доступные уровни: {items}.",
        "available_programs": "Доступные программы: {items}.",
        "contacts_department_fallback": "Приемная комиссия",
        "contacts_postal_address": "Почтовый адрес:",
        "contacts_address": "Адрес: {value}",
        "address_title": "Адрес приемной комиссии:",
        "address_missing": "Адрес приемной комиссии не указан.",
        "contacts_bachelor": "Бакалавриат:",
        "contacts_graduate": "Магистратура и докторантура:",
        "contacts_schedule": "График работы: {value}",
        "contacts_label_fallback": "Контакт",
        "contacts_phone_missing": "не указан",
        "contacts_phones": "Телефоны: {value}",
        "contacts_emails": "Email: {value}",
        "contacts_working_hours": "Время работы: {value}",
        "contacts_website": "Сайт: {value}",
        "contacts_technical": "Технические специалисты:",
        "programs_title": "Доступные специальности:",
        "programs_level_bachelor": "Бакалавриат",
        "programs_level_master": "Магистратура",
        "programs_level_doctorate": "Докторантура",
        "programs_level_second_higher": "Второе высшее",
        "programs_level_other": "Другие программы",
        "source_label": "Источник",
        "prices_title": "Актуальные цены по обучению:",
        "not_specified": "не указано",
        "passing_scores_title": "Актуальные проходные баллы:",
        "passing_gop": "ГОП {value}",
        "passing_grant_full": "грант полный курс {value}",
        "passing_grant": "грант {value}",
        "passing_grant_short": "грант сокращенный курс {value}",
        "passing_grant_short_missing": "грант сокращенный курс нет данных",
        "passing_paid": "платное {value}",
        "passing_exam": "основание: {value}",
        "passing_notes": "Примечание: {value}",
        "documents_not_found": "Документы не найдены для уровня '{level}'.",
        "durations_title": "Сроки обучения:",
        "academic_mobility_title": "Академическая мобильность:",
        "academic_cooperation_title": "Академическое сотрудничество:",
        "scholarships_title": "Гранты и стипендии:",
        "scholarships_state_grant_title": "Государственный грант и связанные стипендии:",
        "scholarships_rector_grant_title": "Ректорский грант:",
        "scholarships_category_missing": "Отдельная информация по {label} пока не заполнена.",
        "scholarships_available_types": "Доступные разделы: {items}.",
        "admission_exams_title": "ЕНТ, КТ и докторантура:",
        "foreign_admission_title": "Прием иностранных граждан:",
        "management_title": "Руководство университета:",
        "student_house_title": "Студенческий дом TAU:",
        "fallback_answer": "Данные по поступлению загружены, но формат ответа для этого инструмента не настроен.",
    },
    "kk": {
        "overview_title": "Қабылдау комиссиясы туралы ақпарат:",
        "missing_data_file": "Қабылдау комиссиясы деректері файлы табылмады: {data_path}.",
        "invalid_data_file": "Қабылдау комиссиясы деректері файлы бүлінген немесе қате толтырылған. Жолы: {data_path}. Қате: {detail}.",
        "not_found": "Көрсетілген параметрлер бойынша деректер табылмады.",
        "not_found_contacts_hint": "Егер сізге нақты кеңес керек болса, қабылдау комиссиясымен байланысыңыз:",
        "available_levels": "Қолжетімді деңгейлер: {items}.",
        "available_programs": "Қолжетімді бағдарламалар: {items}.",
        "contacts_department_fallback": "Қабылдау комиссиясы",
        "contacts_postal_address": "Пошта мекенжайы:",
        "contacts_address": "Мекенжайы: {value}",
        "address_title": "Қабылдау комиссиясының мекенжайы:",
        "address_missing": "Қабылдау комиссиясының мекенжайы көрсетілмеген.",
        "contacts_bachelor": "Бакалавриат:",
        "contacts_graduate": "Магистратура және докторантура:",
        "contacts_schedule": "Жұмыс кестесі: {value}",
        "contacts_label_fallback": "Байланыс",
        "contacts_phone_missing": "көрсетілмеген",
        "contacts_phones": "Телефондар: {value}",
        "contacts_emails": "Email: {value}",
        "contacts_working_hours": "Жұмыс уақыты: {value}",
        "contacts_website": "Сайт: {value}",
        "contacts_technical": "Техникалық мамандар:",
        "programs_title": "Қолжетімді мамандықтар:",
        "programs_level_bachelor": "Бакалавриат",
        "programs_level_master": "Магистратура",
        "programs_level_doctorate": "Докторантура",
        "programs_level_second_higher": "Екінші жоғары",
        "programs_level_other": "Басқа бағдарламалар",
        "source_label": "Анықтама",
        "prices_title": "Оқу құны:",
        "not_specified": "көрсетілмеген",
        "passing_scores_title": "Өту балдары:",
        "passing_gop": "ГОП {value}",
        "passing_grant_full": "толық курс гранты {value}",
        "passing_grant": "грант {value}",
        "passing_grant_short": "қысқартылған курс гранты {value}",
        "passing_grant_short_missing": "қысқартылған курс гранты бойынша дерек жоқ",
        "passing_paid": "ақылы {value}",
        "passing_exam": "негізі: {value}",
        "passing_notes": "Ескерту: {value}",
        "documents_not_found": "'{level}' деңгейі үшін құжаттар табылмады.",
        "durations_title": "Оқу мерзімдері:",
        "academic_mobility_title": "Академиялық ұтқырлық:",
        "academic_cooperation_title": "Академиялық ынтымақтастық:",
        "scholarships_title": "Гранттар мен стипендиялар:",
        "scholarships_state_grant_title": "Мемлекеттік грант және онымен байланысты стипендиялар:",
        "scholarships_rector_grant_title": "Ректор гранты:",
        "scholarships_category_missing": "{label} бойынша жеке ақпарат әлі толықтырылмаған.",
        "scholarships_available_types": "Қолжетімді бөлімдер: {items}.",
        "admission_exams_title": "ҰБТ, КТ және докторантура:",
        "foreign_admission_title": "Шетел азаматтарын қабылдау:",
        "management_title": "Университет басшылығы:",
        "student_house_title": "TAU студенттер үйі:",
        "fallback_answer": "Оқуға түсу деректері жүктелді, бірақ бұл құрал үшін жауап форматы бапталмаған.",
    },
    "en": {
        "overview_title": "Admissions information:",
        "missing_data_file": "Admission data file not found: {data_path}.",
        "invalid_data_file": "Admission data file is invalid or corrupted. Path: {data_path}. Error: {detail}.",
        "not_found": "No matching data was found for the requested parameters.",
        "not_found_contacts_hint": "If you need an exact answer, contact the admissions office:",
        "available_levels": "Available levels: {items}.",
        "available_programs": "Available programs: {items}.",
        "contacts_department_fallback": "Admissions Office",
        "contacts_postal_address": "Postal address:",
        "contacts_address": "Address: {value}",
        "address_title": "Admissions office address:",
        "address_missing": "The admissions office address is not specified.",
        "contacts_bachelor": "Bachelor programs:",
        "contacts_graduate": "Master's and doctoral programs:",
        "contacts_schedule": "Working hours: {value}",
        "contacts_label_fallback": "Contact",
        "contacts_phone_missing": "not specified",
        "contacts_phones": "Phones: {value}",
        "contacts_emails": "Email: {value}",
        "contacts_working_hours": "Working hours: {value}",
        "contacts_website": "Website: {value}",
        "contacts_technical": "Technical contacts:",
        "programs_title": "Available programs:",
        "programs_level_bachelor": "Bachelor",
        "programs_level_master": "Master",
        "programs_level_doctorate": "Doctorate",
        "programs_level_second_higher": "Second higher education",
        "programs_level_other": "Other programs",
        "source_label": "Source",
        "prices_title": "Current tuition fees:",
        "not_specified": "not specified",
        "passing_scores_title": "Current passing scores:",
        "passing_gop": "GOP {value}",
        "passing_grant_full": "full-course grant {value}",
        "passing_grant": "grant {value}",
        "passing_grant_short": "short-course grant {value}",
        "passing_grant_short_missing": "no short-course grant data",
        "passing_paid": "paid {value}",
        "passing_exam": "basis: {value}",
        "passing_notes": "Notes: {value}",
        "documents_not_found": "Documents not found for level '{level}'.",
        "durations_title": "Study durations:",
        "academic_mobility_title": "Academic mobility:",
        "academic_cooperation_title": "Academic cooperation:",
        "scholarships_title": "Grants and scholarships:",
        "scholarships_state_grant_title": "State grant and related scholarships:",
        "scholarships_rector_grant_title": "Rector's grant:",
        "scholarships_category_missing": "Separate information for {label} has not been filled in yet.",
        "scholarships_available_types": "Available sections: {items}.",
        "admission_exams_title": "UNT, CT, and doctorate:",
        "foreign_admission_title": "Admission of foreign citizens:",
        "management_title": "University leadership:",
        "student_house_title": "TAU Student House:",
        "fallback_answer": "Admission data is loaded, but the response format for this tool is not configured.",
    },
}

SCHOLARSHIP_TYPE_ALIASES = {
    "state_grant": {
        "гос грант",
        "госгрант",
        "государственный грант",
        "образовательный грант",
        "grant funding",
        "state grant",
        "government grant",
        "мемлекеттік грант",
        "білім гранты",
    },
    "rector_grant": {
        "ректорский грант",
        "грант ректора",
        "ректор грант",
        "rector grant",
        "rector's grant",
        "ректор гранты",
    },
}

SCHOLARSHIP_TYPE_KEY_ALIASES = {
    "state_grant": {
        "state_grant",
        "state",
        "government_grant",
        "government",
        "gos_grant",
        "gosgrant",
        "grant_state",
    },
    "rector_grant": {
        "rector_grant",
        "rector",
        "rectoral_grant",
        "grant_rector",
        "rectors_grant",
    },
}

LEVEL_ALIASES = {
    "bachelor": {"bachelor", "бакалав", "undergraduate"},
    "master": {"master", "магистр", "магистрат", "masters"},
    "doctorate": {"doctorate", "doctoral", "phd", "doctor", "докторант", "доктор"},
    "second_higher": {"second higher", "second degree", "второе высшее", "высшее образование"},
}

ADMISSION_CONTACTS = {
    "department": "Приёмная комиссия",
    "postal_address": [
        "010000",
        "г. Астана",
        "Республика Казахстан",
        "ул. Ы. Дукенулы, 29 (по 2ГИС: 29а)",
        "Корпус А",
        "Университет «Туран-Астана»",
        "Приёмная комиссия",
    ],
    "address": (
        "010000, г. Астана, Республика Казахстан, ул. Ы. Дукенулы, 29 "
        "(по 2ГИС: 29а), Корпус А, Университет «Туран-Астана», Приёмная комиссия"
    ),
    "bachelor_contacts": [
        {"phone": "+7 700 139 51 10", "label": "Приемная комиссия"},
        {"phone": "+7 702 912 39 97", "label": "Сауле Сенбековна"},
        {"phone": "+7 747 911 55 28", "label": "Татьяна Юрьевна"},
        {"phone": "+7 777 038 21 52", "label": "Талгат Амирханович"},
        {"phone": "+7 701 158 89 24", "label": "Алмаз Шаирбекович"},
    ],
    "graduate_contacts": [
        {"phone": "+7 702 912 39 97", "label": "Сауле Сенбековна"},
        {"phone": "+7 701 677 99 94", "label": "Алмас Маратбекович"},
    ],
    "working_hours": "Понедельник – Пятница: с 09:00 до 18:00. Обеденный перерыв: с 13:00 до 14:00.",
    "note": "Обращайтесь по любым вопросам — мы всегда готовы помочь!",
}

TOOL_TERMS = {
    "programs": {
        "специальност",
        "специальности",
        "образовательные программы",
        "программы",
        "направления",
        "какие есть программы",
        "какие есть специальности",
        "programs",
        "majors",
        "specialties",
        "degrees",
    },
    "prices": {
        "цена",
        "цены",
        "стоимость",
        "стоит",
        "сколько стоит",
        "оплата",
        "платно",
        "платное",
        "tuition",
        "price",
        "cost",
    },
    "passing_scores": {"проход", "балл", "ент", "грант", "score", "scores"},
    "documents": {"документ", "справк", "что нужно", "что надо", "document", "documents"},
    "address": {
        "адрес приемной комиссии",
        "где находится приемная комиссия",
        "адрес университета",
        "где находится университет",
        "куда подойти",
        "куда приехать",
        "местонахождение",
        "location",
        "where is the admissions office",
        "address",
    },
    "contacts": {
        "контакт",
        "телефон",
        "почта",
        "email",
        "адрес",
        "часы работы",
        "время работы",
        "график работы",
        "режим работы",
        "work hours",
        "working hours",
        "schedule",
        "contact",
        "contacts",
        "phone",
        "mail",
    },
    "durations": {"срок", "длительность", "сколько уч", "duration", "study period", "how long"},
    "academic_mobility": {
        "академическая мобильность",
        "акад мобильность",
        "академ мобил",
        "мобильность",
        "обмен",
        "обучение за рубежом",
        "semester abroad",
        "student exchange",
        "exchange program",
        "academic mobility",
        "mobility",
    },
    "academic_cooperation": {
        "академическая мобильность",
        "мобильност",
        "внутренняя академическая мобильность",
        "международная академическая мобильность",
        "академическое сотрудничество",
        "обмен",
        "обучение по обмену",
        "двудипломное",
        "двудиплом",
        "double degree",
        "mobility",
        "academic mobility",
        "internal academic mobility",
        "international academic mobility",
    },
    "foreign_admission": {
        "иностранный гражданин",
        "иностранные граждане",
        "иностранным гражданам",
        "иностранных граждан",
        "иностранного гражданина",
        "иностранный абитуриент",
        "иностранные абитуриенты",
        "иностранным абитуриентам",
        "иностранных абитуриентов",
        "иностранный студент",
        "иностранные студенты",
        "иностранным студентам",
        "иностранных студентов",
        "для иностранцев",
        "иностранцам",
        "иностранному гражданину",
        "прием иностранных граждан",
        "приём иностранных граждан",
        "поступление иностранных граждан",
        "поступление для иностранцев",
        "нострификация",
        "нострификац",
        "иин иностран",
        "foreign citizen",
        "foreign citizens",
        "foreign applicant",
        "foreign applicants",
        "international applicant",
        "international applicants",
        "international student",
        "international students",
        "foreign admission",
        "admission of foreign citizens",
        "nostrification",
        "iin for foreign",
        "РФ",
        "Россия",
        "Украина",
        "Беларусь",
        "Узбекистан",
        "Кыргызстан",
        "Китай",
        "Монголия",
    },
}

PROFILE_SUBJECT_ALIASES: Dict[str, set[str]] = {
    "Математика": {"математика", "math", "mathematics"},
    "География": {"география", "geography"},
    "Информатика": {"информатика", "computer science", "informatics"},
    "Биология": {"биология", "biology"},
    "Всемирная история": {"всемирная история", "мировая история", "world history"},
    "Иностранный язык": {
        "иностранный язык",
        "английский",
        "английский язык",
        "english",
        "foreign language",
    },
    "Основы права": {"основы права", "право", "law basics"},
    "Язык обучения": {"язык обучения", "казахский язык", "русский язык", "language of instruction"},
    "Литература": {"литература", "literature"},
    "Творческий экзамен 1": {"творческий экзамен 1", "творческий экзамен", "creative exam 1"},
    "Творческий экзамен 2": {"творческий экзамен 2", "creative exam 2"},
}

PROFILE_SUBJECT_CONTEXT_TERMS = {
    "профиль",
    "предмет",
    "предметы",
    "ент",
    "ұбт",
    "комбинация",
    "комбинац",
    "сдаю",
    "сдал",
    "сдала",
    "profile subject",
    "profile subjects",
    "unt",
}

TOOL_TERMS["student_house"] = {
    "студенческий дом",
    "студ дом",
    "общежитие",
    "общага",
    "проживание",
    "жилье",
    "жильё",
    "hostel",
    "dorm",
    "dormitory",
    "student house",
    "student residence",
    "campus housing",
    "tau student house",
}

LEVEL_ALIASES["bachelor"].update(
    {
        "бакалавриат",
        "бакалавр",
        "бакалаврият",
        "бакалавриатқа",
        "бакалавриатта",
        "после школы",
        "выпускник школы",
        "выпускников школ",
        "после колледжа",
        "на базе колледжа",
        "выпускник колледжа",
        "выпускников колледжей",
    }
)
LEVEL_ALIASES["master"].update({"магистратура", "магистратураға", "магистратурада", "магистрлік"})
LEVEL_ALIASES["doctorate"].update({"докторантура", "докторантураға", "докторантурада", "докторлық"})
LEVEL_ALIASES["second_higher"].update({"екінші жоғары", "екінші білім", "екінші жоғары білім"})

TOOL_TERMS["programs"].update(
    {
        "бағдарлама",
        "бағдарламалар",
        "білім беру бағдарламалары",
        "мамандық",
        "мамандықтар",
        "қандай бағдарламалар бар",
        "қандай мамандықтар бар",
    }
)
TOOL_TERMS["prices"].update({"құны", "бағасы", "оқу ақысы"})
TOOL_TERMS["passing_scores"].update(
    {
        "өту балы",
        "балл",
        "ұбт",
        "шекті балл",
        "профильный предмет",
        "профильные предметы",
        "предметы по специальности",
        "какие профильные",
        "profile subject",
        "profile subjects",
    }
)
TOOL_TERMS["documents"].update({"құжат", "құжаттар", "не керек", "қандай құжаттар керек"})
TOOL_TERMS["contacts"].update({"байланыс", "телефон", "пошта", "мекенжай"})
TOOL_TERMS["durations"].update({"мерзім", "ұзақтығы", "қанша жыл", "оқу мерзімі"})
TOOL_TERMS["academic_cooperation"].update(
    {
        "академиялық ынтымақтастық",
        "академиялық ұтқырлық",
        "ұтқырл",
        "ішкі академиялық ұтқырлық",
        "халықаралық академиялық ұтқырлық",
        "екі диплом",
    }
)
TOOL_TERMS["foreign_admission"].update(
    {
        "шетел азаматы",
        "шетел азаматтары",
        "шетел азаматтарына",
        "шетелдік талапкер",
        "шетелдік талапкерлер",
        "шетелдік талапкерлерге",
        "шетелдіктерге",
        "шетелдіктер үшін",
        "шетел азаматтарын қабылдау",
        "нострификация",
        "жсн шетел",
    }
)


def load_admission_data() -> Dict[str, Any]:
    """Load structured admission data from JSON."""
    configured_path = os.getenv("ADMISSION_DATA_PATH")
    data_path = Path(configured_path) if configured_path else DEFAULT_DATA_PATH
    try:
        return json.loads(data_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"status": "missing_data_file", "data_path": str(data_path)}
    except json.JSONDecodeError as exc:
        return {
            "status": "invalid_data_file",
            "data_path": str(data_path),
            "detail": str(exc),
        }


def normalize_language(language: Optional[str]) -> str:
    value = (language or DEFAULT_LANGUAGE).strip().lower()
    if "-" in value:
        value = value.split("-", 1)[0]
    return value if value in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def _text(language: Optional[str], key: str, **kwargs: Any) -> str:
    lang = normalize_language(language)
    template = TEXTS.get(lang, TEXTS[DEFAULT_LANGUAGE]).get(key) or TEXTS[DEFAULT_LANGUAGE][key]
    return template.format(**kwargs)


def _resolve_localized_value(value: Any, language: Optional[str]) -> Any:
    lang = normalize_language(language)
    if isinstance(value, dict):
        localized_keys = []
        for key in value.keys():
            if not isinstance(key, str):
                continue
            normalized_key = key.strip().lower()
            if "-" in normalized_key:
                normalized_key = normalized_key.split("-", 1)[0]
            if normalized_key in SUPPORTED_LANGUAGES:
                localized_keys.append(key)
        if localized_keys:
            for key in (lang, DEFAULT_LANGUAGE, "kk", "en"):
                if key in value and value.get(key) not in (None, "", [], {}):
                    return _resolve_localized_value(value[key], lang)
            for key in localized_keys:
                nested = value.get(key)
                if nested not in (None, "", [], {}):
                    return _resolve_localized_value(nested, lang)
        return {key: _resolve_localized_value(item, lang) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_localized_value(item, lang) for item in value]
    return value


def _as_text(value: Any, language: Optional[str]) -> str:
    resolved = _resolve_localized_value(value, language)
    if resolved is None:
        return ""
    return str(resolved)


def _format_duration_summary_clean(
    duration: Any,
    duration_by_basis: Any,
    *,
    language: Optional[str],
) -> str:
    resolved_duration = _resolve_localized_value(duration, language)
    resolved_by_basis = _resolve_localized_value(duration_by_basis, language)

    if isinstance(resolved_by_basis, dict) and resolved_by_basis:
        labels = {
            "ru": {
                "school": "После школы",
                "college": "На базе колледжа",
                "higher_education": "Второе высшее",
            },
            "kk": {
                "school": "ЖОБ",
                "college": "ТжКБ",
                "higher_education": "ЖБ",
            },
            "en": {
                "school": "School",
                "college": "College",
                "higher_education": "Higher education",
            },
        }.get(normalize_language(language), {
            "school": "После школы",
            "college": "На базе колледжа",
            "higher_education": "Второе высшее",
        })
        parts: List[str] = []
        for key in ("school", "college", "higher_education"):
            value = resolved_by_basis.get(key)
            if value in (None, "", [], {}):
                continue
            parts.append(f"{labels.get(key, key)} — {value}")
        if parts:
            return "; ".join(parts)

    if resolved_duration in (None, "", [], {}):
        return _text(language, "not_specified")
    return str(resolved_duration)




def get_current_prices(
    *,
    program: Optional[str] = None,
    level: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    matches = _match_programs(data, program=program, level=level)
    if not matches:
        return _not_found("prices", data, level=level, program=program, language=lang)

    results = []
    for item in matches:
        tuition = item.get("tuition") or {}
        results.append(
            {
                "program": _program_display_name(item, language=lang),
                "level": item.get("level"),
                "amount": tuition.get("amount"),
                "currency": data.get("currency", "KZT"),
                "period": _resolve_localized_value(tuition.get("period"), lang),
                "updated_at": tuition.get("updated_at") or data.get("last_updated"),
            }
        )
    return {
        "status": "ok",
        "tool": "prices",
        "language": lang,
        "results": results,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_available_programs(
    *,
    program: Optional[str] = None,
    level: Optional[str] = None,
    language: Optional[str] = None,
    profile_subjects: Optional[List[str]] = None,
) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    requested_profile_subjects = _normalize_profile_subjects(profile_subjects or [])
    matches = _match_programs(
        data,
        program=program,
        level=level,
        profile_subjects=requested_profile_subjects,
    )
    if not matches:
        return _not_found("programs", data, level=level, program=program, language=lang)

    results = []
    for item in matches:
        score = item.get("passing_score") or {}
        results.append(
            {
                "program": _program_display_name(item, language=lang),
                "level": item.get("level"),
                "duration": _resolve_localized_value(item.get("duration"), lang),
                "duration_by_basis": _resolve_localized_value(item.get("duration_by_basis"), lang),
                "profile_subject_1": _resolve_localized_value(item.get("profile_subject_1"), lang),
                "profile_subject_2": _resolve_localized_value(item.get("profile_subject_2"), lang),
                "gop_code": score.get("gop_code"),
                "grant": score.get("grant"),
                "grant_full": score.get("grant_full"),
                "grant_short": score.get("grant_short"),
                "paid": score.get("paid"),
                "exam": _resolve_localized_value(score.get("exam"), lang),
                "notes": _resolve_localized_value(score.get("notes") or [], lang),
                "passing_score_updated_at": score.get("updated_at") or data.get("last_updated"),
                "source": item.get("source"),
            }
        )
    return {
        "status": "ok",
        "tool": "programs",
        "language": lang,
        "requested_program": program,
        "requested_profile_subjects": requested_profile_subjects,
        "results": results,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_passing_scores(
    *,
    program: Optional[str] = None,
    level: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    matches = _match_programs(data, program=program, level=level)
    if not level:
        meaningful_matches = [item for item in matches if _has_meaningful_passing_score(item)]
        if meaningful_matches:
            matches = meaningful_matches
    if not matches:
        return _not_found("passing_scores", data, level=level, program=program, language=lang)

    results = []
    for item in matches:
        score = item.get("passing_score") or {}
        results.append(
            {
                "program": _program_display_name(item, language=lang),
                "level": item.get("level"),
                "gop_code": score.get("gop_code"),
                "grant": score.get("grant"),
                "grant_full": score.get("grant_full"),
                "grant_short": score.get("grant_short"),
                "paid": score.get("paid"),
                "exam": _resolve_localized_value(score.get("exam"), lang),
                "notes": _resolve_localized_value(score.get("notes") or [], lang),
                "profile_subject_1": _resolve_localized_value(item.get("profile_subject_1"), lang),
                "profile_subject_2": _resolve_localized_value(item.get("profile_subject_2"), lang),
                "updated_at": score.get("updated_at") or data.get("last_updated"),
            }
        )
    return {
        "status": "ok",
        "tool": "passing_scores",
        "language": lang,
        "results": results,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def _has_meaningful_passing_score(program_item: Dict[str, Any]) -> bool:
    score = program_item.get("passing_score") or {}
    return any(
        score.get(field) not in (None, "", [], {})
        for field in ("grant", "grant_full", "grant_short", "paid", "exam", "gop_code")
    )


def get_required_documents(*, level: Optional[str] = None, language: Optional[str] = None) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    normalized_level = _normalize_level(level)
    documents = data.get("documents") or {}
    if normalized_level:
        doc_entry = documents.get(normalized_level)
        if not doc_entry:
            return {
                "status": "not_found",
                "tool": "documents",
                "language": lang,
                "message": _text(lang, "documents_not_found", level=normalized_level),
                "available_levels": sorted(documents.keys()),
                "source_path": _source_path(),
            }
        results = [{"level": normalized_level, **_resolve_localized_value(doc_entry, lang)}]
    else:
        results = [{"level": item_level, **_resolve_localized_value(entry, lang)} for item_level, entry in documents.items()]

    return {
        "status": "ok",
        "tool": "documents",
        "language": lang,
        "results": results,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_admission_contacts(*, language: Optional[str] = None) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    contacts = _resolve_localized_value(data.get("contacts") or {}, lang)
    return {
        "status": "ok",
        "tool": "contacts",
        "language": lang,
        "contacts": contacts,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_admission_address(*, language: Optional[str] = None) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    contacts = _resolve_localized_value(data.get("contacts") or {}, lang)
    if not isinstance(contacts, dict):
        contacts = {}
    return {
        "status": "ok",
        "tool": "address",
        "language": lang,
        "department": contacts.get("department"),
        "address": contacts.get("address"),
        "working_hours": contacts.get("working_hours"),
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_study_durations(
    *,
    program: Optional[str] = None,
    level: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    normalized_level = _normalize_level(level)
    duration_rules = data.get("duration_rules") or {}

    if normalized_level and not program:
        rules = duration_rules.get(normalized_level)
        if rules:
            return {
                "status": "ok",
                "tool": "durations",
                "language": lang,
                "results": [],
                "duration_rules": [{"level": normalized_level, **_resolve_localized_value(rules, lang)}],
                "data_updated_at": data.get("last_updated"),
                "source_path": _source_path(),
            }

    matches = _match_programs(data, program=program, level=level)
    if not matches:
        return _not_found("durations", data, level=level, program=program, language=lang)

    results = []
    for item in matches:
        results.append(
            {
                "program": _program_display_name(item, language=lang),
                "level": item.get("level"),
                "duration": _resolve_localized_value(item.get("duration"), lang),
                "duration_by_basis": _resolve_localized_value(item.get("duration_by_basis"), lang),
            }
        )
    return {
        "status": "ok",
        "tool": "durations",
        "language": lang,
        "results": results,
        "duration_rules": (
            [{"level": normalized_level, **_resolve_localized_value(duration_rules[normalized_level], lang)}]
            if normalized_level and normalized_level in duration_rules
            else []
        ),
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_academic_cooperation(
    *,
    program: Optional[str] = None,
    query: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    cooperation = _resolve_localized_value(data.get("academic_cooperation") or {}, lang)
    if not isinstance(cooperation, dict) or not cooperation:
        return _not_found("academic_cooperation", data, level=None, program=program or query, language=lang)

    all_programs = cooperation.get("programs") or {}
    matched_programs = _match_academic_cooperation_programs(
        all_programs,
        program=program,
        query=query,
    )
    results = matched_programs or [
        {"id": key, **value}
        for key, value in all_programs.items()
        if isinstance(value, dict)
    ]

    return {
        "status": "ok",
        "tool": "academic_cooperation",
        "language": lang,
        "source": cooperation.get("source") or {},
        "results": results,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_academic_mobility(
    *,
    program: Optional[str] = None,
    query: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    mobility = _resolve_localized_value(data.get("academic_mobility") or {}, lang)
    if not isinstance(mobility, dict) or not mobility:
        return _not_found("academic_mobility", data, level=None, program=program or query, language=lang)

    filtered_partners = _filter_academic_mobility_partners(
        mobility.get("partner_universities") or [],
        program=program,
        query=query,
    )
    result = dict(mobility)
    if filtered_partners:
        result["partner_universities"] = filtered_partners

    return {
        "status": "ok",
        "tool": "academic_mobility",
        "language": lang,
        "mobility": result,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_student_house(*, language: Optional[str] = None) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    student_house = _resolve_localized_value(data.get("student_house") or {}, lang)
    if not isinstance(student_house, dict) or not student_house:
        return _not_found("student_house", data, level=None, program=None, language=lang)

    return {
        "status": "ok",
        "tool": "student_house",
        "language": lang,
        "student_house": student_house,
        "data_updated_at": student_house.get("updated_at") or data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_scholarships(
    *,
    language: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    scholarships = _resolve_localized_value(data.get("scholarships") or {}, lang)
    requested_type = detect_requested_scholarship_type(query)
    selected_scholarships, resolved_type, available_types, missing_requested_type = _select_scholarship_payload(
        scholarships,
        requested_type=requested_type,
    )
    return {
        "status": "ok",
        "tool": "scholarships",
        "language": lang,
        "scholarships": selected_scholarships,
        "scholarship_type": resolved_type,
        "requested_scholarship_type": requested_type,
        "available_scholarship_types": available_types,
        "scholarship_type_missing": missing_requested_type,
        "data_updated_at": (
            selected_scholarships.get("updated_at")
            if isinstance(selected_scholarships, dict)
            else data.get("last_updated")
        ) or data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_admission_exams(
    *,
    language: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    exams = _resolve_localized_value(data.get("admission_exams") or {}, lang)
    if not isinstance(exams, dict) or not exams:
        return _not_found("admission_exams", data, level=None, program=query, language=lang)

    selected_key = _detect_admission_exam_key(query)
    sections = exams.get("sections") or []
    if selected_key:
        sections = [
            section
            for section in sections
            if isinstance(section, dict) and str(section.get("key") or "") == selected_key
        ]

    return {
        "status": "ok",
        "tool": "admission_exams",
        "language": lang,
        "admission_exams": {
            **exams,
            "sections": sections,
        },
        "selected_exam": selected_key,
        "data_updated_at": exams.get("updated_at") or data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_foreign_admission_info(*, language: Optional[str] = None) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    foreign_admission = _resolve_localized_value(data.get("foreign_admission") or {}, lang)
    if not isinstance(foreign_admission, dict) or not foreign_admission:
        return _not_found("foreign_admission", data, level=None, program=None, language=lang)

    return {
        "status": "ok",
        "tool": "foreign_admission",
        "language": lang,
        "foreign_admission": foreign_admission,
        "data_updated_at": foreign_admission.get("updated_at") or data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_management(*, language: Optional[str] = None) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    management = _resolve_localized_value(data.get("management") or {}, lang)
    return {
        "status": "ok",
        "tool": "management",
        "language": lang,
        "management": management,
        "data_updated_at": (
            management.get("updated_at")
            if isinstance(management, dict)
            else data.get("last_updated")
        ) or data.get("last_updated"),
        "source_path": _source_path(),
    }


def detect_requested_tool(query: str) -> str:
    normalized_query = _normalize_text(query)
    raw_query = (query or "").casefold()
    passing_score_priority_terms = {"проход", "балл", "ент", "score", "scores"}
    scholarship_terms = {
        "грант",
        "гранты",
        "стипенд",
        "стипендия",
        "стипендии",
        "гос стипендия",
        "государственная стипендия",
        "повышенная стипендия",
        "президентская стипендия",
        "grant",
        "grants",
        "scholarship",
        "stipend",
        "шәкіртақы",
    }
    for terms in SCHOLARSHIP_TYPE_ALIASES.values():
        scholarship_terms.update(terms)
    is_scholarship_query = _matches_any_term(scholarship_terms, normalized_query, raw_query)
    is_passing_score_query = _matches_any_term(passing_score_priority_terms, normalized_query, raw_query)
    if is_scholarship_query:
        if is_passing_score_query or _looks_like_grant_score_query(normalized_query):
            return "passing_scores"
        return "scholarships"

    if _matches_any_term(TOOL_TERMS["student_house"], normalized_query, raw_query):
        return "student_house"

    if _matches_any_term(TOOL_TERMS["foreign_admission"], normalized_query, raw_query):
        return "foreign_admission"

    if _looks_like_profile_subject_query(normalized_query, raw_query):
        return "passing_scores"

    if (
        _is_admission_exam_query(normalized_query, raw_query)
        and not _looks_like_score_query(normalized_query, raw_query)
        and not _has_non_exam_tool_priority(normalized_query, raw_query)
    ):
        return "admission_exams"

    management_terms = {
        "руководство",
        "руководящий состав",
        "состав руководства",
        "администрация университета",
        "ректор",
        "проректор",
        "first vice rector",
        "leadership",
        "management",
        "rector",
    }
    if _matches_any_term(management_terms, normalized_query, raw_query):
        return "management"

    if _matches_any_term(TOOL_TERMS["academic_mobility"], normalized_query, raw_query):
        return "academic_mobility"

    if _matches_any_term(TOOL_TERMS["academic_cooperation"], normalized_query, raw_query):
        return "academic_cooperation"

    for tool_name in ("programs", "documents", "address", "contacts", "prices", "passing_scores", "durations"):
        if _matches_any_term(TOOL_TERMS[tool_name], normalized_query, raw_query):
            return tool_name
    return "overview"


def _looks_like_profile_subject_query(normalized_query: str, raw_query: str) -> bool:
    terms = {
        "профильный предмет",
        "профильные предметы",
        "предметы по специальности",
        "какие профильные",
        "какие предметы",
        "комбинация предметов",
        "profile subject",
        "profile subjects",
    }
    return _matches_any_term(terms, normalized_query, raw_query)


def _is_admission_exam_query(normalized_query: str, raw_query: str) -> bool:
    terms = {
        "комплексное тестирование",
        "магистратура тест",
        "магистратура экзамен",
        "app.testcenter.kz",
        "докторантура",
        "докторант",
        "phd",
        "doctoral",
        "вступительный экзамен",
        "прием заявлений",
        "приём заявлений",
    }
    return _has_query_word(normalized_query, {"ент", "ұбт", "unt", "кт"}) or _matches_any_term(
        terms,
        normalized_query,
        raw_query,
    )


def _looks_like_score_query(normalized_query: str, raw_query: str) -> bool:
    terms = {
        "проход",
        "проходной",
        "проходные",
        "балл",
        "баллы",
        "сколько баллов",
        "score",
        "scores",
        "passing score",
    }
    return _matches_any_term(terms, normalized_query, raw_query)


def _has_non_exam_tool_priority(normalized_query: str, raw_query: str) -> bool:
    explicit_document_terms = {"документ", "документы", "справк", "document", "documents", "құжат", "құжаттар"}
    if _matches_any_term(explicit_document_terms, normalized_query, raw_query):
        return True
    explicit_duration_terms = {
        "срок обучения",
        "длительность",
        "сколько уч",
        "duration",
        "study period",
        "how long",
        "оқу мерзімі",
        "қанша жыл",
    }
    if _matches_any_term(explicit_duration_terms, normalized_query, raw_query):
        return True
    for tool_name in ("programs", "address", "contacts", "prices"):
        if _matches_any_term(TOOL_TERMS[tool_name], normalized_query, raw_query):
            return True
    return False


def _looks_like_grant_score_query(normalized_query: str) -> bool:
    if not normalized_query:
        return False

    basis_terms = {
        "после школы",
        "выпускник школы",
        "выпускников школ",
        "после колледжа",
        "на базе колледжа",
        "выпускник колледжа",
        "выпускников колледжей",
        "school",
        "college",
    }
    if any(term in normalized_query for term in basis_terms):
        return True

    try:
        data = load_admission_data()
        return bool(extract_programs(normalized_query, data=data, limit=1))
    except Exception:
        return False


def detect_requested_scholarship_type(query: Optional[str]) -> Optional[str]:
    normalized_query = _normalize_text(query)
    raw_query = (query or "").casefold()
    for scholarship_type, terms in SCHOLARSHIP_TYPE_ALIASES.items():
        if _matches_any_term(terms, normalized_query, raw_query):
            return scholarship_type
    return None


def _detect_admission_exam_key(query: Optional[str]) -> Optional[str]:
    normalized_query = _normalize_text(query)
    raw_query = (query or "").casefold()
    if _matches_any_term(
        {"докторантура", "докторант", "phd", "doctoral", "doctorate"},
        normalized_query,
        raw_query,
    ):
        return "doctorate"
    if _has_query_word(normalized_query, {"ент", "ұбт", "unt"}):
        return "ent"
    if _has_query_word(normalized_query, {"кт"}) or _matches_any_term(
        {"комплексное тестирование", "магистратура", "master", "masters"},
        normalized_query,
        raw_query,
    ):
        return "kt"
    return None


def _has_query_word(normalized_query: str, words: set[str]) -> bool:
    query_words = set(normalized_query.split())
    return any(word in query_words for word in words)


def extract_level(query: str) -> Optional[str]:
    normalized_query = _normalize_text(query)
    for normalized, variants in LEVEL_ALIASES.items():
        if any(_term_matches_query(variant, normalized_query) for variant in variants):
            return normalized
    return None


def extract_programs(
    query: str,
    *,
    data: Optional[Dict[str, Any]] = None,
    limit: int = 5,
) -> List[str]:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return []

    source = data if data is not None else load_admission_data()
    matches: list[tuple[int, str]] = []
    seen: set[str] = set()
    for program in source.get("programs") or []:
        canonical_name = _program_display_name(program)
        if not canonical_name:
            continue
        canonical_key = _normalize_text(canonical_name)
        if not canonical_key or canonical_key in seen:
            continue

        best_score = 0
        for variant in _program_candidates(program, include_topic_aliases=True):
            if not variant:
                continue
            normalized_variant = _normalize_text(variant)
            if not normalized_variant:
                continue
            if _term_matches_query(normalized_variant, normalized_query):
                best_score = max(best_score, len(normalized_variant))

        if best_score <= 0:
            continue

        seen.add(canonical_key)
        matches.append((best_score, canonical_name))

    if not matches:
        matches.extend(_match_programs_by_topics(normalized_query, source, seen))

    matches.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in matches[:limit]]


def extract_program(query: str, *, data: Optional[Dict[str, Any]] = None) -> Optional[str]:
    matches = extract_programs(query, data=data, limit=1)
    return matches[0] if matches else None


def extract_programs_with_history(
    query: str,
    *,
    history: Any = None,
    data: Optional[Dict[str, Any]] = None,
    limit: int = 5,
) -> List[str]:
    source = data if data is not None else load_admission_data()
    current_matches = extract_programs(query, data=source, limit=limit)
    if current_matches:
        return current_matches

    for roles in ({"user"}, {"assistant"}):
        history_matches = _extract_programs_from_history(history, data=source, roles=roles, limit=limit)
        if history_matches:
            return history_matches
    return []


def extract_program_with_history(
    query: str,
    *,
    history: Any = None,
    data: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    matches = extract_programs_with_history(query, history=history, data=data, limit=1)
    return matches[0] if matches else None


def build_minimal_admission_overview(
    *,
    programs: Optional[List[str]] = None,
    level: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    lang = normalize_language(language)
    requested_programs = [item for item in (programs or []) if item]
    supported_topics = ["programs", "prices", "passing_scores", "durations", "documents", "contacts"]

    if requested_programs:
        blocks: List[str] = []
        summary_items: List[Dict[str, Any]] = []
        for program_name in requested_programs:
            prices = get_current_prices(program=program_name, level=level, language=lang)
            scores = get_passing_scores(program=program_name, level=level, language=lang)
            durations = get_study_durations(program=program_name, level=level, language=lang)
            block_text, summary_item = _build_program_overview_block(
                program_name=program_name,
                prices=prices,
                scores=scores,
                durations=durations,
                language=lang,
            )
            blocks.append(block_text)
            summary_items.append(
                {
                    **summary_item,
                    "has_prices": bool(prices.get("results")),
                    "has_scores": bool(scores.get("results")),
                    "has_durations": bool(durations.get("results") or durations.get("duration_rules")),
                }
            )

        answer = "\n\n".join(blocks)
        return {
            "status": "ok",
            "tool": "overview",
            "language": lang,
            "answer": answer,
            "summary": {
                "mode": "program_details",
                "requested_programs": requested_programs,
                "level": _normalize_level(level),
                "items": summary_items,
                "supported_topics": supported_topics,
            },
            "source_path": _source_path(),
        }

    programs_result = get_available_programs(level=level, language=lang)
    program_items = programs_result.get("results") or []
    program_entries: List[Dict[str, str]] = []
    programs_by_level: Dict[str, List[str]] = {}
    unique_program_names: List[str] = []
    seen_entries: set[tuple[str, str]] = set()
    seen_program_names: set[str] = set()
    for item in program_items:
        program_name = str(item.get("program") or "").strip()
        program_level = str(item.get("level") or "other").strip() or "other"
        normalized_name = _normalize_text(program_name)
        normalized_level = _normalize_level(program_level) or "other"
        entry_key = (normalized_name, normalized_level)
        if not normalized_name or entry_key in seen_entries:
            continue
        seen_entries.add(entry_key)
        program_entries.append({"program": program_name, "level": normalized_level})
        programs_by_level.setdefault(normalized_level, []).append(program_name)
        if normalized_name not in seen_program_names:
            seen_program_names.add(normalized_name)
            unique_program_names.append(program_name)
    level_name = _normalize_level(level)

    intro_map = {
        "ru": "Даю краткий обзор без лишних данных. Если нужна конкретная специальность, напишите её название, и я отдельно подтяну стоимость, проходной балл, срок обучения и другие детали.",
        "kk": "Артық дерексіз қысқа шолу беремін. Егер нақты мамандық керек болса, атауын жазыңыз, сонда құнын, өту балын, оқу мерзімін және басқа деректерді жеке шығарамын.",
        "en": "Here is a short overview without extra context. If you need a specific program, send its name and I will fetch tuition, passing score, duration, and other details separately.",
    }
    programs_map = {
        "ru": "Доступные специальности",
        "kk": "Қолжетімді мамандықтар",
        "en": "Available programs",
    }
    level_label_map = {
        "bachelor": _text(lang, "programs_level_bachelor"),
        "master": _text(lang, "programs_level_master"),
        "doctorate": _text(lang, "programs_level_doctorate"),
        "second_higher": _text(lang, "programs_level_second_higher"),
        "other": _text(lang, "programs_level_other"),
    }
    tools_map = {
        "ru": "По запросу могу отдельно показать: стоимость, проходной балл, срок обучения, документы, контакты.",
        "kk": "Сұрау бойынша мыналарды бөлек көрсете аламын: оқу құны, өту балы, оқу мерзімі, құжаттар, байланыстар.",
        "en": "On request I can show separately: tuition, passing scores, duration, documents, contacts.",
    }

    answer_lines = [intro_map.get(lang, intro_map["en"])]
    if program_entries:
        answer_lines.append(f"{programs_map.get(lang, programs_map['en'])}:")
        for program_level, names in programs_by_level.items():
            answer_lines.append(f"{level_label_map.get(program_level, program_level)}:")
            answer_lines.extend(f"- {program_name}" for program_name in names)
    answer_lines.append(tools_map.get(lang, tools_map["en"]))

    return {
        "status": "ok",
        "tool": "overview",
        "language": lang,
        "answer": "\n".join(answer_lines),
        "summary": {
            "mode": "catalog",
            "level": level_name,
            "program_count": len(program_entries),
            "unique_program_count": len(unique_program_names),
            "programs": program_entries,
            "programs_by_level": programs_by_level,
            "supported_topics": supported_topics,
        },
        "source_path": _source_path(),
        "data_updated_at": programs_result.get("data_updated_at"),
    }


def format_admission_tool_result(result: Dict[str, Any], language: Optional[str] = None) -> str:
    lang = normalize_language(language or result.get("language"))
    if result.get("tool") == "overview" and result.get("answer"):
        return str(result["answer"])
    if result.get("tool") == "application_form" and result.get("answer"):
        return str(result["answer"])
    if result.get("tool") == "contacts":
        contacts = result.get("contacts")
        if not isinstance(contacts, dict):
            return str(contacts or _text(lang, "not_specified"))

    status = result.get("status")
    if status == "missing_data_file":
        return _text(lang, "missing_data_file", data_path=result.get("data_path"))
    if status == "invalid_data_file":
        return _text(lang, "invalid_data_file", data_path=result.get("data_path"), detail=result.get("detail"))
    if status == "not_found":
        available_programs = result.get("available_programs") or []
        available_levels = result.get("available_levels") or []
        lines = [result.get("message") or _text(lang, "not_found")]
        if available_levels:
            lines.append(_text(lang, "available_levels", items=", ".join(available_levels)))
        if available_programs:
            lines.append(_text(lang, "available_programs", items=", ".join(available_programs)))
        contacts = result.get("contacts")
        if isinstance(contacts, dict) and contacts:
            lines.append("")
            lines.append(_text(lang, "not_found_contacts_hint"))
            lines.append(
                format_admission_tool_result(
                    {
                        "status": "ok",
                        "tool": "contacts",
                        "language": lang,
                        "contacts": contacts,
                    },
                    language=lang,
                )
            )
        return "\n".join(lines)

    tool = result.get("tool")
    if tool == "programs":
        lines = [_text(lang, "programs_title")]
        seen_programs: set[str] = set()
        for item in result.get("results") or []:
            program_name = str(item.get("program") or "").strip()
            normalized_name = _normalize_text(program_name)
            if not normalized_name or normalized_name in seen_programs:
                continue
            seen_programs.add(normalized_name)
            details: List[str] = []
            profile_subjects = _format_profile_subjects(
                item.get("profile_subject_1"),
                item.get("profile_subject_2"),
                language=lang,
            )
            if profile_subjects:
                details.append(profile_subjects)
            if item.get("level"):
                details.append(str(item.get("level")))
            suffix = f": {', '.join(details)}" if details else ""
            lines.append(f"- {program_name}{suffix}")
        return "\n".join(lines)

    if tool == "prices":
        lines = [_text(lang, "prices_title")]
        for item in result.get("results") or []:
            amount = item.get("amount")
            amount_text = f"{int(amount):,}".replace(",", " ") if isinstance(amount, (int, float)) else _text(lang, "not_specified")
            lines.append(
                f"- {item.get('program')} ({item.get('level')}): {amount_text} {item.get('currency')} {item.get('period') or ''}".rstrip()
            )
        return "\n".join(lines)

    if tool == "passing_scores":
        lines = [_text(lang, "passing_scores_title")]
        for item in result.get("results") or []:
            grant = item.get("grant")
            grant_full = item.get("grant_full")
            grant_short = item.get("grant_short")
            paid = item.get("paid")
            score_parts = []
            if item.get("gop_code"):
                score_parts.append(_text(lang, "passing_gop", value=item.get("gop_code")))
            if grant_full is not None:
                score_parts.append(_text(lang, "passing_grant_full", value=grant_full))
            elif grant is not None:
                score_parts.append(_text(lang, "passing_grant", value=grant))
            if grant_short is not None:
                score_parts.append(_text(lang, "passing_grant_short", value=grant_short))
            else:
                score_parts.append(_text(lang, "passing_grant_short_missing"))
            score_parts.append(_text(lang, "passing_paid", value=paid if paid is not None else _text(lang, "not_specified")))
            score_parts.append(_text(lang, "passing_exam", value=item.get("exam") or _text(lang, "not_specified")))
            line = f"- {item.get('program')} ({item.get('level')}): " + ", ".join(score_parts) + "."
            profile_subjects = _format_profile_subjects(
                item.get("profile_subject_1"),
                item.get("profile_subject_2"),
                language=lang,
            )
            if profile_subjects:
                line += f" {profile_subjects}."
            notes = item.get("notes") or []
            if notes:
                line += " " + _text(lang, "passing_notes", value=" ".join(str(note) for note in notes))
            lines.append(line)
        return "\n".join(lines)

    if tool == "documents":
        lines = []
        for entry in result.get("results") or []:
            lines.append(f"{entry.get('title')}:")
            for note in entry.get("notes") or []:
                lines.append(f"- {note}")
            for item in entry.get("items") or []:
                lines.append(f"- {item}")
            for variant in entry.get("variants") or []:
                lines.append(f"{variant.get('title')}:")
                for note in variant.get("notes") or []:
                    lines.append(f"- {note}")
                for item in variant.get("items") or []:
                    lines.append(f"- {item}")
        return "\n".join(lines)

    if tool == "contacts":
        contacts = result.get("contacts") or {}
        phones = ", ".join(contacts.get("phone") or []) or _text(lang, "not_specified")
        emails = ", ".join(contacts.get("email") or []) or _text(lang, "not_specified")
        technical_contacts = contacts.get("technical_contacts") or []
        technical_lines = []
        for entry in technical_contacts:
            name = entry.get("name") or _text(lang, "contacts_label_fallback")
            phone = entry.get("phone") or _text(lang, "contacts_phone_missing")
            note = entry.get("note") or ""
            suffix = f" ({note})" if note else ""
            technical_lines.append(f"- {name}: {phone}{suffix}")
        technical_block = (
            "\n" + _text(lang, "contacts_technical") + "\n" + "\n".join(technical_lines)
            if technical_lines
            else ""
        )
        return (
            f"{contacts.get('department') or _text(lang, 'contacts_department_fallback')}\n"
            f"{_text(lang, 'contacts_phones', value=phones)}\n"
            f"{_text(lang, 'contacts_emails', value=emails)}\n"
            f"{_text(lang, 'contacts_address', value=contacts.get('address') or _text(lang, 'not_specified'))}\n"
            f"{_text(lang, 'contacts_working_hours', value=contacts.get('working_hours') or _text(lang, 'not_specified'))}\n"
            f"{_text(lang, 'contacts_website', value=contacts.get('website') or _text(lang, 'not_specified'))}"
            f"{technical_block}"
        )

    if tool == "address":
        address = result.get("address")
        department = result.get("department") or _text(lang, "contacts_department_fallback")
        if not address:
            return _text(lang, "address_missing")
        working_hours = result.get("working_hours")
        lines = [
            _text(lang, "address_title"),
            f"{department}",
            _text(lang, "contacts_address", value=address),
        ]
        if working_hours:
            lines.append(_text(lang, "contacts_working_hours", value=working_hours))
        return "\n".join(lines)

    if tool == "durations":
        lines = [_text(lang, "durations_title")]
        for item in result.get("results") or []:
            duration_text = _format_duration_summary_clean(
                item.get("duration"),
                item.get("duration_by_basis"),
                language=lang,
            )
            lines.append(
                f"- {item.get('program')} ({item.get('level')}): {duration_text}."
            )
        for rule in result.get("duration_rules") or []:
            lines.append(f"{rule.get('title')}:")
            for item in rule.get("items") or []:
                lines.append(f"- {item}")
        return "\n".join(lines)

    if tool == "academic_mobility":
        mobility = result.get("mobility") or {}
        if not isinstance(mobility, dict):
            return str(mobility or _text(lang, "not_specified"))

        program_info = mobility.get("program") or {}
        eligibility = mobility.get("eligibility") or {}
        financials = mobility.get("financials") or {}
        deadlines = mobility.get("deadlines") or {}
        documents = mobility.get("documents") or {}
        contacts = mobility.get("contacts") or {}
        selection_process = mobility.get("selection_process") or []
        partner_universities = mobility.get("partner_universities") or []

        labels = {
            "ru": {
                "program_types": "Форматы",
                "eligibility": "Кто может участвовать",
                "financials": "Финансовые условия",
                "deadlines": "Сроки подачи",
                "documents": "Документы",
                "required": "Обязательные",
                "optional": "Дополнительные",
                "partners": "Вузы-партнеры",
                "selection": "Этапы отбора",
                "contacts": "Контакты",
                "logic": "Условия отбора",
                "gpa": "Минимальный GPA",
                "language": "Минимальный уровень языка",
                "bachelor": "Бакалавриат",
                "master": "Магистратура",
                "covered": "Расходы студента",
                "tuition": "Обучение",
                "credit_transfer": "Требуется перезачет кредитов",
            },
            "kk": {
                "program_types": "Форматтар",
                "eligibility": "Қатыса алатындар",
                "financials": "Қаржылық шарттар",
                "deadlines": "Өтінім мерзімдері",
                "documents": "Құжаттар",
                "required": "Міндетті",
                "optional": "Қосымша",
                "partners": "Серіктес ЖОО",
                "selection": "Іріктеу кезеңдері",
                "contacts": "Байланыстар",
                "logic": "Іріктеу шарттары",
                "gpa": "Ең төмен GPA",
                "language": "Тіл деңгейінің минимумы",
                "bachelor": "Бакалавриат",
                "master": "Магистратура",
                "covered": "Студент төлейтін шығындар",
                "tuition": "Оқу ақысы",
                "credit_transfer": "Кредиттерді қайта есептеу қажет",
            },
            "en": {
                "program_types": "Formats",
                "eligibility": "Eligibility",
                "financials": "Financial terms",
                "deadlines": "Deadlines",
                "documents": "Documents",
                "required": "Required",
                "optional": "Optional",
                "partners": "Partner universities",
                "selection": "Selection process",
                "contacts": "Contacts",
                "logic": "Selection logic",
                "gpa": "Minimum GPA",
                "language": "Minimum language level",
                "bachelor": "Bachelor",
                "master": "Master",
                "covered": "Student-covered costs",
                "tuition": "Tuition",
                "credit_transfer": "Credit transfer required",
            },
        }
        text = labels.get(lang, labels["en"])
        lines = [_text(lang, "academic_mobility_title")]
        if isinstance(program_info, dict):
            name = program_info.get("name")
            if name:
                lines.append(str(name))
            university = program_info.get("university")
            description = program_info.get("description")
            duration = program_info.get("duration")
            if university:
                lines.append(f"- university: {university}")
            if description:
                lines.append(f"- description: {description}")
            if duration:
                lines.append(f"- duration: {duration}")
            types = program_info.get("types") or {}
            if isinstance(types, dict) and types:
                lines.append(f"{text['program_types']}:")
                for key, value in types.items():
                    lines.append(f"- {key}: {value}")
            if program_info.get("credit_transfer_required") is not None:
                lines.append(f"- {text['credit_transfer']}: {program_info.get('credit_transfer_required')}")

        if isinstance(eligibility, dict) and eligibility:
            lines.append(f"{text['eligibility']}:")
            bachelor = eligibility.get("bachelor") or {}
            master = eligibility.get("master") or {}
            requirements = eligibility.get("requirements") or {}
            if isinstance(bachelor, dict) and bachelor:
                bachelor_parts = []
                if bachelor.get("4_year_program"):
                    bachelor_parts.append(f"4-year: {', '.join(str(item) for item in bachelor['4_year_program'])}")
                if bachelor.get("5_year_program"):
                    bachelor_parts.append(f"5-year: {', '.join(str(item) for item in bachelor['5_year_program'])}")
                lines.append(f"- {text['bachelor']}: {'; '.join(bachelor_parts)}")
            if isinstance(master, dict) and master:
                master_parts = []
                if master.get("allowed_courses"):
                    master_parts.append(f"courses: {', '.join(str(item) for item in master['allowed_courses'])}")
                if master.get("mode"):
                    master_parts.append(f"mode: {master['mode']}")
                lines.append(f"- {text['master']}: {'; '.join(master_parts)}")
            if isinstance(requirements, dict) and requirements:
                if requirements.get("min_gpa") is not None:
                    lines.append(f"- {text['gpa']}: {requirements['min_gpa']}")
                if requirements.get("language_level_min"):
                    lines.append(f"- {text['language']}: {requirements['language_level_min']}")

        if isinstance(financials, dict) and financials:
            lines.append(f"{text['financials']}:")
            tuition = financials.get("tuition")
            if tuition:
                lines.append(f"- {text['tuition']}: {tuition}")
            covered = financials.get("covered_by_student") or []
            if covered:
                lines.append(f"- {text['covered']}: {', '.join(str(item) for item in covered)}")

        if isinstance(deadlines, dict) and deadlines:
            lines.append(f"{text['deadlines']}:")
            for key, value in deadlines.items():
                lines.append(f"- {key}: {value}")

        if isinstance(documents, dict) and documents:
            lines.append(f"{text['documents']}:")
            required = documents.get("required") or []
            optional = documents.get("optional") or []
            if required:
                lines.append(f"- {text['required']}: {', '.join(str(item) for item in required)}")
            if optional:
                lines.append(f"- {text['optional']}: {', '.join(str(item) for item in optional)}")

        if partner_universities:
            lines.append(f"{text['partners']}:")
            for partner in partner_universities:
                if isinstance(partner, dict):
                    name = partner.get("name") or _text(lang, "not_specified")
                    country = partner.get("country")
                    city = partner.get("city")
                    programs = partner.get("programs") or []
                    suffix_parts = [str(part) for part in (country, city) if part]
                    suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
                    lines.append(f"- {name}{suffix}")
                    if programs:
                        lines.append(f"  programs: {', '.join(str(item) for item in programs)}")
                else:
                    lines.append(f"- {partner}")

        if selection_process:
            lines.append(f"{text['selection']}:")
            for step in selection_process:
                lines.append(f"- {step}")

        if isinstance(contacts, dict) and contacts:
            lines.append(f"{text['contacts']}:")
            for key, value in contacts.items():
                lines.append(f"- {key}: {value}")
        logic = mobility.get("logic") or {}
        if isinstance(logic, dict) and logic:
            lines.append(f"{text['logic']}:")
            for key, value in logic.items():
                lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    if tool == "academic_cooperation":
        lines = [_text(lang, "academic_cooperation_title")]
        source = result.get("source") or {}
        source_name = source.get("name")
        source_url = source.get("url")
        if source_name or source_url:
            source_value = source_name or _text(lang, "not_specified")
            if source_url:
                source_value = f"{source_value} ({source_url})"
            lines.append(f"{_text(lang, 'source_label')}: {source_value}")

        for entry in result.get("results") or []:
            lines.append("")
            lines.append(str(entry.get("name") or _text(lang, "not_specified")))

            description = entry.get("description")
            if description:
                lines.append(f"- {description}")

            advantages = entry.get("advantages") or []
            if advantages:
                lines.append("Advantages:")
                for item in advantages:
                    lines.append(f"- {item}")

            eligibility = entry.get("eligibility_criteria") or {}
            if isinstance(eligibility, dict) and eligibility:
                lines.append("Eligibility:")
                for key, value in eligibility.items():
                    lines.append(f"- {key}: {value}")

            requirements = entry.get("requirements") or []
            if requirements:
                lines.append("Requirements:")
                for item in requirements:
                    lines.append(f"- {item}")

            languages = entry.get("languages") or []
            if languages:
                lines.append(f"Languages: {', '.join(str(item) for item in languages)}")

            duration = entry.get("duration") or []
            if duration:
                lines.append(f"Duration: {', '.join(str(item) for item in duration)}")

            partner_universities = entry.get("partner_universities") or []
            if partner_universities:
                lines.append("Partner universities:")
                for item in partner_universities:
                    lines.append(f"- {item}")

            documents = entry.get("documents") or []
            if documents:
                lines.append("Documents:")
                for item in documents:
                    lines.append(f"- {item}")

            contacts = entry.get("contacts") or {}
            if isinstance(contacts, dict) and contacts:
                lines.append("Contacts:")
                for key in ("address", "phone", "email", "working_hours"):
                    value = contacts.get(key)
                    if value:
                        lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    if tool == "student_house":
        student_house = result.get("student_house") or {}
        if not isinstance(student_house, dict):
            return str(student_house or _text(lang, "not_specified"))

        labels = {
            "location": "Локация",
            "accommodation": "Проживание",
            "food": "Питание",
            "infrastructure": "Инфраструктура",
            "community": "Сообщество",
            "security": "Безопасность",
        }
        lines = [_text(lang, "student_house_title")]
        description = student_house.get("description")
        if description:
            lines.append(str(description))

        for key, label in labels.items():
            items = student_house.get(key) or []
            if not items:
                continue
            lines.append(f"{label}:")
            for item in items:
                lines.append(f"- {item}")

        contacts = student_house.get("contacts") or {}
        if isinstance(contacts, dict) and contacts:
            lines.append("Контакты:")
            office = contacts.get("office")
            phone = contacts.get("phone")
            if office:
                lines.append(f"- Офис: {office}")
            if phone:
                lines.append(f"- Телефон: {phone}")
        return "\n".join(lines)

    if tool == "scholarships":
        scholarships = result.get("scholarships") or {}
        if not isinstance(scholarships, dict):
            return str(scholarships or _text(lang, "not_specified"))

        scholarship_type = result.get("scholarship_type")
        title_key = {
            "state_grant": "scholarships_state_grant_title",
            "rector_grant": "scholarships_rector_grant_title",
        }.get(scholarship_type, "scholarships_title")
        lines = [_text(lang, title_key)]

        if result.get("scholarship_type_missing") and scholarship_type:
            lines.append(
                _text(
                    lang,
                    "scholarships_category_missing",
                    label=_scholarship_type_label(scholarship_type, language=lang),
                )
            )
            available_types = result.get("available_scholarship_types") or []
            if available_types:
                available_labels = ", ".join(
                    _scholarship_type_label(str(item), language=lang)
                    for item in available_types
                )
                lines.append(_text(lang, "scholarships_available_types", items=available_labels))
            return "\n".join(lines)

        categories = _extract_scholarship_categories(scholarships)
        if categories and not scholarship_type:
            for category_type in ("state_grant", "rector_grant"):
                category = categories.get(category_type)
                if not category:
                    continue
                lines.append(_scholarship_type_label(category_type, language=lang))
                _append_scholarship_sections(lines, category)
            return "\n".join(lines)

        _append_scholarship_sections(lines, scholarships)
        return "\n".join(lines)

    if tool == "admission_exams":
        exams = result.get("admission_exams") or {}
        if not isinstance(exams, dict):
            return str(exams or _text(lang, "not_specified"))

        lines = [_text(lang, "admission_exams_title")]
        for section in exams.get("sections") or []:
            if not isinstance(section, dict):
                continue
            title = section.get("title")
            if title:
                lines.append(str(title))
            for item in section.get("items") or []:
                lines.append(f"- {item}")
        return "\n".join(lines)

    if tool == "foreign_admission":
        info = result.get("foreign_admission") or {}
        if not isinstance(info, dict):
            return str(info or _text(lang, "not_specified"))

        lines = [_text(lang, "foreign_admission_title")]
        title = info.get("title")
        if title:
            lines.append(str(title))

        format_items = info.get("format") or []
        if format_items:
            lines.append("Формат поступления:")
            for item in format_items:
                lines.append(f"- {item}")

        bachelor_documents = info.get("bachelor_documents") or {}
        if isinstance(bachelor_documents, dict) and bachelor_documents:
            doc_title = bachelor_documents.get("title")
            if doc_title:
                lines.append(str(doc_title) + ":")
            for item in bachelor_documents.get("items") or []:
                lines.append(f"- {item}")

        nostrification = info.get("nostrification") or {}
        if isinstance(nostrification, dict) and nostrification:
            nostrification_title = nostrification.get("title")
            if nostrification_title:
                lines.append(str(nostrification_title) + ":")
            summary = nostrification.get("summary")
            if summary:
                lines.append(f"- {summary}")
            documents = nostrification.get("documents") or []
            if documents:
                lines.append("Документы:")
                for item in documents:
                    lines.append(f"- {item}")

        requirements = info.get("key_requirements") or []
        if requirements:
            lines.append("Ключевые требования:")
            for item in requirements:
                lines.append(f"- {item}")
        return "\n".join(lines)

    if tool == "management":
        management = result.get("management") or {}
        if not isinstance(management, dict):
            return str(management or _text(lang, "not_specified"))

        lines = [_text(lang, "management_title")]
        rector = management.get("rector") or {}
        rector_name = rector.get("name")
        if rector_name:
            lines.append("Ректор:")
            lines.append(f"- {rector_name}")
            for item in rector.get("items") or []:
                lines.append(f"- {item}")

        leadership = management.get("leadership") or []
        if leadership:
            lines.append("Руководящий состав:")
            for entry in leadership:
                name = entry.get("name")
                if not name:
                    continue
                lines.append(f"- {name}")
                for item in entry.get("items") or []:
                    lines.append(f"- {item}")
        return "\n".join(lines)

    return _text(lang, "fallback_answer")


def build_context_entries(result: Dict[str, Any], language: Optional[str] = None) -> List[Dict[str, Any]]:
    lang = normalize_language(language or result.get("language"))
    content = _build_compact_context_content(result, language=lang)
    return [
        {
            "content": content,
            "metadata": {
                "source_path": result.get("source_path") or "backend/data/admission_info.json",
                "tool": result.get("tool") or "admission_info",
                "data_updated_at": result.get("data_updated_at"),
                "language": lang,
            },
        }
    ]


def _build_compact_context_content(result: Dict[str, Any], language: Optional[str] = None) -> str:
    lang = normalize_language(language or result.get("language"))
    if result.get("tool") == "programs":
        return _format_programs_context(result, language=lang)
    if result.get("tool") == "passing_scores":
        return _format_passing_scores_context(result, language=lang)
    return format_admission_tool_result(result, language=lang)


def _format_programs_context(result: Dict[str, Any], language: Optional[str] = None) -> str:
    lang = normalize_language(language or result.get("language"))
    lines = [_text(lang, "programs_title")]
    seen_programs: set[str] = set()
    for item in result.get("results") or []:
        program_name = str(item.get("program") or "").strip()
        normalized_name = _normalize_text(program_name)
        if not normalized_name or normalized_name in seen_programs:
            continue
        seen_programs.add(normalized_name)
        details: List[str] = []
        if item.get("level"):
            details.append(str(item.get("level")))
        profile_subjects = _format_profile_subjects(
            item.get("profile_subject_1"),
            item.get("profile_subject_2"),
            language=lang,
        )
        if profile_subjects:
            details.append(profile_subjects)
        if item.get("gop_code"):
            details.append(_text(lang, "passing_gop", value=item.get("gop_code")))
        score_details = _format_program_score_details(item, language=lang)
        if score_details:
            details.append(score_details)
        suffix = f": {', '.join(details)}" if details else ""
        lines.append(f"- {program_name}{suffix}")
    return "\n".join(lines)


def _format_program_score_details(item: Dict[str, Any], language: Optional[str] = None) -> str:
    lang = normalize_language(language)
    score_parts: List[str] = []
    grant_full = item.get("grant_full")
    grant = item.get("grant")
    grant_short = item.get("grant_short")
    paid = item.get("paid")
    if grant_full is not None:
        score_parts.append(_text(lang, "passing_grant_full", value=grant_full))
    elif grant is not None:
        score_parts.append(_text(lang, "passing_grant", value=grant))
    if grant_short is not None:
        score_parts.append(_text(lang, "passing_grant_short", value=grant_short))
    if paid is not None:
        score_parts.append(_text(lang, "passing_paid", value=paid))
    if item.get("exam"):
        score_parts.append(_text(lang, "passing_exam", value=item.get("exam")))
    return "; ".join(score_parts)


def _format_passing_scores_context(result: Dict[str, Any], language: Optional[str] = None) -> str:
    lang = normalize_language(language or result.get("language"))
    lines = [_text(lang, "passing_scores_title")]
    for item in result.get("results") or []:
        score_parts: List[str] = []
        if item.get("gop_code"):
            score_parts.append(_text(lang, "passing_gop", value=item.get("gop_code")))
        grant_full = item.get("grant_full")
        grant = item.get("grant")
        grant_short = item.get("grant_short")
        paid = item.get("paid")
        if grant_full is not None:
            score_parts.append(_text(lang, "passing_grant_full", value=grant_full))
        elif grant is not None:
            score_parts.append(_text(lang, "passing_grant", value=grant))
        if grant_short is not None:
            score_parts.append(_text(lang, "passing_grant_short", value=grant_short))
        score_parts.append(_text(lang, "passing_paid", value=paid if paid is not None else _text(lang, "not_specified")))
        score_parts.append(_text(lang, "passing_exam", value=item.get("exam") or _text(lang, "not_specified")))
        profile_subjects = _format_profile_subjects(
            item.get("profile_subject_1"),
            item.get("profile_subject_2"),
            language=lang,
        )
        if profile_subjects:
            score_parts.append(profile_subjects)
        lines.append(f"- {item.get('program')} ({item.get('level')}): " + ", ".join(score_parts) + ".")
    return "\n".join(lines)


def _build_program_overview_block(
    *,
    program_name: str,
    prices: Dict[str, Any],
    scores: Dict[str, Any],
    durations: Dict[str, Any],
    language: str,
) -> tuple[str, Dict[str, Any]]:
    lang = normalize_language(language)
    labels = {
        "ru": {
            "title": "Кратко по программе",
            "tuition": "Стоимость",
            "scores": "Порог / проходной балл",
            "duration": "Срок обучения",
            "subjects": "Профильные предметы",
            "basis": "Основание",
            "details": "Если нужно, могу отдельно расписать документы, гранты, формат обучения и контакты приемной комиссии.",
        },
        "kk": {
            "title": "Бағдарлама бойынша қысқаша",
            "tuition": "Оқу құны",
            "scores": "Өту балы",
            "duration": "Оқу мерзімі",
            "subjects": "Бейіндік пәндер",
            "basis": "Негізі",
            "details": "Қажет болса, құжаттар, гранттар, оқу форматы және қабылдау комиссиясының байланыстарын бөлек көрсете аламын.",
        },
        "en": {
            "title": "Program summary",
            "tuition": "Tuition",
            "scores": "Passing score",
            "duration": "Duration",
            "subjects": "Profile subjects",
            "basis": "Basis",
            "details": "If needed, I can also provide documents, grants, study format, and admissions contacts separately.",
        },
    }
    text = labels.get(lang, labels["en"])

    price_rows = _program_specific_rows(prices, program_name)
    score_rows = _program_specific_rows(scores, program_name)
    duration_rows = _program_specific_rows(durations, program_name)

    lines = [f"{text['title']}: {program_name}"]
    levels: List[str] = []

    for item in price_rows[:3]:
        level_value = str(item.get("level") or "")
        if level_value and level_value not in levels:
            levels.append(level_value)
        amount = item.get("amount")
        amount_text = f"{int(amount):,}".replace(",", " ") if isinstance(amount, (int, float)) else _text(lang, "not_specified")
        period = str(item.get("period") or "").strip()
        price_text = f"{amount_text} {item.get('currency') or 'KZT'}".strip()
        if period:
            price_text = f"{price_text} {period}".strip()
        lines.append(f"- {text['tuition']} ({level_value}): {price_text}")

    for item in score_rows[:3]:
        level_value = str(item.get("level") or "")
        if level_value and level_value not in levels:
            levels.append(level_value)
        score_parts: List[str] = []
        if item.get("gop_code"):
            score_parts.append(_text(lang, "passing_gop", value=item.get("gop_code")))
        grant_full = item.get("grant_full")
        grant = item.get("grant")
        grant_short = item.get("grant_short")
        paid = item.get("paid")
        if grant_full is not None:
            score_parts.append(_text(lang, "passing_grant_full", value=grant_full))
        elif grant is not None:
            score_parts.append(_text(lang, "passing_grant", value=grant))
        if grant_short is not None:
            score_parts.append(_text(lang, "passing_grant_short", value=grant_short))
        score_parts.append(_text(lang, "passing_paid", value=paid if paid is not None else _text(lang, "not_specified")))
        score_text = ", ".join(score_parts) if score_parts else _text(lang, "not_specified")
        basis = str(item.get("exam") or _text(lang, "not_specified"))
        lines.append(f"- {text['scores']} ({level_value}): {score_text}")
        subject_parts = [
            str(item.get("profile_subject_1") or "").strip(),
            str(item.get("profile_subject_2") or "").strip(),
        ]
        subjects = ", ".join(part for part in subject_parts if part)
        if subjects:
            lines.append(f"- {text['subjects']}: {subjects}")
        lines.append(f"- {text['basis']}: {basis}")

    for item in duration_rows[:3]:
        level_value = str(item.get("level") or "")
        if level_value and level_value not in levels:
            levels.append(level_value)
        duration_value = _format_duration_summary_clean(
            item.get("duration"),
            item.get("duration_by_basis"),
            language=lang,
        )
        lines.append(f"- {text['duration']} ({level_value}): {duration_value}")

    lines.append(text["details"])
    return "\n".join(lines), {
        "program": program_name,
        "levels": levels,
        "price_count": len(price_rows),
        "score_count": len(score_rows),
        "duration_count": len(duration_rows),
    }


def _program_specific_rows(result: Dict[str, Any], program_name: str) -> List[Dict[str, Any]]:
    normalized_program = _normalize_text(program_name)
    rows = result.get("results") or []
    matched: List[Dict[str, Any]] = []
    for item in rows:
        candidate = str(item.get("program") or "")
        if _normalize_text(candidate) == normalized_program:
            matched.append(item)
    return matched


def extract_profile_subjects(query: str) -> List[str]:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return []
    if not any(_term_matches_query(term, normalized_query) for term in PROFILE_SUBJECT_CONTEXT_TERMS):
        return []

    matches: List[tuple[int, str]] = []
    seen: set[str] = set()
    for canonical, aliases in PROFILE_SUBJECT_ALIASES.items():
        terms = {canonical, *aliases}
        positions = [
            normalized_query.find(_normalize_text(term))
            for term in terms
            if _normalize_text(term) and _term_matches_query(term, normalized_query)
        ]
        positions = [position for position in positions if position >= 0]
        if not positions or canonical in seen:
            continue
        seen.add(canonical)
        matches.append((min(positions), canonical))

    matches.sort(key=lambda item: item[0])
    return [canonical for _, canonical in matches[:2]]


def _match_programs(
    data: Dict[str, Any],
    *,
    program: Optional[str],
    level: Optional[str],
    profile_subjects: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    programs = data.get("programs") or []
    normalized_level = _normalize_level(level)
    normalized_program = _normalize_text(program)
    normalized_profile_subjects = _normalize_profile_subjects(profile_subjects or [])
    matches: List[Dict[str, Any]] = []
    exact_matches: List[Dict[str, Any]] = []
    for item in programs:
        if normalized_level and item.get("level") != normalized_level:
            continue
        if normalized_profile_subjects and not _program_matches_profile_subjects(item, normalized_profile_subjects):
            continue
        if normalized_program:
            candidates = _program_candidates(item)
            normalized_candidates = [_normalize_text(candidate) for candidate in candidates if candidate]
            if any(candidate == normalized_program for candidate in normalized_candidates):
                exact_matches.append(item)
                continue
            if not any(_program_matches(normalized_program, candidate) for candidate in candidates if candidate):
                continue
        matches.append(item)
    return exact_matches or matches


def _normalize_profile_subjects(subjects: List[str]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for subject in subjects:
        canonical = _canonical_profile_subject(subject)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        result.append(canonical)
    return result


def _canonical_profile_subject(subject: Any) -> str:
    normalized_subject = _normalize_text(str(subject or ""))
    if not normalized_subject:
        return ""
    for canonical, aliases in PROFILE_SUBJECT_ALIASES.items():
        normalized_terms = {_normalize_text(canonical), *(_normalize_text(alias) for alias in aliases)}
        if normalized_subject in normalized_terms:
            return canonical
    return str(subject or "").strip()


def _program_matches_profile_subjects(program: Dict[str, Any], requested_subjects: List[str]) -> bool:
    program_subjects = _normalize_profile_subjects(
        [
            str(program.get("profile_subject_1") or ""),
            str(program.get("profile_subject_2") or ""),
        ]
    )
    if not program_subjects:
        return False
    if len(requested_subjects) >= 2:
        return set(program_subjects) == set(requested_subjects[:2])
    return requested_subjects[0] in program_subjects


def _program_candidates(program: Dict[str, Any], *, include_topic_aliases: bool = False) -> List[str]:
    candidates: List[Any] = [
        program.get("name"),
        program.get("name_ru"),
        program.get("name_kk"),
        program.get("name_en"),
    ]
    aliases = program.get("aliases")
    if isinstance(aliases, list):
        candidates.extend(aliases)
    elif aliases is not None:
        candidates.append(aliases)
    if include_topic_aliases:
        candidates.extend(_program_topic_aliases(program))
    result: List[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        resolved = _resolve_localized_value(candidate, DEFAULT_LANGUAGE)
        values = resolved if isinstance(resolved, list) else [resolved]
        for value in values:
            normalized = _normalize_text(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(str(value))
    return result


def _program_topic_aliases(program: Dict[str, Any]) -> List[str]:
    program_text = " ".join(
        str(value or "")
        for value in (
            program.get("id"),
            program.get("name"),
            program.get("name_ru"),
            program.get("name_kk"),
            program.get("name_en"),
        )
    )
    normalized_text = _normalize_text(program_text)
    if not normalized_text:
        return []

    topic_aliases: List[str] = []

    if (
        "информационные системы" in normalized_text
        or "information systems" in normalized_text
    ):
        topic_aliases.extend(
            [
                "айти",
                "айт",
                "it",
                "ит",
                "информационные технологии",
                "информацион",
                "технолог",
                "it специальности",
                "it направления",
                "технологии",
                "digital technologies",
            ]
        )

    if (
        "вычислительная техника" in normalized_text
        or "программное обеспечение" in normalized_text
        or "computer engineering" in normalized_text
        or "software" in normalized_text
    ):
        topic_aliases.extend(
            [
                "айти",
                "айт",
                "it",
                "ит",
                "информационные технологии",
                "информацион",
                "технолог",
                "программирование",
                "программир",
                "разработка",
                "разработк",
                "software engineering",
                "computer science",
                "computer engineering",
            ]
        )

    if (
        "цифровая юриспруденция" in normalized_text
        or "digital jurisprudence" in normalized_text
        or "digital law" in normalized_text
    ):
        topic_aliases.extend(
            [
                "цифровая юриспруденция",
                "цифровой юрист",
                "digital law",
                "digital jurisprudence",
            ]
        )
    elif "юриспруденция" in normalized_text or "jurisprudence" in normalized_text:
        topic_aliases.extend(
            [
                "юрист",
                "юриста",
                "юриспруденция",
                "право",
                "law",
                "lawyer",
                "jurisprudence",
            ]
        )
    elif "право" in normalized_text or "law" in normalized_text:
        topic_aliases.extend(["право", "law"])

    return topic_aliases


def _match_programs_by_topics(
    normalized_query: str,
    source: Dict[str, Any],
    seen: set[str],
) -> List[tuple[int, str]]:
    if not normalized_query.split():
        return []

    matches: List[tuple[int, str]] = []
    for program in source.get("programs") or []:
        canonical_name = _program_display_name(program)
        canonical_key = _normalize_text(canonical_name)
        if not canonical_name or not canonical_key or canonical_key in seen:
            continue

        topic_aliases = _program_topic_aliases(program)
        best_score = 0
        for alias in topic_aliases:
            normalized_alias = _normalize_text(alias)
            if not normalized_alias:
                continue
            if _term_matches_query(normalized_alias, normalized_query):
                best_score = max(best_score, len(normalized_alias))

        if best_score <= 0:
            continue

        seen.add(canonical_key)
        matches.append((best_score, canonical_name))

    return matches


def _extract_programs_from_history(
    history: Any,
    *,
    data: Dict[str, Any],
    roles: set[str],
    limit: int,
) -> List[str]:
    if not isinstance(history, list):
        return []

    matches: List[str] = []
    seen: set[str] = set()
    for item in reversed(history[-12:]):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        if role == "bot":
            role = "assistant"
        if role not in roles:
            continue

        content = str(item.get("content") or "").strip()
        if not content:
            continue

        for program_name in extract_programs(content, data=data, limit=limit):
            normalized_name = _normalize_text(program_name)
            if not normalized_name or normalized_name in seen:
                continue
            seen.add(normalized_name)
            matches.append(program_name)
            if len(matches) >= limit:
                return matches
    return matches


def _program_display_name(program: Dict[str, Any], language: Optional[str] = None) -> str:
    lang = normalize_language(language)
    localized_name = _resolve_localized_value(program.get(f"name_{lang}"), lang)
    return str(
        localized_name
        or _resolve_localized_value(program.get("name_ru"), lang)
        or _resolve_localized_value(program.get("name"), lang)
        or _resolve_localized_value(program.get("name_kk"), lang)
        or _resolve_localized_value(program.get("name_en"), lang)
        or program.get("id")
        or ""
    )


def _match_academic_cooperation_programs(
    programs: Dict[str, Any],
    *,
    program: Optional[str],
    query: Optional[str],
) -> List[Dict[str, Any]]:
    normalized_program = _normalize_text(program)
    normalized_query = _normalize_text(query)
    matches: List[Dict[str, Any]] = []

    extra_terms = {
        "internal_academic_mobility": {"внутренняя", "internal", "ішкі"},
        "international_academic_mobility": {"международная", "international", "зарубеж", "халықаралық"},
        "double_degree_program": {"двудиплом", "double degree", "екі диплом"},
    }

    for key, value in programs.items():
        if not isinstance(value, dict):
            continue

        candidates = [
            str(value.get("name") or ""),
            str(key),
            str(value.get("description") or ""),
        ]
        if normalized_program and not any(_program_matches(normalized_program, candidate) for candidate in candidates if candidate):
            continue

        if normalized_query and not normalized_program:
            direct_match = any(_term_matches_query(candidate, normalized_query) for candidate in candidates if candidate)
            extra_match = any(
                _term_matches_query(term, normalized_query) or _normalize_text(term) in normalized_query
                for term in extra_terms.get(key, set())
            )
            if not direct_match and not extra_match:
                continue

        matches.append({"id": key, **value})

    return matches


def _filter_academic_mobility_partners(
    partners: List[Any],
    *,
    program: Optional[str],
    query: Optional[str],
) -> List[Dict[str, Any]]:
    normalized_program = _normalize_text(program)
    normalized_query = _normalize_text(query)
    matched: List[Dict[str, Any]] = []

    for partner in partners:
        if not isinstance(partner, dict):
            continue

        programs = partner.get("programs") or []
        candidate_terms = [
            str(partner.get("name") or ""),
            str(partner.get("country") or ""),
            str(partner.get("city") or ""),
            *(str(item) for item in programs),
        ]

        if normalized_program:
            if not any(_program_matches(normalized_program, candidate) for candidate in candidate_terms if candidate):
                continue
        elif normalized_query:
            if not any(_term_matches_query(candidate, normalized_query) for candidate in candidate_terms if candidate):
                continue

        matched.append(partner)

    return matched


def _format_profile_subjects(
    subject_1: Any,
    subject_2: Any,
    *,
    language: Optional[str],
) -> str:
    lang = normalize_language(language)
    labels = {
        "ru": ("Профильный предмет 1", "Профильный предмет 2"),
        "kk": ("Бейіндік пән 1", "Бейіндік пән 2"),
        "en": ("Profile subject 1", "Profile subject 2"),
    }
    left_label, right_label = labels.get(lang, labels[DEFAULT_LANGUAGE])
    parts: List[str] = []
    if subject_1 not in (None, "", [], {}):
        parts.append(f"{left_label}: {subject_1}")
    if subject_2 not in (None, "", [], {}):
        parts.append(f"{right_label}: {subject_2}")
    return ", ".join(parts)


def _matches_any_term(terms: set[str], normalized_query: str, raw_query: str) -> bool:
    return any(
        _term_matches_query(term, normalized_query)
        or _normalize_text(term) in normalized_query
        or term.casefold() in raw_query
        for term in terms
    )


def _extract_scholarship_categories(scholarships: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if not isinstance(scholarships, dict):
        return {}

    categories = scholarships.get("categories")
    source = categories if isinstance(categories, dict) else scholarships
    extracted: Dict[str, Dict[str, Any]] = {}
    for scholarship_type, aliases in SCHOLARSHIP_TYPE_KEY_ALIASES.items():
        for alias in aliases:
            entry = source.get(alias)
            normalized_entry = _normalize_scholarship_entry(entry)
            if normalized_entry is None:
                continue
            extracted[scholarship_type] = normalized_entry
            break

    if "state_grant" not in extracted:
        legacy_sections = scholarships.get("sections")
        if isinstance(legacy_sections, list) and legacy_sections:
            extracted["state_grant"] = {"sections": legacy_sections}
    return extracted


def _normalize_scholarship_entry(entry: Any) -> Optional[Dict[str, Any]]:
    if isinstance(entry, dict):
        return dict(entry)
    if isinstance(entry, list):
        return {"sections": entry}
    return None


def _select_scholarship_payload(
    scholarships: Any,
    *,
    requested_type: Optional[str],
) -> tuple[Dict[str, Any], Optional[str], List[str], bool]:
    normalized = _normalize_scholarship_entry(scholarships) or {}
    categories = _extract_scholarship_categories(normalized)
    available_types = list(categories.keys())

    if requested_type:
        if categories:
            selected = categories.get(requested_type)
            if selected is not None:
                return selected, requested_type, available_types, False
            return {"sections": []}, requested_type, available_types, True

        inferred_type = _infer_scholarship_type(normalized)
        if inferred_type == requested_type or (inferred_type is None and requested_type == "state_grant"):
            fallback_types = [inferred_type] if inferred_type else (["state_grant"] if normalized else [])
            return normalized, requested_type, fallback_types, False
        return {"sections": []}, requested_type, [inferred_type] if inferred_type else [], True

    return normalized, None, available_types, False


def _infer_scholarship_type(scholarships: Dict[str, Any]) -> Optional[str]:
    chunks: List[str] = []
    for section in scholarships.get("sections") or []:
        if not isinstance(section, dict):
            continue
        for key in ("title", "notes", "items"):
            value = section.get(key)
            if isinstance(value, list):
                chunks.extend(str(item) for item in value)
            elif value:
                chunks.append(str(value))
    haystack = _normalize_text(" ".join(chunks))
    for scholarship_type, terms in SCHOLARSHIP_TYPE_ALIASES.items():
        if any(_normalize_text(term) in haystack for term in terms):
            return scholarship_type
    return None


def _append_scholarship_sections(lines: List[str], scholarships: Dict[str, Any]) -> None:
    for section in scholarships.get("sections") or []:
        if not isinstance(section, dict):
            continue
        title = section.get("title")
        if title:
            lines.append(str(title))
        for note in section.get("notes") or []:
            lines.append(f"- {note}")
        for item in section.get("items") or []:
            lines.append(f"- {item}")


def _scholarship_type_label(scholarship_type: str, *, language: Optional[str]) -> str:
    lang = normalize_language(language)
    label_key = {
        "state_grant": "scholarships_state_grant_title",
        "rector_grant": "scholarships_rector_grant_title",
    }.get(scholarship_type)
    if not label_key:
        return scholarship_type
    return _text(lang, label_key).rstrip(":")


def _normalize_level(level: Optional[str]) -> Optional[str]:
    if not level:
        return None
    level_text = level.lower().strip()
    for normalized, variants in LEVEL_ALIASES.items():
        if level_text in variants:
            return normalized
    return level_text


def _normalize_text(text: Optional[str]) -> str:
    raw = (text or "").lower().strip()
    cleaned = re.sub(r"[^\w\s]+", " ", raw)
    return re.sub(r"\s+", " ", cleaned).strip()


def _program_matches(requested_program: str, candidate: str) -> bool:
    normalized_candidate = _normalize_text(candidate)
    return (
        normalized_candidate == requested_program
        or _term_matches_query(normalized_candidate, requested_program)
        or _term_matches_query(requested_program, normalized_candidate)
    )


def _term_matches_query(term: str, normalized_query: str) -> bool:
    normalized_term = _normalize_text(term)
    if not normalized_term:
        return False
    if " " in normalized_term:
        return normalized_term in normalized_query

    query_words = normalized_query.split()
    return any(
        word == normalized_term or word.startswith(normalized_term)
        for word in query_words
    )


def _not_found(
    tool: str,
    data: Dict[str, Any],
    *,
    level: Optional[str],
    program: Optional[str],
    language: Optional[str],
) -> Dict[str, Any]:
    lang = normalize_language(language)
    return {
        "status": "not_found",
        "tool": tool,
        "language": lang,
        "message": _text(lang, "not_found"),
        "requested_level": _normalize_level(level),
        "requested_program": program,
        "contacts": _resolve_localized_value(data.get("contacts") or {}, lang),
        "available_programs": [
            _program_display_name(item, language=lang)
            for item in data.get("programs") or []
            if _program_display_name(item, language=lang)
        ],
        "available_levels": sorted({item.get("level") for item in data.get("programs") or [] if item.get("level")}),
        "source_path": _source_path(),
    }


def _source_path() -> str:
    configured_path = os.getenv("ADMISSION_DATA_PATH")
    path = Path(configured_path) if configured_path else DEFAULT_DATA_PATH
    return str(path)
