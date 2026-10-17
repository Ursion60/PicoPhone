"""
i18n : fonction de traduction centrale pour toute l'interface (accueil en C, applis en Python).

    import i18n
    i18n.t("app_notes")          -> "Notes" / "Notes" / "Notas" / "Notizen" / "メモ" / "笔记"
    i18n.set_lang("EN")          -> persiste le choix (fichier lang.txt) + met à jour l'accueil (C)

Codes de langue : FR, EN, ES, AL (allemand), JP, CN. Ajouter une langue = ajouter une colonne à
STRINGS ci-dessous, puis relancer tools/gen_font.py (pour JP/CN : glyphes générés automatiquement
à partir des chaînes utilisées ici, voir ce script).
"""

LANGS = ["FR", "EN", "ES", "AL", "JP", "CN"]

# Nom de chaque langue, toujours affiché dans SA PROPRE langue (comme sur un vrai téléphone).
LANG_NAMES = {
    "FR": "Français", "EN": "English", "ES": "Español",
    "AL": "Deutsch", "JP": "日本語", "CN": "中文",
}

_FALLBACK = "FR"
_FILE = "lang.txt"

# ---------------------------------------------------------------------------
# clé -> { code langue : texte }
# Traductions EN/ES/AL/JP/CN faites de mon mieux (pas de relecture native) :
# à corriger dans ce tableau si une formulation sonne mal.
# ---------------------------------------------------------------------------
STRINGS = {
    # Écran d'accueil (poussé vers le C par push_to_home())
    "home_title":     {"FR": "Accueil",        "EN": "Home",          "ES": "Inicio",        "AL": "Start",          "JP": "ホーム",          "CN": "主屏幕"},
    "app_edt":        {"FR": "EDT",            "EN": "Timetable",     "ES": "Horario",       "AL": "Stundenplan",    "JP": "時間割",          "CN": "课程表"},
    "app_notes":      {"FR": "Notes",          "EN": "Notes",         "ES": "Notas",         "AL": "Notizen",        "JP": "メモ",            "CN": "笔记"},
    "app_nfc":        {"FR": "NFC",            "EN": "NFC",           "ES": "NFC",           "AL": "NFC",            "JP": "NFC",            "CN": "NFC"},
    "app_shop":       {"FR": "Shop",           "EN": "Shop",          "ES": "Tienda",        "AL": "Shop",           "JP": "ショップ",        "CN": "商店"},
    "app_synchro":    {"FR": "Synchro",        "EN": "Sync",          "ES": "Sincro",        "AL": "Synchro",        "JP": "同期",            "CN": "同步"},
    "app_parametres": {"FR": "Paramètres",     "EN": "Settings",      "ES": "Ajustes",       "AL": "Einstellungen",  "JP": "設定",            "CN": "设置"},
    "app_musique":    {"FR": "Musique",        "EN": "Music",         "ES": "Música",        "AL": "Musik",          "JP": "音楽",            "CN": "音乐"},
    "app_lecteur_pdf":{"FR": "Lecteur PDF",    "EN": "PDF Reader",    "ES": "Lector PDF",    "AL": "PDF-Leser",      "JP": "PDFリーダー",     "CN": "PDF阅读器"},
    "options":        {"FR": "Options",        "EN": "Options",       "ES": "Opciones",      "AL": "Optionen",       "JP": "オプション",      "CN": "选项"},
    "all_apps":       {"FR": "Toutes les apps","EN": "All apps",      "ES": "Todas las apps","AL": "Alle Apps",      "JP": "すべてのアプリ",  "CN": "所有应用"},
    "starting":       {"FR": "Démarrage",      "EN": "Starting",      "ES": "Iniciando",     "AL": "Startet",        "JP": "起動中",          "CN": "启动中"},
    "ready":          {"FR": "Prêt",           "EN": "Ready",         "ES": "Listo",         "AL": "Bereit",         "JP": "準備完了",        "CN": "就绪"},

    # Éléments communs (appkit)
    "back":           {"FR": "« Retour",       "EN": "« Back",        "ES": "« Atrás",       "AL": "« Zurück",       "JP": "« 戻る",          "CN": "« 返回"},
    "cancel":         {"FR": "Annuler",        "EN": "Cancel",        "ES": "Cancelar",      "AL": "Abbrechen",      "JP": "キャンセル",      "CN": "取消"},
    "ok":             {"FR": "OK",             "EN": "OK",            "ES": "OK",            "AL": "OK",             "JP": "OK",              "CN": "OK"},
    "space_key":      {"FR": "espace",         "EN": "space",         "ES": "espacio",       "AL": "Leertaste",      "JP": "スペース",        "CN": "空格"},
    "text_default":   {"FR": "Texte",          "EN": "Text",          "ES": "Texto",         "AL": "Text",           "JP": "テキスト",        "CN": "文本"},

    "missing_title":  {"FR": "Pas encore disponible", "EN": "Not available yet", "ES": "Aún no disponible", "AL": "Noch nicht verfügbar", "JP": "まだ利用できません", "CN": "暂未提供"},
    "missing_l1":     {"FR": "Pour créer cette appli, écrivez", "EN": "To create this app, write", "ES": "Para crear esta app, escribe", "AL": "Um diese App zu erstellen, schreiben Sie", "JP": "このアプリを作るには、次を書いてください", "CN": "要创建此应用，请编写"},
    "missing_l2":     {"FR": "le fichier :",   "EN": "the file:",     "ES": "el archivo:",   "AL": "die Datei:",     "JP": "次のファイル：", "CN": "文件："},
    "error_title":    {"FR": "Erreur",         "EN": "Error",         "ES": "Error",         "AL": "Fehler",         "JP": "エラー",          "CN": "错误"},
    "crashed_title":  {"FR": "Cette appli a planté", "EN": "This app crashed", "ES": "Esta app falló", "AL": "Diese App ist abgestürzt", "JP": "このアプリはクラッシュしました", "CN": "此应用已崩溃"},

    # Notes (onglets Tâches / Notes)
    "tab_tasks":            {"FR": "Tâches",          "EN": "Tasks",      "ES": "Tareas",       "AL": "Aufgaben",     "JP": "タスク",       "CN": "任务"},
    "tab_notes":            {"FR": "Notes",           "EN": "Notes",      "ES": "Notas",        "AL": "Notizen",      "JP": "メモ",         "CN": "笔记"},
    "notes_new_task_btn":   {"FR": "+ Nouvelle tâche","EN": "+ New task", "ES": "+ Nueva tarea","AL": "+ Neue Aufgabe","JP": "+ 新しいタスク","CN": "+ 新建任务"},
    "notes_new_task_title": {"FR": "Nouvelle tâche",  "EN": "New task",   "ES": "Nueva tarea",  "AL": "Neue Aufgabe", "JP": "新しいタスク", "CN": "新建任务"},
    "notes_new_note_btn":   {"FR": "+ Nouvelle note", "EN": "+ New note", "ES": "+ Nueva nota", "AL": "+ Neue Notiz", "JP": "+ 新しいメモ", "CN": "+ 新建笔记"},
    "notes_new_note_title": {"FR": "Nouvelle note",   "EN": "New note",   "ES": "Nueva nota",   "AL": "Neue Notiz",   "JP": "新しいメモ",   "CN": "新建笔记"},
    "notes_edit_title":     {"FR": "Modifier",        "EN": "Edit",       "ES": "Editar",       "AL": "Bearbeiten",   "JP": "編集",         "CN": "编辑"},
    "notes_title_prompt":   {"FR": "Titre",           "EN": "Title",      "ES": "Título",       "AL": "Titel",        "JP": "タイトル",     "CN": "标题"},
    "notes_body_prompt":    {"FR": "Description",     "EN": "Description","ES": "Descripción",  "AL": "Beschreibung", "JP": "説明",         "CN": "描述"},
    "notes_back_to_list":   {"FR": "< Liste",         "EN": "< List",     "ES": "< Lista",      "AL": "< Liste",      "JP": "< 一覧",         "CN": "< 列表"},
    "notes_demo_1":   {"FR": "Flasher la carte",             "EN": "Flash the board",          "ES": "Flashear la placa",           "AL": "Board flashen",                 "JP": "ボードを書き込む",   "CN": "烧录开发板"},
    "notes_demo_2":   {"FR": "Écrire ma première appli",     "EN": "Write my first app",        "ES": "Escribir mi primera app",     "AL": "Meine erste App schreiben",     "JP": "最初のアプリを書く", "CN": "编写我的第一个应用"},
    "notes_demo_3":   {"FR": "Brancher le lecteur NFC",      "EN": "Connect the NFC reader",    "ES": "Conectar el lector NFC",      "AL": "NFC-Lesegerät anschließen",     "JP": "NFCリーダーを接続する", "CN": "连接NFC读卡器"},

    # Lecteur PDF
    "pdf_none":      {"FR": "Aucun PDF",              "EN": "No PDF",                "ES": "Sin PDF",                 "AL": "Keine PDF",             "JP": "PDFがありません",     "CN": "没有PDF"},
    "pdf_hint":      {"FR": "Copiez vos .pdf dans",   "EN": "Copy your .pdf files to", "ES": "Copia tus .pdf en",      "AL": "Kopiere deine PDFs nach", "JP": "PDFを次にコピー",   "CN": "请将PDF复制到"},
    "pdf_page":      {"FR": "Page",                   "EN": "Page",                  "ES": "Pág.",                    "AL": "Seite",                 "JP": "ページ",              "CN": "页"},
    "pdf_unit_kb":   {"FR": "Ko",                     "EN": "KB",                    "ES": "KB",                      "AL": "KB",                    "JP": "KB",                  "CN": "KB"},
    "pdf_loading":   {"FR": "Lecture...",             "EN": "Reading...",            "ES": "Leyendo...",              "AL": "Lese...",               "JP": "読み込み中...",       "CN": "读取中..."},
    "pdf_no_text":   {"FR": "Pas de texte sur cette page", "EN": "No text on this page", "ES": "Sin texto en esta página", "AL": "Kein Text auf dieser Seite", "JP": "このページにテキストはありません", "CN": "此页没有文字"},
    "pdf_garbled":   {"FR": "Texte non décodable (police sans table Unicode)", "EN": "Text can't be decoded (font has no Unicode table)", "ES": "Texto no descifrable (fuente sin tabla Unicode)", "AL": "Text nicht lesbar (Schrift ohne Unicode-Tabelle)", "JP": "テキストを解読できません", "CN": "无法解码文字"},
    "pdf_encrypted": {"FR": "PDF chiffré : non géré", "EN": "Encrypted PDF: unsupported", "ES": "PDF cifrado: no soportado", "AL": "Verschlüsseltes PDF: nicht unterstützt", "JP": "暗号化PDFは非対応です", "CN": "不支持加密PDF"},
    "pdf_bad":       {"FR": "PDF illisible",          "EN": "Unreadable PDF",        "ES": "PDF ilegible",            "AL": "PDF nicht lesbar",      "JP": "PDFを読めません",     "CN": "无法读取PDF"},
    "pdf_truncated": {"FR": "[page tronquée]",        "EN": "[page truncated]",      "ES": "[página truncada]",       "AL": "[Seite gekürzt]",       "JP": "[ページ省略]",        "CN": "[页面已截断]"},

    # Paramètres
    "settings_brightness": {"FR": "Luminosité", "EN": "Brightness", "ES": "Brillo",  "AL": "Helligkeit", "JP": "明るさ", "CN": "亮度"},
    "settings_language":   {"FR": "Langue",     "EN": "Language",   "ES": "Idioma",  "AL": "Sprache",    "JP": "言語",   "CN": "语言"},
    "settings_system":     {"FR": "Système",    "EN": "System",     "ES": "Sistema", "AL": "System",     "JP": "システム", "CN": "系统"},
    "settings_ram_free":   {"FR": "RAM libre",  "EN": "Free RAM",   "ES": "RAM libre","AL": "Freier RAM", "JP": "空きRAM", "CN": "可用内存"},
}

_current = _FALLBACK


def t(key, lang=None):
    """Traduit `key` dans la langue courante (ou `lang` si précisé). Repli sur FR puis sur la clé
    elle-même si absente, pour ne jamais planter un affichage."""
    entry = STRINGS.get(key)
    if not entry:
        return key
    lang = lang or _current
    return entry.get(lang) or entry.get(_FALLBACK) or key


def get_lang():
    return _current


def load():
    """À appeler au démarrage (main.py) : relit la langue choisie précédemment, sinon FR."""
    global _current
    try:
        with open(_FILE) as f:
            code = f.read().strip().upper()
        if code in LANGS:
            _current = code
    except OSError:
        pass
    return _current


def set_lang(code):
    """Change la langue, la persiste sur la carte, et retraduit l'écran d'accueil (C)."""
    global _current
    if code not in LANGS:
        raise ValueError("langue inconnue : %r" % code)
    _current = code
    try:
        with open(_FILE, "w") as f:
            f.write(code)
    except OSError:
        pass                                     # pas grave : le choix vivra pour cette session
    push_to_home()


_HOME_APP_IDS = ("edt", "notes", "nfc", "shop", "synchro", "parametres", "musique", "lecteur_pdf")


def push_to_home():
    """Réinjecte les libellés traduits dans l'écran d'accueil (module C `phone`). Sans effet si le
    module `phone` n'est pas chargé (permet d'importer/tester i18n.py hors carte, ex. CPython)."""
    try:
        import phone
    except ImportError:
        return
    phone.set_home_title(t("home_title"))
    phone.set_options_label(t("options"))
    phone.set_allapps_label(t("all_apps"))
    for app_id in _HOME_APP_IDS:
        phone.set_app_label(app_id, t("app_" + app_id))
