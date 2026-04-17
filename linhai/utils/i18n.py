import locale


def t(messages: dict[str, str]) -> str:
    """根据系统语言选择对应文本。字典必须包含 'en' 作为默认。"""
    if "en" not in messages:
        raise ValueError("i18n messages dict must contain 'en' key as default")
    lang, _ = locale.getlocale()
    if lang and lang in messages:
        return messages[lang]
    return messages["en"]
