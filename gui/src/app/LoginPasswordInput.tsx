type LoginPasswordInputProps = {
  value: string;
  visible: boolean;
  onChange: (value: string) => void;
  onVisibleChange: (value: boolean) => void;
};

export function LoginPasswordInput({
  value,
  visible,
  onChange,
  onVisibleChange,
}: LoginPasswordInputProps) {
  return (
    <div className="password-input-wrap">
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="密码"
        type={visible ? "text" : "password"}
      />
      <button
        className="password-visibility-button"
        type="button"
        aria-label={visible ? "隐藏密码" : "显示密码"}
        onClick={() => onVisibleChange(!visible)}
      >
        {visible ? "隐藏" : "显示"}
      </button>
    </div>
  );
}
