import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { sendChatMessage } from "../api/chat";
import type { ChatRequestPayload, ChatResult } from "../types";

const FAKE_PROFILE = {
  user_id: 42,
  language: "ru",
  context: {
    university: "TAU",
    program: "ComputerScience",
    year: 2,
    itp: "ИТП-2024",
  },
  metadata: {
    channel: "telegram",
    session_id: "abc123",
  },
} as const;

type ChatMessage = {
  id: string;
  role: "user" | "bot";
  content: string;
  status?: "pending" | "error";
  details?: ChatResult;
};

const BOT_PLACEHOLDER = "Получаем ответ...";
const INTRO_MESSAGE = `Можешь задать вопрос — запросы уходят в реальный API с тестовыми данными университета ${
  FAKE_PROFILE.context.university
} и ИТП ${FAKE_PROFILE.context.itp}.`;

export function FakeChat() {
  const [inputValue, setInputValue] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    { id: "intro", role: "bot", content: INTRO_MESSAGE },
  ]);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const requestMeta = useMemo(
    () => ({
      language: FAKE_PROFILE.language,
      channel: FAKE_PROFILE.metadata.channel,
      session: FAKE_PROFILE.metadata.session_id,
      university: FAKE_PROFILE.context.university,
      program: FAKE_PROFILE.context.program,
      itp: FAKE_PROFILE.context.itp,
    }),
    []
  );

  const chatMutation = useMutation<ChatResult, Error, string>({
    mutationFn: async (message: string) => {
      const payload: ChatRequestPayload = {
        user_id: FAKE_PROFILE.user_id,
        message,
        language: FAKE_PROFILE.language,
        context: FAKE_PROFILE.context,
        metadata: FAKE_PROFILE.metadata,
      };
      const response = await sendChatMessage(payload);
      return response.result;
    },
  });

  const replaceMessage = (id: string, data: Partial<ChatMessage>) => {
    setMessages((prev) =>
      prev.map((message) => (message.id === id ? { ...message, ...data } : message))
    );
  };

  const toggleDetails = (id: string) => {
    setExpandedId((current) => (current === id ? null : id));
  };

  const handleSend = () => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
    };
    const botMessageId = `bot-${Date.now()}`;
    const placeholderMessage: ChatMessage = {
      id: botMessageId,
      role: "bot",
      content: BOT_PLACEHOLDER,
      status: "pending",
    };

    setMessages((prev) => [
      ...prev,
      userMessage,
      placeholderMessage,
    ]);
    setInputValue("");

    chatMutation.mutate(trimmed, {
      onSuccess: (result) => {
        replaceMessage(botMessageId, {
          content: result.final_answer || "Нет ответа от агентов.",
          status: undefined,
          details: result,
        });
      },
      onError: (error) => {
        replaceMessage(botMessageId, {
          content: error instanceof Error ? error.message : "Ошибка запроса",
          status: "error",
        });
      },
    });
  };

  return (
    <section className="fake-chat">
      <header className="fake-chat__header">
        <div>
          <p className="eyebrow">Chat</p>
          <h2>Диалоги</h2>
        </div>
        <div className="fake-chat__meta">
          <span>Университет: {requestMeta.university}</span>
          <span>Программа: {requestMeta.program}</span>
          <span>ИТП: {requestMeta.itp}</span>
          <span>Язык: {requestMeta.language}</span>
          <span>Канал: {requestMeta.channel}</span>
          <span>Сессия: {requestMeta.session}</span>
        </div>
      </header>

      <div className="chat-window">
        <div className="chat-messages">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`chat-bubble ${message.role === "user" ? "user" : "bot"}${
                message.status === "pending" ? " pending" : ""
              }${message.status === "error" ? " error" : ""}`}
              onClick={() => {
                if (message.role === "bot" && message.details) {
                  toggleDetails(message.id);
                }
              }}
              role={message.role === "bot" && message.details ? "button" : undefined}
              tabIndex={message.role === "bot" && message.details ? 0 : undefined}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  message.role === "bot" &&
                  message.details
                ) {
                  event.preventDefault();
                  toggleDetails(message.id);
                }
              }}
            >
              <span className="bubble-label">
                {message.role === "user" ? "Пользователь" : "Бот"}
              </span>
              <p>{message.content}</p>
              {message.role === "bot" && message.details ? (
                <div
                  className={`chat-bubble__details ${
                    expandedId === message.id ? "open" : ""
                  }`}
                >
                  <span className="chat-bubble__details-label">Details JSON</span>
                  <pre>{JSON.stringify(message.details, null, 2)}</pre>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>

      <div className="chat-input-area">
        <textarea
          placeholder="Введите вопрос..."
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value)}
          rows={2}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              handleSend();
            }
          }}
        />
        <button
          type="button"
          className="primary"
          onClick={handleSend}
          disabled={!inputValue.trim() || chatMutation.isPending}
        >
          Отправить
        </button>
      </div>
    </section>
  );
}
