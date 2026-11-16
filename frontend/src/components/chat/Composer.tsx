import { forwardRef, useEffect, useImperativeHandle, useRef, type KeyboardEvent } from "react";
import { Icon } from "../ui/Icon";

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  isStreaming: boolean;
  placeholder: string;
  maxLength?: number;
  footnote?: string;
};

export type ComposerHandle = { focus: () => void };

const MAX_HEIGHT = 220;

export const Composer = forwardRef<ComposerHandle, Props>(function Composer(
  { value, onChange, onSubmit, onStop, isStreaming, placeholder, maxLength = 4000, footnote },
  ref,
) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  useImperativeHandle(ref, () => ({ focus: () => textareaRef.current?.focus() }), []);

  useEffect(() => {
    const element = textareaRef.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, MAX_HEIGHT)}px`;
  }, [value]);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (!isStreaming) onSubmit();
    }
  };

  const nearLimit = value.length > maxLength * 0.9;
  return (
    <div className="composer">
      <div className="composer__box">
        <textarea
          ref={textareaRef}
          className="composer__input"
          value={value}
          onChange={(event) => onChange(event.target.value.slice(0, maxLength))}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={1}
          aria-label="Сообщение"
          autoFocus
        />
        <div className="composer__toolbar">
          <span className={`composer__counter${nearLimit ? " is-warning" : ""}`}>
            {nearLimit ? `${value.length}/${maxLength}` : "Enter — отправить, Shift+Enter — новая строка"}
          </span>
          {isStreaming ? (
            <button type="button" className="composer__send composer__send--stop" onClick={onStop} aria-label="Остановить ответ" title="Остановить">
              <Icon name="stop" size={14} strokeWidth={2.4} />
            </button>
          ) : (
            <button
              type="button"
              className="composer__send"
              onClick={onSubmit}
              disabled={!value.trim()}
              aria-label="Отправить"
              title="Отправить"
            >
              <Icon name="arrowUp" size={18} strokeWidth={2.2} />
            </button>
          )}
        </div>
      </div>
      {footnote ? <p className="composer__footnote">{footnote}</p> : null}
    </div>
  );
});
