import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Icon, type IconName } from "./ui/Icon";

const FEATURES: { icon: IconName; title: string; text: string }[] = [
  { icon: "cap", title: "Программы и гранты", text: "Бакалавриат, магистратура и докторантура: направления, профильные предметы ЕНТ и гранты." },
  { icon: "wallet", title: "Стоимость обучения", text: "Актуальные цены по каждой программе, скидки и варианты оплаты." },
  { icon: "file", title: "Документы и сроки", text: "Что подготовить для подачи, когда идёт приём и как проходят вступительные экзамены." },
  { icon: "phone", title: "Связь с комиссией", text: "Контакты, адрес и часы работы — без звонков и ожидания на линии." },
];

const STEPS = [
  { title: "Задайте вопрос", text: "Простым языком — на русском, казахском или английском." },
  { title: "ИИ найдёт ответ", text: "Агенты сверяются с официальными данными приёмной комиссии TAU." },
  { title: "Получите точный ответ", text: "С цифрами и источниками. Нужна консультация — оставьте контакт." },
];

const EXAMPLES = [
  "Сколько стоит обучение на программной инженерии?",
  "Какие предметы ЕНТ нужны на IT?",
  "Есть ли общежитие для иногородних?",
];

export function PublicLanding() {
  const navigate = useNavigate();
  const [question, setQuestion] = useState("");

  const openChat = (prefill?: string) => navigate("/chat", { state: prefill?.trim() ? { prefill: prefill.trim() } : undefined });

  return (
    <div className="landing">
      <section className="landing-hero">
        <div className="landing-hero__copy">
          <span className="landing-pill">
            <span className="status-dot" /> Приём 2026 открыт · ИИ-консультант 24/7
          </span>
          <h1>
            Всё о поступлении в <span className="text-brand">Turan-Astana University</span> — за минуту
          </h1>
          <p className="landing-hero__lead">
            Академический ИИ-ассистент отвечает на вопросы абитуриентов и родителей по официальным данным приёмной
            комиссии: программы, стоимость, проходные баллы, документы и гранты.
          </p>
          <div className="landing-hero__actions">
            <Link to="/chat" className="primary btn--lg">
              <Icon name="sparkles" size={18} /> Задать вопрос
            </Link>
            <Link to="/telegram-login" className="ghost btn--lg">
              Я студент TAU <Icon name="arrowRight" size={16} />
            </Link>
          </div>
          <ul className="landing-hero__trust">
            <li><Icon name="shield" size={16} /> Официальные данные</li>
            <li><Icon name="clock" size={16} /> Ответ за секунды</li>
            <li><Icon name="book" size={16} /> RU · KZ · EN</li>
          </ul>
        </div>

        <div className="landing-preview" aria-hidden="true">
          <div className="landing-preview__window">
            <div className="landing-preview__bar">
              <span /><span /><span />
            </div>
            <div className="landing-preview__msg landing-preview__msg--user">Сколько стоит обучение на IT?</div>
            <div className="landing-preview__steps">
              <span><Icon name="check" size={12} strokeWidth={3} /> Понимаю вопрос</span>
              <span><Icon name="check" size={12} strokeWidth={3} /> Проверяю данные приёмной комиссии</span>
            </div>
            <div className="landing-preview__msg landing-preview__msg--bot">
              <strong>Стоимость обучения на IT-программах</strong>
              <span className="landing-preview__line" />
              <span className="landing-preview__line landing-preview__line--short" />
              <span className="landing-preview__line" />
              <span className="landing-preview__source"><Icon name="file" size={12} /> Данные приёмной комиссии</span>
            </div>
          </div>
        </div>
      </section>

      <section className="landing-ask">
        <form
          className="landing-ask__form"
          onSubmit={(event) => {
            event.preventDefault();
            openChat(question);
          }}
        >
          <Icon name="search" size={20} />
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Спросите что угодно о поступлении…"
            aria-label="Вопрос о поступлении"
          />
          <button type="submit" className="primary">Спросить</button>
        </form>
        <div className="landing-ask__examples">
          {EXAMPLES.map((example) => (
            <button key={example} type="button" onClick={() => openChat(example)}>{example}</button>
          ))}
        </div>
      </section>

      <section className="landing-section">
        <div className="landing-section__head">
          <span className="eyebrow">Возможности</span>
          <h2>Ответы на главные вопросы абитуриента</h2>
        </div>
        <div className="landing-features">
          {FEATURES.map((item) => (
            <article key={item.title} className="landing-feature">
              <span className="landing-feature__icon"><Icon name={item.icon} size={20} /></span>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section">
        <div className="landing-section__head">
          <span className="eyebrow">Как это работает</span>
          <h2>Три шага до ответа</h2>
        </div>
        <ol className="landing-steps">
          {STEPS.map((step, index) => (
            <li key={step.title} className="landing-step">
              <span className="landing-step__num">{index + 1}</span>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="landing-cta">
        <div>
          <h2>Готовы начать?</h2>
          <p>Задайте первый вопрос — регистрация не нужна.</p>
        </div>
        <Link to="/chat" className="primary btn--lg">
          Открыть чат <Icon name="arrowRight" size={16} />
        </Link>
      </section>
    </div>
  );
}
