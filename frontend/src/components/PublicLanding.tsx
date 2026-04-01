import { NavLink } from "react-router-dom";

const BENEFITS = [
  {
    title: "Поступление без лишних звонков",
    text: "Сервис сразу подсказывает по программам, стоимости обучения, проходным баллам и срокам подачи документов.",
  },
  {
    title: "Чат с ИИ-агентом приемной комиссии",
    text: "Неавторизованный пользователь может задать вопрос прямо на сайте и получить ответ по данным приемной комиссии TAU.",
  },
  {
    title: "Быстрый переход к подаче заявки",
    text: "После первичной консультации можно перейти к авторизации и продолжить работу уже в персональном кабинете.",
  },
] as const;

const FAQ_ITEMS = [
  "Какие образовательные программы доступны на бакалавриате, магистратуре и докторантуре.",
  "Сколько стоит обучение и какие есть проходные баллы.",
  "Какие документы нужны для поступления.",
  "Как связаться с приемной комиссией и когда она работает.",
] as const;

export function PublicLanding() {
  return (
    <section className="public-landing">
      <div className="public-hero">
        <div className="public-hero__content">
          <p className="eyebrow">TAU Admissions</p>
          <h1>Публичная страница для абитуриентов и родителей</h1>
          <p className="muted public-hero__lead">
            Academiq помогает быстро понять, как поступить в Turan-Astana University:
            узнать про программы, документы, стоимость обучения и сразу написать
            ИИ-агенту приемной комиссии без авторизации.
          </p>
          <div className="public-hero__actions">
            <NavLink to="/chat" className="primary public-link-button">
              Открыть чат приемной комиссии
            </NavLink>
            <NavLink to="/telegram-login" className="ghost public-link-button">
              Войти в личный кабинет
            </NavLink>
          </div>
        </div>

        <div className="public-hero__panel">
          <span className="public-hero__panel-label">Что можно спросить</span>
          <ul>
            {FAQ_ITEMS.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="public-grid">
        {BENEFITS.map((item) => (
          <article key={item.title} className="public-card">
            <h2>{item.title}</h2>
            <p>{item.text}</p>
          </article>
        ))}
      </div>

      <section className="public-section">
        <div>
          <p className="eyebrow">Сценарий</p>
          <h2>Как это работает</h2>
        </div>
        <div className="public-steps">
          <article className="public-step">
            <span>01</span>
            <h3>Открываете сайт</h3>
            <p>Публичная страница объясняет назначение сервиса и ведет в чат приемной комиссии.</p>
          </article>
          <article className="public-step">
            <span>02</span>
            <h3>Задаете вопрос</h3>
            <p>Можно спросить про стоимость, программы, документы, сроки обучения и контакты.</p>
          </article>
          <article className="public-step">
            <span>03</span>
            <h3>Переходите в личный кабинет</h3>
            <p>Если нужен персональный сценарий, пользователь авторизуется через Telegram.</p>
          </article>
        </div>
      </section>
    </section>
  );
}
